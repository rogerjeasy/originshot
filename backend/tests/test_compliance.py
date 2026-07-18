"""Compliance scorecard: rendition checks, the endpoint, and the pack.json integration."""
import io
import json
import zipfile

from PIL import Image

from originshot_pipelines.compliance import check_rendition, studio_scorecard
from originshot_pipelines.presets import get_preset


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def product_on_white(size=900) -> bytes:
    img = Image.new("RGB", (size, size), (255, 255, 255))
    q = size // 5
    for x in range(q, size - q):
        for y in range(q, size - q):
            img.putpixel((x, y), (70, 60, 50))
    return _png(img)


def busy_grey_scene(w=900, h=700) -> bytes:
    img = Image.new("RGB", (w, h), (120, 120, 120))
    for x in range(0, w, 3):
        for y in range(0, h, 3):
            img.putpixel((x, y), (200, 190, 60))
    return _png(img)


def test_scorecard_white_channels_pass_with_clean_master():
    items = studio_scorecard(product_on_white())
    by_market = {i["marketplace"]: i for i in items}
    assert set(by_market) == {"amazon", "etsy", "shopify", "ebay", "social"}
    assert by_market["amazon"]["passed"] is True
    assert by_market["ebay"]["passed"] is True
    # Cover-cropped channels only need exact dims + a non-blank frame.
    assert by_market["etsy"]["passed"] is True
    assert by_market["social"]["passed"] is True


def test_dimensions_always_measured():
    items = studio_scorecard(product_on_white(), ["amazon"])
    dims = next(c for c in items[0]["checks"] if c["name"] == "dimensions")
    assert dims["passed"] is True and dims["value"] == "2000x2000"


def test_blank_master_fails_fill():
    blank = _png(Image.new("RGB", (900, 900), (255, 255, 255)))
    items = studio_scorecard(blank, ["amazon"])
    fill = next(c for c in items[0]["checks"] if c["name"] == "product_fill")
    assert fill["passed"] is False
    assert items[0]["passed"] is False


def test_check_rendition_flags_wrong_dimensions():
    # A file that skipped the renderer: right rules, wrong pixels.
    wrong = _png(Image.new("RGB", (800, 800), (255, 255, 255)))
    report = check_rendition(wrong, get_preset("amazon"))
    dims = next(c for c in report["checks"] if c["name"] == "dimensions")
    assert dims["passed"] is False


def test_cover_crop_scene_passes_not_blank():
    items = studio_scorecard(busy_grey_scene(), ["etsy"])
    nb = next(c for c in items[0]["checks"] if c["name"] == "not_blank")
    assert nb["passed"] is True


def test_compliance_endpoint(client, png_bytes):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()

    # Nothing uploaded yet → an actionable 400, not an empty scorecard.
    assert client.get(f"/api/skus/{sku['id']}/compliance").status_code == 400

    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes((900, 900)), "image/png")})
    r = client.get(f"/api/skus/{sku['id']}/compliance")
    assert r.status_code == 200
    body = r.json()
    assert body["source_style"] == "original"      # no studio asset yet — says so honestly
    assert len(body["items"]) == 5
    assert all("checks" in i for i in body["items"])


def test_compliance_reads_legacy_assets_with_only_a_url(client, png_bytes):
    """An asset carrying only a sink URL (no b2_key) must still be measurable.

    Assets generated before manifest embedding was wired store `b2_url` and leave `b2_key`
    unset. Requiring `b2_key` made this endpoint 400 on SKUs whose studio page rendered
    perfectly — the export path already handled both, and this one has to agree.
    """
    from app.repo import get_repo

    sku = client.post("/api/skus", json={"title": "Legacy"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes((900, 900)), "image/png")})

    repo = get_repo()
    original = repo.list_assets("dev-user", sku["id"])[0]
    # A newer studio asset that only knows its URL — the preferred candidate, unreadable.
    repo.add_asset("dev-user", {
        "sku_id": sku["id"], "sha256": "f" * 64,
        "b2_key": None, "b2_url": "https://example.invalid/off-bucket.png",
        "modality": "image", "style": "studio", "is_authentic": False,
        "parent_sha256": original["sha256"],
    })

    r = client.get(f"/api/skus/{sku['id']}/compliance")
    assert r.status_code == 200, r.text
    # Falls through to the authentic original rather than refusing, and says so.
    assert r.json()["source_style"] == "original"
    assert len(r.json()["items"]) == 5


def test_compliance_400_only_when_nothing_is_readable(client):
    sku = client.post("/api/skus", json={"title": "Empty"}).json()
    assert client.get(f"/api/skus/{sku['id']}/compliance").status_code == 400


def test_export_pack_json_carries_compliance(client, png_bytes):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes((900, 900)), "image/png")})

    r = client.post(f"/api/skus/{sku['id']}/export", json={"marketplaces": ["amazon", "etsy"]})
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    root = zf.namelist()[0].split("/")[0]
    pack = json.loads(zf.read(f"{root}/pack.json"))
    markets = {i["marketplace"] for i in pack["compliance"]}
    assert markets == {"amazon", "etsy"}
