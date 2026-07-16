# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Bundes-RAG is a tool that lets a user describe, in natural language, which
documents from the Bundestag's DIP (Dokumentations- und Informationssystem
für Parlamentsmaterialien) to download and index, then answer
natural-language questions about them via RAG, with citations to source
documents and pages. User-facing output is localized (German by default,
English available via the `language` setting; see i18n below). It has two
equivalent interfaces sharing the same data directory: a
CLI (`src/bundesrag/cli.py`) and a web UI (FastAPI backend in
`src/bundesrag/web/`, Vue 3 + Vite SPA in `frontend/`).

## Commands

```sh
uv sync                  # install/sync dependencies
uv run pre-commit install  # one-time: enable lint/format checks on commit
uv run pytest            # run the test suite
uv run pytest tests/test_dip_client.py::test_name  # run a single test
uv run ruff check .      # lint
uv run ruff format .     # format
uv run bundesrag download "Plenarprotokolle der 21. Wahlperiode."  # download docs
uv run bundesrag index  # index downloaded-but-not-yet-indexed docs
uv run bundesrag ask "Welche Gesetzesvorhaben gibt es bzgl. künstlicher Intelligenz?"  # query
uv run bundesrag status  # show downloaded/indexed counts and per-file status
uv run bundesrag clear  # delete all downloaded PDFs and reset the vector store
uv run bundesrag serve  # start the web UI at http://127.0.0.1:8000/
cd frontend && npm install && npm run dev  # frontend dev server (proxies /api to :8000)
cd frontend && npm run build  # build the SPA that `serve` hosts (frontend/dist)
```

Requires `MISTRAL_API_KEY` and `DIP_API_KEY` in `.env` (copy from
`.env.example`). Tests use the `settings` fixture in `tests/conftest.py`,
which builds `Settings` with fake keys and `_env_file=None`, so no real `.env`
or network access is needed for unit tests.

After editing `.py` files, run `uv run ruff check . --fix && uv run ruff format .`
before considering the change done — don't rely on pre-commit to be the first
check. Lint config lives in `ruff.toml`.

## Architecture

Five pipelines share the same Chroma vector store (`src/bundesrag/vectorstore.py`),
all driven from `src/bundesrag/cli.py` (Typer app with `download`, `index`,
`ask`, `status`, `clear`, and `serve` commands; help text is English
docstrings, runtime output is localized via i18n).

**`download` pipeline** (`ingestion/pipeline.py: run_download`):
1. `query_agent/agent.py: QueryAgent` — a Mistral LLM with structured output
   (`with_structured_output(QueryAgentResult)`) turns the NL prompt into
   `DipQueryFilters` (`query_agent/schema.py`). If the LLM can't produce valid
   filters, it returns a `ClarificationRequest` instead; `QueryAgent.build_query`
   loops asking the user (via an injected `ask_user` callable) up to
   `MAX_CLARIFICATION_ROUNDS` times. Proposed filters are shown to the user
   for confirmation (injected `confirm_filters` callable); declining prompts
   for feedback that is fed back into the LLM conversation.
2. `dip/client.py: DipClient` calls the DIP API (`list_drucksachen` /
   `list_plenarprotokolle`), paginating via the API's cursor until it stops
   advancing. Note `urheber`/`ressort_fdf` are repeated-value filters with AND
   semantics across distinct values in the DIP API — querying for either of
   two ministries/fractions needs two separate `download` calls. Both
   endpoints serve Bundestag and Bundesrat documents mixed unless the
   `zuordnung` filter (`BT`/`BR`/`BV`/`EK`) is set; the query-agent prompt
   instructs the LLM to set it whenever the request names a chamber
   ("Bundestagsplenarprotokolle" → `zuordnung="BT"`).
3. Documents whose PDF already exists locally are filtered out first (counted
   as `num_skipped` in the summary), so repeating a query neither re-downloads
   nor re-queues them for indexing. If any new documents remain, the user is
   asked (via an injected `confirm_count` callable receiving a
   `DownloadCounts` with matched / already-downloaded / to-download
   quantities, all three shown in the dialogue) how many of the new ones to
   download; entering nothing downloads all of them, entering `0` aborts
   (`DownloadAborted`), and entering a smaller number keeps only that many,
   most recent (`datum`) first. When every match already exists locally, the
   confirmation is skipped entirely.
4. The remaining documents are downloaded into
   `data/pdfs/<endpoint>/`; individual download failures are counted
   (`num_failed`) and skipped rather than aborting the run. Each downloaded
   PDF is recorded as a `PendingDocument` in the `data/pending_index.json`
   manifest (`ingestion/manifest.py`) for the `index` command to pick up
   later. Aborting mid-run (Ctrl+C, web cancel) leaves no bad state: PDFs are
   streamed to a `.part` temp file and renamed only once complete, and the
   manifest update runs in a `finally`, so already-downloaded documents are
   still queued for indexing instead of being skipped-but-never-indexed on
   later runs.

**`index` pipeline** (`ingestion/pipeline.py: run_index`):
1. Gets the pending entries and a `StatusSummary` from `_scan_documents`
   (the routine shared with `run_status`, see `status` below), which prunes
   pending entries whose PDF was deleted manually — so the indexing loop only
   sees files that exist instead of failing on the first missing one. An
   optional `on_counts` callback receives an `IndexCounts` (documents to
   index vs. already indexed, the latter taken from the status summary)
   before the loop starts; the CLI prints it as a localized line (`index_counts`),
   the web index job stores it on the job (`counts` in the job response) so
   the SPA shows the same text while the job runs.
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
   (`format_context`); the chat LLM is instructed (German system prompt that
   names the configured answer language) to cite passages by number, to say
   explicitly when the context doesn't answer the question rather than guess,
   and to answer in `settings.language`.
3. A deduplicated sources list (citation label, page, document number,
   similarity score) is built from chunk metadata (`citation_for`) and
   returned alongside the answer text.

**`status` pipeline** (`ingestion/pipeline.py: run_status`): wraps
`_scan_documents`, which first prunes pending entries whose PDF no longer
exists on disk (deleted manually) from the `pending_index.json` manifest —
they can never be indexed, and a stale entry would otherwise make every
`index` run fail on the missing file — then lists every PDF under
`data/pdfs/` and reports each as indexed unless it still appears in the
manifest. On top of that, `run_status` (which, unlike `_scan_documents`,
takes the vectorstore as an argument) reads all chunk metadata from the
Chroma collection to add the total chunk count and the disk usage of
`data/pdfs/` and the Chroma directory, and attaches per-document metadata
(`DocumentInfo` on `FileStatus.info`: doc id, dokumentnummer, title, date,
source URL, chunk/page counts, matched to files by PDF path): for indexed
documents it's aggregated from the chunk metadata (the document-level
fields are identical across a document's chunks; pages/chunks are counted),
for not-yet-indexed ones it comes from the pending manifest — which stores
the full DIP record — with the page count read from the PDF itself
(`pdf_loader.pdf_page_count`, None if unparseable) and `num_chunks` None,
since chunks only exist after indexing. The CLI prints the high-level stats
(downloaded/indexed counts, chunk count, both disk usages) and the plain
per-file list; the web UI (`GET /api/status`) shows the same stats and a
per-file table that also includes each file's document kind
(`FileStatus.kind`, read back from its endpoint subdirectory under
`data/pdfs/` — file names alone can collide across endpoints, e.g.
Drucksache and BT-Plenarprotokoll 21/5 are both `21_5.pdf`) and the
per-document metadata. `run_index` starts with the same `_scan_documents`
call, using the pending entries it returns alongside the summary, so
pruning and counting live in one place.

**`clear` pipeline** (`ingestion/pipeline.py: run_delete_all`): removes every
PDF under `data/pdfs/`, calls `vectorstore.delete_collection()` to reset the
Chroma collection, and clears `data/pending_index.json`. The CLI asks for
confirmation (`--yes`/`-y` to skip it) since this is destructive and
irreversible.

**Single-file delete** (`ingestion/pipeline.py: run_delete_file`, web-only —
the CLI has no counterpart): the web status table has a per-file delete
button (`POST /api/files/delete` in `routes_sync.py`, body
`{pdf_path, confirmed}` with the `pdf_path` string from `GET /api/status`).
It deletes the document's chunks from the vector store first
(`vectorstore.delete(where={"pdf_path": …})`, unconditional so chunks left by
an index run that crashed between embedding and manifest update are covered
too), then the PDF from disk, then the pending-manifest entry. The requested
path must match a file the status scan reports — anything else raises
`FileNotFoundError` (mapped to a localized 404) — so the endpoint can't be
used to delete arbitrary files outside `data/pdfs/`.

**Dependency injection**: all pipelines take their LLM, vectorstore, and DIP
client as constructor/function arguments (not constructed internally), which
is how the test suite substitutes fakes/mocks without touching real APIs.
`create_query_agent` / `create_chat_llm` are the only places that construct
real `ChatMistralAI` instances, and import `langchain_mistralai` lazily inside
the function body.

**Config** (`config.py: Settings`): a `pydantic-settings` `BaseSettings`
loading from `.env`; holds API keys, model names, the output `language`, and
chunk/retrieval tuning knobs. `data_dir` defaults to `./data`, with
`pdf_dir`/`chroma_dir`/`log_file` derived properties.

**i18n** (`i18n.py`, `locales/`): all user-facing runtime strings go through
`t(key, **kwargs)`, which looks them up in `locales/de.py` / `locales/en.py`
(`AVAILABLE_LANGUAGES = ("de", "en")`, default `de`). The language is set
once per process from `settings.language` (`set_language`, called in
`cli._init` and `web.app.create_app`) — it's module-level state, not passed
per call. LLM system prompts (query agent, answer agent) are written in
German but embed the configured language's name (`locales.LANGUAGE_NAMES`)
so clarification questions and answers come back in that language. Yes/no
confirmations use `cli._confirm` with `i18n.yes_no_tokens()` instead of
`typer.confirm`, which only ever accepts English y/yes/n/no and would
silently reject a German "j". Typer help text is localized too (`*_help`
locale keys passed as `help=` to the decorators), but it's resolved when
`cli.py` is imported — before any command's `_init()` — so `cli.py` calls
`set_language(config.detect_language())` at module level;
`detect_language` reads only the `language` setting so that `--help` works
without API keys, falling back to the default for unsupported values.
The Vue SPA has its own vue-i18n catalogs (`frontend/src/locales/de.js`/`en.js`,
Composition API mode): `main.js` fetches the configured language from
`GET /api/config` before mounting (falling back to German if the API is
unreachable) and sets the vue-i18n locale plus `<html lang>`. Catalog keys
that duplicate backend strings (`download_done`, `index_done`, `delete_done`,
`ask_download_count`, …) deliberately reuse the Python locale key names so
drift between `locales/*.py` and `frontend/src/locales/*.js` is greppable —
when changing one of these strings, update both catalogs.

**Logging** (`logging_config.py`): the `bundesrag` package logger writes to
`data/bundesrag.log` (file only, INFO level, no propagation). `setup_logging`
is idempotent per log-file path and re-points the handler when the path
changes (e.g. per-test `tmp_path`). CLI commands log details/tracebacks
there and show the user only a generic localized error message
(`unexpected_error`) on failure. The web endpoints and job workers log the
same success stats and failure tracebacks as their CLI counterparts (with a
`web ` prefix), so the log reads the same regardless of which interface ran
the operation.

**Progress reporting** (`progress.py`): long multi-step CLI operations print
a localized step line (German: `[Schritt n/total] <name>`) before each step;
per-item loops (downloads, indexing) use `tqdm`. `run_download`/`run_index`
also accept an optional `on_progress(num_done, total)` callback (called with
`(0, total)` before the loop, then once per item, including failed ones);
the CLI leaves it unset, the web job routes use it to store progress on the
job so the SPA can render a `<progress>` bar while polling.
`run_download`/`run_index` similarly accept an optional `should_cancel()`
callback, checked between items (the current item always finishes first);
when it returns true the pipeline raises `OperationCancelled`. The CLI
leaves it unset — Ctrl+C fills that role there — while the web job routes
wire it to the job's cancel flag.

**Web layer** (`src/bundesrag/web/`): additive over the pipelines — the only
pipeline changes made for it are the optional `on_progress` and
`should_cancel` callbacks above. `app.py: create_app` (uvicorn
factory used by the `serve` CLI command) stores `Settings` and a `JobManager`
on `app.state` and mounts `frontend/dist` as static files (path overridable
via `BUNDESRAG_FRONTEND_DIST`; if missing, the API still runs). Fast
operations (`/api/ask`, `/api/clear`, `/api/status`, and `/api/config` —
which exposes `settings.language` for the SPA's i18n bootstrap — in
`routes_sync.py`) are plain sync endpoints; their `HTTPException` details
are localized via `t()` (as are the job-route 400/404/409 details), while
the job `error` field stays raw exception text. Long-running ones (`/api/download`, `/api/index` in
`routes_jobs.py`) run in a background thread via `jobs.py: JobManager` and
are polled by the frontend (`GET /api/download/{job_id}`). The CLI's
interactive prompts (`ask_user`/`confirm_filters`/`confirm_count`) are
bridged to HTTP without touching `QueryAgent`: the injected callables block
on a `threading.Event` in `JobManager.wait_for_answer`, which sets the job
to `waiting_input`; the frontend renders the matching form and POSTs to
`/api/download/{job_id}/respond`, unblocking the worker thread. Running or
waiting jobs can be aborted via `POST /api/download/{job_id}/cancel` /
`POST /api/index/{job_id}/cancel` (`JobManager.request_cancel`): the cancel
flag makes the pipeline's `should_cancel` check raise `OperationCancelled`
(a job blocked in `wait_for_answer` is woken and raises immediately), which
`JobManager._run` maps to the `cancelled` job status the SPA displays. This
design requires running the server as a single process (the job store is an
in-process dict). Web tests (`tests/test_web_*.py`) inject fakes via
`app.dependency_overrides` on the `dependencies.py` provider functions.
