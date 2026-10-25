import json
from typing import Callable
import streamlit as st

from assistant.agent import Assistant, azure_configured
from security.limits import Limits

from .access import minutes

HISTORY_KEY = "chat"
CONTEXT_MESSAGES = 6
EXAMPLES = [
    "How many unique users are in STORE1?",
    "Top 3 genres by revenue in STORE2",
    "How many users have an e-mail starting with s or p in STORE3?",
    "Who is the best buyer in STORE4 and what are all their ids?",
]

def _show_steps(steps: list[dict]) -> None:
    if not steps:
        return
    with st.expander(f"How I got this ({len(steps)} tool call{'s' if len(steps) != 1 else ''})"):
        for step in steps:
            st.markdown(f"**`{step['tool']}`**")
            st.code(json.dumps(step["arguments"], indent=2, ensure_ascii=False), language="json")
            st.code(json.dumps(step["result"], indent=2, ensure_ascii=False, default=str)[:4000], language="json")

def _allowed(limits: Limits, ip: str, question: str) -> str | None:
    if len(question) > limits.question_max_chars:
        return f"Please keep questions under {limits.question_max_chars} characters."
    allowed, wait = limits.questions_per_ip.hit(ip)
    if not allowed:
        return f"Question limit reached for your address. Try again in {minutes(wait)} min."
    allowed, wait = limits.questions_total.hit("all")
    if not allowed:
        return "The daily question limit for this app is reached. Try again tomorrow."
    return None

def render_chat(get_assistant: Callable[[], Assistant], limits: Limits, ip: str) -> None:
    st.title("Ask the data")
    st.caption("Answers come from computed queries over the cleaned data, never from the model's memory. "
               "Open “How I got this” under an answer to see every query and its raw result.")
    if not azure_configured():
        st.warning("The assistant is off: set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT.")
        return

    history = st.session_state.setdefault(HISTORY_KEY, [])
    if not history:
        st.markdown("Try: " + " · ".join(f"*{q}*" for q in EXAMPLES))
    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            _show_steps(message.get("steps", []))

    question = st.chat_input("Ask about sales, books or customers")
    if not question:
        return
    with st.chat_message("user"):
        st.markdown(question)
    refusal = _allowed(limits, ip, question)
    with st.chat_message("assistant"):
        if refusal:
            st.warning(refusal)
            return
        context = [{"role": m["role"], "content": m["content"]} for m in history[-CONTEXT_MESSAGES:]]
        try:
            with st.spinner("Querying the data..."):
                answer = get_assistant().ask(question, context)
        except Exception as e:  # network, quota or auth errors from the model API
            st.error(f"The assistant failed: {type(e).__name__}. Try again in a moment.")
            return
        st.markdown(answer.text)
        steps = [vars(s) for s in answer.steps]
        _show_steps(steps)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer.text, "steps": steps})

def clear_chat_button() -> None:
    if st.session_state.get(HISTORY_KEY) and st.sidebar.button("Clear conversation", icon=":material/delete_sweep:"):
        st.session_state[HISTORY_KEY] = []
        st.rerun()
