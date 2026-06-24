# Bundes-RAG

[![CI](https://github.com/Jakob-Bach/Bundes-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/Jakob-Bach/Bundes-RAG/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/Jakob-Bach/Bundes-RAG/graph/badge.svg)](https://codecov.io/gh/Jakob-Bach/Bundes-RAG)
[![License](https://img.shields.io/github/license/Jakob-Bach/Bundes-RAG)](LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/Jakob-Bach/Bundes-RAG)](https://github.com/Jakob-Bach/Bundes-RAG/commits/main)

An agentically engineered search tool for German parliamentary documentation.

Bundes-RAG lets you describe, in German, which documents from the Bundestag's
[DIP](https://dip.bundestag.de/) (Dokumentations- und Informationssystem für
Parlamentsmaterialien) should be downloaded and indexed, and then lets you ask
natural-language questions about them, with answers citing the source
documents and pages.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency/environment management
- API keys for:
  - [Mistral](https://console.mistral.ai/) (`MISTRAL_API_KEY`) — powers the query-building and answering agents, and document/question embeddings (has a free tier)
  - the [DIP API](https://dip.bundestag.de/über-dip/hilfe/api) (`DIP_API_KEY`) — request one via parlamentsdokumentation@bundestag.de

## Setup

```sh
uv sync
cp .env.example .env
# then fill in MISTRAL_API_KEY, DIP_API_KEY in .env
uv run pre-commit install  # lint/format checks on every commit
```

## Usage

### Download documents

```sh
uv run bundesrag download "Plenarprotokolle der 21. Wahlperiode."
```

The agent turns the prompt into a DIP API query and downloads the matching
PDFs into `data/pdfs/`. If the prompt is too ambiguous to turn into a valid
query (e.g. no date or Wahlperiode given for a broad request), it will ask a
clarifying question on the terminal instead of guessing. If a query matches
an unusually large number of documents, it will ask for confirmation before
downloading all of them.

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

### Clear all data

```sh
uv run bundesrag clear
```

Deletes every downloaded PDF, resets the Chroma vector store, and clears the
pending-index manifest. Asks for confirmation unless `--yes`/`-y` is passed.
This is destructive and irreversible.

## Data storage

- `data/pdfs/` — downloaded PDFs, organized by document type
- `data/pending_index.json` — manifest of downloaded PDFs awaiting indexing
- `data/chroma/` — the persisted vector store

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
```

The container's entrypoint is the `bundesrag` CLI, so any arguments after the
image name are passed straight to it (run without arguments to see `--help`).

## Running tests

```sh
uv run pytest
```

## Known limitations

- The DIP API's `urheber`/`ressort_fdf` filters use AND semantics when given
  multiple values in one call (an intersection, not an OR). Querying for
  documents matching either of two distinct ministries/fractions requires
  two separate `download` runs.
- `download` only fetches `Drucksache` and `Plenarprotokoll` documents (not
  `Vorgang`, `Person`, or `Aktivität` records).
