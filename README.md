# AI Data Analyser

[![Tests](https://github.com/MiroslavKocian/AI-Data-Analyser/actions/workflows/test.yml/badge.svg)](https://github.com/MiroslavKocian/AI-Data-Analyser/actions/workflows/test.yml)

Upload messy Excel sales exports, let **Mistral** clean and structure the rows, store them in **SQLite**, export CSV, and ask questions in natural language that become **SQL** queries.

**Repository:** https://github.com/MiroslavKocian/AI-Data-Analyser

**Live app (Streamlit Cloud):** https://ai-sales-analyser.streamlit.app/

The hosted app reads `MISTRAL_API_KEY` from the Streamlit Cloud **Settings → Secrets**
dashboard (not from this git repo). For local runs, use `.env` or
`.streamlit/secrets.toml` below.

## Tech stack

| Layer | Technology |
|--------|------------|
| UI | Streamlit |
| AI / LLM | Mistral AI (`mistral-small-latest`) |
| Data | Pandas |
| Database | SQLite |
| Testing | Pytest |
| API Client | OpenAI-compatible SDK |
| Quality | Ruff, GitHub Actions, Docker |

## Requirements

- Python 3.11 — https://www.python.org/downloads/
- Git
- A free **Mistral API key** — https://console.mistral.ai
- Docker Desktop — only for the Docker section — https://www.docker.com/products/docker-desktop/

## API key (two supported options)

Use **either** local `.env` **or** Streamlit secrets (for example Streamlit Community Cloud).

**Option A — `.env` in the project root**

```env
MISTRAL_API_KEY="your_mistral_api_key_here"
```

**Option B — `.streamlit/secrets.toml`**

Create the folder `.streamlit` in the project root and add:

```toml
MISTRAL_API_KEY = "your_mistral_api_key_here"
```

Never commit real keys. Both paths are listed in `.gitignore`.

## Run locally

### 1. Download the project

```sh
git clone https://github.com/MiroslavKocian/AI-Data-Analyser.git
cd AI-Data-Analyser
```

Run the following steps inside this folder (the **project root**).

### 2. Install dependencies

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Add your API key

Follow [API key (two supported options)](#api-key-two-supported-options) above.

### 4. Start the app

Runs tests first; Streamlit starts only if tests pass:

```sh
python run_app.py
```

Or start Streamlit directly:

```sh
streamlit run main.py
```

Open http://127.0.0.1:8501 (Streamlit default port).

### 5. Demo flow

1. Click **Load sample data**, or upload your own `.xlsx` file.
2. Review the raw table, then click **Run AI process** in the sidebar.
3. Download CSV or ask a question in **AI SQL analyst**.

Sample file on disk (for manual upload tests):

`examples/messy_sales_example.xlsx`

## Docker

Create a `.env` file with `MISTRAL_API_KEY` in the project root, then:

```sh
docker compose up --build
```

Open http://127.0.0.1:8501 in your browser.

Stop with **Ctrl+C**, then:

```sh
docker compose down
```

## Tests and lint

```sh
pytest
ruff check .
ruff format --check .
```

GitHub Actions runs the same steps on every push.

## Project layout

```text
AI-Data-Analyser/
├── main.py              Streamlit entry (streamlit run main.py)
├── app.py               Page flow
├── startup.py           API key resolution
├── config.py            Constants
├── ai_provider.py       Mistral calls
├── repository.py        SQLite writes
├── data_transformer.py  Date helpers and display scrubbing
├── sql_runner.py        Execute generated SELECT queries
├── pipeline_manager.py  Cleaning pipeline
├── state_manager.py     Session state
├── ui_renderer.py       Streamlit widgets
├── sample_loader.py     Built-in Excel sample
├── run_app.py           pytest then Streamlit
├── examples/
│   └── messy_sales_example.xlsx
├── tests/
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── pyproject.toml
└── AGENTS.md
```

Runtime file (not in git): `sales_intelligence.db` in the project root.

## Security note

The **AI SQL analyst** runs model-generated SQL against your local SQLite file. This is a **portfolio demo**, not a hardened production service. In production you would restrict queries to read-only `SELECT` statements and validate SQL before execution.

## License

Portfolio and interview use; no `LICENSE` file unless one is added later.
