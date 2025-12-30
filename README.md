# wqbrain-open

A minimal, resumable batch **simulate → store results to SQLite** tool for WorldQuant Brain.

Scope (intentionally small):
- Input: a `.txt` file with **one FASTEXPR formula per line**
- Runs `POST /simulations`, polls until finished, fetches alpha details
- Stores results + errors + status in SQLite
- Supports concurrency, global rate limiting, resume, operator fallback, and automatic retries

## Setup

1) Create a virtual environment and install:

```powershell
cd d:\MyProject\wqbrain-open
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e ".[dev]"
```

2) Create `credentials.json` (do **not** commit it):

See `credentials.example.json`.

## Quick start

```powershell
# Simulate the sample 10 formulas
wqbrain-open run --input .\inputs\arxiv_sample.txt --db .\data\results.sqlite --credentials .\credentials.json

# Resume later (skips SUCCESS/UNSUPPORTED by default)
wqbrain-open run --input .\inputs\arxiv_sample.txt --db .\data\results.sqlite --credentials .\credentials.json

# Force re-run everything
wqbrain-open run --input .\inputs\arxiv_sample.txt --db .\data\results.sqlite --credentials .\credentials.json --force
```

## Notes

- This tool assumes you only have FASTEXPR enabled.
- Use `--min-request-interval` to avoid throttling.
- The repository contains only a small sample input file; supply your own formula list for real runs.

## License

Apache-2.0. See [LICENSE](LICENSE).
