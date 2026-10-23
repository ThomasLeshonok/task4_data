from itertools import combinations
import pandas as pd

from .names import strip_titles

USER_FIELDS = ["name", "address", "phone", "email"]

def _find(parent, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x

def reconcile_users(users: pd.DataFrame) -> pd.Series:
    ids = users["id"].astype(int).tolist()
    parent = {i: i for i in ids}
    for fields in combinations(USER_FIELDS, len(USER_FIELDS) - 1):
        cols = list(fields)
        for _, group in users.dropna(subset=cols).groupby(cols)["id"]:
            root = _find(parent, int(group.iloc[0]))
            for other in group.iloc[1:]:
                parent[_find(parent, int(other))] = root
    roots = pd.Series([_find(parent, i) for i in ids], index=ids)
    return roots.groupby(roots).transform("min").rename("person")

def author_sets(books: pd.DataFrame) -> pd.Series:
    names = strip_titles(books["author"].str.split(",").explode()).dropna()
    names = names[names != ""]
    sets = {i: tuple(sorted(set(group))) for i, group in names.groupby(level=0)}
    return pd.Series(sets, dtype=object).reindex(books.index).rename("authors")
