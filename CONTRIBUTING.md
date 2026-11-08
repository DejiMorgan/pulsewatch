# Contributing

PulseWatch is maintained by Arabome Obadiah Ayodeji.

For a change, open an issue describing the problem, current behavior, expected result and a reproducible example. Keep pull requests focused; add tests for changes to worker scheduling, alert delivery, incident transitions and URL handling.

Backend verification:

```bash
cd backend
DATABASE_URL=sqlite+pysqlite:// python -m pytest -q
```

Frontend verification:

```bash
cd frontend
npm install
npm run build
```

Do not commit credentials, monitoring targets that identify real customers, or screenshots containing bearer tokens. A change to `httpx`, `httpcore` or `safe_http.py` must include a network-safety regression test and explicit review of address pinning.
