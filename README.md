# AI Data Analyser

[![Tests](https://github.com/MiroslavKocian/AI-Data-Analyser/actions/workflows/test.yml/badge.svg)](https://github.com/MiroslavKocian/AI-Data-Analyser/actions/workflows/test.yml)

Upload messy Excel sales exports, let **Groq** clean and structure the rows, store
them in **SQLite**, export CSV, and ask questions in plain language that become
**SQL** queries.

Built with Python 3.11, Streamlit, Groq (`openai/gpt-oss-20b`), pandas, and SQLite.

**Live demo:** [ai-sales-analyser.streamlit.app](https://ai-sales-analyser.streamlit.app/)  
(Hosted app name is `ai-sales-analyser`; the title in the UI is **AI Data Analyser**.)

## Requirements

- [Python 3.11](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- Free [Groq API key](https://console.groq.com) (for AI cleaning and SQL generation)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (only if you want to run the app in Docker)

## Run locally

### 1. Download the project

```sh
git clone https://github.com/MiroslavKocian/AI-Data-Analyser.git
cd AI-Data-Analyser
```

This creates a folder named `AI-Data-Analyser`. Run every following command inside this folder.

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

If PowerShell refuses to run `Activate.ps1`, run this once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 3. Set the Groq API key

Use **either** a root `.env` file **or** Streamlit secrets. If both exist locally,
`.env` wins.

**Option A — `.env` in the project root**

```env
GROQ_API_KEY="your_groq_api_key_here"
```

**Option B — `.streamlit/secrets.toml`**

```toml
GROQ_API_KEY = "your_groq_api_key_here"
```

Never commit real keys. `.env` and `secrets.toml` are in `.gitignore`.

For [Streamlit Cloud](https://share.streamlit.io): **Settings** → **Secrets** → set
`GROQ_API_KEY`, then **Reboot** the app after changes.

### 4. Start the app

```sh
python run_app.py
```

Equivalent:

```sh
python -m streamlit run main.py
```

Keep this terminal window open. The app runs as long as it is open. To stop it, press **Ctrl+C**.

On Windows, prefer `python -m streamlit` (not bare `streamlit`) so the active `.venv` is used.

### 5. Use the app

1. Open [http://127.0.0.1:8501](http://127.0.0.1:8501) in your browser.

   ![AI Data Analyser home at http://127.0.0.1:8501](docs/images/01-app-home.jpg)

2. In the sidebar, click **Load sample data** (uses `examples/messy_sales_example.xlsx`), **or** upload your own `.xlsx` file.

   ![Raw input after loading sample data](docs/images/02-raw-input.jpg)

3. Review the **Raw input** table, then click **Run AI process** in the sidebar.

   ![Raw and cleaned tables after Run AI process](docs/images/03-cleaned-data.jpg)

4. When cleaning finishes, download **CSV**, or type a question under **AI SQL analyst** and run the generated query.

   ![AI SQL analyst with generated query and result](docs/images/04-sql-analyst.jpg)

The sample file path on disk:

`examples/messy_sales_example.xlsx`

Each new upload or sample load replaces the working dataset in the UI session. The SQLite file on disk is updated when AI processing completes.

## Run with Docker

Create `.env` in the project root with `GROQ_API_KEY`, then start Docker Desktop and run:

```sh
docker compose up --build
```

When the log shows that Streamlit is listening on port 8501, follow the steps in [Use the app](#5-use-the-app). The log may say `http://0.0.0.0:8501`; that is the address inside the container. In your browser, use [http://127.0.0.1:8501](http://127.0.0.1:8501).

To stop, press **Ctrl+C** (on Windows, press **Enter** if the prompt hangs), then run:

```sh
docker compose down
```

The database file lives inside the container, so after `docker compose down` stored rows are gone. Load the sample or upload again after the next start.

## Excel file rules

- The file must be `.xlsx` (sidebar upload and sample loader).
- Messy real-world exports are expected: odd date formats, text in numeric fields, blanks.
- The app reads the sheet with pandas; very large files may hit Groq rate limits because cleaning runs in batches (see `BATCH_SIZE` in `config.py`).
- AI cleaning and the SQL analyst need a valid `GROQ_API_KEY`. Without it, the app stops with a clear error.

If upload or parsing fails, fix the file or try the sample workbook first.

## How it works

```mermaid
flowchart TD
    ingest[Sidebar: sample or upload] --> raw[Raw DataFrame in session]
    raw --> groq[Groq: structure and clean rows]
    groq --> sqlite[Save to SQLite sales table]
    sqlite --> ui[Show cleaned table and CSV export]
    ui --> question[Natural-language question]
    question --> sql[Groq: generate SELECT]
    sql --> run[Run query on SQLite]
    run --> answer[Show result table]
```

1. Excel is loaded into Streamlit session state (sample file or upload).
2. **Run AI process** sends batches of rows to Groq and merges structured records.
3. Cleaned data is saved to `sales_intelligence.db` and shown in the UI.
4. The SQL analyst asks Groq for a `SELECT`, runs it locally, and displays rows.

| File | Responsibility |
|------|----------------|
| `main.py` | Streamlit entry script |
| `run_app.py` | Launches `python -m streamlit run main.py` |
| `app.py` | Page flow (ingest → clean → analyse) |
| `ui_renderer.py` | Streamlit widgets and layout |
| `startup.py` | Resolve `GROQ_API_KEY` from `.env` or secrets |
| `ai_provider.py` | Groq calls for cleaning and SQL generation |
| `pipeline_manager.py` | Clean → persist → session state |
| `repository.py` | Write cleaned frames to SQLite |
| `sql_runner.py` | Execute generated `SELECT` queries |
| `state_manager.py` | Session state helpers |
| `sample_loader.py` | Load `examples/messy_sales_example.xlsx` |
| `data_transformer.py` | Display-safe formatting |
| `config.py` | Paths, model name, batch size, DB table name |
| `quality_gate.py` | Optional local runner: Ruff + pytest (same as CI) |

For a longer walkthrough (request flow, key functions per module, and design notes),
see [docs/architecture.md](docs/architecture.md).

Files created while the app runs (not stored in Git): `sales_intelligence.db` in the project root (or inside the container when using Docker).

## Security note

The **AI SQL analyst** runs model-generated SQL against your SQLite file. This is a
**portfolio demo**, not a hardened production service. In production you would allow
only validated read-only `SELECT` statements.

## Tests

With the virtual environment active:

```sh
pytest
ruff check .
ruff format --check .
```

`pytest` runs all tests and requires 100% code coverage. `ruff` checks code style.

GitHub runs the same three commands automatically after every push (file `.github/workflows/test.yml`). The green **Tests** badge at the top of this page shows the latest result.

Optional: run all three in one step with `python quality_gate.py`.

## Project structure

```text
AI-Data-Analyser/
├── main.py
├── run_app.py
├── app.py
├── startup.py
├── config.py
├── ai_provider.py
├── pipeline_manager.py
├── repository.py
├── sql_runner.py
├── state_manager.py
├── ui_renderer.py
├── data_transformer.py
├── sample_loader.py
├── quality_gate.py
├── examples/
│   └── messy_sales_example.xlsx
├── docs/
│   ├── architecture.md
│   └── images/
│       ├── 01-app-home.jpg
│       ├── 02-raw-input.jpg
│       ├── 03-cleaned-data.jpg
│       └── 04-sql-analyst.jpg
├── tests/
├── .github/workflows/test.yml
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── pyproject.toml
└── AGENTS.md
```

`pyproject.toml` holds the pytest and Ruff settings. `AGENTS.md` holds the coding rules followed while building this project.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Browser says the page cannot be reached | The app is not running. Start it with `python run_app.py` and keep the terminal open. |
| `Address already in use` / port 8501 busy | Another app (or a second copy of this one) is using port 8501. Close it and start again. |
| `GROQ_API_KEY is missing` | Add the key to `.env` or `.streamlit/secrets.toml` (see [Set the Groq API key](#3-set-the-groq-api-key)). |
| AI process fails or times out | Check the Groq key, quotas at [console.groq.com](https://console.groq.com), and try a smaller upload or the sample file. |
| Upload shows an error | Confirm the file is `.xlsx` and readable; try [Excel file rules](#excel-file-rules) or the sample workbook. |
| Docker starts but the UI is empty / errors | Ensure `.env` with `GROQ_API_KEY` exists in the project root before `docker compose up --build`. |

## License

No license is granted. The code is published to be viewed as a portfolio project.
