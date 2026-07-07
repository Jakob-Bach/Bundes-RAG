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
  confirm_use_query: 'Use this query?',
  count_submit: 'Confirm',
  delete_done: 'Done: {num_files} files deleted and vector store reset.',
  download_done: 'Done: {num_documents} documents downloaded.',
  download_partial_failure:
    'Warning: {num_failed} document(s) could not be downloaded and were skipped.',
  download_prompt_label: 'Description of the documents to fetch',
  download_prompt_placeholder: 'Plenary protocols of the 21st electoral term.',
  download_running: 'Processing …',
  download_skipped_existing:
    'Note: {num_skipped} document(s) were already downloaded and were skipped.',
  download_submit: 'Start download',
  download_title: 'Download',
  error_prefix: 'Error: {error}',
  index_description:
    'Splits all downloaded, not yet indexed documents into chunks and stores them in the ' +
    'vector store. Depending on the volume, this can take a while.',
  index_done: 'Done: {num_documents} documents, {num_chunks} chunks stored.',
  index_running: 'Indexing …',
  index_submit: 'Start indexing',
  index_title: 'Index',
  nav_ask: 'Ask',
  nav_clear: 'Clear',
  nav_download: 'Download',
  nav_index: 'Index',
  nav_status: 'Status',
  no: 'No',
  operation_cancelled: 'Operation cancelled.',
  progress_count: '{current} of {total}',
  sources_header: 'Sources:',
  status_file_indexed: 'indexed',
  status_file_not_indexed: 'not indexed',
  status_loading: 'Loading status …',
  status_no_documents: 'No documents downloaded.',
  status_num_downloaded: 'Downloaded: {count}',
  status_num_indexed: 'Indexed: {count}',
  status_th_file: 'File',
  status_th_status: 'Status',
  status_title: 'Status',
  yes: 'Yes',
}
