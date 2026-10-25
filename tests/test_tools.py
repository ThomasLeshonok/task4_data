import json

import pytest

from assistant.calc import calculate

def call(toolbox, name, **args):
    return toolbox.call(name, json.dumps(args))

def test_schemas_have_no_refs(toolbox):
    text = json.dumps(toolbox.schemas())
    assert "$ref" not in text and "$defs" not in text

def test_store_summary_matches_dashboard(toolbox):
    result = call(toolbox, "store_summary", store="STORE1")["result"]
    assert result["unique_users"] == 3221
    assert result["best_buyer"]["user_ids"] == [48403, 48904, 50056]

def test_store_names_are_case_insensitive(toolbox):
    assert "result" in call(toolbox, "count_rows", store="store2", table="books")

def test_count_rows_with_filter(toolbox, store1):
    result = call(toolbox, "count_rows", store="STORE1", table="users",
                  filters={"conditions": [{"column": "email", "op": "startswith", "value": ["s", "p"]}]})
    assert result["result"]["count"] == store1.users["email"].str.match(r"^[sp]", na=False).sum()

def test_all_stores_people_are_store_qualified(toolbox):
    total = call(toolbox, "aggregate", store="ALL", table="users", metric="nunique", column="person")["result"]["value"]
    per_store = sum(call(toolbox, "store_summary", store=s)["result"]["unique_users"] for s in toolbox.stores)
    assert total == per_store

def test_find_person_returns_all_aliases(toolbox):
    people = call(toolbox, "find_person", store="STORE1", text="cyril hegmann")["result"]["people"]
    assert people[0]["user_ids"] == [48403, 48904, 50056]
    assert people[0]["total_spent"] == 1317.59

def test_errors_are_returned_not_raised(toolbox):
    assert "Unknown store" in call(toolbox, "store_summary", store="STORE9")["error"]
    assert "Invalid arguments" in call(toolbox, "aggregate", store="STORE1", table="sales", metric="median_ish")["error"]
    assert "Unknown tool" in toolbox.call("drop_table", "{}")["error"]

@pytest.mark.parametrize("expression, expected", [("1 + 2 * 3", 7), ("round(10 / 3, 2)", 3.33), ("-(2 ** 3)", -8)])
def test_calculate(expression, expected):
    assert calculate(expression) == expected

@pytest.mark.parametrize("expression", ["__import__('os')", "open('x')", "(1).real", "9 ** 999", "a + 1"])
def test_calculate_rejects_code(expression):
    with pytest.raises(ValueError):
        calculate(expression)
