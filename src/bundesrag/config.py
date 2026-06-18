from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    voyage_api_key: str
    dip_api_key: str

    data_dir: Path = Path("data")

    chat_model: str = "claude-sonnet-4-5-20250929"
    embedding_model: str = "voyage-3"

    # Page size for DIP API list requests, and a safety cap on documents
    # fetched per run before the user is asked to confirm a large download.
    dip_page_size: int = 50
    dip_max_results_before_confirm: int = 200

    retrieval_top_k: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 150

    @property
    def pdf_dir(self) -> Path:
        return self.data_dir / "pdfs"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"
