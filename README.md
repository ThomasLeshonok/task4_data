# TASK 4

## Start the app (Windows PowerShell)

Run these commands from the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The dashboard reads `data/<STORE>/clean/*_clean.parquet` and shows one tab per store that has them.
To rebuild clean data for a store:

```powershell
python src/data_loader.py data/STORE1
```

Print the same metrics in the terminal: `python src/queries.py STORE1`.

## Layout

| Path | Role |
|------|------|
| `src/data_loader.py` | Pipeline entry: reads raw files, calls cleaning, then saving |
| `src/clear_data.py` | Cleaning functions only; `clean_store` runs them for all tables |
| `src/save_cleaned_data.py` | Writes cleaned tables to `clean/*.parquet` |
| `src/bookstore/repository.py` | Finds stores, loads clean tables into a `Store` |
| `src/bookstore/entities.py` | User alias reconciliation, author sets |
| `src/bookstore/analytics.py` | Every metric, returned as plain Python values |
| `src/dashboard/` | Streamlit cards, tables, chart, page sections |
| `streamlit_app.py` | Entry point: caching, store tabs |

Extension points:

- AI answers (part 2): expose `bookstore.analytics` functions as model tools. They return JSON-ready values, so the model reads computed numbers instead of counting.
- AI dashboard control (part 3): widgets keep their state in `st.session_state` (the store tab uses key `store`). A command handler sets those keys and reruns.

## Deploy (Streamlit Community Cloud)

1. Commit the clean parquet files: `data/STORE*/clean/` must be in the repository.
   `.gitignore` excludes `data/STORE2`-`STORE5`, so change those lines to `/data/STORE2/*` plus `!/data/STORE2/clean/` (same for 3-5).
2. Push to GitHub, open https://share.streamlit.io, create an app from the repository with main file `streamlit_app.py`.

