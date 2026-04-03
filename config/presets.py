from typing import Dict, Optional, List

# List of synthetic categories used during the augmentation phase.
# Centralized here for easy access by main.py and synthetic.py
CATEGORIES_TO_GENERATE: List[str] = [
    "Cyber Crimes (Hacking, Phishing, Identity Theft, Online Harassment)",
    "Financial Crimes (Fraud, Money Laundering, Embezzlement, Bribery, Tax Evasion)",
    "Organized Crimes (Drug Trafficking, Human Trafficking, Racketeering, Weapon Smuggling)",
    "Public Order/Justice (Perjury, Obstruction of Justice, Disorderly Conduct)"
]

class PipelineConfig:
    """
    Configuration object for pipeline execution profiles.
    """
    def __init__(self, gen_workers: int, judge_workers: int, limit: Optional[int], description: str):
        # Number of workers dedicated to generating content via OpenRouter
        self.gen_workers = gen_workers
        # Number of workers dedicated to the Multi-Judge
        self.judge_workers = judge_workers
        # Optional limit on the number of input events to process
        self.limit = limit
        # Human-readable description of the preset
        self.description = description

# Available presets
PRESETS: Dict[str, PipelineConfig] = {
    "test": PipelineConfig(
        gen_workers=2,
        judge_workers=0,
        limit=3,
        description="FAST TEST: Runs 5 items with minimal workers. Validates API connections and logic."
    ),
    "dev": PipelineConfig(
        gen_workers=5,
        judge_workers=2,
        limit=100,
        description="DEVELOPMENT: Runs 100 items. Useful for prompt engineering and debugging."
    ),
    "gen_only": PipelineConfig(
        gen_workers=40,
        judge_workers=0,
        limit=None,
        description="GENERATION ONLY: Uses all capacity for generation. No judging phase."
    ),
    "full_tribunal": PipelineConfig(
        gen_workers=28,
        judge_workers=12,
        limit=None,
        description="FULL PRODUCTION: Balanced split between Generation (28) and Multi-Judge Tribunal (12)."
    ),
    "tribunal_only": PipelineConfig(
        gen_workers=0,
        judge_workers=3,
        limit=5,
        description="FAST TEST: Runs 5 items with minimal judge workers. Validates API connections and logic for judges."
    )
}