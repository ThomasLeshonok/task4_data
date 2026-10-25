# TASK 4

Bookstore sales dashboard (part 1) with filters and natural-language questions (part 2), behind a login.

## Run locally (Windows PowerShell)

Run these commands from the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python src/security/auth.py
streamlit run streamlit_app.py
```

`python src/security/auth.py` asks for a password and prints `APP_PASSWORD_HASH=...`; put that line in `.env`.
Log in as `Customer` with that password. Set `GROQ_API_KEY` (free key from console.groq.com) or the
`AZURE_OPENAI_*` values in `.env` to turn on "Ask the data". Groq is used when both are set.

The dashboard reads `data/<STORE>/clean/*_clean.parquet` and shows one tab per store that has them.
To rebuild clean data for a store:

```powershell
python src/data_loader.py data/STORE1
```

Print the dashboard metrics in the terminal: `python src/queries.py STORE1`.

## Tests

```powershell
python -m pytest tests
```

`tests/test_eval_questions.py` asks the real model (Groq or Azure OpenAI) grader-style questions and compares the
answers with values computed by pandas. It is skipped until `GROQ_API_KEY` or `AZURE_OPENAI_*` is set.

## Layout

| Path | Role |
|------|------|
| `src/data_loader.py` | Pipeline entry: reads raw files, calls cleaning, then saving |
| `src/clear_data.py` | Cleaning functions only; `clean_store` runs them for all tables |
| `src/save_cleaned_data.py` | Writes cleaned tables to `clean/*.parquet` |
| `src/bookstore/repository.py` | Finds stores, loads clean tables into a `Store` |
| `src/bookstore/entities.py` | User alias reconciliation, author sets |
| `src/bookstore/analytics.py` | Dashboard metrics, returned as plain Python values |
| `src/bookstore/views.py` | Flat `books`, `users`, `sales` tables for filtering and questions |
| `src/bookstore/query.py` | `FilterSpec` / `Condition` and safe filter, aggregate, list operations |
| `src/assistant/tools.py` | Tools the model may call; each wraps `bookstore.query` |
| `src/assistant/agent.py` | Tool-calling loop, system prompt, Groq and Azure OpenAI clients |
| `src/security/` | Password hashing, per-IP rate limits, client IP detection |
| `src/dashboard/` | Streamlit pages: login, filters, store view, chat |
| `streamlit_app.py` | Entry point: caching, login gate, pages |

How questions are answered: the model never sees the raw data. It chooses tools (`count_rows`, `aggregate`,
`list_rows`, `find_person`, `store_summary`, `calculate`...) and pandas computes every number. Under each answer,
"How I got this" shows every tool call and its raw result.

Part 3 hook: dashboard filters are a `FilterSpec` kept in `st.session_state` (`extra_conditions` and the `f_*` keys).
An AI command only has to produce the same `FilterSpec`.

## Deploy to Streamlit Community Cloud (free)

1. Get a free API key at console.groq.com > API Keys.
2. Push this repository to GitHub (`.env` stays out: it is in `.gitignore`).
3. share.streamlit.io > Create app > pick the repository, branch, main file `streamlit_app.py`.
   Advanced settings: Python 3.13, and paste the secrets (the hash comes from `python src/security/auth.py`):

   ```toml
   APP_USERNAME = "Customer"
   APP_PASSWORD_HASH = "<hash>"
   GROQ_API_KEY = "<key>"
   ```

4. Deploy, open the `*.streamlit.app` link and log in as `Customer`. Every push redeploys.

Free tier notes: the app sleeps after a few days without visits (first open wakes it). Groq's free tier limits
requests and tokens per minute and per day; when hit, the chat shows "The assistant failed: RateLimitError".
Default model `openai/gpt-oss-120b`; set `GROQ_MODEL` for another one with tool calling, e.g. `openai/gpt-oss-20b`.
