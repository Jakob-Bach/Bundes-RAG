import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from bundesrag.config import Settings
from bundesrag.dip.models import DocumentMeta


class PendingDocument(BaseModel):
    """A downloaded PDF that still needs to be chunked/embedded into the vector
    store."""

    kind: Literal["drucksache", "plenarprotokoll"]
    pdf_path: Path
    meta: dict

    def resolve_meta(self) -> DocumentMeta:
        return DocumentMeta.model_validate(self.meta)


def manifest_path(settings: Settings) -> Path:
    return settings.data_dir / "pending_index.json"


def load_pending(settings: Settings) -> list[PendingDocument]:
    path = manifest_path(settings)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [PendingDocument.model_validate(item) for item in raw]


def save_pending(settings: Settings, entries: list[PendingDocument]) -> None:
    path = manifest_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [entry.model_dump(mode="json") for entry in entries],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def add_pending(settings: Settings, new_entries: list[PendingDocument]) -> None:
    if not new_entries:
        return
    entries = load_pending(settings)
    entries.extend(new_entries)
    save_pending(settings, entries)


def remove_pending(settings: Settings, pdf_path: Path) -> None:
    entries = load_pending(settings)
    remaining = [entry for entry in entries if entry.pdf_path != pdf_path]
    save_pending(settings, remaining)
