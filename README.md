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
Log in as `Customer` with that password. Add the `AZURE_OPENAI_*` values to `.env` to turn on "Ask the data".

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

`tests/test_eval_questions.py` asks the real Azure OpenAI deployment grader-style questions and compares the
answers with values computed by pandas. It is skipped until `AZURE_OPENAI_*` is set.

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
| `src/assistant/agent.py` | Azure OpenAI tool-calling loop and system prompt |
| `src/security/` | Password hashing, per-IP rate limits, client IP detection |
| `src/dashboard/` | Streamlit pages: login, filters, store view, chat |
| `streamlit_app.py` | Entry point: caching, login gate, pages |

How questions are answered: the model never sees the raw data. It chooses tools (`count_rows`, `aggregate`,
`list_rows`, `find_person`, `store_summary`, `calculate`...) and pandas computes every number. Under each answer,
"How I got this" shows every tool call and its raw result.

Part 3 hook: dashboard filters are a `FilterSpec` kept in `st.session_state` (`extra_conditions` and the `f_*` keys).
An AI command only has to produce the same `FilterSpec`.

## Deploy to Azure App Service

You need an Azure subscription and the Azure CLI (`winget install Microsoft.AzureCLI`).

1. In Azure AI Foundry create an Azure OpenAI resource and deploy a chat model that supports tool calling
   (for example `gpt-4.1` or `gpt-4o`). Note the endpoint, key and deployment name.
2. Create the web app (pick a unique `<app>` name; use the newest `PYTHON:3.x` from `az webapp list-runtimes --os linux`):

   ```powershell
   az login
   az group create -n task4-rg -l westeurope
   az appservice plan create -g task4-rg -n task4-plan --sku B1 --is-linux
   az webapp create -g task4-rg -p task4-plan -n <app> --runtime "PYTHON:3.13"
   az webapp config set -g task4-rg -n <app> --web-sockets-enabled true --always-on true --startup-file "python -m streamlit run streamlit_app.py --server.port 8000 --server.address 0.0.0.0"
   az webapp update -g task4-rg -n <app> --https-only true
   ```

3. Settings (the password hash comes from `python src/security/auth.py`; keep the quotes):

   ```powershell
   az webapp config appsettings set -g task4-rg -n <app> --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true APP_USERNAME=Customer "APP_PASSWORD_HASH=<hash>" AZURE_OPENAI_ENDPOINT=<endpoint> AZURE_OPENAI_API_KEY=<key> AZURE_OPENAI_DEPLOYMENT=<deployment>
   ```

   For reasoning models that reject `temperature`, also set `AZURE_OPENAI_TEMPERATURE=` (empty).
4. Portal: App Service > Deployment Center > GitHub, pick this repository and branch. Every push redeploys.
5. Open `https://<app>.azurewebsites.net` and log in as `Customer`.

### Abuse protection

- Network floods: Azure DDoS infrastructure protection covers every App Service at no cost (network and
  transport layers). It does not count HTTP requests per visitor.
- The app limits each client IP itself (`src/security/limits.py`, defaults in `.env.example`):
  30 new sessions per 10 min, 5 failed logins per 15 min, 20 questions per hour,
  plus 500 questions per day for the whole app to cap model cost.
- Limits are kept in memory, so they hold for one instance (B1). With several instances, move them to Redis.
- For stronger HTTP-level protection, put Azure Front Door with a WAF rate-limit rule in front (paid).
- Also set a monthly budget alert on the subscription and a token limit on the model deployment.
