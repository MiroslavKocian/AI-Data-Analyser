# 🚀 AI Data Analyser
### From Messy Legacy Excel → Clean Structured Data → Natural Language SQL

---

## 📌 Project Overview

Enterprise data is messy. Dates in five different formats, inconsistent casing, missing values, non-numeric strings in number columns — this is the reality of real-world Excel exports from CRM and ERP systems.

This project demonstrates an end-to-end AI-powered data pipeline that:

1. **Ingests** any Excel file — no fixed column names required
2. **Cleans and normalises** the data using an LLM — no brittle regex rules
3. **Persists** the structured result to a SQLite database
4. **Exports** the cleaned data as a CSV with one click
5. **Answers** natural language questions by generating and executing SQL live

Built as a deliberate bridge between **traditional RPA/VBA automation** (where rules break the moment a format changes) and a modern **AI-driven approach** (where the model understands intent, not just pattern).

---

## 🖥️ Application Walkthrough

**Step 1 — Load Data**
Upload any `.xlsx` file via **Browse files**, or click **Load Sample Data** to use the built-in contract dataset.

**Step 2 — Run AI Process**
Click **Run AI Process**. The LLM cleans data in batches with a live progress bar. It applies exactly three transformations — nothing else is changed or guessed:

- **Dates** — any date format normalised to `YYYY-MM-DD`, null if unparseable
- **Numbers** — currency symbols and units stripped, keeping only the numeric value (e.g. `$1,200.50` → `1200.50`, `15 units` → `15`), null if missing
- **Empty values** — `N/A`, `n/a`, `-`, blank cells → null

**Step 3 — Explore and Export**
- Cleaned data table — structured and display-ready
- **⬇️ Download Cleaned Data as CSV** — one-click export
- **🗣️ AI SQL Analyst** — ask a question in plain English (or Slovak, or French) and get a live SQL result back

---

## 💻 Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| AI / LLM | Groq (`openai/gpt-oss-20b`) |
| Data | Pandas |
| Database | SQLite |
| Testing | Pytest |
| API Client | OpenAI-compatible SDK |

---

## 🚀 How to Run

**1. Clone the repository**
```bash
git clone https://github.com/your-username/AI-Data-Analyser.git
cd AI-Data-Analyser
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```
**3. Add your API key**

Create a `.env` file in the root directory:
```env
GROQ_API_KEY="your_groq_api_key_here"
```
Get a free key at [console.groq.com](https://console.groq.com).

Create a folder `.streamlit` in the root directory, create a file `secrets.toml` inside:
```toml
GROQ_API_KEY = "your_groq_api_key_here"
```

**4. Launch**

Use the launcher — it runs the full test suite first and only starts the app if all tests pass:
```bash
python run_app.py
```

Or run directly:
```bash
streamlit run main.py
```

---

## 🧪 Testing

```bash
python -m pytest
```

The test suite covers all components with no hardcoded column names — tests work with any data shape:

- `DataTransformer` — date parsing across 6+ formats, all null variants, type checks
- `Repository` — SQLite persistence, replace behaviour, column name preservation
- `AIProvider` — SQL markdown stripping, prompt content verification, batch count, error handling, partial batch failure recovery
- `PipelineManager` — service call order, session state assignment, raw data forwarding
- `StateManager` — key creation, no-overwrite on re-init, processed data reset on new load

---

## 🏗️ Architecture

Six classes, one responsibility each:

```
Config            → centralised constants and sample data
Repository        → SQLite persistence
DataTransformer   → date parsing and display sanitisation
AIProvider        → LLM calls: data cleaning and SQL generation
StateManager      → Streamlit session state abstraction
UIRenderer        → all Streamlit UI components
PipelineManager   → orchestrates the cleaning pipeline
```

Tests mock at the class boundary — no real API or database calls are made during testing.

---

## 💡 Why This Exists

After 10 years of enterprise automation using Blue Prism and IBM RPA, I built this to demonstrate that:

- **LLMs replace fragile rule engines.** Traditional RPA breaks when a date format changes from `DD/MM/YYYY` to `Month DD, YYYY`. An LLM understands both.
- **Domain knowledge + AI = better automation.** Understanding what the data means leads to better prompts and better results.
- **Natural language is the new SQL interface.** Non-technical stakeholders can now query their own data without knowing SQL — in whichever language they think in.
