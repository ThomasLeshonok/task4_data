import sys
from functools import cache
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bookstore.repository import list_stores, load_store  # noqa: E402

get_store = cache(load_store)

@pytest.fixture(scope="session")
def store1():
    return get_store("STORE1")

@pytest.fixture(scope="session")
def toolbox():
    from assistant.tools import Toolbox
    return Toolbox(get_store, list_stores())
