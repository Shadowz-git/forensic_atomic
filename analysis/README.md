# Human and LLM Judgment Analysis

### `judgement_analysis_final.ipynb`

Compares human decisions with the recorded LLM tribunal decision. Run the notebook from any directory inside the repository; its first cell finds the repository root. It calls `human_llm_statistics.py` to calculate tables and figures. The same results can be regenerated with `python analysis/human_llm_statistics.py` in an environment with pandas, NumPy, and Matplotlib.

- **Historical forms:** 550 form-event rows from `data/form_results/global_comparison_results.csv`.
- **Unified forms:** 671 distinct events from `data/form_results/unified_human_judgments.csv`, matched to `data/judged_log.csv` by row ID and event. Individual responses also provide 700 form-event observations.
- **Decision rules:** Human score and approval percentage are tested separately at 50 and 60. A third rule requires the score threshold and at least 50% human approval. The unified confusion matrix for this joint rule at score 50 contains 596 confirmed and 75 unconfirmed events.
- **Output:** Tables and figures are saved separately under `results/human_llm/historical/` and `results/human_llm/unified/`. Running the notebook from its first cell recreates these folders if needed.

The 35 selected generation events are a separate experiment and are not included in these human judgment cohorts.
