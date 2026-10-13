"""FocusOS LLM Explainer — 3-tier fallback: Gemma 4 → Gemini → Template.
DuckDuckGo inference removed: web-scraped snippets are unreliable for kernel
diagnostics and were leaking raw search text into the UI.
"""

import json
import os
from google import genai
from google.genai import types


# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------
def _load_env():
    """Load API keys from .env, trying dotenv first then manual parsing."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    base_dir = os.path.dirname(os.path.abspath(__file__))
    for path in [
        os.path.join(base_dir, ".env"),
        os.path.join(os.path.dirname(base_dir), ".env"),
        ".env",
    ]:
        if os.path.exists(path):
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")
            break


_load_env()
gemini_api_key = os.getenv("gem_api_key")
gemma_api_key  = os.getenv("gemma_api_key")


# ---------------------------------------------------------------------------
# Feature helper
# ---------------------------------------------------------------------------
def get_top_features(feature_importances: dict, current_values: dict, top_n: int = 3) -> dict:
    """Return the top-N features by importance with their current values."""
    sorted_features = sorted(feature_importances.items(), key=lambda x: x[1], reverse=True)
    top_features = {}
    for feature_name, _ in sorted_features[:top_n]:
        raw_val = current_values.get(feature_name, 0.0)
        top_features[feature_name] = round(raw_val, 2) if isinstance(raw_val, float) else raw_val
    return top_features


# ---------------------------------------------------------------------------
# Tier 1 — Gemma 4 (via OpenRouter or Google GenAI SDK)
# ---------------------------------------------------------------------------
def try_gemma_explanation(system_prompt: str, user_prompt: str,
                          model_name: str = "gemma-4-26b-a4b-it") -> str:
    if not gemma_api_key:
        raise ValueError("Gemma API key is not set.")

    # OpenRouter path
    if gemma_api_key.startswith("sk-or-"):
        import requests
        headers = {
            "Authorization": f"Bearer {gemma_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 4000,
        }
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15,
        )
        if response.status_code == 200:
            res_data = response.json()
            if "choices" in res_data and len(res_data["choices"]) > 0:
                return res_data["choices"][0]["message"]["content"].strip()
            raise ValueError(f"Unexpected OpenRouter response format: {res_data}")
        raise ValueError(f"OpenRouter HTTP Error {response.status_code}: {response.text}")

    # Google GenAI SDK path
    client = genai.Client(api_key=gemma_api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            max_output_tokens=4000,
        ),
    )
    if response and response.text:
        return response.text.strip()

    candidates_info = "No candidates returned."
    if response and response.candidates:
        candidates_info = "; ".join(
            f"Candidate {i} finish_reason: {c.finish_reason}"
            for i, c in enumerate(response.candidates)
        )
    raise ValueError(f"Empty response from Gemma 4 ({model_name}). Diagnostics: {candidates_info}")


# ---------------------------------------------------------------------------
# Tier 2 — Gemini 2.5 Flash
# ---------------------------------------------------------------------------
def try_gemini_explanation(system_prompt: str, user_prompt: str) -> str:
    if not gemini_api_key:
        raise ValueError("Gemini API key is not set.")

    client = genai.Client(api_key=gemini_api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            max_output_tokens=1000,
        ),
    )
    if response and response.text:
        return response.text.strip()

    candidates_info = "No candidates returned."
    if response and response.candidates:
        candidates_info = "; ".join(
            f"Candidate {i} finish_reason: {c.finish_reason}"
            for i, c in enumerate(response.candidates)
        )
    raise ValueError(f"Empty response from Gemini. Diagnostics: {candidates_info}")


# ---------------------------------------------------------------------------
# Tier 3 — Template Fallback (always succeeds, no external dependency)
# ---------------------------------------------------------------------------
def _template_explanation(prediction: str, conf_pct_str: str, top_features: dict) -> str:
    readable_features = ", ".join(f.replace("_", " ") for f in top_features.keys())
    return (
        f"FocusOS detected a {prediction} workload with {conf_pct_str} confidence "
        f"due to elevated {readable_features}. "
        f"Process priorities and core CPU affinities have been automatically optimized "
        f"to maintain smooth system responsiveness."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_explanation(prediction: str, confidence: float, top_features: dict) -> dict:
    """Run the 3-tier fallback chain and return a dict with 'text' and 'source'.

    Returns:
        {
            "text":   str  — clean explanation, NO source prefix embedded,
            "source": str  — "Gemma 4" | "Gemini" | "Template"
        }

    The source prefix is intentionally kept OUT of 'text' so callers can render
    it as a small UI badge instead of polluting the explanation body.
    """
    conf_val = confidence * 100 if confidence <= 1.0 else confidence
    conf_pct_str = f"{conf_val:.0f}%"

    payload = {
        "predicted_workload": prediction,
        "confidence_score": conf_pct_str,
        "primary_driving_features": top_features,
    }
    system_prompt = (
        "You are the FocusOS System Diagnostics Explainer. "
        "Rules: Output EXACTLY two plain-English sentences. "
        "Sentence 1: Explain WHY the workload was detected using the primary driving features. "
        "Sentence 2: Reassure the user about how FocusOS optimized the system. "
        "Do NOT use markdown, bullet points, or technical jargon like 'feature vector' or 'XGBoost'."
    )
    user_prompt = f"System Payload: {json.dumps(payload)}"

    # --- Tier 1: Gemma 4 ---
    try:
        text = try_gemma_explanation(system_prompt, user_prompt)
        print("LLM Explainer: Tier 1 (Gemma 4) Success")
        return {"text": text, "source": "Gemma 4"}
    except Exception as e:
        print(f"LLM Explainer: Gemma 4 unavailable ({e})")

    # --- Tier 2: Gemini 2.5 Flash ---
    try:
        text = try_gemini_explanation(system_prompt, user_prompt)
        print("LLM Explainer: Tier 2 (Gemini) Success")
        return {"text": text, "source": "Gemini"}
    except Exception as e:
        print(f"LLM Explainer: Gemini unavailable ({e})")

    # --- Tier 3: Template (always succeeds) ---
    print("LLM Explainer: Tier 3 (Template Fallback) Activated.")
    text = _template_explanation(prediction, conf_pct_str, top_features)
    return {"text": text, "source": "Template"}


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample_features = {"cpu_max": 9.0, "disk_io_mean": 5.685, "ram_mean": 27.9358}
    result = generate_explanation("Idle", 0.6471, sample_features)
    print(f"Source : {result['source']}")
    print(f"Text   : {result['text']}")
