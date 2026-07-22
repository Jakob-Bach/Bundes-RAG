MESSAGES = {
    "answer_must_be_integer": "Die Antwort muss eine ganze Zahl sein.",
    "app_help": "Lade Bundestagsdokumente herunter und stelle Fragen dazu.",
    "ask_help": "Beantwortet QUESTION auf Basis der gespeicherten Dokumente.",
    "ask_query_feedback": "Was soll an der Abfrage angepasst werden?",
    "clear_help": "Löscht alle heruntergeladenen Dokumente und setzt die Vektordatenbank zurück.",
    "clear_yes_option_help": "Ohne Rückfrage löschen.",
    "ask_download_count": (
        "{num_matched} Dokumente gefunden, davon {num_existing} bereits heruntergeladen. "
        "Wie viele der verbleibenden {num_to_download} sollen heruntergeladen werden "
        "(die neuesten zuerst, Enter für alle, 0 zum Abbrechen)? "
    ),
    "confirm_delete_all_yn": (
        "Wirklich alle heruntergeladenen Dokumente und die Vektordatenbank löschen? [j/N] "
    ),
    "confirm_use_query_yn": "Abfrage so verwenden? [j/N] ",
    "confirmation_required": "Bestätigung erforderlich.",
    "delete_done": "Fertig: {num_files} Dateien gelöscht und Vektordatenbank zurückgesetzt.",
    "document_reference": "Drucksache/Protokoll {dokumentnummer}",
    "download_aborted": "Abgebrochen: Download von {count} Dokumenten abgebrochen.",
    "download_done": "Fertig: {num_documents} Dokumente heruntergeladen.",
    "download_help": (
        "Lädt Dokumente passend zu PROMPT herunter, ohne sie zu indexieren.\n"
        "\n"
        "PROMPT ist eine natürlichsprachliche Beschreibung der gesuchten Dokumente. "
        "Ein LLM übersetzt sie in DIP-API-Filter und stellt eine Rückfrage, wenn "
        "die Anfrage zu vage ist.\n"
        "\n"
        "Verfügbare Endpunkte:\n"
        "\n"
        "\b\n"
        "- drucksache: Anträge, Gesetzentwürfe, Kleine Anfragen usw.\n"
        "- plenarprotokoll: Plenarsitzungsprotokolle.\n"
        "\n"
        "Verfügbare Filter (alle optional):\n"
        "\n"
        "\b\n"
        '- datum_start / datum_end: Datumsbereich (z. B. "seit 01.01.2026")\n'
        "- wahlperiode: Wahlperiodennummer (z. B. 21)\n"
        '- dokumentnummer: exakte Drucksachen-/Protokollnummer (z. B. "19/1")\n'
        "- zuordnung: Herkunft — BT (Bundestag), BR (Bundesrat), BV\n"
        "  (Bundesversammlung), EK (Enquete-Kommission); ohne diesen Filter\n"
        "  liefert plenarprotokoll BT- und BR-Protokolle gemischt\n"
        '- drucksachetyp: Dokumenttyp, z. B. "Antrag", "Gesetzentwurf" (nur drucksache)\n'
        '- urheber: Urheber/Fraktion, z. B. "Fraktion der SPD" (nur drucksache)\n'
        "- ressort_fdf: federführendes Bundesministerium (nur drucksache)\n"
        "- titel: Suchbegriffe im Titel, ODER-verknüpft (nur drucksache)\n"
        "\n"
        "Hinweis: urheber und ressort_fdf werden über mehrere Werte UND-verknüpft. "
        "Um Dokumente von einem von zwei Urhebern zu finden, sind zwei getrennte "
        "download-Aufrufe nötig."
    ),
    "download_partial_failure": (
        "Achtung: {num_failed} Dokument(e) konnten nicht heruntergeladen werden "
        "und wurden übersprungen."
    ),
    "download_skipped_existing": (
        "Hinweis: {num_skipped} Dokument(e) waren bereits heruntergeladen und wurden übersprungen."
    ),
    "file_not_found": "Datei nicht gefunden.",
    "filter_dokumentnummer": "  Dokumentnummer: {value}",
    "filter_drucksachetyp": "  Drucksachetyp: {value}",
    "filter_ressort": "  Ressort: {value}",
    "filter_titel": "  Titel enthält: {value}",
    "filter_urheber": "  Urheber: {value}",
    "filter_wahlperiode": "  Wahlperiode: {value}",
    "filter_zeitraum": "  Zeitraum: {start} bis {end}",
    "filter_zuordnung": "  Zuordnung: {value}",
    "index_counts": ("{num_to_index} Dokument(e) zu indexieren, {num_indexed} bereits indexiert."),
    "index_done": "Fertig: {num_documents} Dokumente, {num_chunks} Textabschnitte gespeichert.",
    "index_help": "Indexiert zuvor heruntergeladene, aber noch nicht indexierte Dokumente.",
    "job_not_cancellable": "Der Job läuft nicht mehr und kann nicht abgebrochen werden.",
    "job_not_found": "Job nicht gefunden.",
    "job_not_waiting": "Der Job wartet nicht auf eine Eingabe.",
    "operation_cancelled": "Vorgang abgebrochen.",
    "page_short": "S. {page}",
    "page_suffix": ", Seite {page}",
    "planned_query_header": "Geplante DIP-Abfrage (Endpunkt: {endpoint}):",
    "progress_step": "[Schritt {n}/{total}] {name}",
    "query_agent_failed": (
        "Konnte aus der Anfrage auch nach mehreren Rückfragen keine gültige DIP-Abfrage erstellen."
    ),
    "serve_help": "Startet die lokale Weboberfläche (FastAPI + Vue SPA).",
    "serve_host_option_help": "Adresse, an die der Webserver gebunden wird.",
    "serve_port_option_help": "Port des Webservers.",
    "serve_reload_option_help": (
        "Bei Quellcode-Änderungen automatisch neu laden (nur für die Entwicklung)."
    ),
    "serve_started": "Weboberfläche läuft auf http://{host}:{port}/ (Beenden mit Strg+C).",
    "similarity_suffix": " (Ähnlichkeit: {score})",
    "sources_header": "\nQuellen:",
    "status_file_indexed": "indexiert",
    "status_file_not_indexed": "nicht indexiert",
    "status_chunk_mismatch": (
        "Warnung: Die Vektordatenbank enthält {num_chunks} Textabschnitte, laut den "
        "Dokument-Metadaten erwartet werden {num_expected} — z. B. durch einen "
        "abgebrochenen Indexierungslauf oder außerhalb des Tools geänderte Daten."
    ),
    "status_files_header": "Dateien:",
    "status_help": "Zeigt an, wie viele Dokumente heruntergeladen und indexiert sind.",
    "status_num_chunks": "Textabschnitte in der Vektordatenbank: {count}",
    "status_num_downloaded": "Heruntergeladen: {count}",
    "status_num_indexed": "Indexiert: {count}",
    "status_pdf_size": "Speicherplatz PDFs: {size}",
    "status_vectorstore_size": "Speicherplatz Vektordatenbank: {size}",
    "step_download_pdfs": "PDFs herunterladen",
    "step_generate_answer": "Antwort erzeugen",
    "step_interpret_request": "Anfrage interpretieren",
    "step_search_documents": "Dokumente suchen",
    "step_search_passages": "Passagen suchen",
    "unexpected_error": "Ein unerwarteter Fehler ist aufgetreten. Details siehe Logdatei.",
    "unknown_document": "Unbekanntes Dokument",
    "usage_chat": (
        "  Chat: {input_tokens} Eingabe- + {output_tokens} Ausgabe-Tokens ({num_calls} Aufruf(e))"
    ),
    "usage_cost": "  Geschätzte Kosten: {cost} {currency}",
    "usage_cost_suffix": ", ≈ {cost} {currency}",
    "usage_embedding": "  Embeddings: {tokens} Tokens ({num_calls} Aufruf(e))",
    "usage_header": "Mistral-API-Nutzung:",
    "usage_op_ask": "Fragen",
    "usage_op_download": "Herunterladen",
    "usage_op_index": "Indexieren",
    "usage_time": "  API-Zeit: {seconds} s",
    "usage_totals_header": "Mistral-API-Nutzung insgesamt:",
    "usage_totals_line": (
        "  {operation}: {tokens} Tokens (Vorgänge: {num_operations}, API-Zeit: {seconds} s)"
    ),
}
