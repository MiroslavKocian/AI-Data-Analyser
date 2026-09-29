# Architecture

This document describes how AI Data Analyser is structured: UI flow, main modules,
and the most important functions in each file. The [README](../README.md) stays
focused on running the app; this page goes deeper for code review and interviews.

## Execution model

The app is a **Streamlit** script, not a REST API. Each user interaction triggers a
**rerun** of `main.py` → `ai_data_analyser.app.main()`: widgets are redrawn and session
state persists in `st.session_state`. There is no separate background job queue;
**Run AI process** and Groq calls run synchronously in the request cycle of that rerun.

Entry points:

| Command | What runs |
|---------|-----------|
| `python run_app.py` | Subprocess: `python -m streamlit run main.py` |
| `streamlit run main.py` | Same Streamlit script |
| Docker `CMD` | `streamlit run main.py` on `0.0.0.0:8501` |

Quality checks (`pytest`, Ruff) are **not** tied to app startup. Run them locally or
in GitHub Actions; optionally `python quality_gate.py`.

## Page flow (one rerun)

`app.main()` calls methods on `UIRenderer` in a fixed order:

1. **`setup_page`** — Page config and title.
2. **`bootstrap_application`** (`startup.py`) — Session keys + `AIProvider` with Groq key.
3. **`handle_sidebar_ingestion`** — Sample button or `.xlsx` upload → `load_new_data`.
4. If `raw_data` is set — **`handle_raw_data_view`** — Show raw table; sidebar **Run AI process**.
5. If `processed_data` is set — **`handle_analytics_view`** — Cleaned table, CSV download, SQL analyst.

Loading new data clears `processed_data` so old AI output never pairs with a new file.

## Ingestion pipeline

Two paths into the same session shape:

1. **Sample** — `load_sample_excel()` reads `examples/messy_sales_example.xlsx` via
   `config.SAMPLE_EXCEL_PATH`; `load_new_data(df, "sample_data")`.
2. **Upload** — Sidebar file uploader (`.xlsx` only). On a new `file_id`,
   `pd.read_excel(..., keep_default_na=False)` then `load_new_data(df, filename)`.

`keep_default_na=False` keeps literal `"N/A"` cells instead of pandas NA, which
matches how messy exports arrive and what the cleaning prompt expects.

No server-side file store: uploads live in memory for the session. Only cleaned data
is written to SQLite.

## LLM cleaning rules

Source of truth: **`build_cleaning_prompt`** in `ai_data_analyser/ai_provider.py`.
Each batch receives the column list from the upload and a JSON array of row dicts
(strings).

| # | Rule sent to the model |
|---|------------------------|
| 1 | Output must be one JSON object with key `records` (list of objects). |
| 2 | Each object uses the **exact** column keys from the spreadsheet (unchanged). |
| 3 | Dates: parse and emit `YYYY-MM-DD`; invalid or missing → JSON `null`. |
| 4 | Numeric fields: strip currency/units, numeric value only; non-numeric or missing → `null`. |
| 5 | Other fields: empty markers (`N/A`, `n/a`, `-`, `""`) → `null`; no other reformatting or guessing. |

Implementation details around the prompt:

- Rows are processed in chunks of **`config.BATCH_SIZE`** (10).
- Input rows are `astype(str)` with `N/A`, `n/a`, `nan`, `NaN` replaced by `""`
  before `json.dumps` into the prompt.
- Groq call: `temperature=0`, `response_format={"type": "json_object"}`.
- Parsed `records` are turned into DataFrames with the original `schema_columns`;
  batches are concatenated. Failures on one batch do not abort later batches.

The README section [What **Run AI process** does](../README.md#what-run-ai-process-does)
summarizes the same rules for end users.

## Cleaning pipeline (happy path)

Triggered by **Run AI process** → `execute_cleaning_pipeline`:

1. **`AIProvider.clean_data_with_ai`** — Apply [LLM cleaning rules](#llm-cleaning-rules)
   per batch; Streamlit progress bar while batches run.
2. **`save_to_sqlite`** (`repository.py`) — `df.to_sql("sales", ..., if_exists="replace")`
   into `config.DB_NAME` (`sales_intelligence.db`).
3. **`scrub_for_display`** — Stringify for stable Streamlit tables; store in
   `st.session_state.processed_data`.

If every batch fails parsing or the LLM errors, the result can be an empty frame with
the original column names; the UI still shows **Analysis Ready!** when the pipeline
returns—tests cover edge cases for empty LLM JSON.

Failed batches log a warning and show `st.error` for that batch; other batches may
still contribute rows.

## LLM SQL analyst rules

Source of truth: **`build_sql_prompt`** in `ai_data_analyser/ai_provider.py`. The model sees table
name `sales` and the column list from cleaned data.

| # | Guideline sent to the model |
|---|------------------------------|
| 1 | Trend/time questions: `SELECT` date + metric, `ORDER BY` date; no row-to-row diffs unless asked. |
| 2 | Column names with spaces or special characters must be double-quoted in SQL. |
| 3 | If a `JOIN` is used, every selected column needs a table alias prefix. |
| 4 | Return **only** the raw SQL string (no markdown, no explanation). |

**`strip_sql_markdown`** removes ``` fences if the model adds them anyway.

## SQL analyst pipeline

When the user types a question in **AI SQL analyst**:

1. **`generate_sql`** — Column list from `processed_data`; prompt from
   `build_sql_prompt` ([rules above](#llm-sql-analyst-rules)); Groq chat completion;
   **`strip_sql_markdown`** on the reply.
2. UI shows the SQL in a code block.
3. **`validate_read_only_select`** then **`run_select_query`** — normalized SQL only;
   SQLite opened with `file:…?mode=ro`; `pd.read_sql_query` against
   `sales_intelligence.db`.
4. Result table or **`st.error`** on validation or SQLite errors (`SqlValidationError`
   surfaces in the UI message).

Rejected SQL (multi-statement, mutating keywords, non-`SELECT`) never reaches the
database. See the README [Security note](../README.md#security-note).

## Module reference

### `main.py`

Thin Streamlit entry: imports `ai_data_analyser.app.main` and calls it when executed as `__main__`.
Streamlit’s runner invokes the module on each rerun.

### `run_app.py`

- **`main`** — Spawns `python -m streamlit run main.py` with the current interpreter.

### `ai_data_analyser/app.py`

- **`main`** — Orchestrates `UIRenderer` + `bootstrap_application`; gates sections on
  session state flags.

### `ai_data_analyser/startup.py`

- **`resolve_groq_api_key`** — `.env` via `python-dotenv`, else `st.secrets`.
- **`require_groq_api_key`** — `st.error` + `st.stop()` when missing.
- **`bootstrap_application`** — `initialize()` then `AIProvider(api_key)`.

### `ai_data_analyser/state_manager.py`

- **`initialize`** — Default `None` for `raw_data`, `processed_data`, `current_file`,
  `last_uploaded_file_id`.
- **`load_new_data`** — Set raw frame and source id; clear processed output.

### `ai_data_analyser/ui_renderer.py`

All Streamlit I/O for easier unit testing of everything else.

- **`handle_sidebar_ingestion`** — Upload deduplication via `last_uploaded_file_id`.
- **`handle_raw_data_view`** — Raw dataframe + cleaning button.
- **`handle_analytics_view`** — Cleaned data, CSV export, SQL input, sample question
  hints when `current_file == "sample_data"`.

### `ai_data_analyser/ai_provider.py`

- **`build_cleaning_prompt`** / **`build_sql_prompt`** — Prompt templates (rules for
  dates, numbers, nulls, quoted SQLite identifiers).
- **`strip_sql_markdown`** — Remove ``` fences from model output.
- **`AIProvider.clean_data_with_ai`** — Batched Groq JSON cleaning with progress UI.
- **`AIProvider.generate_sql`** — Single-shot SQL string generation.

Uses the OpenAI Python SDK against `config.LLM_BASE_URL` (Groq) and
`config.LLM_MODEL`.

### `ai_data_analyser/pipeline_manager.py`

- **`execute_cleaning_pipeline`** — Connects LLM clean, SQLite save, and session
  processed frame + success message.

### `ai_data_analyser/repository.py`

- **`save_to_sqlite`** — Full replace of table `config.SALES_TABLE` (`sales`).

Persistence uses pandas `to_sql`, not hand-written DDL. Schema follows cleaned
DataFrame columns from the LLM.

### `ai_data_analyser/sql_runner.py`

- **`normalize_sql`** / **`validate_read_only_select`** — Comment strip, single-statement
  check, allow `SELECT` / `WITH … SELECT`, block mutating keywords. The `REPLACE()`
  function inside a `SELECT` is allowed; `REPLACE INTO` is not a `SELECT`.
- **`run_select_query`** — Validate, then read-only URI + `pd.read_sql_query`.
- **`SqlValidationError`** — Raised for invalid analyst SQL (shown in Streamlit).

### `ai_data_analyser/data_transformer.py`

- **`parse_date_safely`** — `dateutil` parsing for tests and any non-LLM date logic;
  returns `None` on garbage dates.
- **`scrub_for_display`** — Replace pandas null sentinels with empty strings for UI.

### `ai_data_analyser/sample_loader.py`

- **`load_sample_excel`** — Read demo workbook from disk.

### `ai_data_analyser/config.py`

Constants: `REPO_ROOT`, `SAMPLE_EXCEL_PATH`, `LLM_MODEL`, `LLM_BASE_URL`, `DB_NAME`,
`SALES_TABLE`, `BATCH_SIZE`.

### `quality_gate.py`

- **`run_quality_checks`** — Subprocess chain: Ruff check, Ruff format check, pytest.
- **`__main__`** — CLI entry for local CI parity.

## Runtime artifacts (not in Git)

| Path | Purpose |
|------|---------|
| `sales_intelligence.db` | SQLite file; table `sales` replaced on each successful clean |
| `.env` | Local `GROQ_API_KEY` (gitignored) |
| `.streamlit/secrets.toml` | Optional local secrets (gitignored) |

In Docker, the database file lives in the container filesystem and is lost after
`docker compose down` unless you add a volume (not configured in this repo).

## Testing layout

Tests live under `tests/` and mock Streamlit, Groq, and filesystem where needed.
`pyproject.toml` enforces 100% line coverage on `ai_data_analyser`, `main`, `run_app`,
and `quality_gate`. Importing `main` during tests does not start Streamlit or run quality checks.

## Design choices (short)

- **Separate UI from logic** — `UIRenderer` holds widgets; pipelines and providers stay
  testable without a browser.
- **Batch LLM cleaning** — Respects Groq payload limits and gives progress feedback;
  tradeoff: partial failures can yield incomplete rows.
- **Replace, not merge** — Each clean overwrites the whole `sales` table; one active
  dataset in SQLite matches one successful AI run.
- **Display vs storage** — `scrub_for_display` is for tables only; SQLite stores the
  cleaned DataFrame as returned from the LLM path.
- **Secrets** — Key from env or Streamlit secrets; never embedded in code.
- **SQL analyst** — `sql_runner` validates read-only `SELECT` and opens SQLite in
  `mode=ro` before execution; production would still add allow-lists and query limits.
