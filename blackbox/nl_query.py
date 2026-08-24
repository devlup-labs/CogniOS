"""Natural-language query engine for CogniOS telemetry using Groq LLM API."""

import os
import sys
import sqlite3
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from groq import Groq
from blackbox.recorder import get_blackbox_conn
from blackbox.replay import build_llm_context
from config import GROQ_API_KEY, GROQ_MODEL

load_dotenv()


SYSTEM_PROMPT = """You are CogniOS AI, an expert Linux system observability and post-crash forensic analyst.
Your job is to analyze real-time Linux OS telemetry data, rolling timelines, and event chains to answer user queries accurately, concisely, and insightfully.

When diagnosing performance issues or anomalies:
1. Identify root cause metrics (CPU, RAM, Disk I/O, Zombies, Swap, Thermal pressure).
2. Assess severity and impact on system stability.
"""
from blackbox.replay import build_llm_context  # replace old replay import

def query_telemetry(
    user_query: str,
    conn: sqlite3.Connection | None = None,
    stream: bool = True,
    model: str = GROQ_MODEL,
    api_key: str | None = None,
    crash_time: float | None = None,
    crash_info: dict | None = None
) -> str:
    close_conn = False
    if conn is None:
        conn = get_blackbox_conn()
        close_conn = True
    try:
        context_str = build_llm_context(
            conn,
            crash_time=crash_time,
            heartbeat_gap=crash_info.get('heartbeat_gap') if crash_info else None,
            systemd_crash=crash_info.get('systemd_crash') if crash_info else None
        )
        full_user_content = (
            f"Here is the telemetry context from CogniOS BlackBox:\n\n"
            f"{context_str}\n\n"
            f"User Question: {user_query}"
        )
        _chat_history.append({"role": "user", "content": full_user_content})
        response = ask_groq(
            user_content=None,
            system_prompt=SYSTEM_PROMPT,
            model=model,
            stream=stream,
            api_key=api_key,
            history=_chat_history
        )
        _chat_history.append({"role": "assistant", "content": response})
        return response
    finally:
        if close_conn:
            conn.close()


def ask_groq(
    user_content: str,
    system_prompt: str = SYSTEM_PROMPT,
    model: str = GROQ_MODEL,
    stream: bool = True,
    api_key: str | None = None,
    history: list | None = None
) -> str:
    effective_api_key = api_key or os.environ.get("GROQ_API_KEY") or GROQ_API_KEY
    if not effective_api_key or effective_api_key == "your_groq_api_key_here":
        raise ValueError(
            "GROQ_API_KEY is not set or contains the default placeholder. "
            "Please set your GROQ_API_KEY in the .env file."
        )

    client = Groq(api_key=effective_api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages += history
    elif user_content:
        messages.append({"role": "user", "content": user_content})

    if stream:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_completion_tokens=3000,
            top_p=1,
            stream=True,
            stop=None,
            reasoning_format="hidden",
            # reasoning_effort="low",
        )

        full_response = []
        for chunk in completion:
            content = chunk.choices[0].delta.content or ""
            print(content, end="", flush=True)
            full_response.append(content)
        print()  # Newline after streaming finishes
        return "".join(full_response)
    else:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=1,
            max_completion_tokens=1500,
            top_p=1,
            stream=False,
            stop=None,
            reasoning_format="hidden",
        )
        response_text = completion.choices[0].message.content or ""
        return response_text
_chat_history = []


def main():
    """Interactive CLI for CogniOS Natural Language Telemetry Query."""
    if len(sys.argv) > 1:
        # one-shot mode: single query, no follow-up loop
        query = " ".join(sys.argv[1:])
        print(f"CogniOS Telemetry Query: '{query}'\n")
        try:
            query_telemetry(query, stream=True)
        except Exception as e:
            print(f"\nError executing query: {e}")
        return

    # interactive mode: no args given, drop into a REPL
    print("CogniOS Telemetry Query — interactive mode (type 'exit' or Ctrl+C to quit)\n")
    while True:
        try:
            query = input("\n> ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                break
            query_telemetry(query, stream=True)
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"\nError executing query: {e}")


if __name__ == "__main__":
    main()
