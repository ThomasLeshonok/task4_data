from dataclasses import asdict, dataclass
import pandas as pd

from .repository import Store

DATE_FORMAT = "%Y-%m-%d"

def daily_revenue(store: Store) -> pd.DataFrame:
    revenue = store.orders.groupby(pd.to_datetime(store.orders["date"]))["paid_price"].sum().round(2)
    revenue = revenue.asfreq("D", fill_value=0)
    return revenue.rename("revenue").rename_axis("date").reset_index()

def top_revenue_days(store: Store, n: int = 5) -> list[dict]:
    top = daily_revenue(store).nlargest(n, "revenue")
    return [{"date": d.strftime(DATE_FORMAT), "revenue": float(r)} for d, r in zip(top["date"], top["revenue"])]

def total_revenue(store: Store) -> float:
    return round(float(store.orders["paid_price"].sum()), 2)

def unique_users(store: Store) -> int:
    return int(store.people.nunique())

def unique_author_sets(store: Store) -> int:
    return int(store.authors.dropna().nunique())

def author_set_sales(store: Store) -> pd.Series:
    books = store.books[["id"]].assign(authors=store.authors).dropna(subset=["authors"])
    sold = store.orders.merge(books, left_on="book_id", right_on="id")
    return sold.groupby("authors")["quantity"].sum().sort_values(ascending=False)

def most_popular_authors(store: Store) -> dict:
    sales = author_set_sales(store)
    best = sales[sales == sales.max()]
    return {"author_sets": [list(a) for a in best.index], "books_sold": int(best.iloc[0])}

def best_buyer(store: Store) -> dict:
    spend = store.orders.groupby(store.orders["user_id"].map(store.people))["paid_price"].sum()
    person = spend.idxmax()
    ids = store.people.index[store.people == person]
    records = store.users[store.users["id"].isin(ids)]
    return {
        "user_ids": sorted(int(i) for i in ids),
        "names": sorted(records["name"].dropna().unique().tolist()),
        "total_spent": round(float(spend[person]), 2),
        "orders": int(store.orders["user_id"].isin(ids).sum()),
    }

@dataclass
class StoreSummary:
    store: str
    top_days: list[dict]
    total_revenue: float
    unique_users: int
    user_records: int
    unique_author_sets: int
    popular_authors: dict
    best_buyer: dict

    def to_dict(self) -> dict:
        return asdict(self)

def summarize(store: Store) -> StoreSummary:
    return StoreSummary(
        store=store.name,
        top_days=top_revenue_days(store),
        total_revenue=total_revenue(store),
        unique_users=unique_users(store),
        user_records=len(store.users),
        unique_author_sets=unique_author_sets(store),
        popular_authors=most_popular_authors(store),
        best_buyer=best_buyer(store),
    )
