import json
from dataclasses import dataclass
from typing import Any, Callable, Literal
import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from bookstore.analytics import summarize
from bookstore.query import FilterSpec, Metric, aggregate, apply_filters, describe, list_rows, to_records
from bookstore.repository import Store
from bookstore.views import combined_view

from .calc import calculate

ALL = "ALL"
Table = Literal["books", "users", "sales"]

class NoArgs(BaseModel):
    pass

class StoreArgs(BaseModel):
    store: str = Field(description="Store name, e.g. STORE1. ALL combines every store.")

class TableArgs(StoreArgs):
    table: Table

class FilteredArgs(TableArgs):
    filters: FilterSpec = Field(default_factory=FilterSpec)

class AggregateArgs(FilteredArgs):
    metric: Metric = Field(description="count = rows (or non-null values of column); nunique = distinct values.")
    column: str | None = Field(None, description="Column to aggregate. Optional for count.")
    group_by: list[str] = Field(default_factory=list, description="Group by these columns; empty = one total.")
    descending: bool = True
    limit: int = Field(10, description="Groups to return, best first. Ties with the last group are added.")

class ListRowsArgs(FilteredArgs):
    columns: list[str] | None = None
    sort_by: str | None = None
    descending: bool = False
    limit: int = Field(20, description="At most 50.")

class FindPersonArgs(StoreArgs):
    text: str = Field(description="Part of a name, e-mail, phone or address, or a user id.")

class CalculateArgs(BaseModel):
    expression: str = Field(description="Arithmetic on numbers from tool results, e.g. '(3719.35 - 3587.94) / 3587.94 * 100'.")

@dataclass
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[[Any], Any]

    def schema(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": _inline_refs(self.args.model_json_schema()),
        }}

def _inline_refs(schema: dict) -> dict:
    defs = schema.pop("$defs", {})
    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node
    return resolve(schema)

class Toolbox:
    def __init__(self, get_store: Callable[[str], Store], stores: list[str]):
        self.get_store = get_store
        self.stores = stores
        self.tools = {t.name: t for t in [
            Tool("list_stores", "Names of all stores.", NoArgs, lambda a: self.stores),
            Tool("describe_table",
                 "Columns of a table with types, null counts and either all values (short text columns) or examples. "
                 "Call it before filtering on a column whose exact values you have not seen.",
                 TableArgs, self._describe),
            Tool("store_summary",
                 "Dashboard metrics for one store: top 5 revenue days, total revenue, unique users (people after "
                 "merging aliases), user records, unique author sets, most popular author set, best buyer with all ids.",
                 StoreArgs, self._summary),
            Tool("count_rows", "Number of rows in a table that match the filters.", FilteredArgs, self._count),
            Tool("aggregate",
                 "count/sum/mean/median/min/max/nunique of a column, optionally grouped and ranked. Use it for every "
                 "total, average, distinct count and top-N question.",
                 AggregateArgs, self._aggregate),
            Tool("list_rows", "Matching rows (at most 50) and how many rows match in total.", ListRowsArgs, self._list),
            Tool("find_person",
                 "Find customers by part of a name, e-mail, phone, address or by user id. Returns each person with "
                 "all alias user ids, orders and total spent.",
                 FindPersonArgs, self._find_person),
            Tool("calculate", "Exact arithmetic on numbers taken from tool results.", CalculateArgs,
                 lambda a: {"result": calculate(a.expression)}),
        ]}

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self.tools.values()]

    def call(self, name: str, arguments: str | dict) -> dict:
        tool = self.tools.get(name)
        if tool is None:
            return {"error": f"Unknown tool '{name}'. Tools: {list(self.tools)}"}
        try:
            raw = json.loads(arguments or "{}") if isinstance(arguments, str) else arguments
            args = tool.args.model_validate(raw)
            return {"result": tool.run(args)}
        except ValidationError as e:
            return {"error": f"Invalid arguments: {e.errors(include_url=False)}"}
        except (ValueError, KeyError, TypeError, ZeroDivisionError, json.JSONDecodeError) as e:
            return {"error": str(e)}

    def _resolve(self, store: str) -> list[Store]:
        if store.upper() == ALL:
            return [self.get_store(s) for s in self.stores]
        match = next((s for s in self.stores if s.casefold() == store.casefold()), None)
        if match is None:
            raise ValueError(f"Unknown store '{store}'. Stores: {self.stores} or {ALL}")
        return [self.get_store(match)]

    def _table(self, args: TableArgs) -> pd.DataFrame:
        return combined_view(self._resolve(args.store), args.table)

    def _describe(self, args: TableArgs) -> dict:
        df = self._table(args)
        return {"rows": len(df), "columns": describe(df)}

    def _summary(self, args: StoreArgs) -> dict:
        stores = self._resolve(args.store)
        if len(stores) > 1:
            raise ValueError("store_summary works on one store; call it once per store")
        return summarize(stores[0]).to_dict()

    def _count(self, args: FilteredArgs) -> dict:
        return {"count": len(apply_filters(self._table(args), args.filters))}

    def _aggregate(self, args: AggregateArgs) -> dict:
        df = apply_filters(self._table(args), args.filters)
        return aggregate(df, args.metric, args.column, args.group_by, args.descending, args.limit)

    def _list(self, args: ListRowsArgs) -> dict:
        df = apply_filters(self._table(args), args.filters)
        return list_rows(df, args.columns, args.sort_by, args.descending, args.limit)

    def _find_person(self, args: FindPersonArgs) -> dict:
        stores = self._resolve(args.store)
        users = combined_view(stores, "users")
        sales = combined_view(stores, "sales")
        text = args.text.strip().casefold()
        searchable = users[["name", "email", "phone", "address"]].astype("string").apply(lambda s: s.str.casefold())
        hit = searchable.apply(lambda s: s.str.contains(text, regex=False)).fillna(False).any(axis=1)
        hit |= users["id"].astype("string") == text
        people = users.loc[hit, "person"].unique()
        found = []
        for person in people[:10]:
            records = users[users["person"] == person]
            orders = sales[sales["person"] == person]
            found.append({
                "person": person,
                "user_ids": sorted(int(i) for i in records["id"]),
                "records": to_records(records[["id", "name", "email", "phone", "address"]]),
                "orders": len(orders),
                "total_spent": round(float(orders["paid_price"].sum()), 2),
            })
        return {"people_found": len(people), "people": found}
