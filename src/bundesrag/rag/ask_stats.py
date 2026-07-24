"""Ask-stats: how large the corpus an ask searches is.

Every answer is prefaced with these figures — how many documents and chunks
are indexed, and how many chunks retrieval selects at most
(`retrieval_top_k`). When a filter is active (web UI only), the figures also
report how many of those documents/chunks match the filter, so users can
judge how narrow their filter is — the web UI shows the same figures before
the ask, too. Distinct from the Mistral *usage* stats (`usage.py`) and the
*status* command's summary.
"""

from dataclasses import dataclass

from langchain_chroma import Chroma

from bundesrag.config import Settings
from bundesrag.ingestion.manifest import load_indexed_info
from bundesrag.rag.filters import AskFilters, matching_pdf_paths
from bundesrag.vectorstore import collection_chunk_count


@dataclass
class AskStats:
    """How large the corpus an ask searches is.

    `num_filtered_documents`/`num_filtered_chunks` are set only when an active
    filter restricts retrieval; both None means no filter was applied.
    """

    num_documents: int
    num_chunks: int
    top_k: int
    num_filtered_documents: int | None = None
    num_filtered_chunks: int | None = None


def compute_ask_stats(
    settings: Settings, vectorstore: Chroma, filters: AskFilters | None = None
) -> AskStats:
    indexed = load_indexed_info(settings)
    stats = AskStats(
        num_documents=len(indexed),
        num_chunks=collection_chunk_count(vectorstore),
        top_k=settings.retrieval_top_k,
    )
    if filters is not None and filters.is_active:
        paths = set(matching_pdf_paths(filters, settings))
        stats.num_filtered_documents = len(paths)
        # Per-document chunk counts come from the indexed-docs manifest — the
        # vector store can't be cheaply counted per filter — so documents
        # without a recorded count contribute 0.
        stats.num_filtered_chunks = sum(
            info.num_chunks or 0 for path, info in indexed.items() if str(path) in paths
        )
    return stats
