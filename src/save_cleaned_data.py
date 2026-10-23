from pathlib import Path
import pandas as pd

from bookstore.repository import clean_file

def save_cleaned_data(tables: dict[str, pd.DataFrame], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(clean_file(out_dir, name), index=False)
        print(f"{name}: {df.shape}  nulls:\n{df.isna().sum()[lambda s: s > 0].to_dict()}\n")
