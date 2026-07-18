"""Listing copy: prompt/normalize logic, the endpoint, and the export integration.
The chat transport is always stubbed — the suite never spends provider money."""
import json

import pytest

from originshot_pipelines import listing as listing_mod


def _fake_model_json():
    return {
        "amazon": {
            "title": "T" * 300,                       # over the 200 cap — must be cut
            "description": "A sturdy handmade mug.",
            "bullets": [f"Bullet {i}" for i in range(9)],  # over the 5 cap
            "keywords": [],
        },
        "etsy": {
            "title": "Handmade ceramic mug",
            "description": "Wheel-thrown stoneware.",
            "bullets": [],
            "keywords": [f"#tag{i}" for i in range(20)],   # over 13, and with # prefixes
        },
    }


class _FakeResp:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {
            "content": "Here you go:\n" + json.dumps(_fake_model_json())}}]}


@pytest.fixture
def stub_chat(monkeypatch):
    import httpx

    calls: list[dict] = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "body": json})
        return _FakeResp()

    monkeypatch.setattr(httpx, "post", fake_post)
    # conftest blanks GMI_API_KEY for the whole suite; the endpoint requires one, so give
    # it a fake — the transport above guarantees no real call can happen anyway.
    monkeypatch.setattr("app.api.listing.get_settings",
                        lambda: type("S", (), {"gmi_api_key": "test-key"})())
    return calls


def test_generate_listing_enforces_hard_limits(stub_chat):
    result = listing_mod.generate_listing(
        {"title": "Mug", "id": "s1"}, None, ["amazon", "etsy"],
        api_key="k", base_url="http://x", model="test-model")

    amazon = result["marketplaces"]["amazon"]
    assert len(amazon["title"]) == 200          # truncated in code, not trusted
    assert len(amazon["bullets"]) == 5
    etsy = result["marketplaces"]["etsy"]
    assert len(etsy["keywords"]) == 13
    assert all(not k.startswith("#") for k in etsy["keywords"])
    assert "AI-generated" in result["disclosure"]
    assert result["model"] == "test-model"


def test_prompt_carries_facts_and_rules():
    prompt = listing_mod.build_prompt(
        {"title": "Blue Mug", "category": "Kitchen", "description": "Hand thrown."},
        {"vibe": "warm, minimal"}, ["amazon"])
    assert "Blue Mug" in prompt and "Kitchen" in prompt and "Hand thrown." in prompt
    assert "warm, minimal" in prompt
    assert "200" in prompt          # the channel's title cap is taught, then enforced
    assert "never invent" in prompt


def test_listing_endpoint_stores_and_returns(client, stub_chat):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()

    # Nothing generated yet.
    assert client.get(f"/api/skus/{sku['id']}/listing").status_code == 404

    r = client.post(f"/api/skus/{sku['id']}/listing",
                    json={"marketplaces": ["amazon", "etsy"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["marketplaces"]) == {"amazon", "etsy"}

    # Stored on the SKU: GET now serves it without another model call.
    calls_before = len(stub_chat)
    fetched = client.get(f"/api/skus/{sku['id']}/listing")
    assert fetched.status_code == 200
    assert fetched.json()["generated_at"] == body["generated_at"]
    assert len(stub_chat) == calls_before


def test_listing_endpoint_503_when_unconfigured(client, monkeypatch):
    # conftest blanks GMI_API_KEY, so generation must refuse — never fabricate copy.
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    monkeypatch.setattr("app.api.listing.get_settings",
                        lambda: type("S", (), {"gmi_api_key": None})())
    r = client.post(f"/api/skus/{sku['id']}/listing", json={})
    assert r.status_code == 503
    assert "GMI_API_KEY" in r.json()["detail"]


def test_export_ships_listing_files(client, png_bytes, stub_chat):
    import io
    import zipfile

    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes(), "image/png")})
    client.post(f"/api/skus/{sku['id']}/listing", json={"marketplaces": ["amazon", "etsy"]})

    r = client.post(f"/api/skus/{sku['id']}/export", json={"marketplaces": ["amazon"]})
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    root = names[0].split("/")[0]
    assert f"{root}/listing/listing.json" in names
    assert f"{root}/listing/amazon.txt" in names
    # etsy copy exists on the SKU but wasn't a selected export channel.
    assert f"{root}/listing/etsy.txt" not in names

    txt = zf.read(f"{root}/listing/amazon.txt").decode()
    assert "AMAZON LISTING COPY" in txt and "AI-generated" in txt
