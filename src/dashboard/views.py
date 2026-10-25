import streamlit as st

from bookstore import analytics
from bookstore.analytics import StoreSummary
from bookstore.entities import USER_FIELDS
from bookstore.repository import Store
from bookstore.views import build_view

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

def data_explorer(store: Store, filtered: Store) -> None:
    sales = build_view(store, "sales")
    sales = sales[sales["order_id"].isin(filtered.orders["id"])]
    books = build_view(store, "books")
    users = build_view(store, "users")
    if filtered is not store:
        books = books[books["id"].isin(sales["book_id"])]
        users = users[users["id"].isin(sales["user_id"])]
    with st.expander("Explore data"):
        tabs = st.tabs([f"Sales ({len(sales):,})", f"Books ({len(books):,})", f"Users ({len(users):,})"])
        for tab, frame in zip(tabs, (sales, books, users)):
            tab.dataframe(frame.drop(columns="store"), hide_index=True, width="stretch")

def render_store(store: Store, filtered: Store, summary: StoreSummary | None) -> None:
    if filtered is not store:
        st.caption(f"Filtered: {len(filtered.orders):,} of {len(store.orders):,} orders. "
                   "Users and author sets count only the customers and books in these orders.")
    if summary is None:
        st.info("No orders match the current filters.")
        return
    kpis(summary)
    highlights(summary)
    revenue(filtered, summary)
    data_explorer(store, filtered)
