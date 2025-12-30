# wqbrain-open

A minimal, resumable batch tool that reads alphas (FASTEXPR formulas) from a `.txt` file, submits them to WorldQuant Brain for simulation/testing, and stores results in SQLite.

Scope (intentionally small):
- Input: a `.txt` file with **one FASTEXPR formula per line** (you can append more lines to add more alphas)
- Submits simulations (`POST /simulations`), polls until finished, fetches alpha details
- Stores results + errors + status in SQLite (supports resume)
- Supports concurrency, global rate limiting, resume, operator fallback, and automatic retries

## Setup

1) Create a virtual environment and install:

```powershell
cd path\to\wqbrain-open
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
