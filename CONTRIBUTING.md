# Contributing

Contributions are welcome: bug fixes, more language examples, docs, and confirmed KRA response shapes.

```bash
cd server
pip install -r requirements-dev.txt
ruff check . && pytest
```

Ground rules:

- No real credentials, PINs, ID numbers or taxpayer names in code, tests, issues or screenshots.
  Use the probe script (`python -m scripts.probe_sandbox`), which prints shapes only.
- Tests must run offline (use `httpx.MockTransport` or mock mode).
- If you change a KRA response assumption, link to the portal documentation or paste the probe output.
- Keep logs free of full PINs and ID numbers.
