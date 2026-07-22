from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from bundesrag.i18n import DEFAULT_LANGUAGE
from bundesrag.locales import AVAILABLE_LANGUAGES


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mistral_api_key: str
    dip_api_key: str

    # Language of CLI output (help text, prompts, citations); see bundesrag.i18n.
    language: str = "de"

    data_dir: Path = Path("data")

    chat_model: str = "mistral-large-latest"
    embedding_model: str = "mistral-embed"

    retrieval_top_k: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Prices per million tokens for the estimated-cost statistic; the defaults
    # match Mistral's published EUR prices for the default models above
    # (mistral-large-latest / mistral-embed). Override them when using other
    # models, or unset them (empty value in .env) to hide the cost estimate.
    chat_input_price_per_mtok: float | None = 0.44
    chat_output_price_per_mtok: float | None = 1.3
    embedding_price_per_mtok: float | None = 0.1
    price_currency: str = "EUR"

    @property
    def pdf_dir(self) -> Path:
        return self.data_dir / "pdfs"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def log_file(self) -> Path:
        return self.data_dir / "bundesrag.log"


class _LanguageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    language: str = DEFAULT_LANGUAGE


def detect_language() -> str:
    """Reads only the language setting, without requiring the API keys.

    The CLI's help text is built at import time, before any command constructs
    the full Settings, and `--help` must work even when the API keys are not
    configured. Unsupported values fall back to the default so `--help` still
    works; set_language() rejects them once a command actually runs."""
    language = _LanguageSettings().language
    return language if language in AVAILABLE_LANGUAGES else DEFAULT_LANGUAGE
