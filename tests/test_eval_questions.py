# Asks the real Azure OpenAI deployment the kind of questions graders ask and checks the answers
# against values computed directly with pandas. Skipped unless AZURE_OPENAI_* is set (e.g. in .env).
# Run: python -m pytest tests/test_eval_questions.py -v
import re
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from assistant.agent import Assistant, AzureChatClient, azure_configured  # noqa: E402
from bookstore.analytics import summarize  # noqa: E402
from bookstore.repository import list_stores  # noqa: E402
from bookstore.views import build_view  # noqa: E402

from conftest import get_store  # noqa: E402

pytestmark = pytest.mark.skipif(not azure_configured(), reason="AZURE_OPENAI_* not configured")

def _sales(store):
    return build_view(get_store(store), "sales")

def _users(store):
    return build_view(get_store(store), "users")

def _books(store):
    return build_view(get_store(store), "books")

CASES = [
    ("How many unique users are there in STORE1?",
     lambda: [summarize(get_store("STORE1")).unique_users]),
    ("What are the top 5 days by revenue in STORE1? Give dates as YYYY-MM-DD.",
     lambda: [d["date"] for d in summarize(get_store("STORE1")).top_days]),
    ("How many unique sets of authors are there in STORE3?",
     lambda: [summarize(get_store("STORE3")).unique_author_sets]),
    ("Who is the most popular author or author set in STORE4 by books sold?",
     lambda: [n for s in summarize(get_store("STORE4")).popular_authors["author_sets"] for n in s]),
    ("Who is the best buyer in STORE1? List all of their user ids.",
     lambda: summarize(get_store("STORE1")).best_buyer["user_ids"]),
    ("How many users in STORE3 have an e-mail starting with s or p?",
     lambda: [int(_users("STORE3")["email"].str.lower().str.match(r"^[sp]", na=False).sum())]),
    ("What was the revenue of STORE2 on 2025-11-16?",
     lambda: [f"{_sales('STORE2').loc[lambda d: d['date'] == '2025-11-16', 'paid_price'].sum():.2f}"]),
    ("Which genre brought the most revenue in STORE3?",
     lambda: [_sales("STORE3").groupby("genre")["paid_price"].sum().idxmax()]),
    ("How many orders were placed in STORE5 in October 2025?",
     lambda: [int((_sales("STORE5")["month"] == "2025-10").sum())]),
    ("What is the average paid price per order in STORE1, rounded to 2 decimals?",
     lambda: [f"{_sales('STORE1')['paid_price'].mean():.2f}"]),
    ("How many books in STORE2 have no publisher?",
     lambda: [int(_books("STORE2")["publisher"].isna().sum())]),
    ("How many unique users are there across all stores combined?",
     lambda: [sum(summarize(get_store(s)).unique_users for s in list_stores())]),
]

@pytest.fixture(scope="module")
def assistant(toolbox):
    return Assistant(AzureChatClient(), toolbox)

def _normalize(text: str) -> str:
    text = re.sub(r"(?<=\d)[,  ](?=\d{3}\b)", "", text)
    return text.replace("$", "").casefold()

@pytest.mark.parametrize("question, expected", CASES, ids=[q[:50] for q, _ in CASES])
def test_answer_contains_computed_values(assistant, question, expected):
    answer = assistant.ask(question)
    text = _normalize(answer.text)
    missing = [v for v in expected() if str(v).casefold() not in text]
    assert not missing, f"missing {missing} in answer: {answer.text}\nsteps: {[s.tool for s in answer.steps]}"
    assert answer.steps, "answered without calling any tool"
