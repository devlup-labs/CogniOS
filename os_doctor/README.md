OSDoctor
Real-Time Intelligent Operating System Monitoring & Anomaly Detection System

Project Documentation

1. Introduction

OSDoctor is an intelligent observability system that continuously monitors operating system telemetry, detects abnormal system behavior using machine learning, identifies the likely root cause, and explains the issue in natural language. Its objective is to answer the question: “Why is my laptop slow right now?”

2. Objectives

- Monitor real-time system telemetry.
- Detect system anomalies automatically.
- Identify causes of performance issues.
- Detect CPU, memory, disk, and process-related faults.
- Explain issues in simple, human-readable language.
- Provide actionable alerts and recommendations.


3. System Architecture

```text
CogniOS Telemetry Collector
        │
        ▼
OSDoctor (Data Extraction)
        │
        ▼
System Metrics + Process Metrics
        │
        ▼
SQLite Database
        │
        ▼
Feature Engineering
        │
        ▼
Isolation Forest
        │
        ├── No Anomaly
        │      │
        │      ▼
        │   Continue Monitoring
        │
        └── Anomaly Detected
               │
               ▼
         Alerts Table
               │
               ▼
        LLM Explanation Layer
               │
               ▼
        Streamlit Dashboard
```

4. File Structure

```text
os_doctor/
│── _init_.py             # Marks the directory as a Python package
│── featuring.py           # Feature engineering and preprocessing
│── i_forest.py             # Isolation Forest model implementation
│── llm_layer.py           # LLM integration and response generation
│── streamlit.py           # Streamlit web application
│── README.md          # Project overview and setup guide
```


5. Function Documentation
6. Feature Engineering
7. Machine Learning Model
8. LLM Explanation Layer
9. Dashboard
10. Installation
11. Future Scope