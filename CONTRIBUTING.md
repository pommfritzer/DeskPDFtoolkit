# Contributing

Use Python 3.11 or newer and install `.[dev]` in a virtual environment. Run `python -m pytest -q` before submitting a change.

Keep PDF operations in `engine.py` and presentation behavior in `app.py`. Name functions and values so their intent is apparent. Add comments only when an invariant, format peculiarity, or non-obvious decision needs explanation.

For processing changes, generate small PDF fixtures in tests and assert document content or structure. Avoid committing private documents. Test failures and destination preservation as well as successful output. For UI changes, inspect the actual rendered window at the supported minimum size and a typical desktop size.

Do not introduce analytics, remote document processing, automatic downloads, or hidden network dependencies. New optional integrations should be explicit about installation requirements and format fidelity.

Contributions are licensed under AGPL-3.0-or-later, matching the project.
