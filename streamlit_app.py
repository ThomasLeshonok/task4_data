import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from bookstore.analytics import StoreSummary, summarize
from bookstore.repository import Store, list_stores, load_store 
from dashboard import views  
from dashboard.components import apply_styles  

STORE_KEY = "store"

st.set_page_config(page_title="Bookstore Sales", page_icon=":material/menu_book:", layout="wide")

@st.cache_resource(show_spinner="Loading store data...")
def get_store(name: str) -> Store:
    return load_store(name)

@st.cache_data(show_spinner="Computing metrics...")
def get_summary(name: str) -> StoreSummary:
    return summarize(get_store(name))

def main() -> None:
    apply_styles()
    st.title("Bookstore Sales Dashboard")
    st.caption("Revenue, customers and authors per store, computed from cleaned order data. Amounts in USD.")

    stores = list_stores()
    if not stores:
        st.error("No clean data found. Run `python src/data_loader.py data/STORE1` to build it.")
        st.stop()

    tabs = st.tabs(stores, key=STORE_KEY, on_change="rerun")
    for name, tab in zip(stores, tabs):
        if tab.open:
            with tab:
                views.render_store(get_store(name), get_summary(name))

main()
