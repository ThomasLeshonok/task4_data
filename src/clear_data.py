import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
import pandas as pd

from bookstore.names import strip_titles

NULL_TOKENS = {"", "NULL", "NONE", "NAN", "N/A", "NA", "-", "--"}
CURRENCY_RX = re.compile(r'(\$|€|USD|EUR)', re.I)
EXCHANGE_RATE = {'$': 1.0, 'usd': 1.0, '€': 1.2, 'eur': 1.2}

_ADDR_RULES = [
    (r"\s*,\s*",                                 ", ",         0),
    (r"(?:,\s*)+,",                              ",",          0),
    (r"^(?:apartment|apt)\.?\s*#?\s*(\d+)\s+",   r"Apt. \1 ",  re.I),
    (r"^(?:suite|ste|unit)\.?\s*#?\s*(\d+)\s+",  r"Suite \1 ", re.I),
    (r"([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)$",
     lambda m: f"{m[1].upper()} {m[2]}",                       0),
]
ADDR_RX = re.compile(
    r"^(?:(?:Apt\.|Suite) \d+ )?"
    r"\d+ [^,]+, "
    r"[^,]+, "
    r"[A-Z]{2} \d{5}(?:-\d{4})?$"
)
TIME_RE = r"(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?\s*(?P<ap>[AaPp])?\.?[Mm]?\.?"

DATE_FORMATS = [
    (r"\d{4}-\d{1,2}-\d{1,2}", "%Y-%m-%d"),
    (r"\d{1,2}-[A-Za-z]{3}-\d{4}", "%d-%b-%Y"),
    (r"\d{1,2}-[A-Za-z]{4,9}-\d{4}", "%d-%B-%Y"),
    (r"\d{1,2}/\d{1,2}/\d{2}", "%m/%d/%y"),
    (r"\d{1,2}/\d{1,2}/\d{4}", "%m/%d/%Y"),
    (r"\d{1,2}\.\d{1,2}\.\d{4}", "%d.%m.%Y"),
    (
        r"[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{1,2}:\d{2}:\d{2}\s+\d{4}",
        "%a %b %d %H:%M:%S %Y",
    ),
]

def clean_text(data, columns):
    for c in columns:
        data[c] = data[c].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
        data[c] = data[c].mask(data[c].str.upper().isin(NULL_TOKENS))
    return data

def clean_name(data, columns):
    data = clean_text(data, columns)
    for c in columns:
        data[c] = strip_titles(data[c])
    return data

def clean_address(data, columns):
    s = clean_text(data, columns).astype("string")
    s = s.iloc[:, 0].str.cat(s.iloc[:, 1:], sep=", ")

    for pat, repl, flags in _ADDR_RULES:
        s = s.str.replace(pat, repl, regex=True, flags=flags)

    s = s.str.strip(" ,")
    return s.where(s.str.match(ADDR_RX, na=False))

def clean_email(data, columns):
    for c in columns:
        data[c] = data[c].str.lower()
        bad_email = ~data[c].str.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", na=False)
        data.loc[bad_email, c] = pd.NA
    return data

def clean_phone_data(data, columns):
    for c in columns:
        digits = data[c].str.replace(r"\D", "", regex=True)
        digits = digits.str[-10:].where(digits.str.len().isin([10, 11]))
        data[c] = digits.str.replace(r"^(\d{3})(\d{3})(\d{4})$", r"\1-\2-\3", regex=True)
    return data

def exchange_currency(cur, rate):
    return ((Decimal(cur) * Decimal(rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if cur and rate else None)

def clean_currency(s):
    s = str(s)
    m = CURRENCY_RX.search(s)
    rate = EXCHANGE_RATE.get(m.group(1).lower()) if m else None
    s = re.sub(r'(?<=\d)\s*[€$¢]\s*(?=\d)', '.', s)
    s = CURRENCY_RX.sub('', s).replace('¢', '')
    s = re.sub(r'[^\d.,]', '', s).replace(',', '.')
    return exchange_currency(s, rate)

def parse_date(ts: pd.Series) -> pd.Series:
    date = pd.Series(pd.NaT, index=ts.index, dtype="datetime64[ns]")
    for pattern, date_format in DATE_FORMATS:
        missing = date.isna()
        values = ts[missing].str.extract(f"({pattern})", expand=False)
        date.loc[missing] = pd.to_datetime(values, format=date_format, errors="coerce")
    return date

def parse_time(ts: pd.Series) -> pd.Series:
    t = ts.str.extract(TIME_RE)
    h = pd.to_numeric(t["h"]).astype("Int64")
    ap = t["ap"].str.upper()
    pm = ((ap == "P") & (h < 12)).fillna(False).astype(bool)
    am12 = ((ap == "A") & (h == 12)).fillna(False).astype(bool)
    h = h.mask(pm, h + 12).mask(am12, 0)
    secs = h * 3600 + pd.to_numeric(t["m"]).astype("Int64") * 60 + pd.to_numeric(t["s"]).fillna(0).astype("Int64")
    return pd.to_timedelta(secs.astype("float"), unit="s")

def clean_timestamp_data(data):
    date = parse_date(data["timestamp"].astype("string"))
    data["timestamp"] = date + parse_time(data["timestamp"].astype("string"))
    data["date"] = date.dt.normalize().dt.date
    return data


def clear_ruby_formatting(data):
    data.columns = data.columns.str.lstrip(":")
    return data

def convert_into_numeric(data, types):
    for column, column_type in types.items():
        data[column] = pd.to_numeric(data[column], errors="coerce").astype(column_type)
    return data

def convert_into_type(data, types):
    for column, column_type in types.items():
        data[column] = data[column].astype(column_type)
    return data

def nullify_invalid_years(data, column, min_year=1400, max_year=None):
    max_year = max_year or date.today().year
    data[column] = data[column].where(data[column].between(min_year, max_year))
    return data

def null_non_positive(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    data = data.copy()
    data[columns] = data[columns].mask(data[columns] <= 0)
    return data

def drop_missing_and_duplicate_values(data, columns, keep="first"):
    for c in columns:
        data = data.dropna(subset=[c]).drop_duplicates(subset=[c], keep=keep)
    return data


def build_lookup(source, key, value):
    src = source.loc[source[value].notna(), [key, value]]
    src[value] = clean_address(source[[value]], [value])
    return src.dropna(subset=[value]).drop_duplicates(key).set_index(key)[value]

def fill_missing_addresses(data, source, cols, on):
    data_id, src_id = on
    lookups = {}
    for col, src_col in cols.items():
        data[col] = clean_address(data[[col]], [col])
        mask = data[col].isna()
        if not mask.any():
            continue
        if src_col not in lookups:
            lookups[src_col] = build_lookup(source, src_id, src_col)
        data.loc[mask, col] = data.loc[mask, data_id].map(lookups[src_col])
    return data

def keep_valid_references(data, refs):
    mask = pd.Series(True, index=data.index)
    for column, (source, key) in refs.items():
        mask &= data[column].isin(source[key])
    return data[mask]


def clean_books_data(data):
    data = clear_ruby_formatting(data)
    data = convert_into_numeric(data, {"id": "Int64", "year": "Int16"})
    data = clean_text(data, ["title", "author", "genre", "publisher"])
    data = nullify_invalid_years(data, "year")
    data = drop_missing_and_duplicate_values(data, ["id"])
    data = convert_into_type(data, {"genre": "category"})
    return data.reset_index(drop=True)

def clean_users_data(data):
    data = clean_text(data, ["phone", "email"])
    data = clean_name(data, ["name"])
    data["address"] = clean_address(data[["address"]], ["address"])
    data = convert_into_numeric(data, {"id": "Int64"})
    data = clean_email(data, ["email"])
    data = clean_phone_data(data, ["phone"])
    data = drop_missing_and_duplicate_values(data, ["id"])
    return data.reset_index(drop=True)

def clean_orders_data(data, users):
    data["unit_price"] = data["unit_price"].apply(clean_currency)
    data = convert_into_numeric(data, {
        "id": "Int64",
        "user_id": "Int64",
        "book_id": "Int64",
        "quantity": "Int16",
        "unit_price": "float64",
    })
    data = null_non_positive(data, ["quantity", "unit_price"])
    data["paid_price"] = (data["quantity"] * data["unit_price"]).round(2)
    data = drop_missing_and_duplicate_values(data, ["id"])
    data = clean_timestamp_data(data)
    data = data.dropna(subset=["id", "user_id", "book_id"])
    data = fill_missing_addresses(data, users, {"shipping": "address"}, on=("user_id", "id"))
    return data.reset_index(drop=True)

def clean_store(books, users, orders) -> dict[str, pd.DataFrame]:
    books = clean_books_data(books)
    users = clean_users_data(users)
    orders = clean_orders_data(orders, users)
    users = fill_missing_addresses(users, orders, {"address": "shipping"}, on=("id", "user_id"))
    orders = keep_valid_references(orders, {
        "user_id": (users, "id"),
        "book_id": (books, "id"),
    })
    return {"books": books, "users": users, "orders": orders}
