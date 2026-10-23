"""Page sections for one store."""
import streamlit as st

from bookstore import analytics
from bookstore.analytics import StoreSummary
from bookstore.entities import USER_FIELDS
from bookstore.repository import Store

from .components import card, money, revenue_chart, top_days_table

def kpis(summary: StoreSummary) -> None:
    merged = summary.user_records - summary.unique_users
    with st.container(horizontal=True):
        st.metric("Total revenue", money(summary.total_revenue), border=True)
        st.metric(
            "Unique users", f"{summary.unique_users:,}", border=True,
            help=f"{summary.user_records:,} user records, {merged:,} merged as aliases. "
                 f"Records that differ in at most one of {', '.join(USER_FIELDS)} are one person.",
        )
        st.metric("Unique author sets", f"{summary.unique_author_sets:,}", border=True,
                  help="Each distinct group of co-authors counts once; solo books are a set of one.")
        st.metric("Best buyer spent", money(summary.best_buyer["total_spent"]), border=True)

def highlights(summary: StoreSummary) -> None:
    left, right = st.columns(2)
    with left:
        popular = summary.popular_authors
        sets = [" & ".join(names) for names in popular["author_sets"]]
        card("Most popular author(s)", "\n".join(f"#### {s}" for s in sets),
             f"{popular['books_sold']:,} books sold")
    with right:
        buyer = summary.best_buyer
        card("Best buyer (all aliases)", f"#### `{buyer['user_ids']}`",
             f"{', '.join(buyer['names'])} · {money(buyer['total_spent'])} across {buyer['orders']} orders")

def revenue(store: Store, summary: StoreSummary) -> None:
    with st.container(horizontal=True):
        with st.container(border=True, key="top-days"):
            st.markdown("**Top 5 days by revenue**")
            top_days_table(summary.top_days)
        with st.container(border=True, key="revenue-trend"):
            st.markdown("**Daily revenue**")
            revenue_chart(analytics.daily_revenue(store), [d["date"] for d in summary.top_days])

def data_explorer(store: Store) -> None:
    with st.expander("Explore data"):
        books, users, orders = st.tabs(["Books", "Users", "Orders"])
        books.dataframe(store.books, hide_index=True, width="stretch")
        users.dataframe(store.users.assign(person=store.users["id"].map(store.people)),
                        hide_index=True, width="stretch")
        orders.dataframe(store.orders, hide_index=True, width="stretch")

def render_store(store: Store, summary: StoreSummary) -> None:
    kpis(summary)
    highlights(summary)
    revenue(store, summary)
    data_explorer(store)
