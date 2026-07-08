# Bundes-RAG

[![CI](https://github.com/Jakob-Bach/Bundes-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/Jakob-Bach/Bundes-RAG/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/Jakob-Bach/Bundes-RAG/graph/badge.svg)](https://codecov.io/gh/Jakob-Bach/Bundes-RAG)
[![License](https://img.shields.io/github/license/Jakob-Bach/Bundes-RAG)](LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/Jakob-Bach/Bundes-RAG)](https://github.com/Jakob-Bach/Bundes-RAG/commits/main)

An agentically engineered search tool for German parliamentary documentation.

Bundes-RAG lets you describe, in natural language, which documents from the
Bundestag's [DIP](https://dip.bundestag.de/) (Dokumentations- und
Informationssystem für Parlamentsmaterialien) should be downloaded and
indexed, and then lets you ask natural-language questions about them, with
answers citing the source documents and pages. All user-facing output is in
German by default; English is available via the `LANGUAGE` setting (see
[Configuration](#configuration)).

## Requirements

- API keys for:
  - [Mistral](https://console.mistral.ai/) (`MISTRAL_API_KEY`) — powers the query-building and answering agents, and document/question embeddings (has a free tier)
  - the [DIP API](https://dip.bundestag.de/über-dip/hilfe/api) (`DIP_API_KEY`) — request one via parlamentsdokumentation@bundestag.de
- Python 3.12+ and [uv](https://docs.astral.sh/uv/) for
  dependency/environment management
- [Node.js](https://nodejs.org/) — only for the web interface (it builds the
  frontend that `bundesrag serve` hosts), not for the CLI commands

Alternatively, run everything via [Docker](#running-with-docker) — then only
Docker and the API keys are needed on the host, since the image contains
Python, the dependencies, and the pre-built frontend.

## Setup

```sh
uv sync
cp .env.example .env
# then fill in MISTRAL_API_KEY, DIP_API_KEY in .env
uv run pre-commit install  # lint/format checks on every commit
```

To use the web interface (`bundesrag serve`), additionally build the frontend
once (skip this if you only use the CLI):

```sh
cd frontend
npm install
npm run build  # writes frontend/dist, which `bundesrag serve` hosts
```

## Usage

### Download documents

```sh
uv run bundesrag download "Plenarprotokolle der 21. Wahlperiode."
```

The agent turns the prompt into a DIP API query and downloads the matching
PDFs into `data/pdfs/`. If the prompt is too ambiguous to turn into a valid
query (e.g. no date or Wahlperiode given for a broad request), it will ask a
clarifying question on the terminal instead of guessing. The proposed query
filters are shown for confirmation before searching; declining lets you give
feedback that is used to refine the query. Once documents are found, you are
told how many matched, how many of those already exist locally, and how many
are new, and asked how many of the new ones to download: pressing Enter
downloads all of them, a smaller number keeps only that many most recent
documents, and `0` aborts. Documents whose PDF already exists locally are
skipped (if every match already exists, the question is skipped too), so
repeating a query neither re-downloads nor re-indexes them.

```sh
uv run bundesrag download "Drucksachen des Bundesministeriums für Forschung, Technologie und Raumfahrt seit dem 01.01.2026."
```

Downloaded documents are recorded as pending in `data/pending_index.json`
until they're indexed.

### Index downloaded documents

```sh
uv run bundesrag index
```

Chunks and embeds the text of any downloaded-but-not-yet-indexed PDFs into a
local Chroma vector store under `data/chroma/`. This is a separate step from
`download` because indexing can take considerably longer and may fail
partway through (e.g. an API rate limit); each document is removed from the
pending list right after it's indexed, so re-running `index` after a failure
or interruption only processes what's left.

### Ask questions

```sh
uv run bundesrag ask "Welche Gesetzesvorhaben gibt es bzgl. künstlicher Intelligenz?"
```

The answer is generated only from the indexed documents, and is followed by
a "Quellen:" list naming the source document and page for each passage used.

### Check download/index status

```sh
uv run bundesrag status
```

Prints how many documents have been downloaded and how many of those are
indexed, plus a per-file list showing which PDFs are still awaiting indexing.
Pending entries whose PDF was deleted manually are dropped from the manifest
(both `status` and `index` do this), so a missing file doesn't block indexing.

### Clear all data

```sh
uv run bundesrag clear
```

Deletes every downloaded PDF, resets the Chroma vector store, and clears the
pending-index manifest. Asks for confirmation unless `--yes`/`-y` is passed.
This is destructive and irreversible.

### Web interface

```sh
uv run bundesrag serve
```

Starts a local web UI at http://127.0.0.1:8000/ covering the same
download/index/ask/status/clear operations as the CLI commands above, using
the same `data/` directory and Chroma store — the CLI and web interface can
be used interchangeably against the same data. Use `--host`/`--port` to
change the bind address, and `--reload` during development.

The clarifying questions and filter/count confirmations during download work
the same way as the CLI's interactive prompts, just rendered as web forms.
The page is served from the pre-built frontend in `frontend/dist` — building
it is part of [Setup](#setup). The server must run as a single process (the
state of running download/index jobs is held in memory), so don't run it with
multiple uvicorn workers.

## Configuration

All settings are read from `.env` (or environment variables). Besides the two
required API keys, these optional settings are available (shown with their
defaults):

- `LANGUAGE=de` — language of all user-facing output (CLI, web UI, and
  answers); `de` or `en`
- `DATA_DIR=data` — where PDFs, the vector store, the pending-index manifest,
  and the log file are stored
- `CHAT_MODEL=mistral-large-latest` / `EMBEDDING_MODEL=mistral-embed` — the
  Mistral models used for the agents and for embeddings
- `RETRIEVAL_TOP_K=5` — number of text chunks retrieved per question
- `CHUNK_SIZE=1000` / `CHUNK_OVERLAP=150` — text-splitting parameters used
  during indexing

## Data storage

- `data/pdfs/` — downloaded PDFs, organized by document type
- `data/pending_index.json` — manifest of downloaded PDFs awaiting indexing
- `data/chroma/` — the persisted vector store
- `data/bundesrag.log` — log file; errors are detailed here (with tracebacks),
  while the CLI/web UI only shows a generic error message

All are gitignored; re-running `index` does not duplicate already-indexed
chunks.

## Running with Docker

Build the image:

```sh
docker build -t bundesrag .
```

Run a command, passing your `.env` for the API keys and mounting `data/` so
downloaded PDFs and the vector store persist across runs:

```sh
docker run --rm -it --env-file .env -v ./data:/app/data bundesrag download "Plenarprotokolle der 21. Wahlperiode."
docker run --rm -it --env-file .env -v ./data:/app/data bundesrag index
docker run --rm -it --env-file .env -v ./data:/app/data bundesrag ask "Welche Gesetzesvorhaben gibt es bzgl. künstlicher Intelligenz?"
docker run --rm -it --env-file .env -v ./data:/app/data -p 8000:8000 bundesrag serve --host 0.0.0.0
```

The image builds the web frontend in a separate stage, so running `serve`
works out of the box without Node.js on the host.

The container's entrypoint is the `bundesrag` CLI, so any arguments after the
image name are passed straight to it (run without arguments to see `--help`).

## Running tests

```sh
uv run pytest
```

## Technology overview

### Backend (Python 3.12+, `src/bundesrag/`)

- [LangChain](https://python.langchain.com/) with
  [langchain-mistralai](https://python.langchain.com/docs/integrations/providers/mistralai/) —
  LLM orchestration: the query-building agent (structured output), the
  answering agent, and document/question embeddings, all backed by
  [Mistral](https://mistral.ai/) models (`mistral-large-latest` and
  `mistral-embed` by default)
- [Chroma](https://www.trychroma.com/) (via `langchain-chroma`) — local,
  persisted vector store for the document chunks
- [langchain-text-splitters](https://pypi.org/project/langchain-text-splitters/) —
  recursive character-based chunking of PDF text before embedding
- [pypdf](https://pypdf.readthedocs.io/) — page-wise text extraction from the
  downloaded PDFs (page numbers feed the answer citations)
- [httpx](https://www.python-httpx.org/) — HTTP client for the DIP API and
  for streaming PDF downloads
- [Typer](https://typer.tiangolo.com/) — the `bundesrag` CLI, with
  [tqdm](https://tqdm.github.io/) progress bars for downloads/indexing
- [FastAPI](https://fastapi.tiangolo.com/) +
  [uvicorn](https://www.uvicorn.org/) — the web backend serving the JSON API
  and the built frontend
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
  (+ python-dotenv) — typed configuration loaded from `.env` (see
  [Configuration](#configuration))

### Frontend (`frontend/`)

- [Vue 3](https://vuejs.org/) (Composition API) with
  [vue-router](https://router.vuejs.org/) and
  [vue-i18n](https://vue-i18n.intlify.dev/) — the single-page web UI and its
  German/English localization
- [Vite](https://vite.dev/) — build tool and hot-reloading dev server
- [Pico.css](https://picocss.com/) — lightweight, mostly class-less styling

### Development tooling

- [uv](https://docs.astral.sh/uv/) — Python dependency and environment
  management
- [pytest](https://docs.pytest.org/) (with pytest-cov and pytest-mock) — test
  suite; coverage is reported to Codecov
- [Ruff](https://docs.astral.sh/ruff/) — linting and formatting, enforced via
  [pre-commit](https://pre-commit.com/) hooks and CI (GitHub Actions)
- [Docker](https://www.docker.com/) — multi-stage image that builds the
  frontend and packages the CLI/server (see
  [Running with Docker](#running-with-docker))

## Frontend development

The web UI source lives in `frontend/` (Vue 3 + Vite, styled with Pico.css).
To work on it with hot-reload against a locally running backend:

```sh
uv run bundesrag serve   # backend on :8000
cd frontend
npm run dev              # frontend dev server on :5173, proxies /api to :8000
```

When done, rerun `npm run build` (see [Setup](#setup)) to refresh the static
build that `bundesrag serve` hosts.

## Known limitations

- The DIP API's `urheber`/`ressort_fdf` filters use AND semantics when given
  multiple values in one call (an intersection, not an OR). Querying for
  documents matching either of two distinct ministries/fractions requires
  two separate `download` runs.
- `download` only fetches `Drucksache` and `Plenarprotokoll` documents (not
  `Vorgang`, `Person`, or `Aktivität` records).
