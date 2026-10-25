import re
from typing import Any, Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

Op = Literal[
    "eq", "ne", "gt", "gte", "lt", "lte", "between", "in",
    "contains", "startswith", "endswith", "regex", "isnull",
]
Metric = Literal["count", "sum", "mean", "median", "min", "max", "nunique"]

MAX_ROWS = 50

class Condition(BaseModel):
    column: str | list[str] = Field(description="Column name, or several columns where any may match.")
    op: Op
    value: Any = Field(None, description="Not used for isnull. A list for between [low, high] and in. "
                                         "contains/startswith/endswith also take a list: any item matches.")
    negate: bool = Field(False, description="Keep rows that do NOT match.")

    def label(self) -> str:
        column = " or ".join(self.column) if isinstance(self.column, list) else self.column
        value = "" if self.op == "isnull" else f" {self.value}"
        return f"{'not ' if self.negate else ''}{column} {self.op}{value}"

class FilterSpec(BaseModel):
    conditions: list[Condition] = Field(default_factory=list)
    match: Literal["all", "any"] = Field("all", description="all = AND between conditions, any = OR.")

    def is_empty(self) -> bool:
        return not self.conditions

def check_columns(df: pd.DataFrame, columns) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Unknown column(s) {missing}. Available: {list(df.columns)}")

def _as_list(value) -> list:
    return list(value) if isinstance(value, (list, tuple, set)) else [value]

def _is_text(s: pd.Series) -> bool:
    return pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s) or isinstance(s.dtype, pd.CategoricalDtype)

def _coerce(s: pd.Series, value):
    if isinstance(value, (list, tuple)):
        return [_coerce(s, v) for v in value]
    if pd.api.types.is_datetime64_any_dtype(s):
        return pd.Timestamp(value)
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        return float(value)
    return value

def _text(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.casefold()

def _match_one(s: pd.Series, op: str, value) -> pd.Series:
    if op == "isnull":
        return s.isna()
    if op in ("contains", "startswith", "endswith", "regex"):
        text = _text(s)
        hits = pd.Series(False, index=s.index)
        for item in _as_list(value):
            item = str(item)
            if op == "regex":
                hit = text.str.contains(item, flags=re.IGNORECASE, regex=True)
            elif op == "contains":
                hit = text.str.contains(item.casefold(), regex=False)
            else:
                hit = getattr(text.str, op)(item.casefold())
            hits |= hit.fillna(False).astype(bool)
        return hits
    if _is_text(s) and op in ("eq", "ne", "in"):
        text = _text(s)
        wanted = [str(v).strip().casefold() for v in _as_list(value)]
        hit = text.isin(wanted).fillna(False).astype(bool)
        return ~hit if op == "ne" else hit
    value = _coerce(s, value)
    if op == "between":
        low, high = value
        hit = s.between(low, high)
    elif op == "in":
        hit = s.isin(value)
    else:
        hit = {"eq": s.eq, "ne": s.ne, "gt": s.gt, "gte": s.ge, "lt": s.lt, "lte": s.le}[op](value)
    return pd.Series(hit, index=s.index).fillna(False).astype(bool)

def condition_mask(df: pd.DataFrame, cond: Condition) -> pd.Series:
    columns = _as_list(cond.column)
    check_columns(df, columns)
    mask = pd.Series(False, index=df.index)
    for column in columns:
        mask |= _match_one(df[column], cond.op, cond.value)
    return ~mask if cond.negate else mask

def apply_filters(df: pd.DataFrame, spec: FilterSpec | None) -> pd.DataFrame:
    if spec is None or spec.is_empty():
        return df
    masks = [condition_mask(df, c) for c in spec.conditions]
    combined = np.logical_and.reduce(masks) if spec.match == "all" else np.logical_or.reduce(masks)
    return df[combined]

def to_records(df: pd.DataFrame) -> list[dict]:
    out = df.copy()
    for column in out.columns:
        s = out[column]
        if pd.api.types.is_datetime64_any_dtype(s):
            only_dates = (s.dropna() == s.dropna().dt.normalize()).all()
            out[column] = s.dt.strftime("%Y-%m-%d" if only_dates else "%Y-%m-%d %H:%M:%S")
        elif pd.api.types.is_float_dtype(s):
            out[column] = s.round(2)
    out = out.astype(object).where(out.notna(), None)
    return [{k: (v.item() if isinstance(v, np.generic) else v) for k, v in row.items()} for row in out.to_dict("records")]

def aggregate(df: pd.DataFrame, metric: str, column: str | None = None, group_by: list[str] | None = None,
              descending: bool = True, limit: int | None = 10) -> dict:
    group_by = group_by or []
    if metric != "count" and not column:
        raise ValueError(f"metric '{metric}' needs a column")
    check_columns(df, [c for c in [column, *group_by] if c])
    name = metric if metric == "count" else f"{metric}_{column}"

    if not group_by:
        if metric == "count":
            value = len(df) if not column else int(df[column].notna().sum())
        else:
            value = getattr(df[column], metric)()
        return {"value": _scalar(value), "rows_used": len(df)}

    grouped = df.groupby(group_by, dropna=False, observed=True)
    if metric == "count":
        result = grouped.size() if not column else grouped[column].count()
    else:
        result = getattr(grouped[column], metric)()
    result = result.rename(name).reset_index().sort_values(name, ascending=not descending, kind="stable")

    total_groups = len(result)
    note = None
    if limit and total_groups > limit:
        cutoff = result[name].iloc[limit - 1]
        keep = limit + int((result[name].iloc[limit:] == cutoff).sum())
        if keep > limit:
            note = f"{keep - limit} extra row(s) included because they tie with row {limit}"
        result = result.head(keep)
    return {"rows": to_records(result), "total_groups": total_groups, "rows_used": len(df), "note": note}

def _scalar(value):
    if value is None or (isinstance(value, float) and np.isnan(value)) or value is pd.NA:
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, np.generic):
        value = value.item()
    return round(value, 2) if isinstance(value, float) else value

def list_rows(df: pd.DataFrame, columns: list[str] | None = None, sort_by: str | None = None,
              descending: bool = False, limit: int = 20) -> dict:
    if columns:
        check_columns(df, columns)
    if sort_by:
        check_columns(df, [sort_by])
        df = df.sort_values(sort_by, ascending=not descending, kind="stable")
    limit = max(1, min(limit, MAX_ROWS))
    shown = df[columns] if columns else df
    return {"rows": to_records(shown.head(limit)), "total_matching": len(df), "shown": min(limit, len(df))}

def describe(df: pd.DataFrame, max_values: int = 40) -> list[dict]:
    columns = []
    for column in df.columns:
        s = df[column]
        unique = s.dropna().unique()
        info = {"column": column, "type": str(s.dtype), "nulls": int(s.isna().sum()), "distinct": len(unique)}
        if len(unique) <= max_values and _is_text(s):
            info["values"] = sorted(map(str, unique))
        else:
            info["examples"] = to_records(pd.DataFrame({column: unique[:3]}))
        columns.append(info)
    return columns
