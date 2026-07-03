from pathlib import Path

from bundesrag.config import Settings, detect_language


def test_required_keys_are_read_from_constructor():
    settings = Settings(
        mistral_api_key="a",
        dip_api_key="c",
        _env_file=None,
    )
    assert settings.mistral_api_key == "a"
    assert settings.dip_api_key == "c"


def test_pdf_and_chroma_dirs_are_derived_from_data_dir():
    settings = Settings(
        mistral_api_key="a",
        dip_api_key="c",
        data_dir=Path("custom-data"),
        _env_file=None,
    )
    assert settings.pdf_dir == Path("custom-data/pdfs")
    assert settings.chroma_dir == Path("custom-data/chroma")


def test_detect_language_reads_environment_without_api_keys(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("DIP_API_KEY", raising=False)
    monkeypatch.setenv("LANGUAGE", "en")
    assert detect_language() == "en"


def test_detect_language_falls_back_to_default_for_unsupported_value(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "fr")
    assert detect_language() == "de"
