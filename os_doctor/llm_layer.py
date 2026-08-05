"""
OS Doctor - LLM Explanation Layer
Converts raw telemetry payloads into natural language explanations.
"""

import json
import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 1. Pydantic schema enforcing structured JSON output from LLM
class OSDoctorReport(BaseModel):
    cause: str = Field(description="Clear reason why the system is slow based on top_process and CPU usage.")
    severity: str = Field(description="Severity level: Low, Medium, High, or Critical.")
    suggested_action: str = Field(description="Simple recommended action for the user.")
    confidence: float = Field(description="Confidence percentage (e.g. 91.0).")

def generate_llm_explanation(metadata: dict) -> dict:
    """
    Receives raw metadata from i_forest_predict.py, formats the prompt,
    calls Gemini API, and returns a structured explanation dictionary.
    """
    # Build standardized input JSON as required by OS Doctor specifications
    payload = {
        "cpu": metadata.get("cpu", 0),
        "memory": metadata.get("memory", 0),
        "top_process": metadata.get("top_process", "Unknown"),
        "process_cpu": metadata.get("process_cpu", 0),
        "issue": metadata.get("issue", "high_cpu")
    }

    system_instruction = (
        "You are OS Doctor, an intelligent system monitoring assistant. "
        "Explain system anomalies in simple language. "
        "You MUST provide: Cause, Severity, Suggested action, and Confidence percentage."
    )

    prompt = f"System Telemetry Summary:\n{json.dumps(payload, indent=2)}"
    api_key = os.environ.get("GEMINI_API_KEY")

    # Fallback if API key is missing
    if not api_key:
        return {
            "cause": f"Process '{payload['top_process']}' consumed {payload['process_cpu']}% CPU.",
            "severity": "High" if payload["cpu"] > 85 else "Medium",
            "suggested_action": "Close unnecessary background tasks.",
            "confidence": 85.0
        }

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=OSDoctorReport,
                temperature=0.2,
            ),
        )
        return json.loads(response.text)

    except Exception as e:
        print(f"LLM Generation Error: {e}")
        return {
            "cause": f"High resource consumption detected on process '{payload['top_process']}'.",
            "severity": "Medium",
            "suggested_action": "Inspect active processes in system manager.",
            "confidence": 70.0
        }

