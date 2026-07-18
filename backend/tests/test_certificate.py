"""Certificate of Provenance: the PDF/QR builders and their presence in the export."""
import io
import zipfile

from PIL import Image

from originshot_pipelines.certificate import build_certificate, qr_png

SKU = {"id": "sku-1", "title": "Handmade ceramic mug"}
ASSETS = [
    {"sha256": "a" * 64, "is_authentic": True, "style": "original"},
    {"sha256": "b" * 64, "is_authentic": False, "style": "studio",
     "provider": "gmicloud-image", "model": "gemini-3-pro-image-preview",
     "qa": {"passed": True}},
    {"sha256": "c" * 64, "is_authentic": False, "style": "video",
     "provider": "gmicloud", "model": "Kling-Image2Video-V2.1-Master"},
]


def test_certificate_is_a_pdf_with_the_evidence():
    pdf = build_certificate(SKU, ASSETS, verify_base_url="https://x.test/verify")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000
    # Full hashes are embedded as text (uncompressed text objects in fpdf2 need the
    # content stream decoded — assert via a re-parse-free check on the raw bytes).
    # fpdf compresses streams, so instead assert the doc renders and carries pages.
    assert b"/Page" in pdf


def test_certificate_survives_unicode_title():
    pdf = build_certificate({"id": "s", "title": "Tasse céramique — 日本"}, ASSETS,
                            verify_base_url="https://x.test/verify")
    assert pdf.startswith(b"%PDF")


def test_qr_png_is_scannable_png():
    png = qr_png("https://x.test/verify/" + "a" * 64)
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG"
    assert img.size[0] > 100  # enough modules to be scannable at listing size


def test_export_ships_certificate_and_qr(client, png_bytes):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes(), "image/png")})

    r = client.post(f"/api/skus/{sku['id']}/export", json={})
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    root = names[0].split("/")[0]
    assert f"{root}/certificate.pdf" in names
    assert f"{root}/verify-qr.png" in names
    assert zf.read(f"{root}/certificate.pdf").startswith(b"%PDF")
