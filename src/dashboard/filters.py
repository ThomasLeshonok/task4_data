from dataclasses import dataclass
import datetime as dt
import pandas as pd
import streamlit as st

from bookstore.query import Condition, FilterSpec, apply_filters

CONDITIONS_KEY = "extra_conditions"
WIDGET_KEYS = ("f_dates", "f_genres", "f_book", "f_customer")

OP_LABELS = {
    "contains": "contains", "startswith": "starts with", "endswith": "ends with",
    "eq": "equals", "ne": "not equal", "in": "is one of",
    "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "between": "between",
    "regex": "matches regex", "isnull": "is empty",
}
LIST_OPS = {"in", "between", "contains", "startswith", "endswith"}

@dataclass
class FilterOptions:
    columns: list[str]
    genres: list[str]
    first_day: dt.date
    last_day: dt.date
    sample: pd.DataFrame


def keep_filter_state() -> None:
    for key in WIDGET_KEYS:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]

def _parse_value(op: str, text: str):
    if op == "isnull":
        return None
    parts = [p.strip() for p in text.split(",")]
    return parts if op in LIST_OPS and len(parts) > 1 else text.strip()

def _clear() -> None:
    for key in WIDGET_KEYS:
        st.session_state.pop(key, None)
    st.session_state[CONDITIONS_KEY] = []

def set_filters(spec: FilterSpec) -> None:
    """Replace every sidebar filter with the conditions of spec (all must match)."""
    _clear()
    st.session_state[CONDITIONS_KEY] = [c.model_dump() for c in spec.conditions]

def _remove(index: int) -> None:
    st.session_state[CONDITIONS_KEY].pop(index)

def _condition_builder(options: FilterOptions) -> None:
    conditions = st.session_state.setdefault(CONDITIONS_KEY, [])
    with st.expander("More conditions", expanded=bool(conditions)):
        column = st.selectbox("Column", options.columns, key="b_column")
        op = st.selectbox("Operator", list(OP_LABELS), format_func=OP_LABELS.get, key="b_op")
        value = st.text_input("Value", key="b_value", disabled=op == "isnull",
                              help="Separate several values with commas: 'between' takes low, high.")
        negate = st.checkbox("Exclude matching rows", key="b_negate")
        if st.button("Add condition", width="stretch"):
            condition = Condition(column=column, op=op, value=_parse_value(op, value), negate=negate)
            try:
                apply_filters(options.sample, FilterSpec(conditions=[condition]))
            except (ValueError, TypeError) as e:
                st.error(f"Can't use that value: {e}")
            else:
                conditions.append(condition.model_dump())
        for i, raw in enumerate(conditions):
            st.button(Condition(**raw).label(), key=f"rm_{i}", icon=":material/close:",
                      on_click=_remove, args=(i,), width="stretch")

def filter_sidebar(options: FilterOptions) -> FilterSpec:
    with st.sidebar:
        st.header("Filters")
        st.session_state.setdefault("f_dates", (options.first_day, options.last_day))
        dates = st.date_input("Order date", min_value=options.first_day, max_value=options.last_day, key="f_dates")
        genres = st.multiselect("Genre", options.genres, key="f_genres")
        book = st.text_input("Title or author contains", key="f_book")
        customer = st.text_input("Customer name or e-mail contains", key="f_customer")
        _condition_builder(options)

        conditions = []
        if len(dates) == 2 and tuple(dates) != (options.first_day, options.last_day):
            conditions.append(Condition(column="date", op="between", value=[str(dates[0]), str(dates[1])]))
        if genres:
            conditions.append(Condition(column="genre", op="in", value=genres))
        if book.strip():
            conditions.append(Condition(column=["title", "authors"], op="contains", value=book.strip()))
        if customer.strip():
            conditions.append(Condition(column=["customer_name", "customer_email"], op="contains", value=customer.strip()))
        conditions += [Condition(**c) for c in st.session_state[CONDITIONS_KEY]]

        if conditions:
            st.button("Clear all filters", on_click=_clear, icon=":material/filter_alt_off:", width="stretch")
    return FilterSpec(conditions=conditions)
