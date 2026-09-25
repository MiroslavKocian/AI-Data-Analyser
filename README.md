# AI Data Analyser

[![Tests](https://github.com/MiroslavKocian/AI-Data-Analyser/actions/workflows/test.yml/badge.svg)](https://github.com/MiroslavKocian/AI-Data-Analyser/actions/workflows/test.yml)

Upload messy Excel sales exports, let **Groq** clean and structure the rows, store
them in **SQLite**, export CSV, and ask questions in natural language that become
**SQL** queries.

**GitHub:** https://github.com/MiroslavKocian/AI-Data-Analyser

**Live demo:** https://ai-sales-analyser.streamlit.app/  
(Streamlit app name is `ai-sales-analyser`; the product title in the UI is
**AI Data Analyser**.)

---

## Tech stack

| Layer | Technology |
|--------|------------|
| UI | Streamlit |
| AI / LLM | Groq (`openai/gpt-oss-20b`) |
| Data | Pandas |
| Database | SQLite |
| Testing | Pytest |
| API Client | OpenAI-compatible SDK |
| Quality | Ruff, GitHub Actions, Docker |

---

## Quality checks (automatic)

You **do not** need a separate “run tests” step for normal use.

Whenever the app **starts** (`python run_app.py`, `python -m streamlit run main.py`,
Docker, or Streamlit Cloud after deploy/restart), `main.py` runs **once per server
process**:

`ruff check` → `ruff format --check` → `pytest` (100 % coverage)

If anything fails, the UI does not open. The [![Tests](https://github.com/MiroslavKocian/AI-Data-Analyser/actions/workflows/test.yml/badge.svg)](https://github.com/MiroslavKocian/AI-Data-Analyser/actions/workflows/test.yml)
workflow runs the same checks on every **git push**.

On Windows, prefer **`python -m streamlit`** (not bare `streamlit`) so the active
`.venv` is used.

---

## Requirements

- Python **3.11** — https://www.python.org/downloads/
- Git
- Free **Groq API key** — https://console.groq.com
- Docker Desktop — only for [Docker](#docker) — https://www.docker.com/products/docker-desktop/

---

## API key (two supported options)

Use **either** a root `.env` file **or** Streamlit secrets. `.env` wins if both
are set locally.

**Option A — `.env` in the project root**

```env
GROQ_API_KEY="your_groq_api_key_here"
```

**Option B — `.streamlit/secrets.toml`**

Create `.streamlit` in the project root:

```toml
GROQ_API_KEY = "your_groq_api_key_here"
```

**Streamlit Cloud:** open the app on [share.streamlit.io](https://share.streamlit.io)
→ **Settings** → **Secrets** and set `GROQ_API_KEY` (not committed to git). Save
and **Reboot** the app after changes.

Never commit real keys. `.env` and `secrets.toml` are in `.gitignore`.

---

## Run locally

All commands below assume your shell is in the **project root**
(`AI-Data-Analyser/`, next to `main.py`).

### 1. Clone

```sh
git clone https://github.com/MiroslavKocian/AI-Data-Analyser.git
cd AI-Data-Analyser
```

### 2. Virtual environment and dependencies

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. API key

Follow [API key (two supported options)](#api-key-two-supported-options).

### 4. Start the app

Ruff and pytest run automatically, then the UI opens at http://127.0.0.1:8501

```sh
python run_app.py
```

Equivalent:

```sh
python -m streamlit run main.py
```

The first start after a code change can take a few extra seconds.

### 5. Demo in the browser

1. **Load sample data** — uses `examples/messy_sales_example.xlsx` (messy dates,
   units in text, blanks).
2. Or **upload** your own `.xlsx` via the sidebar.
3. Click **Run AI process** (sidebar).
4. Download **CSV** or use **AI SQL analyst** with a plain-English question.

To test upload manually, pick this file in the file dialog:

`examples/messy_sales_example.xlsx`

---

## Docker

Create `.env` in the project root with `GROQ_API_KEY`, then:

```sh
docker compose up --build
```

Open http://127.0.0.1:8501 (quality checks run on container start, same as locally).

Stop with **Ctrl+C** (press **Enter** on Windows if the prompt hangs), then:

```sh
docker compose down
```

---

## Project layout

```text
AI-Data-Analyser/
├── main.py               Streamlit entry; startup quality gate
├── run_app.py            Launches: python -m streamlit run main.py
├── quality_gate.py       Ruff + pytest before UI loads
├── app.py                Page flow
├── startup.py            GROQ_API_KEY from .env or secrets
├── config.py             Paths, model name, batch size
├── ai_provider.py        Groq LLM (cleaning + SQL generation)
├── repository.py         SQLite persistence (pandas to_sql)
├── data_transformer.py   Display helpers
├── sql_runner.py         Run generated SELECT queries
├── pipeline_manager.py   Clean → save → session state
├── state_manager.py      Streamlit session state
├── ui_renderer.py        Widgets and tables
├── sample_loader.py      Load examples/messy_sales_example.xlsx
├── examples/
│   └── messy_sales_example.xlsx
├── tests/
├── .github/workflows/test.yml
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── pyproject.toml        Pytest, Ruff, coverage settings
└── AGENTS.md
```

Runtime file (not in git): `sales_intelligence.db` in the project root.

---

## Security note

The **AI SQL analyst** runs model-generated SQL against your SQLite file. This is a
**portfolio demo**, not a hardened production service. In production you would
allow only validated read-only `SELECT` statements.

---

## License

Portfolio and interview use; no `LICENSE` file unless one is added later.
