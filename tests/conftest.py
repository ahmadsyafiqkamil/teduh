"""Shared fixtures. `fixture_store` is the default for unit tests: 3 kelurahan and 173 cells,
built by pipeline/make_fixtures.py with a deliberate spread in canopy and HVI so that
sign-direction assertions actually have something to bite on.

`real_store` is for integration checks and skips cleanly, because
data/processed/grid_features.parquet is gitignored (7 MB) and will be absent on a fresh clone.
"""

from pathlib import Path

import pytest

from teduh_agent import store as store_module

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
REAL_GRID = ROOT / "data" / "processed" / "grid_features.parquet"


@pytest.fixture
def isolated_brief_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point brief rendering at a throwaway dir so tests never touch data/briefs/.

    api/routes.py imports BRIEF_DIR by value, so patching only the brief module would leave
    the endpoint tests hitting the real directory. Both must be patched.
    """
    briefs = tmp_path / "briefs"
    briefs.mkdir()
    monkeypatch.setattr("teduh_agent.tools.brief.BRIEF_DIR", briefs)
    monkeypatch.setattr("api.routes.BRIEF_DIR", briefs)
    return briefs


@pytest.fixture(scope="session")
def fixture_store() -> store_module.Store:
    return store_module.load(
        kelurahan_path=FIXTURES / "kelurahan_metrics_sample.parquet",
        grid_path=FIXTURES / "grid_features_sample.parquet",
    )


@pytest.fixture(scope="session")
def real_store() -> store_module.Store:
    if not REAL_GRID.exists():
        pytest.skip(
            "data/processed/grid_features.parquet tidak ada (gitignored). "
            "Jalankan: uv run python -m pipeline.build_grid"
        )
    return store_module.load()
