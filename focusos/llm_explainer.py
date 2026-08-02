import json
import os
from google import genai
from google.genai import types

try:
    from ddgs import DDGS
    DDG_avail = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        DDG_avail = True
    except ImportError:
        DDG_avail = False

# API key fallback to test key if env var is not set
gemini_api_key = os.getenv("gem_api_key")
gemma_api_key = os.getenv("gemma_api_key")
def get_top_features(feature_importances: dict, current_values: dict, top_n: int = 3) -> dict:
    sorted_features = sorted(feature_importances.items(), key=lambda x: x[1], reverse=True)
    top_features = {}
    for feature_name, importance_score in sorted_features[:top_n]:
        raw_val = current_values.get(feature_name, 0.0)
        top_features[feature_name] = round(raw_val, 2) if isinstance(raw_val, float) else raw_val
    return top_features

def try_gemma_explanation(system_prompt: str, user_prompt: str, model_name: str = "gemma-4-26b-a4b-it") -> str:
    if not gemma_api_key:
        raise ValueError("Gemma API key is not set.")
    
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
    
    # provides diagnostic information on why the response might be empty
    candidates_info = "No candidates returned."
    if response and response.candidates:
        candidates_info = []
        for idx, c in enumerate(response.candidates):
            candidates_info.append(f"Candidate {idx} finish_reason: {c.finish_reason}")
        candidates_info = "; ".join(candidates_info)
    raise ValueError(f"Empty response string from Gemma 4 ({model_name}). Diagnostics: {candidates_info}")

def try_gemini_explanation(system_prompt: str, user_prompt: str) -> str:
    if not gemini_api_key:
        raise ValueError("API key is not set.")
    
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
        candidates_info = []
        for idx, c in enumerate(response.candidates):
            candidates_info.append(f"Candidate {idx} finish_reason: {c.finish_reason}")
        candidates_info = "; ".join(candidates_info)
    raise ValueError(f"Empty response string from Gemini. Diagnostics: {candidates_info}")

def try_duck_duck_go_explanation(prediction: str) -> str:
    if not DDG_avail:
        raise ImportError("Duck Duck Go search package is not installed")
    search_query = f"{prediction} workload high CPU GPU usage optimization"
    results = DDGS().text(search_query, max_results=1)
    if results and len(results) > 0:
        return results[0].get("body", "")
    raise ValueError("DuckDuckGo returned no search results.")

def clean_ddg_snippet(snippet: str) -> str:
    import re
    # Remove common date prefixes like "March 20, 2026 - ", "May 28, 2026 · ", etc.
    cleaned = re.sub(r'^[A-Za-z]+ \d+, \d{4}\s*[^A-Za-z0-9\s]?\s*', '', snippet)
    cleaned = re.sub(r'^\d{4}-\d{2}-\d{2}\s*[^A-Za-z0-9\s]?\s*', '', cleaned)
    # Remove HTML tags if any
    cleaned = re.sub(r'<[^>]*>', '', cleaned)
    # Replace multiple whitespaces/newlines with single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()
    
    # Try to get the first sentence
    sentences = re.split(r'(?<=[.!?])\s+', cleaned)
    if sentences:
        for s in sentences:
            s_clean = s.strip()
            if len(s_clean) > 20:
                return s_clean
    return cleaned[:150].strip()

def generate_explanation(prediction: str, confidence: float, top_features: dict) -> str:
    # Handle confidence format gracefully (handles both 0.61 and 61.0)
    conf_val = confidence * 100 if confidence <= 1.0 else confidence
    conf_pct_str = f"{conf_val:.0f}%"

    payload = {
        "predicted_workload": prediction,
        "confidence_score": conf_pct_str,
        "primary_driving_features": top_features
    }
    system_prompt = (
        "You are the FocusOS System Diagnostics Explainer. "
        "Rules: Output EXACTLY two plain-English sentences. "
        "Sentence 1: Explain WHY the workload was detected using the primary driving features. "
        "Sentence 2: Reassure the user about how FocusOS optimized the system. "
        "Do NOT use markdown, bullet points, or technical jargon like 'feature vector' or 'XGBoost'."
    )
    user_prompt = f"System Payload: {json.dumps(payload)}"

    #Gemma 4 API
    try:
        explanation = try_gemma_explanation(system_prompt, user_prompt)
        print("LLM Explainer: Tier 1 (Gemma 4) Success")
        return f"[Gemma 4 API] {explanation}"
    except Exception as e_gemma:
        print(f"LLM Explainer: Gemma 4 unavailable ({e_gemma})")

    #Gemini API
    try:
        explanation = try_gemini_explanation(system_prompt, user_prompt)
        print("LLM Explainer: Tier 2 (Gemini AI) Success")
        return f"[Gemini API] {explanation}"
    except Exception as e_gemini:
        print(f"LLM Explainer: Gemini unavailable ({e_gemini})")

    #Try DuckDuckGo search fallback
    try:
        raw_explanation = try_duck_duck_go_explanation(prediction)
        ddg_advice = clean_ddg_snippet(raw_explanation)
        if ddg_advice and not ddg_advice.endswith('.'):
            ddg_advice += '.'
            
        feature_names = list(top_features.keys())
        readable_features = ", ".join([f.replace("_", " ") for f in feature_names])
        
        explanation = (
            f"FocusOS detected a {prediction} workload with {conf_pct_str} confidence due to elevated {readable_features}. "
            f"To optimize this, resources have been adjusted according to recommendation: {ddg_advice}"
        )
        print("LLM Explainer: Tier 3 (DuckDuckGo Search) Success")
        return f"[DuckDuckGo Search] {explanation}"
    except Exception as e_ddg:
        print(f"LLM Explainer: DuckDuckGo unavailable ({e_ddg})")

    #FocusOS Diagnostic Template Fallback (Matching Gemma/Gemini style)
    print("LLM Explainer: Tier 4 (FocusOS Diagnostic Template) Activated.")
    feature_names = list(top_features.keys())
    readable_features = ", ".join([f.replace("_", " ") for f in feature_names])
    
    explanation = (
        f"FocusOS detected a {prediction} workload with {conf_pct_str} confidence due to elevated {readable_features}. "
        f"Process priorities and core CPU affinities have been automatically optimized to maintain smooth system responsiveness."
    )
    return f"[Template Fallback] {explanation}"

if __name__ == "__main__":
    sample_features = {"cpu_max": 9.0, "disk_io_mean": 5.685, "ram_mean": 27.9358}
    explanation = generate_explanation("Idle", 0.6471, sample_features)
    print("Generated Explanation:")
    print(explanation)


