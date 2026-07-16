# Lessons Learned from Working with `Claude Code`

## Summary

- Overall, code generation worked really well in multiple scenarios: (big) new features (-> planning mode), changes, and bugfixing
- No manual coding necessary at all, only few clarifications requested by Claude (particularly for design decisions)
- Prompts need not be long, as long as they are clear (user's intent suffices, no details on how to implement needed)
- Claude typically finds where to implement changes (without user pointing to a specific file/function)
- Code worked as intended, only small/subtle bugs
- Code quality generally high, sometimes overengineering
- Inconsistencies are an issue, particularly for broad changes and changes over time
  - E.g., `Claude.md` and `README.md` losing sync with code (not all changes included), internationalization only partial first, logging different in CLI and GUI
  - Also a few other occasions of "laziness", i.e., multiple user requests needed till problem investigated more deeply (CI pipeline, tooling permission)
- Tooling permissions were quite bad (whitelisting did not work well), leading to more permission prompts than necessary

## Individual Observations

- From initial specification, Claude could generate first version of application with barely any intervention
  - Asked clarification for some design decisions (e.g., which framework to use)
  - I added one comment to implementation plan (regarding a parameter Claude overlooked in DPI API)
  - Code worked, no manual changes necessary
  - Code style is a bit weird in some places (like Python files containing < 10 LoC, but justifications given if asked)
- After initial generation, I switched the LLMs for embedding and agents, but that was related to API capabilities / rate limiting rather than non-working code
- Introducing `GitHub` CI pipeline took some iterations (with error detection and fixing by Claude)
  - Versions of included `GitHub Actions` were outdated in first and second attempt (after that, Claude actively checked latest release)
  - One version tag in third attempt did not exist
  - CI included an unnecessary Python installation step (as Python installed by `uv` anyway)
- When introducing download-query confirmation, first version of code was overengineered (unnecessarily checked a value for `None` and put it in a one-value dict)
- When introducing internationalization (initial version was German-only), ordinary console output was adapted, but there were several misses:
  - One ordinary output string overlooked for translation
  - LLM output ("download" clarification and "ask" answer) remained German (required adapting system prompts, but these were part of source code and could have been found)
  - Translation keys for CLI command help were introduced, but not used (instead, help generated from docstrings, which were switched to English on my request)
  - Answer options provided by `typer` for confirmations remained English (y/n) (required creating a custom confirmation routine)
- When introducing logging, first referred to logger by string instead of constant Claude defined itself
- When introducing "status" command, I first named it "info" and then immediately demanded renaming, which was only carried out partially first
- Initial data model for DIP meta-data was overengineered (unused class, unused fields, largely overlapping classes) for subsequent processing, though it was faithful to the DIP API's data model
- General (vague) refactoring requests seem to be processed rather conservatively; better propose concrete refactorings
  - E.g., unused fields in the data model were only found when data model explicitly mentioned
  - Merging of data types "Drucksache"/"Plenarportokoll" needed to be requested as well
- Bug in download: System prompt for translating user query into DIP API request mentioned "Bundestag" and "Bundesrat" only with their API parameter value ("BT", "BR"), so user requests for either chamber of parliament were not properly interpreted
- Bug in download/indexing: If one document appeared in multiple download queries, was only downloaded once, but queued for indexing multiple times
- Bug in indexing: If document deleted manually on disk, still listed as pending for indexing, which failed
  - Rather subtle bug and not related to expected user behavior (actually found by Claude in some other refactoring), so forgivable
- `CLAUDE.md` did get updated automatically for some new features, but not all
  - E.g., "status" command, logging, and CLI internationalization missed; for web internationalization, I needed to remind it as well
- `README.md` also missed some updates ("status" command, logging, internationalization, change to always confirm number of downloads)
- Generating web interface worked quite well (similar to CLI), with only a few design decisions to be clarified; a few bugs/misses:
  - GUI was German-only (while CLI already had internationalization)
  - Download and indexing GUI did not show progress (just a static text), only web server's console output did
  - Logging was incomplete compared to CLI (most but not all command invocations logged, completion/cancellation/failure not logged)
- When asked to check whether aborting download/index worked cleanly in CLI, could identify issues (partially downloaded files, files missed for indexing)
- Though you can attach specific files / file parts as context to a prompt, Claude usually is able to find the relevant locations itself
- Whitelisting tool permissions (`npm`, `pytest`, or `Ruff`) via `.claude/settings.json` was a nightmare
  - For quite some time, Claude still asked for permission even if exactly same command whitelisted
    - Multiple debug attempts failed (e.g., certain Claude versions had bugs regarding permissions; separate Claude installations in `VS Code` and for user)
    - In the end, was in issue with missing setting `"hasTrustDialogAccepted": true` in the user's `.claude.json`
    - In particular, repo's directory was listed multiple times in file (with different slashes and capitalization), depending on how opened
  - Claude often used compound commands (two commands separated by `;`) or slight variations not matching the whitelist
    - Reminded several times to avoid this, Claude itself wrote this to memory thrice (first and second memory apparently insufficient)
