# Generation Experiment

The main comparison uses 35 events from `data/atomic_dataset/selected_events_atomic.csv`. The notebooks run in this order:

1. `01_train.ipynb` trains the Phi-4-mini adapter.
2. `02_generate.ipynb` generates base and fine-tuned outputs. Select each model variant in the notebook before running it.
3. `03_validate.ipynb` applies the shared validator to base, fine-tuned, and DeepSeek outputs.
4. `04_clean_compare.ipynb` cleans the outputs and exports paired event statistics and figures.
5. `05_audit_supplied_outputs.ipynb` checks the additional prompt variants and DeepSeek judge records on a CPU.

### Saved sources

- **Main comparison:** `results/phi4_mini/generation/raw/`, `validated/`, and `cleaned/`. The DeepSeek CSV in `raw/` is a byte-identical copy of the supplied `generati_deepseek.csv`.
- **DeepSeek judgments:** `results/phi4_mini/generation/judged/deepseek_selected_judgments.csv` contains 70 judge records for the 70 generated branches. Each `original_row_id` identifies a zero-based row in the DeepSeek raw CSV. All 70 records are approved.
- **Prompt variants:** `results/phi4_mini/generation/prompt_variants/with_extra_examples/` contains 63 successful branches from 33 events and two failed events. `without_extra_examples/` contains 38 successful branches from 19 events and 16 failed events. Each pair of success and failure files covers all 35 inputs.

The audit notebook writes coverage, shared-event label agreement, and DeepSeek judge summaries beside these sources. The supplied prompt-variant CSVs do not identify their exact model checkpoint, alternate prompt text, generation settings, or seed. The current `prompt.py` contains one example and does not contain the stated two additional examples. A judge log for the fine-tuned Phi-4 branches is also absent, so judge scores cannot yet be compared with DeepSeek. The existing validated and cleaned CSVs support structural comparisons.
