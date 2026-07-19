"""The transparency log — append-only hash chain plus published checkpoints.

The assertions that matter are the negative ones. A chain that verifies its own untouched
data proves nothing; what earns the claim is that altering, reordering, removing or
back-dating an entry is *detected*, and that a checkpoint pins history so a later rewrite of
the past cannot be hidden.
"""
import pytest

from originshot_pipelines import transparency as chain

UID = "dev-user"


def _entries(n: int) -> list[dict]:
    """A valid chain of n entries, built the way the repo builds them."""
    out: list[dict] = []
    prev = chain.GENESIS_HASH
    for i in range(n):
        entry = chain.make_entry(
            seq=i, prev_hash=prev, subject_sha256=f"{i:064x}",
            manifest_hash=None, kind="generated",
            recorded_at=f"2026-07-19T10:{i:02d}:00Z",
        )
        out.append(entry)
        prev = entry["entry_hash"]
    return out


# ── The chain ─────────────────────────────────────────────────────────
def test_a_clean_chain_verifies():
    result = chain.verify_chain(_entries(5))
    assert result["consistent"] is True
    assert result["size"] == 5
    assert result["broken_at"] is None


def test_an_empty_log_is_consistent_at_genesis():
    result = chain.verify_chain([])
    assert result["consistent"] is True
    assert result["head"] == chain.GENESIS_HASH


def test_editing_an_entry_is_detected():
    """The core claim: a recorded subject cannot be swapped after the fact."""
    entries = _entries(5)
    entries[2] = {**entries[2], "subject_sha256": "f" * 64}
    result = chain.verify_chain(entries)
    assert result["consistent"] is False
    assert result["broken_at"] == 2
    assert "altered" in result["reason"]


def test_back_dating_an_entry_is_detected():
    entries = _entries(4)
    entries[1] = {**entries[1], "recorded_at": "2020-01-01T00:00:00Z"}
    assert chain.verify_chain(entries)["broken_at"] == 1


def test_removing_an_entry_is_detected():
    """Deleting a regeneration you'd rather nobody saw breaks every hash after it."""
    entries = _entries(5)
    del entries[2]
    result = chain.verify_chain(entries)
    assert result["consistent"] is False
    assert result["broken_at"] == 2


def test_reordering_entries_is_detected():
    entries = _entries(5)
    entries[1], entries[3] = entries[3], entries[1]
    assert chain.verify_chain(entries)["consistent"] is False


def test_appending_a_forged_entry_is_detected():
    """An entry with a valid-looking hash but the wrong predecessor doesn't splice in."""
    entries = _entries(3)
    forged = chain.make_entry(
        seq=3, prev_hash=chain.GENESIS_HASH, subject_sha256="a" * 64,
        manifest_hash=None, kind="generated", recorded_at="2026-07-19T11:00:00Z",
    )
    result = chain.verify_chain([*entries, forged])
    assert result["consistent"] is False
    assert result["broken_at"] == 3
    assert "reordered or spliced" in result["reason"]


def test_a_head_that_disagrees_with_the_chain_is_rejected():
    result = chain.verify_chain(_entries(3), expect_head="b" * 64)
    assert result["consistent"] is False
    assert "does not produce the head that was published" in result["reason"]


def test_entry_hash_is_stable_across_key_order():
    """Hashing is canonical, so a verifier written elsewhere gets the same answer."""
    a = chain.entry_payload(seq=1, prev_hash="a" * 64, subject_sha256="b" * 64,
                            manifest_hash=None, kind="original",
                            recorded_at="2026-07-19T10:00:00Z")
    shuffled = dict(reversed(list(a.items())))
    assert chain.compute_entry_hash(a) == chain.compute_entry_hash(shuffled)


def test_absent_and_empty_manifest_hash_agree():
    """None normalises to "" so two implementations can't disagree on null handling."""
    base = dict(seq=0, prev_hash=chain.GENESIS_HASH, subject_sha256="c" * 64,
                kind="original", recorded_at="2026-07-19T10:00:00Z")
    assert (chain.compute_entry_hash(chain.entry_payload(manifest_hash=None, **base))
            == chain.compute_entry_hash(chain.entry_payload(manifest_hash="", **base)))


# ── Checkpoints ───────────────────────────────────────────────────────
def test_checkpoint_verifies_and_detects_tampering():
    entries = _entries(4)
    cp = chain.build_checkpoint(size=4, head=entries[-1]["entry_hash"],
                                issued_at="2026-07-19T12:00:00Z")
    assert chain.verify_checkpoint(cp) is True
    assert chain.verify_checkpoint({**cp, "size": 99}) is False
    assert chain.verify_checkpoint({**cp, "head": "d" * 64}) is False


def test_inclusion_proof_holds_and_fails_honestly():
    entries = _entries(6)
    cp = chain.build_checkpoint(size=6, head=entries[-1]["entry_hash"],
                                issued_at="2026-07-19T12:00:00Z")

    good = chain.verify_inclusion(entries[2], entries[3:], cp)
    assert good["included"] is True

    # A proof that omits an intermediate entry cannot reach the published head.
    short = chain.verify_inclusion(entries[2], entries[4:], cp)
    assert short["included"] is False


def test_a_substituted_entry_cannot_be_proved_included():
    """An inclusion proof takes its first prev_hash as given — this is why that's sound.

    A forger swaps in an entry claiming a different subject at the same position. Its own
    hash therefore changes, so the genuine next entry no longer chains from it and the
    replay cannot reach the published head.
    """
    entries = _entries(6)
    cp = chain.build_checkpoint(size=6, head=entries[-1]["entry_hash"],
                                issued_at="2026-07-19T12:00:00Z")
    forged = chain.make_entry(
        seq=2, prev_hash=entries[2]["prev_hash"], subject_sha256="f" * 64,
        manifest_hash=None, kind="generated", recorded_at=entries[2]["recorded_at"],
    )
    result = chain.verify_inclusion(forged, entries[3:], cp)
    assert result["included"] is False


def test_an_entry_cannot_claim_a_different_position():
    """Relabelling an entry's seq to sit elsewhere fails the size check."""
    entries = _entries(6)
    cp = chain.build_checkpoint(size=6, head=entries[-1]["entry_hash"],
                                issued_at="2026-07-19T12:00:00Z")
    result = chain.verify_inclusion({**entries[2], "seq": 4}, entries[3:], cp)
    assert result["included"] is False


def test_rewriting_history_before_a_checkpoint_is_caught():
    """The append-only claim itself: an old checkpoint pins everything before it."""
    entries = _entries(6)
    early = chain.build_checkpoint(size=3, head=entries[2]["entry_hash"],
                                   issued_at="2026-07-19T11:00:00Z")
    later = chain.build_checkpoint(size=6, head=entries[-1]["entry_hash"],
                                   issued_at="2026-07-19T12:00:00Z")

    assert chain.verify_consistency(early, later, entries)["consistent"] is True

    # Now rewrite entry 1 and rebuild the chain so it is internally valid again — exactly
    # what a dishonest operator would do. The earlier checkpoint no longer reproduces.
    rewritten = _entries(6)
    rewritten[1] = chain.make_entry(
        seq=1, prev_hash=rewritten[0]["entry_hash"], subject_sha256="e" * 64,
        manifest_hash=None, kind="generated", recorded_at="2026-07-19T10:01:00Z",
    )
    prev = rewritten[1]["entry_hash"]
    for i in range(2, 6):
        rewritten[i] = chain.make_entry(
            seq=i, prev_hash=prev, subject_sha256=f"{i:064x}", manifest_hash=None,
            kind="generated", recorded_at=f"2026-07-19T10:{i:02d}:00Z",
        )
        prev = rewritten[i]["entry_hash"]

    assert chain.verify_chain(rewritten)["consistent"] is True, "internally valid again"
    result = chain.verify_consistency(early, later, rewritten)
    assert result["consistent"] is False
    assert "earlier checkpoint" in result["reason"]


def test_a_shrinking_log_is_rejected():
    entries = _entries(3)
    big = chain.build_checkpoint(size=6, head="a" * 64, issued_at="t1")
    small = chain.build_checkpoint(size=3, head=entries[-1]["entry_hash"], issued_at="t2")
    assert chain.verify_consistency(big, small, entries)["consistent"] is False


# ── Wiring into the app ───────────────────────────────────────────────
def _sku_with_photo(client, png_bytes):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes(), "image/png")})
    return sku


def test_uploading_an_original_records_it(client, png_bytes):
    """Anchoring an authentic original is a logged event, not only AI output."""
    _sku_with_photo(client, png_bytes)
    status = client.get("/api/ledger").json()
    assert status["size"] == 1
    entries = client.get("/api/ledger/entries").json()
    assert entries[0]["kind"] == "original"
    assert entries[0]["prev_hash"] == chain.GENESIS_HASH


def test_generation_appends_every_asset(client, png_bytes):
    """Both ingestion paths log — a generated asset must not bypass the ledger."""
    sku = _sku_with_photo(client, png_bytes)
    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio", "lifestyle"]})

    entries = client.get("/api/ledger/entries").json()
    kinds = [e["kind"] for e in entries]
    assert kinds[0] == "original"
    assert kinds.count("generated") >= 2, f"generated assets missing from the log: {kinds}"
    assert chain.verify_chain(entries)["consistent"] is True


def test_verify_reports_the_ledger_position(client, png_bytes):
    sku = _sku_with_photo(client, png_bytes)
    asset = client.get(f"/api/skus/{sku['id']}/assets").json()[0]

    body = client.get(f"/api/verify/{asset['sha256']}").json()
    assert body["ledger"] is not None
    assert body["ledger"]["seq"] == 0
    assert body["ledger"]["entry_hash"]


def test_verify_of_an_unlogged_hash_says_nothing_negative(client):
    """Absence is not evidence: appends are best-effort, so it must not read as a failure."""
    body = client.get(f"/api/verify/{'a' * 64}").json()
    assert body["ledger"] is None
    assert "log" not in body["disclosure"].lower()


def test_checkpoint_is_cut_and_covers_the_log(client, png_bytes, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "transparency_checkpoint_every", 2)
    _sku_with_photo(client, png_bytes)
    _sku_with_photo(client, png_bytes)   # second upload trips the interval

    cp = client.get("/api/ledger/checkpoint")
    assert cp.status_code == 200
    body = cp.json()
    assert body["size"] == 2
    assert chain.verify_checkpoint(body) is True

    entries = client.get("/api/ledger/entries").json()
    replayed = chain.verify_chain(entries[: body["size"]], expect_head=body["head"])
    assert replayed["consistent"] is True


def test_no_checkpoint_yet_is_a_404_not_an_empty_object(client):
    assert client.get("/api/ledger/checkpoint").status_code == 404


def test_inclusion_proof_endpoint_is_independently_verifiable(client, png_bytes,
                                                              monkeypatch):
    """The proof must verify using only what the endpoint returns."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "transparency_checkpoint_every", 1)
    sku = _sku_with_photo(client, png_bytes)
    asset = client.get(f"/api/skus/{sku['id']}/assets").json()[0]

    proof = client.get(f"/api/ledger/proof/{asset['sha256']}").json()
    result = chain.verify_inclusion(proof["entry"], proof["following"], proof["checkpoint"])
    assert result["included"] is True, result["reason"]


def test_proof_for_an_unknown_hash_is_404(client, png_bytes, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "transparency_checkpoint_every", 1)
    _sku_with_photo(client, png_bytes)
    assert client.get(f"/api/ledger/proof/{'b' * 64}").status_code == 404


def test_self_verification_admits_it_is_not_independent(client, png_bytes):
    _sku_with_photo(client, png_bytes)
    body = client.get("/api/ledger/verify-log").json()
    assert body["consistent"] is True
    assert "not independent evidence" in body["caveat"]


def test_a_ledger_outage_does_not_fail_a_generation(client, png_bytes, monkeypatch):
    """Appends are best-effort by contract — the provider was already paid."""
    import app.transparency as tx

    def boom(body):
        raise RuntimeError("ledger unavailable")

    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    monkeypatch.setattr(tx.get_repo(), "append_transparency_entry", boom)

    r = client.post(f"/api/skus/{sku['id']}/upload",
                    files={"file": ("p.png", png_bytes(), "image/png")})
    assert r.status_code == 201
    assert client.get("/api/ledger").json()["size"] == 0


def test_concurrent_appends_do_not_fork_the_chain():
    """Two writers must never both claim the same predecessor."""
    import threading

    from app.repo import InMemoryRepo

    repo = InMemoryRepo()
    barrier = threading.Barrier(8)

    def append(i: int) -> None:
        barrier.wait()
        repo.append_transparency_entry({
            "subject_sha256": f"{i:064x}", "manifest_hash": None,
            "kind": "generated", "recorded_at": "2026-07-19T10:00:00Z",
        })

    threads = [threading.Thread(target=append, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    entries = repo.list_transparency_entries()
    assert len(entries) == 8
    assert chain.verify_chain(entries)["consistent"] is True
    assert len({e["entry_hash"] for e in entries}) == 8


@pytest.mark.parametrize("field", ["seq", "prev_hash", "subject_sha256", "manifest_hash",
                                   "kind", "recorded_at"])
def test_every_committed_field_actually_affects_the_hash(field):
    """A field listed as committed but not hashed would be silently forgeable."""
    base = chain.entry_payload(seq=1, prev_hash="a" * 64, subject_sha256="b" * 64,
                               manifest_hash="c" * 64, kind="generated",
                               recorded_at="2026-07-19T10:00:00Z")
    mutated = {**base, field: 99 if field == "seq" else "z" * 12}
    assert chain.compute_entry_hash(base) != chain.compute_entry_hash(mutated)
