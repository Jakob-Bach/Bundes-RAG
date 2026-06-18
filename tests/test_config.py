from pathlib import Path

from bundesrag.config import Settings


def test_required_keys_are_read_from_constructor():
    settings = Settings(
        anthropic_api_key="a",
        voyage_api_key="b",
        dip_api_key="c",
        _env_file=None,
    )
    assert settings.anthropic_api_key == "a"
    assert settings.voyage_api_key == "b"
    assert settings.dip_api_key == "c"


def test_pdf_and_chroma_dirs_are_derived_from_data_dir():
    settings = Settings(
        anthropic_api_key="a",
        voyage_api_key="b",
        dip_api_key="c",
        data_dir=Path("custom-data"),
        _env_file=None,
    )
    assert settings.pdf_dir == Path("custom-data/pdfs")
    assert settings.chroma_dir == Path("custom-data/chroma")
