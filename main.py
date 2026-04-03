import asyncio
import csv
import json
import os
import argparse
import random
import pandas as pd
from tqdm.asyncio import tqdm

# Internal imports
from core.logger import log
from config.settings import settings
from config.presets import PRESETS, CATEGORIES_TO_GENERATE
from config.prompts import SYSTEM_PROMPT, get_user_prompt
from core.state_manager import StateManager
from core.generator import UnifiedGenerator
from core.validator import validate_llm_output
from core.judge import MultiJudgeSystem
from core.filter import run_filtering
from json_repair import repair_json

# Global Initialization
state = StateManager()
gen_client = UnifiedGenerator()


# CSV MONITOR
async def csv_writer_monitor(output_file, stop_event):
    """
    Background task: Reads approved results from Redis and writes them to the CSV file.
    Runs until the stop_event is set AND the Redis buffer is empty.
    """
    file_exists = os.path.isfile(output_file)
    with open(output_file, 'a', newline='', encoding='utf-8', buffering=1) as f:
        # Header updated with ALL 16 relations + context fields
        fieldnames = [
            'event', 'crime_category', 'crime_subcategory', 'brief_context',
            'xIntent', 'xNeed', 'xAttr', 'xEffect', 'xReact', 'xWant',
            'oEffect', 'oReact', 'oWant',
            'isAfter', 'HasSubEvent', 'isBefore', 'HinderedBy', 'Causes', 'xReason', 'isFilledBy'
        ]
        # extrasaction='ignore' is crucial if the judge system adds extra metadata fields
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        if not file_exists: writer.writeheader()

        processed_count = 0
        while not stop_event.is_set() or state.r.llen(state.RESULTS_KEY) > 0:
            result_json = state.r.lpop(state.RESULTS_KEY)
            if result_json:
                try:
                    row = json.loads(result_json)
                    # Ensure lists are formatted as JSON strings for CSV compatibility
                    for k, v in row.items():
                        if isinstance(v, list):
                            row[k] = json.dumps(v, ensure_ascii=False)
                    writer.writerow(row)
                    processed_count += 1

                    if processed_count % 50 == 0:
                        log.debug(f"CSV Monitor: saved {processed_count} rows.")
                except Exception as e:
                    log.error(f"CSV Write Error: {e}")
            else:
                await asyncio.sleep(0.5)


# GENERATION WORKER (PRODUCER)
async def generation_worker(worker_id, use_judge=False):
    """
    Fetches raw events, generates inferences using OpenRouter, validates structure,
    and pushes valid items to the Judgment Queue (or directly to results if judging is disabled).
    """
    # Semaphore to respect OpenRouter rate limits
    gen_sem = asyncio.Semaphore(settings.GEN_SEMAPHORE_LIMIT)

    while True:
        # Fetch 1 event from input queue
        events = state.get_generation_batch(1)
        if not events:
            # If input queue is empty, check if we should stop
            await asyncio.sleep(1)
            if state.r.llen(state.QUEUE_KEY) == 0:
                break
            continue

        event = events[0]

        try:
            selected_model = settings.GEN_MODEL_A

            # 1. GENERATION PHASE
            async with gen_sem:
                prompt = get_user_prompt(event)
                raw_text = await gen_client.generate(
                    provider="openrouter",
                    model=selected_model,
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT
                )

            # 2. PARSING PHASE

            if "NOT POSSIBLE" in raw_text.upper():
                log.warning(f"Impossible to create a criminal context '{event}'")
                state.mark_failed(event, "Impossible to create a criminal context")
                continue

            clean_text = gen_client._clean_json(raw_text)

            try:
                raw_data = json.loads(repair_json(clean_text))
            except Exception:
                log.warning(f"JSON Parse failed for '{event}'")
                state.mark_failed(event, "JSON Error")
                continue

            # Handle Multi-Label response (List of objects)
            items_to_save = raw_data if isinstance(raw_data, list) else [raw_data]

            valid_items = []
            for item in items_to_save:
                # Validate against Pydantic schema
                validated = validate_llm_output(item, event)
                if validated:
                    valid_items.append(validated)

            if valid_items:
                for v_item in valid_items:
                    if use_judge:
                        # Push to Intermediate Queue for Judges
                        state.push_to_judge(event, v_item)
                    else:
                        # Save directly to Final Buffer
                        state.mark_final_success(event, v_item)
            else:
                state.mark_failed(event, "No valid data generated")

        except Exception as e:
            log.error(f"Gen Worker Error: {e}")
            state.mark_failed(event, str(e))


# JUDGMENT WORKER (CONSUMER)
async def judgment_worker(worker_id):
    """
    Fetches generated items from Judgment Queue, runs Multi-Judge System,
    and saves approved items. Only runs if --judge is active.
    """
    judge_system = MultiJudgeSystem(gen_client)

    while True:
        # Fetch 1 item (event + generated_data) from Judgment Queue
        packages = state.get_judgment_batch(1)

        if not packages:
            # Check exit condition: Input empty AND Judge Queue empty
            if state.r.llen(state.QUEUE_KEY) == 0 and state.r.llen(state.TO_JUDGE_KEY) == 0:
                # Wait briefly for any stragglers from generators
                await asyncio.sleep(5)
                if state.r.llen(state.TO_JUDGE_KEY) == 0:
                    break
            else:
                await asyncio.sleep(1)
                continue

        package = packages[0]
        event = package['event']
        data = package['data']

        try:
            # Evaluate (Concurrency is handled inside judge_system)
            is_valid, final_data = await judge_system.evaluate_event(event, data)

            if is_valid:
                state.mark_final_success(event, final_data)
            else:
                log.info(f"Event '{event}' rejected by Tribunal.")
                # We do not mark as failed in global Redis to avoid retry loops, just discard.

        except Exception as e:
            log.error(f"Judge Worker Error: {e}")


# CLI ARGS
def parse_arguments():
    parser = argparse.ArgumentParser(description="Forensic Atomic Pipeline")

    parser.add_argument("--preset", type=str, choices=PRESETS.keys(), help="Use a preset config")

    # Specific worker counts
    parser.add_argument("--gen-workers", type=int, default=28, help="Number of generation workers")
    parser.add_argument("--judge-workers", type=int, default=12, help="Number of judge workers")

    parser.add_argument("--limit", type=int, help="Limit input events")

    # Flags
    parser.add_argument("--filter-only", action="store_true", help="Run data prep only")
    parser.add_argument("--use-filtered", action="store_true", help="Use filtered CSV input")
    parser.add_argument("--judge", action="store_true", help="Enable Multi-Judge Tribunal")
    parser.add_argument("--clear-redis", action="store_true", help="Flush Redis before start")

    return parser.parse_args()


# MAIN
async def main():
    args = parse_arguments()
    log.info("PIPELINE STARTING")

    # Apply Preset overrides before anything else
    if args.preset:
        if args.preset in PRESETS:
            p = PRESETS[args.preset]
            args.gen_workers = p.gen_workers
            args.judge_workers = p.judge_workers
            args.limit = p.limit
            log.info(f"Loaded Preset '{args.preset}': {p.description}")
        else:
            log.error(f"Preset '{args.preset}' not found.")
            return

    # Clear Redis
    if args.clear_redis:
        import redis
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        r.flushall()
        log.info("Redis flushed.")

    # File setup
    FILTERED_FILE = "data/filtered_events.csv"

    # PHASE 1: PREPARATION
    if args.filter_only or args.use_filtered:
        if not os.path.exists(FILTERED_FILE) or args.filter_only:
            log.info("Running Regex Filtering...")
            run_filtering(settings.INPUT_FILE, FILTERED_FILE)

    if args.filter_only:
        log.info("Data Preparation Complete. Stopping.")
        return

    # PHASE 2: LOADING
    input_source = FILTERED_FILE if args.use_filtered else settings.INPUT_FILE
    log.info(f"Loading input: {input_source}")

    if not os.path.exists(input_source):
        log.error("Input file not found.")
        return

    df = pd.read_csv(input_source)
    col = 'event' if 'event' in df.columns else df.columns[0]
    all_events = df[col].unique().tolist()

    # Apply limits
    if args.limit:
        all_events = all_events[:args.limit]
        log.info(f"Limit applied: processing only {len(all_events)} items")
    else:
        log.info(f"Processing all {len(all_events)} items")

    # Fill Redis Queue
    state.populate_queue(all_events)

    # PHASE 3: EXECUTION
    stop_event = asyncio.Event()
    monitor = asyncio.create_task(csv_writer_monitor(settings.OUTPUT_FILE, stop_event))

    log.info(f"Starting: {args.gen_workers} Gen Workers | {args.judge_workers} Judge Workers")

    # Initialize tasks lists
    tasks =[]

    # Spawn Generation Workers
    for i in range(args.gen_workers):
        tasks.append(generation_worker(i, use_judge=args.judge))

    # Spawn Judge Workers (only if requested via CLI or if judge_workers > 0 in preset)
    # If using preset, args.judge must be True, or we force it if judge_workers > 0
    if args.judge or args.judge_workers > 0:
        for i in range(args.judge_workers):
            tasks.append(judgment_worker(i))

    # Wait for completion
    await tqdm.gather(*tasks, desc="Pipeline Progress")

    # Finish
    stop_event.set()
    await monitor
    log.info("Pipeline Finished Successfully.")


if __name__ == "__main__":
    asyncio.run(main())