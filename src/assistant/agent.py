import json
import os
from dataclasses import dataclass, field
from typing import Protocol

from .tools import Toolbox

MAX_ROUNDS = 8
MAX_TOOL_RESULT_CHARS = 12_000
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You answer questions about bookstore data. Stores: {stores}.

Tables (per store, or ALL for every store combined):
- books: id, title, author (raw), authors (normalized set, comma separated), author_count, genre, publisher, year.
- users: id, name, address, phone, email, person, aliases. One real customer can have several user records
  (aliases) that differ in at most one of name, address, phone, email; they share the same `person`.
- sales: one row per order with date, month (YYYY-MM), year, weekday, customer and book fields,
  quantity, unit_price, paid_price (= quantity * unit_price, USD), shipping.

Rules:
- Every number, name and id in your answer must come from a tool result in this conversation.
  Never count, add, average or estimate yourself: use count_rows / aggregate, and calculate for arithmetic
  on numbers from tool results.
- "Users", "customers", "buyers" mean real people: count distinct `person`, not rows.
- Revenue = sum of paid_price. Books sold = sum of quantity. "Author set" = the `authors` value.
- Before filtering on a text column whose exact values you have not seen, call describe_table.
- If the question names no store, answer for every store (one call per store, or store ALL for a total).
- Dates are YYYY-MM-DD. Money has 2 decimals.
- If the tools cannot answer the question, say so. Do not guess.
- Answer briefly in the language of the question.
"""

class ChatClient(Protocol):
    def complete(self, messages: list[dict], tools: list[dict]): ...

class AzureChatClient:
    def __init__(self):
        from openai import AzureOpenAI

        self.client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )
        self.deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        temperature = os.environ.get("AZURE_OPENAI_TEMPERATURE", "0")
        self.extra = {"temperature": float(temperature)} if temperature else {}

    def complete(self, messages: list[dict], tools: list[dict]):
        response = self.client.chat.completions.create(
            model=self.deployment, messages=messages, tools=tools, **self.extra
        )
        return response.choices[0].message

class GroqChatClient:
    """Groq's OpenAI-compatible API (free tier at console.groq.com)."""

    def __init__(self):
        from openai import OpenAI

        self.client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url=GROQ_BASE_URL)
        self.model = os.environ.get("GROQ_MODEL") or GROQ_DEFAULT_MODEL
        temperature = os.environ.get("GROQ_TEMPERATURE", "0")
        self.extra = {"temperature": float(temperature)} if temperature else {}

    def complete(self, messages: list[dict], tools: list[dict]):
        response = self.client.chat.completions.create(
            model=self.model, messages=messages, tools=tools, **self.extra
        )
        return response.choices[0].message

def azure_configured() -> bool:
    return all(os.environ.get(k) for k in ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"))

def groq_configured() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))

def llm_configured() -> bool:
    return groq_configured() or azure_configured()

def make_chat_client() -> ChatClient:
    """Groq when GROQ_API_KEY is set, otherwise Azure OpenAI."""
    return GroqChatClient() if groq_configured() else AzureChatClient()

@dataclass
class Step:
    tool: str
    arguments: dict
    result: dict

@dataclass
class Answer:
    text: str
    steps: list[Step] = field(default_factory=list)

class Assistant:
    def __init__(self, client: ChatClient, toolbox: Toolbox):
        self.client = client
        self.toolbox = toolbox
        self.system = SYSTEM_PROMPT.format(stores=", ".join(toolbox.stores))

    def ask(self, question: str, history: list[dict] | None = None) -> Answer:
        messages = [{"role": "system", "content": self.system}, *(history or []), {"role": "user", "content": question}]
        tools = self.toolbox.schemas()
        steps = []
        for _ in range(MAX_ROUNDS):
            message = self.client.complete(messages, tools)
            if not message.tool_calls:
                return Answer(message.content or "", steps)
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                    for c in message.tool_calls
                ],
            })
            for call in message.tool_calls:
                result = self.toolbox.call(call.function.name, call.function.arguments)
                steps.append(Step(call.function.name, _parse(call.function.arguments), result))
                content = json.dumps(result, ensure_ascii=False, default=str)
                if len(content) > MAX_TOOL_RESULT_CHARS:
                    content = content[:MAX_TOOL_RESULT_CHARS] + '... (truncated: narrow the query or lower the limit)'
                messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
        return Answer("I could not finish this question within the allowed number of steps. Please narrow it down.", steps)

def _parse(arguments: str) -> dict:
    try:
        return json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {"raw": arguments}
