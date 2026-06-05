# Data Folder
Contains all input and output files produced across the pipeline stages.

---

### Input
- **`filtered_events.csv`** — Filtered subset of the original ATOMIC dataset. Contains only the events selected for forensic generation, based on verb and context relevance.
- **`atomic_dataset/`** — Folder containing the original ATOMIC dataset.

---

### Generation Output
- **`raw_forensic_atomic.csv`** — Raw output of the generation phase. Contains all instances produced by the LLM before any data understanding pass.
- **`pre-judged_forensic_atomic.csv`** — Cleaned version of the generation output after the Data Understanding phase: non-ASCII sanitization, taxonomy normalization, and removal of malformed or low-quality rows. This is the file used as input for the Multi-Judge Tribunal. Contains **9,414 instances** across 6 forensic macro-categories.

---

### Judgment Output
- **`forensic_atomic.csv`** — Final validated dataset. Contains only the instances approved by the Multi-Judge Tribunal (majority vote ≥ 2/3, average score ≥ 60). This is the main output of the F-Atomic project.
- **`judged_log.csv`** — Per-row audit log produced by the Tribunal. Records the individual verdict, score, and provider for each of the three judges, the final decision, and whether a rewrite was attempted.
- **`judgement_summary.csv`** — Aggregated statistics over the full judgment run, produced by `tools/judgement_analysis.ipynb`. Includes total counts of approved, rejected and rewritten events, approval rate, agreement rate, and average scores.

---

### Validation
- **`form_results/`** — Raw CSV exports from the Google Forms human annotation experiment. Used in `form_creation/event_validation.ipynb` for the comparative Human vs. LLM analysis.
