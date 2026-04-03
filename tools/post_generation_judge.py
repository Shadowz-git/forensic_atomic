import asyncio
import pandas as pd
import json
import os
import sys
import argparse
from tqdm.asyncio import tqdm

# Add project root to system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings
from core.generator import UnifiedGenerator
from core.judge import MultiJudgeSystem
from core.logger import log

# Define which columns contain JSON lists that need to be parsed back
LIST_COLUMNS = [
    'xIntent', 'xNeed', 'xAttr', 'xEffect', 'xReact', 'xWant',
    'oEffect', 'oReact', 'oWant',
    'isAfter', 'HasSubEvent', 'isBefore', 'HinderedBy', 'Causes', 'xReason', 'isFilledBy'
]


def reconstruct_json_from_row(row):
    """
    Reconstructs the dictionary format expected by the Judge System
    starting from a pandas CSV row.
    Resolves '___' placeholders using all isFilledBy values.
    """
    data = {
        "crime_category":    str(row.get("crime_category", "")),
        "crime_subcategory": str(row.get("crime_subcategory", "")),
        "brief_context":     str(row.get("brief_context", "")),
    }

    for col in LIST_COLUMNS:
        val = row.get(col, "[]")
        try:
            if pd.isna(val):
                data[col] = []
            else:
                data[col] = json.loads(val)
        except Exception:
            data[col] = []

    # Resolve '___' placeholder using all isFilledBy values
    event_raw = str(row.get("event", ""))
    filled_by = data.get("isFilledBy", [])

    if "___" in event_raw and filled_by:
        fillers = ", ".join(f'"{v}"' for v in filled_by)
        data["resolved_event"] = f"{event_raw}  [possible targets: {fillers}]"
    else:
        data["resolved_event"] = event_raw

    return data


async def evaluate_single_row(index, row, event, original_row_id, judge_system, sem, valid_results):
    """
    Task to evaluate a single row. Uses a semaphore to limit concurrency.

    Args:
        index:           pandas DataFrame index (local to this chunk).
        row:             pandas Series for this row.
        event:           Raw event string.
        original_row_id: Absolute row index from the source CSV.
        judge_system:    Initialized MultiJudgeSystem instance.
        sem:             Global concurrency semaphore.
        valid_results:   Shared list to collect approved rows.
    """
    async with sem:
        data_dict = reconstruct_json_from_row(row)

        try:
            is_valid, final_data = await judge_system.evaluate_event(
                event, data_dict, original_row_id=original_row_id
            )

            if is_valid and final_data:
                # Remove internal fields before saving
                final_data.pop("resolved_event", None)
                final_data["event"]           = event
                final_data["original_row_id"] = original_row_id
                valid_results.append(final_data)

        except Exception as e:
            log.error(f"Evaluation error on row {index} ('{event}'): {e}")


async def run_post_judgment(input_csv: str, output_csv: str, judgement_log: str, workers: int):
    """
    Main asynchronous function to read the CSV, evaluate all rows, and save the approved ones.
    """
    if not os.path.exists(input_csv):
        print(f"Error: Input file '{input_csv}' not found.")
        return

    print(f"Loading data from {input_csv}...")
    df = pd.read_csv(input_csv)
    total_rows = len(df)
    print(f"Found {total_rows} rows to evaluate.")

    # Initialize the LLM Generator and the Judge System
    gen_client   = UnifiedGenerator()
    judge_system = MultiJudgeSystem(gen_client, judgement_file=judgement_log)

    # Global semaphore for the evaluation loop.
    # MultiJudgeSystem already has internal per-provider semaphores;
    # this one prevents launching thousands of tasks at once (memory safety).
    sem = asyncio.Semaphore(workers)

    valid_results = []
    tasks         = []

    print(f"Starting evaluation with {workers} concurrent workers...")
    print(f"Judgement log → {judgement_log}")

    for index, row in df.iterrows():
        event = str(row.get("event", "Unknown Event"))

        # Use 'original_row_id' if present (added by split_dataset.py),
        # otherwise fall back to the local DataFrame index.
        original_row_id = int(row["original_row_id"]) if "original_row_id" in row else index

        tasks.append(
            evaluate_single_row(
                index, row, event, original_row_id,
                judge_system, sem, valid_results
            )
        )

    # Execute all tasks with a progress bar
    await tqdm.gather(*tasks, desc="Judging Events")

    print(f"Evaluation complete. Approved/Rewritten rows: {len(valid_results)} out of {total_rows}")

    if valid_results:
        final_df = pd.DataFrame(valid_results)

        # Ensure lists are serialised back to JSON strings for CSV storage
        for col in final_df.columns:
            if col not in ["event", "original_row_id",
                           "crime_category", "crime_subcategory", "brief_context"]:
                final_df[col] = final_df[col].apply(
                    lambda x: json.dumps(x) if isinstance(x, list) else x
                )

        # Column order: original_row_id first, then the rest in source order
        original_cols = ["original_row_id", "event"] + [
            c for c in df.columns if c not in ("original_row_id", "event")
        ]
        final_df = final_df.reindex(columns=original_cols)

        os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
        final_df.to_csv(output_csv, index=False)
        print(f"Saved judged dataset to {output_csv}")
    else:
        print("No rows passed the evaluation. Output file not created.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the Multi-Judge system on an existing CSV dataset."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the unjudged CSV file (e.g. data/to_be_judged/to_judge_1.csv)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to save the approved/rewritten rows (e.g. data/judged/judged_events_1.csv)"
    )
    parser.add_argument(
        "--judgement_log",
        type=str,
        default=settings.JUDGEMENT_FILE,
        help="Path to the per-run judgement audit log (default: settings.JUDGEMENT_FILE)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of concurrent rows to process (default: 1)"
    )

    args = parser.parse_args()

    asyncio.run(
        run_post_judgment(
            input_csv=args.input,
            output_csv=args.output,
            judgement_log=args.judgement_log,
            workers=args.workers,
        )
    )