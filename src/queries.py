import json
import sys

from bookstore.analytics import summarize
from bookstore.repository import list_stores, load_store

def main() -> None:
    for name in sys.argv[1:] or list_stores():
        print(json.dumps(summarize(load_store(name)).to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
