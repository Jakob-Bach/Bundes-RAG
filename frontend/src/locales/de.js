// German UI messages. Keys shared with src/bundesrag/locales/de.py keep the
// same name there so drift between the two catalogs is easy to grep for.
export default {
  answer_submit: 'Antworten',
  ask_download_count:
    '{num_matched} Dokumente gefunden, davon {num_existing} bereits heruntergeladen. ' +
    'Wie viele der verbleibenden {num_to_download} sollen heruntergeladen werden ' +
    '(die neuesten zuerst, 0 zum Abbrechen)?',
  ask_placeholder: 'Welche Gesetzesvorhaben gibt es bzgl. künstlicher Intelligenz?',
  ask_question_label: 'Frage zu den indexierten Dokumenten',
  ask_submit: 'Frage stellen',
  ask_title: 'Fragen',
  cancel_requested: 'Abbruch angefordert …',
  cancel_submit: 'Abbrechen',
  clear_description:
    'Löscht alle heruntergeladenen PDFs, setzt die Vektordatenbank zurück und leert die ' +
    'Liste wartender Dokumente. Dieser Schritt kann nicht rückgängig gemacht werden.',
  clear_submit: 'Alles löschen',
  clear_title: 'Löschen',
  confirm_delete_all: 'Wirklich alle heruntergeladenen Dokumente und die Vektordatenbank löschen?',
  confirm_use_query: 'Abfrage so verwenden?',
  count_submit: 'Bestätigen',
  delete_done: 'Fertig: {num_files} Dateien gelöscht und Vektordatenbank zurückgesetzt.',
  download_done: 'Fertig: {num_documents} Dokumente heruntergeladen.',
  download_partial_failure:
    'Achtung: {num_failed} Dokument(e) konnten nicht heruntergeladen werden ' +
    'und wurden übersprungen.',
  download_prompt_label: 'Beschreibung der gewünschten Dokumente',
  download_prompt_placeholder: 'Plenarprotokolle der 21. Wahlperiode.',
  download_running: 'Verarbeitung läuft …',
  download_skipped_existing:
    'Hinweis: {num_skipped} Dokument(e) waren bereits heruntergeladen und wurden übersprungen.',
  download_submit: 'Herunterladen starten',
  download_title: 'Herunterladen',
  error_prefix: 'Fehler: {error}',
  index_description:
    'Zerlegt alle heruntergeladenen, noch nicht indexierten Dokumente in Textabschnitte und ' +
    'speichert sie in der Vektordatenbank. Das kann je nach Umfang einige Zeit dauern.',
  index_done: 'Fertig: {num_documents} Dokumente, {num_chunks} Textabschnitte gespeichert.',
  index_running: 'Indexierung läuft …',
  index_submit: 'Indexieren starten',
  index_title: 'Indexieren',
  nav_ask: 'Fragen',
  nav_clear: 'Löschen',
  nav_download: 'Herunterladen',
  nav_index: 'Indexieren',
  nav_status: 'Status',
  no: 'Nein',
  operation_cancelled: 'Vorgang abgebrochen.',
  progress_count: '{current} von {total}',
  sources_header: 'Quellen:',
  status_file_indexed: 'indexiert',
  status_file_not_indexed: 'nicht indexiert',
  status_loading: 'Lade Status …',
  status_no_documents: 'Keine Dokumente heruntergeladen.',
  status_num_downloaded: 'Heruntergeladen: {count}',
  status_num_indexed: 'Indexiert: {count}',
  status_th_file: 'Datei',
  status_th_status: 'Status',
  status_title: 'Status',
  yes: 'Ja',
}
