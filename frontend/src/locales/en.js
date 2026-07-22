// English UI messages. Keys shared with src/bundesrag/locales/en.py keep the
// same name and wording there so drift between the catalogs is easy to grep for.
export default {
  answer_submit: 'Answer',
  ask_download_count:
    '{num_matched} documents found, {num_existing} of them already downloaded. ' +
    'How many of the remaining {num_to_download} should be downloaded ' +
    '(most recent first, 0 to cancel)?',
  ask_placeholder: 'Which legislative projects exist regarding artificial intelligence?',
  ask_question_label: 'Question about the indexed documents',
  ask_submit: 'Ask question',
  ask_title: 'Ask',
  cancel_requested: 'Cancellation requested …',
  cancel_submit: 'Cancel',
  clear_description:
    'Deletes all downloaded PDFs, resets the vector store, and empties the list of pending ' +
    'documents. This step cannot be undone.',
  clear_submit: 'Delete everything',
  clear_title: 'Clear',
  confirm_delete_all: 'Really delete all downloaded documents and reset the vector store?',
  confirm_delete_file:
    'Really delete file “{file}” (including its entries in the vector store)?',
  confirm_use_query: 'Use this query?',
  count_submit: 'Confirm',
  delete_done: 'Done: {num_files} files deleted and vector store reset.',
  delete_file_label: 'Delete file',
  download_done: 'Done: {num_documents} documents downloaded.',
  download_partial_failure:
    'Warning: {num_failed} document(s) could not be downloaded and were skipped.',
  download_prompt_label: 'Description of the documents to fetch',
  download_prompt_placeholder: 'Plenary protocols of the 21st electoral term.',
  download_running: 'Processing …',
  download_skipped_existing:
    'Note: {num_skipped} document(s) were already downloaded and were skipped.',
  download_submit: 'Build query',
  download_title: 'Download',
  error_prefix: 'Error: {error}',
  index_counts: '{num_to_index} document(s) to index, {num_indexed} already indexed.',
  index_description:
    'Splits all downloaded, not yet indexed documents into chunks and stores them in the ' +
    'vector store. Depending on the volume, this can take a while.',
  index_done: 'Done: {num_documents} documents, {num_chunks} chunks stored.',
  index_running: 'Indexing …',
  index_submit: 'Start indexing',
  index_title: 'Index',
  kind_drucksache: 'Drucksache',
  kind_plenarprotokoll: 'Plenary protocol',
  nav_ask: 'Ask',
  nav_clear: 'Clear',
  nav_download: 'Download',
  nav_index: 'Index',
  nav_status: 'Status',
  no: 'No',
  operation_cancelled: 'Operation cancelled.',
  progress_count: '{current} of {total}',
  source_show_text: 'Show retrieved text',
  sources_header: 'Sources:',
  status_file_indexed: 'indexed',
  status_file_not_indexed: 'not indexed',
  status_chunk_mismatch:
    'Warning: the vector store contains {num_chunks} chunks, but the document ' +
    'metadata accounts for {num_expected} — e.g. due to an aborted indexing run ' +
    'or data modified outside the tool.',
  status_loading: 'Loading status …',
  status_no_documents: 'No documents downloaded.',
  status_num_chunks: 'Chunks in the vector store: {count}',
  status_num_downloaded: 'Downloaded: {count}',
  status_num_indexed: 'Indexed: {count}',
  status_pdf_size: 'Disk usage of PDFs: {size}',
  status_source_link: 'PDF',
  status_th_actions: 'Actions',
  status_th_chunks: 'Chunks',
  status_th_datum: 'Date',
  status_th_doc_id: 'DIP ID',
  status_th_dokumentnummer: 'Document number',
  status_th_file: 'File',
  status_th_kind: 'Type',
  status_th_pages: 'Pages',
  status_th_source: 'Source',
  status_th_status: 'Status',
  status_th_title: 'Title',
  status_title: 'Status',
  status_vectorstore_size: 'Disk usage of the vector store: {size}',
  yes: 'Yes',
}
