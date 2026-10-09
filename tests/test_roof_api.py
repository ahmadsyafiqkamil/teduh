"""The upload path. The metadata tests are the ones that matter: a geotagged roof photo is
a home address, so stripping must be structural (decode pixels, re-encode) rather than a
best-effort tag deletion that can miss a container.

No test here reaches Gemini. Every rejection path returns before analyze_roof_bytes is
called, which is also why those guards are ordered the way they are in routes.py."""

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from api.routes import (
    ALLOWED_PHOTO_TYPES,
    MAX_PHOTO_BYTES,
    MAX_PHOTO_EDGE_PX,
    router,
    strip_metadata,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _photo_with_gps(size=(800, 600)) -> bytes:
    """A JPEG carrying EXIF, including a GPS tag."""
    image = PILImage.new("RGB", size, (120, 90, 70))
    exif = image.getexif()
    exif[0x0110] = "TestCamera"  # Model
    exif[0x9003] = "2026:10:09 12:00:00"  # DateTimeOriginal
    # Degrees/minutes/seconds as plain numbers. Pillow packs the rationals itself; handing
    # it pre-made (numerator, denominator) pairs raises inside TiffImagePlugin.
    exif[0x8825] = {1: "S", 2: (6.0, 10.0, 0.0), 3: "E", 4: (106.0, 50.0, 0.0)}  # GPSInfo
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


@pytest.mark.unit
def test_the_fixture_photo_really_does_carry_metadata():
    # Otherwise the stripping tests below would pass against an already-clean file.
    assert dict(PILImage.open(io.BytesIO(_photo_with_gps())).getexif())


@pytest.mark.unit
def test_strip_metadata_removes_every_exif_tag():
    cleaned, mime_type = strip_metadata(_photo_with_gps())
    assert mime_type == "image/jpeg"
    assert dict(PILImage.open(io.BytesIO(cleaned)).getexif()) == {}


@pytest.mark.unit
def test_strip_metadata_keeps_the_picture_itself():
    cleaned, _ = strip_metadata(_photo_with_gps(size=(800, 600)))
    assert PILImage.open(io.BytesIO(cleaned)).size == (800, 600)


@pytest.mark.unit
def test_strip_metadata_downscales_an_oversized_photo():
    cleaned, _ = strip_metadata(_photo_with_gps(size=(4000, 3000)))
    assert max(PILImage.open(io.BytesIO(cleaned)).size) <= MAX_PHOTO_EDGE_PX


@pytest.mark.unit
def test_strip_metadata_rejects_something_that_is_not_an_image():
    with pytest.raises(ValueError, match="gambar"):
        strip_metadata(b"ini bukan gambar sama sekali")


@pytest.mark.integration
def test_endpoint_rejects_a_disallowed_content_type(client):
    response = client.post(
        "/api/roof", files={"photo": ("a.txt", b"halo", "text/plain")}
    )
    assert response.status_code == 415
    assert "image/jpeg" in response.json()["error"]


@pytest.mark.integration
def test_endpoint_rejects_an_oversized_upload(client):
    oversized = b"\xff\xd8\xff" + b"0" * (MAX_PHOTO_BYTES + 1)
    response = client.post(
        "/api/roof", files={"photo": ("big.jpg", oversized, "image/jpeg")}
    )
    assert response.status_code == 413


@pytest.mark.integration
def test_endpoint_rejects_a_corrupt_image(client):
    response = client.post(
        "/api/roof", files={"photo": ("a.jpg", b"bukan jpeg", "image/jpeg")}
    )
    assert response.status_code == 400


@pytest.mark.integration
def test_allowed_types_are_only_jpeg_and_png():
    assert sorted(ALLOWED_PHOTO_TYPES) == ["image/jpeg", "image/png"]


@pytest.mark.integration
def test_endpoint_never_echoes_a_filesystem_path(client):
    response = client.post(
        "/api/roof", files={"photo": ("a.jpg", b"bukan jpeg", "image/jpeg")}
    )
    assert "/Users" not in response.text
    assert "/tmp" not in response.text


@pytest.mark.integration
def test_endpoint_rejects_a_location_finer_than_kelurahan(client):
    # CONCEPT §8.5: location is kelurahan-level at most.
    response = client.post(
        "/api/roof",
        files={"photo": ("a.jpg", _photo_with_gps(), "image/jpeg")},
        data={"kelurahan": "Jl. Mawar No. 12 RT 03 RW 05"},
    )
    assert response.status_code == 422


@pytest.mark.integration
def test_endpoint_accepts_a_plain_kelurahan_name(client):
    """The address guard must not reject the legitimate case.

    Several Jakarta kelurahan names would trip a careless substring check -- Gandaria,
    Rawa Buaya, Grogol -- so the markers are matched on word boundaries.
    """
    for name in ("Gandaria Utara", "Rawa Buaya", "Grogol Petamburan", "Kebon Jeruk"):
        response = client.post(
            "/api/roof",
            files={"photo": ("a.jpg", b"bukan jpeg", "image/jpeg")},
            data={"kelurahan": name},
        )
        # 400 = got past the location guard and failed on the corrupt image, as intended.
        assert response.status_code == 400, f"{name!r} ditolak padahal nama kelurahan sah"
