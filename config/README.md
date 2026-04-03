# Configuration Module

This folder centralizes all configuration logic, prompt management for the LLM, and pipeline execution profiles.

### `settings.py`
File used for global configurations.
- Reads environment variables (API Keys, URLs) from .env.
- Dynamically configures the client (OpenAI, OpenRouter) based on the `LLM_MODE` variable.
- Defines the connection parameters to the Redis database.
- Centrally defines the Input (`v4_atomic_all_agg.csv`) and Output paths.

**Supported modes (`LLM_MODE`):**
- `openrouter`: (Used) Uses OpenRouter to access models such as DeepSeek-V3 or other online models.
- `openai`: Uses the official OpenAI API.

### `prompts.py`
Contains the prompts used by the model to interpret events.

- **`SYSTEM_PROMPT`**: Implements the **“Diverse Contextual Branching”** directive.
  - Instructs the LLM not to limit itself to a single interpretation.
  - Requires the generation of a **JSON list** containing 2 to 4 distinct interpretations for the same event.
  - Forces the exploration of different contexts:
    1.  **Direct Crime:** The obvious crime.
    2.  **Innocent Context:** The lawful interpretation.
    3.  **Deceptive Context:** A harmless action used as a cover (e.g., “buying ice cream” -> Money Laundering).
  - **`Forensic Taxonomy`**: Provides the model with a list of criminal categories (Violent, Financial, Cyber, Organized, etc.) to draw from.
- **`SYNTHETIC_PROMPT`**: Used to create mass event templates. It follows the ATOMIC format ("PersonX [verb] ...") while maintaining a strict focus on forensic and criminal topics.
- **`JUDGE_PROMPT`**: It evaluates AI-generated inferences based on Logic, Forensic Insight, and Plausibility. It returns a structured verdict (approve/reject) with a score and a specific reason.
- ~~**`REWRITE_PROMPT`**: It could be implemented, but it was not used.~~

### Execution Profiles
The `presets.py` file provides pre-configured execution profiles to simplify the pipeline launch. These presets define the number of workers assigned to content generation versus those dedicated to the judging phase, as well as any processing limits.

| Preset          | Gen Workers | Judge Workers | Limit | Description                                                |
|:----------------|:-----------:|:-------------:|:-----:|:-----------------------------------------------------------|
| `test`          |      2      |       2       |   5   | Fast validation of API connections and JSON logic.         |
| `dev`           |      5      |       2       |  100  | Prompt engineering and debugging on a medium-sized sample. |
| `gen_only`      |     40      |       0       | None  | High-speed generation only, bypassing the judging process. |
| `full_tribunal` |     28      |      12       | None  | Balanced production setup for both generation and review.  |
| `tribunal_only` |      0      |       3       |   5   | Fast validation of API connections with judges.            |
