MESSAGES = {
    "answer_must_be_integer": "The answer must be an integer.",
    "app_help": "Download Bundestag documents and ask questions about them.",
    "ask_help": "Answers QUESTION based on the stored documents.",
    "ask_query_feedback": "What should be adjusted about the query?",
    "clear_help": "Deletes all downloaded documents and resets the vector store.",
    "ask_download_count": (
        "{num_matched} documents found, {num_existing} of them already downloaded. "
        "How many of the remaining {num_to_download} should be downloaded "
        "(most recent first, Enter for all, 0 to cancel)? "
    ),
    "clear_yes_option_help": "Delete without asking for confirmation.",
    "confirm_delete_all_yn": (
        "Really delete all downloaded documents and reset the vector store? [y/N] "
    ),
    "confirm_use_query_yn": "Use this query? [y/N] ",
    "confirmation_required": "Confirmation required.",
    "delete_done": "Done: {num_files} files deleted and vector store reset.",
    "document_reference": "Document/protocol {dokumentnummer}",
    "download_aborted": "Aborted: download of {count} documents cancelled.",
    "download_done": "Done: {num_documents} documents downloaded.",
    "download_help": (
        "Downloads documents matching PROMPT, without indexing them.\n"
        "\n"
        "PROMPT is a natural-language description of the documents to fetch. "
        "An LLM translates it into DIP API filters and asks for clarification "
        "if the prompt is too vague.\n"
        "\n"
        "Available endpoints:\n"
        "\n"
        "\b\n"
        "- drucksache: motions, bills, minor interpellations, etc.\n"
        "- plenarprotokoll: plenary session protocols.\n"
        "\n"
        "Available filters (all optional):\n"
        "\n"
        "\b\n"
        '- datum_start / datum_end: date range (e.g. "since 2026-01-01")\n'
        "- wahlperiode: electoral term number (e.g. 21)\n"
        '- dokumentnummer: exact document/protocol number (e.g. "19/1")\n'
        "- zuordnung: BT, BR, BV, or EK\n"
        '- drucksachetyp: document type, e.g. "Antrag", "Gesetzentwurf" (drucksache only)\n'
        '- urheber: originator/parliamentary group, e.g. "Fraktion der SPD" (drucksache only)\n'
        "- ressort_fdf: lead federal ministry (drucksache only)\n"
        "- titel: search terms in the title, OR-combined (drucksache only)\n"
        "\n"
        "Note: urheber and ressort_fdf use AND logic across multiple values. "
        "To find documents from either of two authors, run separate download "
        "commands."
    ),
    "download_partial_failure": (
        "Warning: {num_failed} document(s) could not be downloaded and were skipped."
    ),
    "download_skipped_existing": (
        "Note: {num_skipped} document(s) were already downloaded and were skipped."
    ),
    "filter_dokumentnummer": "  Document number: {value}",
    "filter_drucksachetyp": "  Document type: {value}",
    "filter_ressort": "  Department: {value}",
    "filter_titel": "  Title contains: {value}",
    "filter_urheber": "  Originator: {value}",
    "filter_wahlperiode": "  Electoral term: {value}",
    "filter_zeitraum": "  Date range: {start} to {end}",
    "filter_zuordnung": "  Assignment: {value}",
    "index_counts": "{num_to_index} document(s) to index, {num_indexed} already indexed.",
    "index_done": "Done: {num_documents} documents, {num_chunks} chunks stored.",
    "index_help": "Indexes previously downloaded but not yet indexed documents.",
    "job_not_cancellable": "The job is no longer running and cannot be cancelled.",
    "job_not_found": "Job not found.",
    "job_not_waiting": "The job is not waiting for input.",
    "operation_cancelled": "Operation cancelled.",
    "page_short": "p. {page}",
    "page_suffix": ", page {page}",
    "planned_query_header": "Planned DIP query (endpoint: {endpoint}):",
    "progress_step": "[Step {n}/{total}] {name}",
    "query_agent_failed": (
        "Could not build a valid DIP query from the request even after "
        "several clarification rounds."
    ),
    "serve_help": "Starts the local web interface (FastAPI + Vue SPA).",
    "serve_host_option_help": "Bind address of the web server.",
    "serve_port_option_help": "Port of the web server.",
    "serve_reload_option_help": "Auto-reload on source changes (development only).",
    "serve_started": "Web interface running at http://{host}:{port}/ (stop with Ctrl+C).",
    "similarity_suffix": " (similarity: {score})",
    "sources_header": "\nSources:",
    "status_file_indexed": "indexed",
    "status_file_not_indexed": "not indexed",
    "status_files_header": "Files:",
    "status_help": "Shows how many documents are downloaded and indexed.",
    "status_num_chunks": "Chunks in the vector store: {count}",
    "status_num_downloaded": "Downloaded: {count}",
    "status_num_indexed": "Indexed: {count}",
    "status_pdf_size": "Disk usage of PDFs: {size}",
    "status_vectorstore_size": "Disk usage of the vector store: {size}",
    "step_download_pdfs": "Downloading PDFs",
    "step_generate_answer": "Generating answer",
    "step_interpret_request": "Interpreting request",
    "step_search_documents": "Searching documents",
    "step_search_passages": "Searching passages",
    "unexpected_error": "An unexpected error occurred. See the log file for details.",
    "unknown_document": "Unknown document",
}
