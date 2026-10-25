import pandas as pd
import pytest

from bookstore.analytics import summarize
from bookstore.query import Condition, FilterSpec, aggregate, apply_filters, list_rows
from bookstore.views import build_view

def spec(*conditions, match="all"):
    return FilterSpec(conditions=[Condition(**c) for c in conditions], match=match)

def test_sales_view_has_one_row_per_order(store1):
    sales = build_view(store1, "sales")
    assert len(sales) == len(store1.orders)
    assert sales["paid_price"].sum() == pytest.approx(store1.orders["paid_price"].sum())

def test_person_key_is_smallest_alias_id(store1):
    users = build_view(store1, "users")
    assert set(users.loc[users["id"].isin([48403, 48904, 50056]), "person"]) == {"STORE1:48403"}

def test_distinct_people_match_dashboard(store1):
    users = build_view(store1, "users")
    assert users["person"].nunique() == summarize(store1).unique_users

def test_startswith_list_is_or(store1):
    users = build_view(store1, "users")
    got = apply_filters(users, spec({"column": "email", "op": "startswith", "value": ["s", "p"]}))
    assert len(got) == users["email"].str.lower().str.match(r"^[sp]", na=False).sum()

def test_text_eq_ignores_case(store1):
    sales = build_view(store1, "sales")
    got = apply_filters(sales, spec({"column": "genre", "op": "eq", "value": "fantasy"}))
    assert len(got) == (sales["genre"] == "Fantasy").sum() > 0

def test_negate_and_any(store1):
    books = build_view(store1, "books")
    fantasy = {"column": "genre", "op": "eq", "value": "Fantasy"}
    assert len(apply_filters(books, spec({**fantasy, "negate": True}))) == len(books) - len(apply_filters(books, spec(fantasy)))
    either = spec(fantasy, {"column": "genre", "op": "eq", "value": "Horror"}, match="any")
    assert len(apply_filters(books, either)) == books["genre"].isin(["Fantasy", "Horror"]).sum()

def test_date_between(store1):
    sales = build_view(store1, "sales")
    got = apply_filters(sales, spec({"column": "date", "op": "between", "value": ["2025-08-01", "2025-08-31"]}))
    assert len(got) == sales["date"].between(pd.Timestamp("2025-08-01"), pd.Timestamp("2025-08-31")).sum()

def test_multi_column_contains(store1):
    sales = build_view(store1, "sales")
    got = apply_filters(sales, spec({"column": ["title", "authors"], "op": "contains", "value": "ernser"}))
    expected = sales["title"].str.contains("ernser", case=False, na=False) | sales["authors"].str.contains("ernser", case=False, na=False)
    assert len(got) == expected.sum()

def test_unknown_column_lists_available(store1):
    with pytest.raises(ValueError, match="Available"):
        apply_filters(build_view(store1, "sales"), spec({"column": "price", "op": "gt", "value": 1}))

def test_aggregate_top_days_match_dashboard(store1):
    result = aggregate(build_view(store1, "sales"), "sum", "paid_price", ["date"], limit=5)
    assert [r["date"] for r in result["rows"]] == [d["date"] for d in summarize(store1).top_days]

def test_aggregate_includes_ties():
    df = pd.DataFrame({"k": list("abcd"), "v": [3, 2, 2, 1]})
    result = aggregate(df, "sum", "v", ["k"], limit=2)
    assert [r["k"] for r in result["rows"]] == ["a", "b", "c"]
    assert result["note"]

def test_list_rows_is_capped(store1):
    result = list_rows(build_view(store1, "books"), limit=500)
    assert result["shown"] == 50 and result["total_matching"] == len(store1.books)

def test_subset_keeps_full_store_aliases(store1):
    sales = build_view(store1, "sales")
    sub = store1.subset(sales.loc[sales["month"] == "2025-08", "order_id"])
    assert set(sub.people.unique()) <= set(store1.people.unique())
    assert sub.orders["paid_price"].sum() == pytest.approx(sales.loc[sales["month"] == "2025-08", "paid_price"].sum())
