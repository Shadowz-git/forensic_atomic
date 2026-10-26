# Forensic ATOMIC: Generative Commonsense Reasoning

This project implements an asynchronous pipeline to generate, validate, and train a **Forensic Knowledge Graph**.

By providing a new version of the **ATOMIC** dataset in forensic format, we extend the events of the original dataset by introducing a criminal, suspicious, or partially harmless context using large language models (LLMs).

## Contributions

- Generates multiple forensic interpretations (violent, financial, cyber) for a single event. 
- Fine-tunes Phi-4-mini for crime category classification and generation on unseen events.
- Compares recorded LLM tribunal decisions with historical and new human judgments.

---

## Results

### Dataset Statistics

The final F-Atomic dataset consists of **9,175 validated forensic instances**, each representing a unique (event, crime_category) pair enriched with 16 relational dimensions from the ATOMIC2020 ontology. The Poly-Category Branching strategy produced multiple distinct criminal interpretations per source event.

| Crime Category         | Instances | Percentage |
|:-----------------------|----------:|:----------:|
| Financial Crimes       |     2,894 |   31.5%    |
| Organized Crimes       |     2,072 |   22.6%    |
| Violent Crimes         |     1,877 |   20.5%    |
| Property Crimes        |     1,254 |   13.7%    |
| Cyber Crimes           |       844 |    9.2%    |
| Public Order / Justice |       234 |    2.6%    |
| **Total**              | **9,175** |  100.0%    |

---

### Multi-Judge Tribunal Performance

The complete judgment audit log and aggregated statistics are available in [`data/judged_log.csv`](./data/judged_log.csv) and [`data/judgement_summary.csv`](./data/judgement_summary.csv). 

The final validated dataset is in [`data/forensic_atomic.csv`](data/forensic_atomic.csv).

The Phi-4-mini experiments and human judgment comparisons are documented in [models/phi4_mini/](models/phi4_mini/README.md) and [analysis/](analysis/README.md). Their saved tables and figures are under `results/`.

---

## Project structure

| Module                                          | Description                                                                      |
|:------------------------------------------------|:---------------------------------------------------------------------------------|
| [**config/**](./config/README.md)               | **Configuration.** Prompts and settings.                                         |
| [**core/**](./core/README.md)                   | **Core.** Generator and state manager on Redis.                                  |
| [**tools/**](./tools/README.md)                 | **Tools.** Scripts for cleaning, splitting, and quality control of the dataset.  |
| [**data/**](./data/README.md)                   | **Data.** Input/Output CSVs and processed data.                                  |
| [**form_creation/**](./form_creation/README.md) | **Form Creation.** Script to generate Google Forms through Google API and results |
| [**models/phi4_mini/**](./models/phi4_mini/README.md) | **Models.** Phi-4-mini classification and generation experiments.             |
| [**analysis/**](./analysis/README.md)         | **Analysis.** Historical and unified human–LLM judgment comparisons.           |
| [**results/**](./results/)                     | **Results.** Saved model predictions, statistics, and figures.                 |

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

The filtering and generation components are under `core/`, and the ATOMIC source files are under `data/atomic_dataset/`. This checkout does not contain a top-level `main.py` launcher. The existing validated output is `data/forensic_atomic.csv`.

### 2. Evaluating Phase
Post-Generation Tribunal:
Validates the raw generated dataset using a Multi-Agent Tribunal (GPT, Claude, Gemini). This step filters out hallucinations, enforces forensic logic through majority voting, and attempts to rewrite rejected inferences (if selected).
```bash 
python tools/post_generation_judge.py --input data/pre-judge_forensic_atomic.csv --output data/forensic_atomic_judged.csv --workers 3
```

*Output*: `data/forensic_atomic_judged.csv`

---

### 3. Phi-4-mini experiments and thesis statistics

The classification notebooks are in `models/phi4_mini/classification/`. The generation notebooks are in `models/phi4_mini/generation/`; they compare base and fine-tuned Phi-4-mini with DeepSeek on 35 unseen events. Training and inference require the separate Poetry environment in `models/phi4_mini/`, and full training requires a compatible CUDA GPU. Adapter weights are not included.

To regenerate saved statistics without a GPU, run these notebooks from their first cell:

1. `models/phi4_mini/classification/03_results_summary.ipynb` — display saved classification comparisons.
2. `models/phi4_mini/generation/04_clean_compare.ipynb` — regenerate generation comparison tables and figures.
3. `models/phi4_mini/generation/05_audit_supplied_outputs.ipynb` — check additional prompt variants and DeepSeek judgments.
4. `analysis/judgement_analysis_final.ipynb` — regenerate separate statistics for 550 historical and 671 unified human judgments in `results/human_llm/`.

The supplied DeepSeek judge log covers 70 generated branches. An equivalent fine-tuned Phi-4 judge log and the exact prompts for the additional output variants are not available; see the [generation README](models/phi4_mini/generation/README.md) for details.
