MESSAGES = {
    "app_help": "Download Bundestag documents and ask questions about them.",
    "ask_help": "Answers QUESTION based on the stored documents.",
    "ask_query_feedback": "What should be adjusted about the query?",
    "clear_help": "Deletes all downloaded documents and resets the vector store.",
    "ask_download_count": (
        "{count} documents found. How many should be downloaded "
        "(most recent first, Enter for all, 0 to cancel)? "
    ),
    "clear_yes_option_help": "Delete without asking for confirmation.",
    "confirm_delete_all_yn": (
        "Really delete all downloaded documents and reset the vector store? [y/N] "
    ),
    "confirm_use_query_yn": "Use this query? [y/N] ",
    "delete_done": "Done: {num_files} files deleted and vector store reset.",
    "document_reference": "Document/protocol {dokumentnummer}",
    "download_aborted": "Aborted: download of {count} documents cancelled.",
    "download_done": "Done: {num_documents} documents downloaded.",
    "download_help": "Downloads documents matching PROMPT, without indexing them.",
    "download_partial_failure": (
        "Warning: {num_failed} document(s) could not be downloaded and were skipped."
    ),
    "filter_dokumentnummer": "  Document number: {value}",
    "filter_drucksachetyp": "  Document type: {value}",
    "filter_ressort": "  Department: {value}",
    "filter_titel": "  Title contains: {value}",
    "filter_urheber": "  Originator: {value}",
    "filter_wahlperiode": "  Electoral term: {value}",
    "filter_zeitraum": "  Date range: {start} to {end}",
    "filter_zuordnung": "  Assignment: {value}",
    "index_done": "Done: {num_documents} documents, {num_chunks} chunks stored.",
    "index_help": "Indexes previously downloaded but not yet indexed documents.",
    "page_short": "p. {page}",
    "page_suffix": ", page {page}",
    "planned_query_header": "Planned DIP query (endpoint: {endpoint}):",
    "progress_step": "[Step {n}/{total}] {name}",
    "query_agent_failed": (
        "Could not build a valid DIP query from the request even after "
        "several clarification rounds."
    ),
    "serve_help": "Starts the local web interface (FastAPI + Vue SPA).",
    "serve_started": "Web interface running at http://{host}:{port}/ (stop with Ctrl+C).",
    "similarity_suffix": " (similarity: {score})",
    "sources_header": "\nSources:",
    "status_file_indexed": "indexed",
    "status_file_not_indexed": "not indexed",
    "status_files_header": "Files:",
    "status_help": "Shows how many documents are downloaded and indexed.",
    "status_num_downloaded": "Downloaded: {count}",
    "status_num_indexed": "Indexed: {count}",
    "step_download_pdfs": "Downloading PDFs",
    "step_generate_answer": "Generating answer",
    "step_interpret_request": "Interpreting request",
    "step_search_documents": "Searching documents",
    "step_search_passages": "Searching passages",
    "unexpected_error": "An unexpected error occurred. See the log file for details.",
    "unknown_document": "Unknown document",
}
