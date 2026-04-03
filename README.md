# Forensic ATOMIC: Generative Commonsense Reasoning
This project implements an asynchronous pipeline to generate, validate, and train a **Forensic Knowledge Graph**.

By providing a new version of the **ATOMIC** dataset in forensic format, we extend the events of the original dataset by introducing a criminal, suspicious, or partially harmless context using large language models (LLMs).

## Contributions

- Generates multiple forensic interpretations (violent, financial, cyber) for a single event. 

---

## Project structure

| Module                                          | Description                                                                      |
|:------------------------------------------------|:---------------------------------------------------------------------------------|
| [**config/**](./config/README.md)               | **Configuration.** Prompts and settings.                                         |
| [**core/**](./core/README.md)                   | **Core.** Generator and state manager on Redis.                                  |
| [**tools/**](./tools/README.md)                 | **Tools.** Scripts for cleaning, splitting, and quality control of the dataset.  |
| [**data/**](./data/README.md)                   | **Data.** Input/Output CSVs and processed data.                                  |
| [**form_creation/**](./form_creation/README.md) | **Form Creation.** Script to generate Google Forms trough Google API and results |

---

## Installation

### Requirements
- **Python 3.11+**
- **Redis server** (Run locally or via Docker)

### Setup
This project uses **Poetry** for dependency management.

**Environment configuration (`.env`):**
```ini
# GENERATION SETTINGS (OpenRouter)
LLM_MODE=openrouter
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_MODEL_A=deepseek/deepseek-chat

# PIPELINE CAPACITY
BATCH_SIZE=40
GEN_SEMAPHORE=28
JUDGE_SEMAPHORE=4

# DATABASE / STATE
REDIS_HOST=localhost
REDIS_PORT=6379

# JUDGE SETTINGS
USE_SINGLE_JUDGE_PROVIDER=true

# Provider to use in test-mode
SINGLE_JUDGE_PROVIDER=openrouter
SINGLE_JUDGE_MODEL=deepseek/deepseek-chat

# Disable the rewrite loop (true = active, false = only pass/fail)
ENABLE_REWRITE=false

# EVALUATION SETTINGS (Multi-Judge-LLMs)
REWRITER_PROVIDER=openai

# OpenAI (Judge 1 + Expert Rewriter)
OPENAI_API_KEY=sk-proj-your-openai-key
OPENAI_MODEL=gpt-4o

# Anthropic (Judge 2)
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
ANTHROPIC_MODEL=claude-3-5-sonnet-latest

# Google Gemini (Judge 3)
GEMINI_API_KEY=AIzaSy-your-google-key
GEMINI_MODEL=gemini-1.5-pro

# PATHS
INPUT_FILE=data/v4_atomic_all_agg.csv
OUTPUT_FILE=data/forensic_atomic_final.csv
JUDGEMENT_FILE=data/judgements_log.csv
```

---

## Workflow
### 1. Generation phase

**Initialization and Filtering:**
Prepares the input by filtering from the original ATOMIC dataset.
```bash
python main.py --use-filtered --filter-only
```

**Massive Generation:**
Launches asynchronous processes to make requests to the LLM.
```bash
python main.py --use-filtered --workers 30
```
*Output:* `data/forensic_atomic.csv`

### 2. Evaluating Phase
Post-Generation Tribunal:
Validates the raw generated dataset using a Multi-Agent Tribunal (GPT, Claude, Gemini). This step filters out hallucinations, enforces forensic logic through majority voting, and attempts to rewrite rejected inferences (if selected).
```bash 
python tools/post_generation_judge.py --input data/forensic_atomicl.csv --output data/forensic_atomic_judged.csv --workers 3
```

*Output*: `data/forensic_atomic_judged.csv`

---
