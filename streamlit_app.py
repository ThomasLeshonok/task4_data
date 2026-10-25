import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")
st.secrets.load_if_toml_exists()  # Streamlit Community Cloud: top-level secrets become environment variables

from assistant.agent import Assistant, make_chat_client
from assistant.tools import Toolbox
from bookstore.analytics import StoreSummary, summarize
from bookstore.query import FilterSpec
from bookstore.repository import Store, list_stores, load_store
from bookstore.views import build_view, filter_store
from dashboard import views
from dashboard.access import login_gate, logout_button, session_allowed
from dashboard.chat import clear_chat_button, render_chat
from dashboard.components import apply_styles
from dashboard.filters import FilterOptions, filter_sidebar, keep_filter_state
from security.limits import Limits, client_ip

STORE_KEY = "store"

st.set_page_config(page_title="Bookstore Sales", page_icon=":material/menu_book:", layout="wide")

@st.cache_resource
def get_limits() -> Limits:
    return Limits.from_env()

@st.cache_resource(show_spinner="Loading store data...")
def get_store(name: str) -> Store:
    return load_store(name)

@st.cache_data(show_spinner="Computing metrics...", max_entries=256)
def get_summary(name: str, spec_json: str) -> StoreSummary | None:
    filtered = filter_store(get_store(name), FilterSpec.model_validate_json(spec_json))
    return summarize(filtered) if len(filtered.orders) else None

@st.cache_resource(show_spinner="Preparing filters...")
def get_filter_options() -> FilterOptions:
    sales = pd.concat([build_view(get_store(s), "sales") for s in list_stores()], ignore_index=True)
    return FilterOptions(
        columns=[c for c in sales.columns if c != "store"],
        genres=sorted(sales["genre"].dropna().unique()),
        first_day=sales["date"].min().date(),
        last_day=sales["date"].max().date(),
        sample=sales.head(50),
    )

@st.cache_resource
def get_assistant() -> Assistant:
    return Assistant(make_chat_client(), Toolbox(get_store, list_stores()))

def dashboard_page() -> None:
    st.title("Bookstore Sales Dashboard")
    st.caption("Revenue, customers and authors per store, computed from cleaned order data. Amounts in USD.")
    stores = list_stores()
    if not stores:
        st.error("No clean data found. Run `python src/data_loader.py data/STORE1` to build it.")
        st.stop()

    spec = filter_sidebar(get_filter_options())
    tabs = st.tabs(stores, key=STORE_KEY, on_change="rerun")
    for name, tab in zip(stores, tabs):
        if tab.open:
            with tab:
                store = get_store(name)
                views.render_store(store, filter_store(store, spec), get_summary(name, spec.model_dump_json()))

def chat_page() -> None:
    clear_chat_button()
    render_chat(get_assistant, get_limits(), client_ip(st.context.headers, st.context.ip_address))

def main() -> None:
    apply_styles()
    limits = get_limits()
    ip = client_ip(st.context.headers, st.context.ip_address)
    if not session_allowed(limits, ip) or not login_gate(limits, ip):
        st.stop()
    logout_button()
    keep_filter_state()
    st.navigation([
        st.Page(dashboard_page, title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page(chat_page, title="Ask the data", icon=":material/chat:", url_path="ask"),
    ]).run()

main()
