# Bundes-RAG

## Overview

The Bundes-RAG application allows users to download German parliamentary documents and ask natural-language questions regarding them.

## Functionality

**General**

- Command-line application.
- For long-running multi-step tasks, indicate the step number + name and show a progress bar where possible.
- The repo's `README.md` should describe the software setup and how to use the application.

**Feature 1: Download parliamentary documents**

- Input: The user specifies in natural language (in German) which documents should be included in the query system. Examples:
  - "Plenarprotokolle der 21. Wahlperiode."
  - "Drucksachen des Bundesministeriums für Forschung, Technologie und Raumfahrt seit dem 01.01.2026."
- Processing:
  - Use an AI agent to turn the user prompt into a valid API call for the DIP (Dokumentations- und Informationssystems für Parlamentsmaterialien).
    The API call should retrieve a list of all documents matching the user prompt.
    The API documentation is here: https://dip.bundestag.de/%C3%BCber-dip/hilfe/api
    If you cannot create a valid API call, chat with the user for clarification.
  - Download all documents from that list (as PDFs).
  - Store these documents in a vector database.
- Output:
  - No direct output except progress; documents are stored.

**Feature 2: Answer user questions**

- Input: The user asks a question (in German) regarding the stored documents. Example:
  - "Welche Gesetzesvorhaben gibt es bzgl. künstlicher Intelligenz?"
  - "Wann wurde über den EU AI Act debattiert?"
- Processing:
  - Use an AI agent (RAG system) to answer the question based on the stored documents.
    Indicate which documents (and ideally, specific pages and text passages) were relevant for the answer.
- Output:
  - Answer to the user's question as natural text.

## Tech Stack

- Programming language: Python
- Environment management: uv
- Testing: pytest
- AI: Mistral via LangChain
- Progress monitoring: tqdm

## Coding and Engineering Guidelines

- Built the application step-by-step.
  Create small, cohesive commits that can be reviewed by humans.
  Ask for clarification where the specification is unclear.
- Write unit tests where appropriate.
- Document the application by using simple code comments above functions/classes and within functions where appropriate.
  Full docstrings are unnecessary.
