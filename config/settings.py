import os
from dotenv import load_dotenv

# This file is in <PROJECT_ROOT>/config/settings.py
# We go up two levels to find <PROJECT_ROOT>
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"))


class Settings:
    """
    Global configuration class.
    Handles environment variables and absolute path resolution.
    """

    # Project Root Path
    # Exposed for other scripts if they need to construct custom paths
    BASE_PATH = BASE_DIR

    # Pipeline & Concurrency
    WORKERS = int(os.getenv("BATCH_SIZE", 40))
    GEN_SEMAPHORE_LIMIT = int(os.getenv("GEN_SEMAPHORE", 28))
    JUDGE_SEMAPHORE_LIMIT = int(os.getenv("JUDGE_SEMAPHORE", 4))

    # Judge Settings
    ENABLE_REWRITE = os.getenv("ENABLE_REWRITE", "true").lower() == "true"

    # Set to True to route ALL three judge slots through a single provider/model.
    # Useful for testing the pipeline logic without spending credits on 3 different APIs.
    # When True, SINGLE_JUDGE_PROVIDER and SINGLE_JUDGE_MODEL are used for every judge call.
    USE_SINGLE_JUDGE_PROVIDER = os.getenv("USE_SINGLE_JUDGE_PROVIDER", "false").lower() == "true"

    # Provider and model to use when USE_SINGLE_JUDGE_PROVIDER is True.
    # Defaults to OpenRouter + the same model used for generation (Model A).
    SINGLE_JUDGE_PROVIDER = os.getenv("SINGLE_JUDGE_PROVIDER", "openrouter")
    SINGLE_JUDGE_MODEL = os.getenv("SINGLE_JUDGE_MODEL", os.getenv("OPENROUTER_MODEL_A", "deepseek/deepseek-v3.2"))

    # Optional limit for testing
    LIMIT = None

    # Database (Redis)
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

    # File Paths (Resolved to Absolute Paths)
    # We join the BASE_DIR with the relative path defined in .env or defaults

    INPUT_FILE = os.path.join(BASE_DIR, os.getenv("INPUT_FILE", "data/atomic_dataset/v4_atomic_all_agg.csv"))

    OUTPUT_FILE = os.path.join(BASE_DIR, os.getenv("OUTPUT_FILE", "data/forensic_atomic_final.csv"))

    JUDGEMENT_FILE = os.path.join(BASE_DIR, os.getenv("JUDGEMENT_FILE", "data/judgements_log.csv"))

    CONCEPTNET_CACHE = os.path.join(BASE_DIR, os.getenv("CONCEPTNET_CACHE", "data/conceptnet_cache.json"))

    LOG_FILE = os.path.join(BASE_DIR, "logs", "pipeline.log")

    # Generation Models (OpenRouter)
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    # Models for generation
    GEN_MODEL_A = os.getenv("OPENROUTER_MODEL_A", "deepseek/deepseek-v3.2")

    # Judge Providers
    # Provider logic for the Rewriter (usually 'openai')
    REWRITER_PROVIDER = os.getenv("REWRITER_PROVIDER", "openai")

    # OpenAI (Direct)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Anthropic (Direct)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    # Google Gemini (Direct via REST)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")


settings = Settings()