import pytest

from bundesrag.config import Settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.delenv("DIP_API_KEY", raising=False)
    return Settings(
        anthropic_api_key="test-anthropic-key",
        voyage_api_key="test-voyage-key",
        dip_api_key="test-dip-key",
        data_dir=tmp_path / "data",
        _env_file=None,
    )
