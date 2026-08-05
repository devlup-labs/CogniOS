"""Natural-language query engine for CogniOS telemetry using Groq LLM API."""

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

from groq import Groq
from blackbox.recorder import get_blackbox_conn, get_recent_rows
from blackbox.replay import replay
from config import BLACKBOX_DB_PATH, GROQ_API_KEY, GROQ_MODEL

load_dotenv()


SYSTEM_PROMPT = """You are CogniOS AI, an expert Linux system observability and post-crash forensic analyst.
Your job is to analyze real-time Linux OS telemetry data, rolling timelines, and event chains to answer user queries accurately, concisely, and insightfully.

When diagnosing performance issues or anomalies:
1. Identify root cause metrics (CPU, RAM, Disk I/O, Zombies, Swap, Thermal pressure).
2. Assess severity and impact on system stability.
"""


def build_telemetry_context(conn: sqlite3.Connection, window_minutes: int = 30) -> str:
    context_sections = []

    # 1. Recent metrics snapshot
    try:
        rows = get_recent_rows(conn, n=5)
        if rows:
            latest = rows[-1]
            metrics_summary = (
                f"=== Current System State ===\n"
                f"Timestamp: {latest.get('timestamp')}\n"
                f"CPU Usage: {latest.get('cpu_usage_percent', 0):.1f}%\n"
                f"Memory Usage: {latest.get('memory_percent', 0):.1f}%\n"
                f"Swap Usage: {latest.get('swap_percent', 0):.1f}%\n"
                f"Disk Read: {latest.get('disk_read', 0):.2f} MB/s | Disk Write: {latest.get('disk_write', 0):.2f} MB/s\n"
                f"Net Rate: {latest.get('net_rate_mb_s', 0):.2f} MB/s\n"
                f"Processes: {latest.get('running_processes', 0)} running / {latest.get('total_processes', 0)} total / {latest.get('zombie_processes', 0)} zombies\n"
                f"Load Average (1m/5m): {latest.get('load_avg1', 0):.2f}, {latest.get('load_avg5', 0):.2f}\n"
                f"Avg Temperature: {latest.get('avg_temp') or 'N/A'} °C\n"
            )
            context_sections.append(metrics_summary)
    except Exception as e:
        context_sections.append(f"Recent metrics error: {e}")

    # 2. Replay timeline and event chain
    try:
        rep_result = replay(conn, window_minutes=window_minutes)
        timeline = rep_result.get("timeline_text", "No events logged.")
        context_sections.append(f"=== Event Chain & Pre-Crash Timeline (Last {window_minutes} min) ===\n{timeline}")
    except Exception as e:
        context_sections.append(f"Replay timeline error: {e}")

    return "\n\n".join(context_sections)


def ask_groq(
    user_content: str,
    system_prompt: str = SYSTEM_PROMPT,
    model: str = GROQ_MODEL,
    stream: bool = True,
    api_key: str | None = None
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
    messages.append({"role": "user", "content": user_content})

    if stream:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=1,
            max_completion_tokens=2048,
            top_p=1,
            stream=True,
            stop=None,
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
            max_completion_tokens=2048,
            top_p=1,
            stream=False,
            stop=None,
        )
        response_text = completion.choices[0].message.content or ""
        return response_text


def query_telemetry(
    user_query: str,
    conn: sqlite3.Connection | None = None,
    window_minutes: int = 30,
    stream: bool = True,
    model: str = GROQ_MODEL,
    api_key: str | None = None
) -> str:
    """Queries CogniOS telemetry using natural language via Groq LLM."""
    close_conn = False
    if conn is None:
        conn = get_blackbox_conn()
        close_conn = True

    try:
        context_str = build_telemetry_context(conn, window_minutes=window_minutes)
        full_user_content = (
            f"Here is the telemetry context from CogniOS BlackBox:\n\n"
            f"{context_str}\n\n"
            f"User Question: {user_query}"
        )
        return ask_groq(
            user_content=full_user_content,
            system_prompt=SYSTEM_PROMPT,
            model=model,
            stream=stream,
            api_key=api_key
        )
    finally:
        if close_conn:
            conn.close()


def main():
    """Command-line interface for CogniOS Natural Language Telemetry Query."""
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "Can you summarize the system performance and report any recent anomalies or resource spikes?"

    print(f"CogniOS Telemetry Query: '{query}'\n")
    try:
        query_telemetry(query, stream=True)
    except Exception as e:
        print(f"\nError executing query: {e}")


if __name__ == "__main__":
    main()
