// German UI messages. Keys shared with src/bundesrag/locales/de.py keep the
// same name there so drift between the two catalogs is easy to grep for.
export default {
  answer_submit: 'Antworten',
  ask_download_count:
    '{num_matched} Dokumente gefunden, davon {num_existing} bereits heruntergeladen. ' +
    'Wie viele der verbleibenden {num_to_download} sollen heruntergeladen werden ' +
    '(die neuesten zuerst, 0 zum Abbrechen)?',
  ask_stats_info:
    'Antwort basierend auf {num_documents} indexierten Dokumenten mit {num_chunks} ' +
    'Textabschnitten, unter Auswahl der {top_k} passendsten Textabschnitte.',
  ask_stats_info_filtered:
    'Antwort basierend auf {num_filtered_documents} von {num_documents} indexierten ' +
    'Dokumenten mit {num_filtered_chunks} von {num_chunks} Textabschnitten (Filter aktiv), ' +
    'unter Auswahl der {top_k} passendsten Textabschnitte.',
  ask_stats_hint:
    '{num_documents} Dokumente mit {num_chunks} Textabschnitten indexiert. ' +
    'Ausgewählt werden die {top_k} passendsten Textabschnitte.',
  ask_stats_hint_filtered:
    'Filter aktiv: {num_filtered_documents} von {num_documents} Dokumenten und ' +
    '{num_filtered_chunks} von {num_chunks} Textabschnitten entsprechen dem Filter. ' +
    'Ausgewählt werden die {top_k} passendsten Textabschnitte.',
  ask_filter_datum_end: 'Datum bis',
  ask_filter_datum_start: 'Datum von',
  ask_filter_kind: 'Dokumentart',
  ask_filter_kind_all: 'Alle',
  ask_filter_wahlperiode: 'Wahlperiode',
  ask_filters_summary: 'Filter (optional)',
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
  confirm_delete_file:
    'Datei „{file}“ wirklich löschen (inklusive ihrer Einträge in der Vektordatenbank)?',
  confirm_use_query: 'Abfrage so verwenden?',
  count_submit: 'Bestätigen',
  delete_done: 'Fertig: {num_files} Dateien gelöscht und Vektordatenbank zurückgesetzt.',
  delete_file_label: 'Datei löschen',
  download_done: 'Fertig: {num_documents} Dokumente heruntergeladen.',
  download_partial_failure:
    'Achtung: {num_failed} Dokument(e) konnten nicht heruntergeladen werden ' +
    'und wurden übersprungen.',
  download_prompt_label: 'Beschreibung der gewünschten Dokumente',
  download_prompt_placeholder: 'Plenarprotokolle der 21. Wahlperiode.',
  download_running: 'Verarbeitung läuft …',
  download_skipped_existing:
    'Hinweis: {num_skipped} Dokument(e) waren bereits heruntergeladen und wurden übersprungen.',
  download_submit: 'Abfrage erstellen',
  download_title: 'Herunterladen',
  error_prefix: 'Fehler: {error}',
  index_counts: '{num_to_index} Dokument(e) zu indexieren, {num_indexed} bereits indexiert.',
  index_description:
    'Zerlegt alle heruntergeladenen, noch nicht indexierten Dokumente in Textabschnitte und ' +
    'speichert sie in der Vektordatenbank. Das kann je nach Umfang einige Zeit dauern.',
  index_done: 'Fertig: {num_documents} Dokumente, {num_chunks} Textabschnitte gespeichert.',
  index_running: 'Indexierung läuft …',
  index_submit: 'Indexieren starten',
  index_title: 'Indexieren',
  kind_drucksache: 'Drucksache',
  kind_plenarprotokoll: 'Plenarprotokoll',
  nav_ask: 'Fragen',
  nav_clear: 'Löschen',
  nav_download: 'Herunterladen',
  nav_index: 'Indexieren',
  nav_status: 'Status',
  no: 'Nein',
  operation_cancelled: 'Vorgang abgebrochen.',
  progress_count: '{current} von {total}',
  source_show_text: 'Textauszug anzeigen',
  sources_header: 'Quellen:',
  status_file_indexed: 'indexiert',
  status_file_not_indexed: 'nicht indexiert',
  status_chunk_mismatch:
    'Warnung: Die Vektordatenbank enthält {num_chunks} Textabschnitte, laut den ' +
    'Dokument-Metadaten erwartet werden {num_expected} — z. B. durch einen ' +
    'abgebrochenen Indexierungslauf oder außerhalb des Tools geänderte Daten.',
  status_loading: 'Lade Status …',
  status_no_documents: 'Keine Dokumente heruntergeladen.',
  status_num_chunks: 'Textabschnitte in der Vektordatenbank: {count}',
  status_num_downloaded: 'Heruntergeladen: {count}',
  status_num_indexed: 'Indexiert: {count}',
  status_pdf_size: 'Speicherplatz PDFs: {size}',
  status_source_link: 'PDF',
  status_th_actions: 'Aktionen',
  status_th_chunks: 'Textabschnitte',
  status_th_datum: 'Datum',
  status_th_doc_id: 'DIP-ID',
  status_th_dokumentnummer: 'Dokumentnummer',
  status_th_file: 'Datei',
  status_th_kind: 'Art',
  status_th_pages: 'Seiten',
  status_th_source: 'Quelle',
  status_th_status: 'Status',
  status_th_title: 'Titel',
  status_title: 'Status',
  status_vectorstore_size: 'Speicherplatz Vektordatenbank: {size}',
  usage_chat: 'Chat: {input_tokens} Eingabe- + {output_tokens} Ausgabe-Tokens ({num_calls} Aufruf(e))',
  usage_cost: 'Geschätzte Kosten: {cost} {currency}',
  usage_cost_suffix: ', ≈ {cost} {currency}',
  usage_embedding: 'Embeddings: {tokens} Tokens ({num_calls} Aufruf(e))',
  usage_header: 'Mistral-API-Nutzung:',
  usage_op_ask: 'Fragen',
  usage_op_download: 'Herunterladen',
  usage_op_index: 'Indexieren',
  usage_time: 'API-Zeit: {seconds} s',
  usage_totals_header: 'Mistral-API-Nutzung insgesamt:',
  usage_totals_line: '{operation}: {tokens} Tokens (Vorgänge: {num_operations}, API-Zeit: {seconds} s)',
  yes: 'Ja',
}
