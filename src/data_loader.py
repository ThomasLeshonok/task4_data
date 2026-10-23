import sys
from pathlib import Path
import pandas as pd
import yaml

from clear_data import clean_store
from save_cleaned_data import save_cleaned_data

DEFAULT_SRC = Path(__file__).resolve().parent.parent / "data" / "STORE1"
RAW_FILES = {"books": "books.yaml", "users": "users.csv", "orders": "orders.parquet"}

def read_yaml(file_path):
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    with open(file_path, encoding="utf-8") as file:
        return pd.DataFrame(yaml.load(file, Loader=loader))

READERS = {".yaml": read_yaml, ".yml": read_yaml, ".csv": pd.read_csv, ".parquet": pd.read_parquet}

def read(file_path: Path) -> pd.DataFrame:
    return READERS[file_path.suffix.lower()](file_path)

def load_raw_data(src: Path) -> dict[str, pd.DataFrame]:
    return {table: read(src / file_name) for table, file_name in RAW_FILES.items()}

def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src / "clean"

    raw = load_raw_data(src)
    cleaned = clean_store(**raw)
    save_cleaned_data(cleaned, out)


if __name__ == "__main__":
    main()
