# Phi-4-mini Experiments

This folder contains separate experiments for crime category classification and forensic interpretation generation. The notebooks find the repository root from the current working directory. Saved metrics and model outputs are under `results/phi4_mini/`.

### Classification

- **Baseline:** `classification/baseline/01_prepare.ipynb` prepares the seed-42 split; `02_train_evaluate.ipynb` trains and evaluates architectures A and C.
- **Context-safe split:** `classification/context_safe/01_prepare.ipynb` prepares the seed-123 split; `02_train_evaluate.ipynb` trains and evaluates the same architectures.
- **Saved results:** `classification/03_results_summary.ipynb` displays the available test comparisons without a GPU.

### Generation

- **Training and inference:** Run `generation/01_train.ipynb`, `02_generate.ipynb`, `03_validate.ipynb`, and `04_clean_compare.ipynb` in order. Training and inference share `generation/prompt.py`. The training split uses seed 321, training uses seed 42, and the 35 unseen inputs are in `data/atomic_dataset/selected_events_atomic.csv`.
- **Supplied output audit:** `generation/05_audit_supplied_outputs.ipynb` checks the additional DeepSeek judge log and prompt variants without a GPU. See [generation/README.md](generation/README.md) for the source files and comparison limits.

### Environment

This directory has a separate Poetry project. Install CPU dependencies with `poetry install` from `models/phi4_mini/`; use `poetry install --with gpu` on a compatible CUDA host for training and inference. The adapter weights are not supplied. Training writes new adapters under the experiment's `adapters/` directory, which is ignored by Git.
