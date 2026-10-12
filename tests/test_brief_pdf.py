"""PDF rendering and the download endpoint. WeasyPrint needs Pango and Cairo as system
libraries, so these tests skip rather than fail when they are absent locally -- the
container installs them (infra/Dockerfile) and M8 verifies the deployed path."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import router
from teduh_agent.facts import SOURCE_DATA, fact, record
from teduh_agent.tools.brief import (
    REQUIRED_SECTIONS,
    ensure_pdf_libraries,
    render_policy_brief,
    to_html,
)

# WeasyPrint fails to import with OSError (not ImportError) when Pango/Cairo are missing,
# because cffi cannot load libgobject at the C level. A plain importorskip would re-raise
# that OSError and crash the whole module instead of skipping, so catch both here. On
# dev macOS the shim must run first, or the whole module would skip despite Homebrew
# already providing the libraries.
ensure_pdf_libraries()

try:
    import weasyprint  # noqa: F401
except (ImportError, OSError):
    pytest.skip("WeasyPrint butuh Pango/Cairo", allow_module_level=True)


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def rendered(isolated_brief_dir) -> dict:
    ctx = FakeToolContext()
    record(ctx, [fact("kel_ID3173040002.lst", "Suhu permukaan rata-rata", 44.61, "degC",
                      SOURCE_DATA)])
    body = "\n\n".join(f"## {section}\n\nIsi bagian." for section in REQUIRED_SECTIONS)
    draft = f"# Policy Brief TEDUH\n\n{body}\n\nSuhu [[F:kel_ID3173040002.lst]].\n"
    result = render_policy_brief(draft, ctx)
    assert "errors" not in result, result.get("errors")
    return result


@pytest.mark.integration
def test_html_conversion_keeps_the_section_headings():
    html = to_html("## Keterbatasan\n\nIsi.\n")
    assert "Keterbatasan" in html
    assert "<h2" in html


@pytest.mark.integration
def test_html_includes_print_styles_so_the_pdf_is_not_naked():
    assert "@page" in to_html("# Judul\n")


@pytest.mark.integration
def test_render_also_writes_a_pdf(rendered, isolated_brief_dir):
    assert rendered["pdf_available"] is True
    pdf = isolated_brief_dir / f"{rendered['brief_id']}.pdf"
    assert pdf.exists()
    assert pdf.stat().st_size > 1000, "PDF terlalu kecil untuk berisi apa pun"


@pytest.mark.integration
def test_pdf_starts_with_the_pdf_magic_bytes(rendered, isolated_brief_dir):
    data = (isolated_brief_dir / f"{rendered['brief_id']}.pdf").read_bytes()
    assert data[:4] == b"%PDF"


@pytest.mark.integration
def test_endpoint_serves_the_markdown_by_default(client, rendered):
    response = client.get(f"/api/brief/{rendered['brief_id']}")
    assert response.status_code == 200
    assert "Ringkasan Eksekutif" in response.text


@pytest.mark.integration
def test_endpoint_serves_the_pdf_when_asked(client, rendered):
    response = client.get(f"/api/brief/{rendered['brief_id']}?format=pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


@pytest.mark.integration
def test_endpoint_404s_for_an_unknown_brief(client):
    assert client.get("/api/brief/tidakada00000").status_code == 404


@pytest.mark.integration
def test_endpoint_rejects_a_path_traversal_attempt(client):
    # brief_id lands in a filesystem path, so this is a real boundary.
    for attempt in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd", "a/b"):
        assert client.get(f"/api/brief/{attempt}").status_code in (404, 422)
