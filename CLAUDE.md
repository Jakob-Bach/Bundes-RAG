# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Bundes-RAG is a CLI tool that lets a user describe, in German, which documents
from the Bundestag's DIP (Dokumentations- und Informationssystem für
Parlamentsmaterialien) to download and index, then answer natural-language
German questions about them via RAG, with citations to source documents and
pages.

## Commands

```sh
uv sync                  # install/sync dependencies
uv run pytest            # run the test suite
uv run pytest tests/test_dip_client.py::test_name  # run a single test
uv run bundesrag download "Plenarprotokolle der 21. Wahlperiode."  # download docs
uv run bundesrag index  # index downloaded-but-not-yet-indexed docs
uv run bundesrag ask "Welche Gesetzesvorhaben gibt es bzgl. künstlicher Intelligenz?"  # query
```

Requires `MISTRAL_API_KEY` and `DIP_API_KEY` in `.env` (copy from
`.env.example`). Tests use the `settings` fixture in `tests/conftest.py`,
which builds `Settings` with fake keys and `_env_file=None`, so no real `.env`
or network access is needed for unit tests.

## Architecture

Three pipelines share the same Chroma vector store (`src/bundesrag/vectorstore.py`),
all driven from `src/bundesrag/cli.py` (Typer app with `download`, `index`,
and `ask` commands, German-language help text and output).

**`download` pipeline** (`ingestion/pipeline.py: run_download`):
1. `query_agent/agent.py: QueryAgent` — a Mistral LLM with structured output
   (`with_structured_output(QueryAgentResult)`) turns the NL prompt into
   `DipQueryFilters` (`query_agent/schema.py`). If the LLM can't produce valid
   filters, it returns a `ClarificationRequest` instead; `QueryAgent.build_query`
   loops asking the user (via an injected `ask_user` callable) up to
   `MAX_CLARIFICATION_ROUNDS` times.
2. `dip/client.py: DipClient` calls the DIP API (`list_drucksachen` /
   `list_plenarprotokolle`), paginating via the API's cursor until it stops
   advancing. Note `urheber`/`ressort_fdf` are repeated-value filters with AND
   semantics across distinct values in the DIP API — querying for either of
   two ministries/fractions needs two separate `download` calls.
3. If the result count exceeds `settings.dip_max_results_before_confirm`, the
   user is asked to confirm (via an injected `confirm` callable) before
   downloading.
4. PDFs are downloaded into `data/pdfs/<endpoint>/`, and each one is recorded
   as a `PendingDocument` in the `data/pending_index.json` manifest
   (`ingestion/manifest.py`) for the `index` command to pick up later.

**`index` pipeline** (`ingestion/pipeline.py: run_index`):
1. Reads pending entries from `ingestion/manifest.py: load_pending`.
2. Each PDF is parsed page-by-page (`ingestion/pdf_loader.py`), chunked with
   `RecursiveCharacterTextSplitter`, and given deterministic ids
   (`{dokumentnummer}-p{page}-{chunk_index}`) so re-running `index` on
   overlapping document sets upserts rather than duplicating chunks in Chroma.
3. After each document is embedded into the vector store, it's removed from
   the manifest individually (`remove_pending`) — this is why `download` and
   `index` are separate commands: indexing many documents takes considerably
   longer than downloading them and can fail partway (e.g. an API rate
   limit), so re-running `index` after a failure only reprocesses documents
   still listed as pending, instead of redoing the whole batch.

**`ask` pipeline** (`rag/answer_agent.py: answer_question`):
1. `rag/retriever.py: retrieve` does a similarity search against the Chroma
   store for `settings.retrieval_top_k` chunks.
2. Retrieved chunks are formatted into a numbered context block
   (`format_context`); the chat LLM is instructed (system prompt, in German)
   to cite passages by number and to say explicitly when the context doesn't
   answer the question rather than guess.
3. A deduplicated "Quellen:" list (citation label, page, document number) is
   built from chunk metadata (`citation_for`) and returned alongside the
   answer text.

**Dependency injection**: all pipelines take their LLM, vectorstore, and DIP
client as constructor/function arguments (not constructed internally), which
is how the test suite substitutes fakes/mocks without touching real APIs.
`create_query_agent` / `create_chat_llm` are the only places that construct
real `ChatMistralAI` instances, and import `langchain_mistralai` lazily inside
the function body.

**Config** (`config.py: Settings`): a `pydantic-settings` `BaseSettings`
loading from `.env`; holds API keys, model names, and chunk/retrieval tuning
knobs. `data_dir` defaults to `./data`, with `pdf_dir`/`chroma_dir` derived
properties.

**Progress reporting** (`progress.py`): long multi-step CLI operations print
`[Schritt n/total] <name>` before each step; per-item loops (downloads,
indexing) use `tqdm`.
