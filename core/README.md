# Core Modules
This folder contains the core components of the forensic generation pipeline.

## `generator.py` (Unified LLM Client)
Provides a unified interface for interacting with multiple Large Language Model providers.
- Supports **OpenRouter**, **OpenAI**, **Anthropic**, and **Google Gemini**, automatically dispatching requests to the correct client depending on the selected provider.
- Uses asynchronous clients (`AsyncOpenAI`, `AsyncAnthropic`) and **`aiohttp`** to enable high-throughput, non-blocking API calls within the pipeline.
- Implements **automatic retry with Exponential Backoff** using `tenacity` to handle API rate limits, transient failures, and network instability.
- Includes output sanitation logic that removes markdown wrappers and chain-of-thought artifacts (e.g., `<think>...</think>` tags produced by models like DeepSeek R1).
- Provides a **REST-based integration for Gemini** instead of the official SDK to avoid `protobuf` dependency conflicts.
- Centralizes generation parameters (temperature, max tokens, system prompts) and logging, ensuring consistent behavior across all model providers.

## `judge.py` (Multi-Agent Validation)
Implements a **multi-agent evaluation system** to verify the quality and consistency of generated forensic data. 
- Queries multiple independent LLM judges (**OpenAI, Anthropic, Gemini**) to evaluate each generated event and its predictions. 
- Uses **parallel asynchronous calls** with provider-specific semaphores to control concurrency and reduce the risk of API rate limits. 
- Applies a **consensus-based decision rule**: content is approved if at least 2 out of 3 judges vote "approve" and the average score passes a minimum threshold. 
- If rejected, triggers a **rewrite phase**, where a dedicated LLM attempts to correct the output based on consolidated feedback from the judges. 
- Performs a **final verification round** where the remaining judges validate the rewritten content. 
- Logs all evaluation outcomes (status, scores, rewrite attempts, and judge feedback) to a CSV file for auditing and analysis.

## `validator.py`
Uses **Pydantic** to structurally validate every generated output.
- Verifies that all 9 forensic dimensions (xIntent, xNeed, etc.) are present and of the correct type.
- Filters responses that are too short, empty, or contain typical AI hallucination "filler words" (e.g., "As an AI language model...").
- Normalizes criminal categories (e.g., converts "Not a crime" into "Non-Criminal").

## `state_manager.py` (Persistence)
Manages execution state using **Redis**.
- Maintains a registry (`forensic:processed`) of already completed events to avoid paying twice for the same input in case of a restart.
- Handles distribution of events to parallel workers (`forensic:queue`).
- Accumulates results in a temporary list before writing to disk to reduce I/O.

## `filter.py` (Preprocessing)
Selects relevant events from the original ATOMIC dataset.
Uses an advanced set of **Regular Expressions (Regex)** to identify verbs and contexts that may be forensically relevant (e.g., "kill", "break", "steal", "hack"), discarding irrelevant events.

## `logger.py` (Logging)
Centralized logging system.
- Configures log levels (INFO/DEBUG). 
- Implements a thread-safe handler compatible with the `tqdm` progress bar, allowing logs to be displayed in real time without "breaking" the loading bar display.
