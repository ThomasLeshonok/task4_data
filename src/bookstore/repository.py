import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
import pandas as pd

from .entities import author_sets, reconcile_users

DATA_DIR = Path(os.environ.get("BOOKSTORE_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
TABLES = ("books", "users", "orders")

@dataclass(eq=False)
class Store:
    name: str
    books: pd.DataFrame
    users: pd.DataFrame
    orders: pd.DataFrame

    @cached_property
    def people(self) -> pd.Series:
        return reconcile_users(self.users)

    @cached_property
    def authors(self) -> pd.Series:
        return author_sets(self.books)

    def subset(self, order_ids) -> "Store":
        orders = self.orders[self.orders["id"].isin(order_ids)]
        books = self.books[self.books["id"].isin(orders["book_id"])]
        users = self.users[self.users["id"].isin(orders["user_id"])]
        sub = Store(self.name, books, users, orders)
        sub.__dict__["people"] = self.people[self.people.index.isin(users["id"])]
        sub.__dict__["authors"] = self.authors.loc[books.index]
        return sub

def clean_dir(store: str, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / store / "clean"

def clean_file(folder: Path, table: str) -> Path:
    return folder / f"{table}_clean.parquet"

def list_stores(data_dir: Path = DATA_DIR) -> list[str]:
    stores = [
        d.name for d in data_dir.iterdir()
        if d.is_dir() and all(clean_file(clean_dir(d.name, data_dir), t).exists() for t in TABLES)
    ]
    return sorted(stores)

def load_store(store: str, data_dir: Path = DATA_DIR) -> Store:
    folder = clean_dir(store, data_dir)
    tables = {t: pd.read_parquet(clean_file(folder, t)) for t in TABLES}
    return Store(name=store, **tables)
