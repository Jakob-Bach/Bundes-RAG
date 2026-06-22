# Bundes-RAG

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
```

## Usage

### Download and index documents

```sh
uv run bundesrag fetch "Plenarprotokolle der 21. Wahlperiode."
```

The agent turns the prompt into a DIP API query, downloads the matching
PDFs into `data/pdfs/`, and stores their chunked, embedded text in a local
Chroma vector store under `data/chroma/`. If the prompt is too ambiguous to
turn into a valid query (e.g. no date or Wahlperiode given for a broad
request), it will ask a clarifying question on the terminal instead of
guessing. If a query matches an unusually large number of documents, it will
ask for confirmation before downloading all of them.

```sh
uv run bundesrag fetch "Drucksachen des Bundesministeriums für Forschung, Technologie und Raumfahrt seit dem 01.01.2026."
```

### Ask questions

```sh
uv run bundesrag ask "Welche Gesetzesvorhaben gibt es bzgl. künstlicher Intelligenz?"
```

The answer is generated only from the indexed documents, and is followed by
a "Quellen:" list naming the source document and page for each passage used.

## Data storage

- `data/pdfs/` — downloaded PDFs, organized by document type
- `data/chroma/` — the persisted vector store

Both are gitignored; re-running `fetch` does not duplicate already-indexed
chunks.

## Running with Docker

Build the image:

```sh
docker build -t bundesrag .
```

Run a command, passing your `.env` for the API keys and mounting `data/` so
downloaded PDFs and the vector store persist across runs:

```sh
docker run --rm -it --env-file .env -v ./data:/app/data bundesrag fetch "Plenarprotokolle der 21. Wahlperiode."
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
  two separate `fetch` runs.
- `fetch` only downloads `Drucksache` and `Plenarprotokoll` documents (not
  `Vorgang`, `Person`, or `Aktivität` records).
