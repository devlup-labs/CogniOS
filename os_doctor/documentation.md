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

# OSDoctor: Core Pipeline Architecture

This document describes the linear data flow and core components of the OSDoctor observability engine as designed.

## 1. System Architecture Diagram

```mermaid
graph TD
    %% Telemetry Collection Layer
    Collector[Telemetry Collector] --> System[System Telemetry]
    Collector --> Process[Per Process Telemetry]
    
    %% Database Interaction
    System --> DB_Script[db.py]
    Process --> DB_Script
    DB_Script --> SQLite[(SQL Lite Database)]
    
    %% Processing Pipeline
    SQLite --> FeatureEng[Feature Engineering]
    FeatureEng --> IForest[Isolation Forest]
    
    %% Evaluation Logic
    IForest -->|No| Nothing[Nothing]
    IForest -->|Yes| AppendAlert[Append to Alerts Table]
    
    %% Output Generation & UI
    AppendAlert --> LLMLayer[LLM Layer]
    LLMLayer --> Streamlit[Streamlit UI]
    
    %% Custom Styling for Visual Clarity
    style Collector fill:#f4f4f4,stroke:#333,stroke-width:2px
    style IForest fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
    style AppendAlert fill:#ffebee,stroke:#c62828,stroke-width:2px

    2. Pipeline Step Descriptions
Step 1: Telemetry Collector (System & Per-Process)
•	The entry point of the pipeline splits data gathering into two concurrent streams:
•	System Telemetry: Monitors macro-level hardware usage across the entire operating system.
•	Per-Process Telemetry: Tracks individual application metrics to identify localized resource usage.

Step 2: Database Pipeline (db.py ➔ SQL Lite)
•	Both telemetry feeds pass synchronously into the central database management script (db.py).
•	The database script handles formatting, opens a transaction, and writes the metric frames safely into persistent storage inside the SQL Lite engine.

Step 3: Feature Engineering
•	This step reads raw performance rows from SQL Lite and transforms them into predictive indicators.
•	It computes dynamic trends, smooths out sudden system noise, and prepares structured multi-dimensional state vectors for the machine learning layer.

Step 4: Isolation Forest Inference
•	The engineered metrics enter the Isolation Forest unsupervised learning model.
•	The pipeline evaluates the model's output via a binary branch:
•	No Anomaly (Output: 1): The execution stops instantly and loops back (Nothing).
•	Anomaly Detected (Output: -1): The execution is flagged as Yes and proceeds downstream.

Step 5: Append to Alerts Table
•	The moment an anomaly is confirmed, the system generates an incident log.
•	This record, containing key anomaly flags and metrics data, is immediately written to the specialized alerts table in the database.

Step 6: LLM Layer
•	The LLM Layer triggers automatically when a new record appears in the alerts table.
•	It processes the structured metric telemetry data and translates it into natural language explanations covering cause, severity, and mitigation paths.

Step 7: Streamlit UI Presentation
•	The final human-readable report and live performance timeline streams are loaded directly into the front-end dashboard.
•	The Streamlit user interface displays recommendations and reactive alerts to let end-users know exactly why their machine is slow.


4. Project Workflow

5. File Structure

[span_0](start_span)[span_1](start_span)[span_2](start_span)[span_3](start_span)This document outlines the standard Python project layout designed to map your pipeline architecture components into distinct modules and files[span_0](end_span)[span_1](end_span)[span_2](end_span)[span_3](end_span).

## 1. Directory Layout Diagram

```mermaid
graph TD
    Project[os_doctor_project/] --> Src[src/]
    Project --> Requirements[requirements.txt]
    Project --> README[README.md]
    
    %% Collectors
    Src --> CollDir[collectors/]
    CollDir --> SysColl[system_collector.py]
    CollDir --> ProcColl[process_collector.py]
    CollDir --> DeepColl[deep_diagnostics.py]
    
    %% Core Processing & ML
    Src --> EngineDir[engine/]
    EngineDir --> DB[db.py]
    EngineDir --> Feature[feature.py]
    EngineDir --> IForest[i_forest.py]
    EngineDir --> Tagger[tagger.py]
    
    %% Analysis & Frontend
    Src --> WorkersDir[workers/]
    WorkersDir --> LLMExec[llm_executor.py]
    
    Src --> AppUI[app.py]
    
    %% Styling
    style Project fill:#f5f5f5,stroke:#333,stroke-width:2px
    style SysColl fill:#e8f5e9,stroke:#2e7d32
    style ProcColl fill:#e8f5e9,stroke:#2e7d32
    style DB fill:#fff3e0,stroke:#ef6c00
    style IForest fill:#e1f5fe,stroke:#0288d1
    style LLMExec fill:#f3e5f5,stroke:#6a1b9a
    style AppUI fill:#ffebee,stroke:#c62828


6. Module Description
7. Function Documentation
8. Database Design
9. Feature Engineering
10. Machine Learning Model
11. LLM Explanation Layer
12. Dashboard
13. Installation
14. Future Scope
