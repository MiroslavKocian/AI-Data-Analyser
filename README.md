# 🚀 AI-Sales-Analyser
### Transitioning from Legacy RPA to a 2026 GenAI Stack

## 📌 Project Overview
This project demonstrates a bridge between traditional **RPA (Blue Prism/IBM)** enterprise environments and modern **AI-driven automation**. It replaces fragile "click-based" workflows with "thought-based" data processing.

## 🛠️ The Solution
* **Data Normalization:** Converts "dirty" legacy Excel exports (inconsistent dates, currency strings) into clean, structured data using LLMs.
* **SQL Warehouse:** Persists cleaned data into a structured **SQLite** database for permanent storage and high-speed querying.
* **Multilingual Intelligence:** A Streamlit interface that accepts natural language queries in **Slovak, English, or French** and converts them instantly to SQL.

## 💻 Tech Stack
* **Python 3.11**
* **Streamlit** (User Interface)
* **SQLite** (Database)
* **Mistral AI** (LLM Engine)

## 🚀 How to Run

1.  **Clone the repository and navigate into it.**

2.  **Set up your environment:**
    *   Install the dependencies listed in `requirements.txt`.
        ```bash
        pip install -r requirements.txt
        ```
    *   Create a `.env` file in the root directory and add your Mistral API key:
        ```env
        MISTRAL_API_KEY="YourMistralApiKey"
        ```

3.  **Run the application:**
    Use the launcher script to automatically run tests before starting:
    ```bash
    python run_app.py
    ```

## 🧪 Testing

To run the automated test suite, simply execute:
```bash
pytest
```
