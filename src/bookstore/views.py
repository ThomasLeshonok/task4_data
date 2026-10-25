from functools import lru_cache
import pandas as pd

from .query import FilterSpec, apply_filters
from .repository import Store

VIEWS = ("books", "users", "sales")

@lru_cache(maxsize=64)
def build_view(store: Store, name: str) -> pd.DataFrame:
    if name not in VIEWS:
        raise ValueError(f"Unknown table '{name}'. Available: {', '.join(VIEWS)}")
    return {"books": _books, "users": _users, "sales": _sales}[name](store)

def _person_key(store: Store) -> pd.Series:
    return store.name + ":" + store.people.astype(str)

def _books(store: Store) -> pd.DataFrame:
    books = store.books.copy()
    books["authors"] = store.authors.map(lambda a: ", ".join(a) if isinstance(a, tuple) else None).astype("string")
    books["author_count"] = store.authors.map(lambda a: len(a) if isinstance(a, tuple) else 0).astype("Int64")
    books["genre"] = books["genre"].astype("string")
    return books.assign(store=store.name)

def _users(store: Store) -> pd.DataFrame:
    users = store.users.copy()
    users["person"] = users["id"].map(_person_key(store)).astype("string")
    users["aliases"] = users.groupby("person")["id"].transform("count").astype("Int64")
    return users.assign(store=store.name)

def _sales(store: Store) -> pd.DataFrame:
    books = _books(store)[["id", "title", "authors", "genre", "publisher", "year"]].rename(
        columns={"id": "book_id", "year": "book_year"})
    users = _users(store)[["id", "person", "name", "email"]].rename(
        columns={"id": "user_id", "name": "customer_name", "email": "customer_email"})
    sales = (
        store.orders.rename(columns={"id": "order_id"})
        .merge(books, on="book_id", how="left")
        .merge(users, on="user_id", how="left")
    )
    sales["date"] = pd.to_datetime(sales["date"])
    sales["month"] = sales["date"].dt.strftime("%Y-%m").astype("string")
    sales["year"] = sales["date"].dt.year.astype("Int64")
    sales["weekday"] = sales["date"].dt.day_name().astype("string")
    columns = [
        "order_id", "date", "month", "year", "weekday", "timestamp",
        "user_id", "person", "customer_name", "customer_email",
        "book_id", "title", "authors", "genre", "publisher", "book_year",
        "quantity", "unit_price", "paid_price", "shipping",
    ]
    return sales[columns].assign(store=store.name)

def filter_store(store: Store, spec: FilterSpec) -> Store:
    if spec.is_empty():
        return store
    return store.subset(apply_filters(build_view(store, "sales"), spec)["order_id"])

def combined_view(stores: list[Store], name: str) -> pd.DataFrame:
    frames = [build_view(s, name) for s in stores]
    return frames[0] if len(frames) == 1 else pd.concat(frames, ignore_index=True)
