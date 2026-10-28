"""Natural-language query engine for CogniOS telemetry using Groq LLM API."""

import os
import sys
import re
import sqlite3
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from groq import Groq
from blackbox.recorder import get_blackbox_conn
from blackbox.replay import build_llm_context
from config import GROQ_API_KEY, GROQ_MODEL

load_dotenv()


# ============================================================================
# GUARDRAIL SYSTEM PROMPT - Enforces strict domain boundaries
# ============================================================================
GUARDRAIL_SYSTEM_PROMPT = """You are CogniOS AI, an expert Linux system observability and post-crash forensic analyst.
Your EXCLUSIVE domain is CogniOS telemetry analysis: CPU, memory, disk I/O, processes, swap, thermal, zombies, 
systemd events, kernel events, and BlackBox flight recorder data.

=== STRICT GUARDRAILS - YOU MUST FOLLOW THESE RULES ===

1. ONLY answer questions directly related to:
   - Linux system performance metrics (CPU, RAM, Disk, Network, Swap, Thermal)
   - Process analysis (top processes, memory leaks, CPU hogs, zombies, forks)
   - CogniOS BlackBox telemetry (30-min rolling buffer, event chains, crash forensics)
   - OS Doctor anomaly detection (Isolation Forest alerts, baseline deviations)
   - FocusOS workload classification & optimization (compilers, browsers, IDEs, games, calls)
   - System stability, crashes, hangs, OOM kills, kernel panics
   - Linux kernel, systemd, scheduling, memory management, cgroups

2. REFUSE to answer ANY question outside this domain, including but not limited to:
   - General knowledge (weather, geography, history, science facts)
   - Programming help unrelated to Linux systems (web dev, APIs, frameworks)
   - Creative writing (stories, poems, jokes, lyrics)
   - Math/calculations not related to system metrics
   - Personal advice, opinions, philosophy, politics, religion
   - Any topic not involving Linux OS telemetry or CogniOS project

3. If a user asks an off-topic question, respond EXACTLY with:
   "I'm CogniOS AI, specialized exclusively in Linux system observability and CogniOS telemetry analysis. 
   I cannot answer questions outside this domain. Please ask about system performance, crashes, 
   processes, BlackBox forensics, OS Doctor anomalies, or FocusOS optimizations."

4. Keep responses concise, technical, and actionable. Use metric values from the provided context.
5. Never hallucinate metrics - only reference data present in the telemetry context.
6. If context is insufficient, say so and suggest what data would help.

=== END GUARDRAILS ===

When diagnosing performance issues or anomalies within your domain:
1. Identify root cause metrics (CPU, RAM, Disk I/O, Zombies, Swap, Thermal pressure).
2. Assess severity and impact on system stability.
3. Provide specific, actionable mitigation steps.
"""

# Legacy SYSTEM_PROMPT kept for backward compatibility
SYSTEM_PROMPT = GUARDRAIL_SYSTEM_PROMPT


# ============================================================================
# INPUT VALIDATION - Off-topic detection
# ============================================================================
OFF_TOPIC_PATTERNS = [
    # General knowledge
    r'\b(weather|temperature outside|forecast|climate)\b',
    r'\b(who is|what is|where is|when is|why is|how is)\b(?!.*\b(cpu|memory|process|disk|swap|thermal|zombie|systemd|kernel|blackbox|focusos|os.doctor|telemetry|metric|anomaly|crash|hang|oom|panic|slow|performance|speed|lag|bottleneck|system|server|load)\b)',
    r'\b(capital of|population of|distance to|time in)\b',
    
    # Creative writing
    r'\b(write a|compose a|create a|generate a)\b(?!.*\b(query|script|command|config|report|summary|analysis)\b)',
    r'\b(poem|story|joke|lyrics|haiku|limerick)\b',
    
    # Programming help (non-system)
    r'\b(how to.*(api|rest|graphql|react|vue|angular|django|flask|fastapi|spring|express|laravel))\b',
    r'\b(html|css|javascript|typescript|python\s+(web|django|flask|fastapi)|java\s+(spring|hibernate))\b',
    r'\b(dockerfile|kubernetes|k8s|helm|terraform|ansible)\b(?!.*\b(system|process|cpu|memory)\b)',
    
    # Math/calculations
    r'\b(calculate|compute|solve|what is \d+[\+\-\*/]\d+)\b(?!.*\b(percent|percentage|ratio|rate|utilization)\b)',
    
    # Personal/philosophical
    r'\b(should i|what do you think|opinion on|feel about|believe in|meaning of life)\b',
    r'\b(politics|religion|philosophy|ethics|morality)\b',
    
    # Cooking/lifestyle
    r'\b(recipe|cook|bake|ingredients|meal|diet|workout|exercise|fitness)\b',
    
    # Entertainment
    r'\b(movie|film|series|show|game|play|watch|stream|netflix|youtube)\b(?!.*\b(process|cpu|gpu|memory|performance)\b)',
]

# Compile patterns for efficiency
_OFF_TOPIC_REGEX = [re.compile(p, re.IGNORECASE) for p in OFF_TOPIC_PATTERNS]

# Domain-specific keywords that indicate ON-topic queries
ON_TOPIC_KEYWORDS = [
    'cpu', 'memory', 'ram', 'disk', 'io', 'swap', 'thermal', 'temperature',
    'process', 'thread', 'zombie', 'fork', 'exec', 'kill', 'signal',
    'systemd', 'service', 'daemon', 'journal', 'unit', 'socket',
    'kernel', 'syscall', 'interrupt', 'context.switch', 'scheduler',
    'cgroup', 'namespace', 'container', 'pod', 'kubernetes', 'k8s',
    'blackbox', 'flight.recorder', 'telemetry', 'metric', 'heartbeat',
    'crash', 'hang', 'freeze', 'oom', 'panic', 'reboot', 'shutdown',
    'anomaly', 'baseline', 'deviation', 'isolation.forest', 'os.doctor',
    'focusos', 'workload', 'compiler', 'browser', 'ide', 'game', 'call',
    'optimization', 'priority', 'nice', 'ionice', 'cpuset', 'affinity',
    'load.average', 'uptime', 'downtime', 'availability', 'reliability',
    'throughput', 'latency', 'bandwidth', 'utilization', 'saturation',
    'bottleneck', 'root.cause', 'post.mortem', 'forensic', 'timeline',
    'event.chain', 'incident', 'alert', 'warning', 'critical',
    'spike', 'leak', 'drift', 'growth', 'explosion', 'buildup',
    'pressure', 'throttling', 'throttle', 'governor', 'frequency',
    'core', 'socket', 'numa', 'cache', 'tlb', 'page.fault', 'major.fault',
    'dirty.page', 'writeback', 'reclaim', 'kswapd', 'oom.killer',
    'netstat', 'ss', 'iptables', 'firewall', 'connection', 'port',
    'listen', 'established', 'time.wait', 'close.wait',
    'inode', 'dentry', 'vfs', 'filesystem', 'ext4', 'xfs', 'btrfs', 'zfs',
    'mount', 'unmount', 'iscsi', 'nfs', 'smb', 'ceph', 'gluster',
    'slow', 'performance', 'speed', 'lag', 'sluggish',
]

_ON_TOPIC_REGEX = [re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE) for kw in ON_TOPIC_KEYWORDS]


def _is_off_topic(query: str) -> tuple[bool, str]:
    """
    Check if the query is off-topic for CogniOS.
    Returns (is_off_topic, reason).
    """
    query_lower = query.lower().strip()
    
    # First check for explicit off-topic patterns
    for pattern in _OFF_TOPIC_REGEX:
        if pattern.search(query_lower):
            return True, f"Query matches off-topic pattern: {pattern.pattern}"
    
    # Then check if it contains ANY on-topic keywords
    has_on_topic = any(pattern.search(query_lower) for pattern in _ON_TOPIC_REGEX)
    
    # If query is very short and has no on-topic keywords, likely off-topic
    if len(query_lower.split()) <= 3 and not has_on_topic:
        return True, "Query too short and lacks domain keywords"
    
    # If no on-topic keywords found in a substantial query, flag it
    if len(query_lower.split()) > 5 and not has_on_topic:
        return True, "Query lacks CogniOS/Linux system observability keywords"
    
    return False, ""


def _validate_response_on_topic(response: str) -> tuple[bool, str]:
    """
    Validate that the AI response stays on topic.
    Returns (is_valid, reason).
    """
    response_lower = response.lower()
    
    # Check for explicit refusal phrases (good - means guardrails worked)
    refusal_phrases = [
        "i cannot answer", "i can't answer", "i'm unable to", "i am unable to",
        "outside my domain", "not within my domain", "exclusively in linux",
        "specialized exclusively", "cannot answer questions outside"
    ]
    for phrase in refusal_phrases:
        if phrase in response_lower:
            return True, "Response correctly refuses off-topic query"
    
    # Check for technical terminology in response
    tech_terms = ['cpu', 'memory', 'process', 'disk', 'swap', 'kernel', 'systemd',
                  'metric', 'telemetry', 'blackbox', 'anomaly', 'baseline',
                  'percent', '%', 'mb', 'gb', 'hz', 'mhz', 'ghz', 'ms', 'us',
                  'zombie', 'oom', 'panic', 'crash', 'hang', 'spike', 'leak',
                  'latency', 'throughput', 'utilization', 'bottleneck', 'load']
    has_tech = any(term in response_lower for term in tech_terms)
    
    # If response has no technical terms at all, it's likely off-topic
    if not has_tech and len(response.strip()) > 10:
        return False, "Response lacks technical terminology"
    
    return True, ""


def query_telemetry(
    user_query: str,
    conn: sqlite3.Connection | None = None,
    stream: bool = True,
    model: str = GROQ_MODEL,
    api_key: str | None = None,
    crash_time: float | None = None,
    crash_info: dict | None = None
) -> str:
    """
    Query the telemetry data with guardrails for off-topic questions.
    """
    # Input validation - check if query is off-topic
    is_off_topic, reason = _is_off_topic(user_query)
    if is_off_topic:
        refusal_msg = (
            "I'm CogniOS AI, specialized exclusively in Linux system observability and CogniOS telemetry analysis. "
            "I cannot answer questions outside this domain. Please ask about system performance, crashes, "
            "processes, BlackBox forensics, OS Doctor anomalies, or FocusOS optimizations."
        )
        return refusal_msg
    
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
            user_content='',
            system_prompt=SYSTEM_PROMPT,
            model=model,
            stream=stream,
            api_key=api_key,
            history=_chat_history
        )
        _chat_history.append({"role": "assistant", "content": response})
        
        # Output validation - check if response stayed on topic
        is_valid, validation_reason = _validate_response_on_topic(response)
        if not is_valid:
            # Log the issue but don't block - the guardrail prompt should handle most cases
            print(f"[Guardrail Warning] Response validation: {validation_reason}", file=sys.stderr)
        
        return response
    finally:
        if close_conn:
            conn.close()


def _groq_chat_completion(client, model, messages, stream, max_tokens, temperature):
    models_to_try = [model]
    for fb in ("llama-3.3-70b-versatile", "llama-3.1-8b-instant"):
        if fb not in models_to_try:
            models_to_try.append(fb)

    last_exc = None
    for m in models_to_try:
        kwargs = {
            "model": m,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
            "top_p": 1,
            "stream": stream,
            "stop": None,
        }
        if "deepseek" in m.lower() or "r1" in m.lower():
            kwargs["reasoning_format"] = "hidden"
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            err_msg = str(exc).lower()
            if "reasoning_format" in err_msg:
                kwargs.pop("reasoning_format", None)
                try:
                    return client.chat.completions.create(**kwargs)
                except Exception as inner_exc:
                    last_exc = inner_exc
                    continue
            last_exc = exc
            if "not found" in err_msg or "does not exist" in err_msg or "decommissioned" in err_msg:
                continue
            raise exc
    if last_exc:
        raise last_exc


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
        completion = _groq_chat_completion(
            client=client,
            model=model,
            messages=messages,
            stream=True,
            max_tokens=3000,
            temperature=0.3,
        )

        full_response = []
        for chunk in completion:
            content = chunk.choices[0].delta.content or ""
            print(content, end="", flush=True)
            full_response.append(content)
        print()  # Newline after streaming finishes
        return "".join(full_response)
    else:
        completion = _groq_chat_completion(
            client=client,
            model=model,
            messages=messages,
            stream=False,
            max_tokens=1500,
            temperature=1.0,
        )
        response_text = completion.choices[0].message.content or ""
        return response_text


_chat_history = []


def main():
    """Interactive CLI for CogniOS Natural Language Telemetry Query."""
    if len(sys.argv) > 1:
        # if argument given, Cannot access chat history (non-interactive)
        query = " ".join(sys.argv[1:])
        print(f"CogniOS Telemetry Query: '{query}'\n")
        try:
            query_telemetry(query, stream=True)
        except Exception as e:
            print(f"\nError executing query: {e}")
        return

    # interactive prompts can be given
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
