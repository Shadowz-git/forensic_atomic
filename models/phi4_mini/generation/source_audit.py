"""Check the supplied DeepSeek judgments and prompt variant outputs."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def event_key(value: str) -> str:
    return " ".join(value.casefold().split())


def audit_variant(root: Path, name: str, events: list[dict[str, str]]) -> tuple[dict, dict[str, set[tuple[str, str]]]]:
    directory = root / "results/phi4_mini/generation/prompt_variants" / name
    outputs = read_csv(directory / "outputs.csv")
    failures = read_csv(directory / "failed_outputs.csv")
    branches: dict[int, set[int]] = {}
    labels: dict[str, set[tuple[str, str]]] = {}

    for row in outputs:
        index = int(row["row_id"])
        if index not in range(len(events)) or event_key(row["event"]) != event_key(events[index]["event"]):
            raise ValueError(f"{name}: output row ID does not match the selected event")
        branch = int(row["interpretation_idx"])
        if branch not in (0, 1) or branch in branches.setdefault(index, set()):
            raise ValueError(f"{name}: duplicate or unexpected branch index for event {index}")
        if row["status"] != "ok":
            raise ValueError(f"{name}: non-success row in outputs.csv")
        branches[index].add(branch)
        labels.setdefault(event_key(row["event"]), set()).add((row["crime_category"], row["crime_subcategory"]))

    failed_ids: set[int] = set()
    for row in failures:
        index = int(row["row_id"])
        if index not in range(len(events)) or event_key(row["event"]) != event_key(events[index]["event"]):
            raise ValueError(f"{name}: failed row ID does not match the selected event")
        if index in failed_ids:
            raise ValueError(f"{name}: duplicate failed event {index}")
        failed_ids.add(index)
    if set(branches) & failed_ids or set(branches) | failed_ids != set(range(len(events))):
        raise ValueError(f"{name}: successful and failed files do not partition the selected events")

    summary = {
        "variant": name,
        "selected_events": len(events),
        "successful_events": len(branches),
        "failed_events": len(failed_ids),
        "successful_branches": len(outputs),
        "events_with_two_branches": sum(len(indices) == 2 for indices in branches.values()),
        "success_rate_pct": round(100 * len(branches) / len(events), 2),
    }
    return summary, labels


def audit_deepseek(root: Path, events: list[dict[str, str]]) -> pd.DataFrame:
    generated = read_csv(root / "results/phi4_mini/generation/raw/deepseek_generated_events.csv")
    judged = read_csv(root / "results/phi4_mini/generation/judged/deepseek_selected_judgments.csv")
    selected = {event_key(row["event"]) for row in events}
    if {event_key(row["event"]) for row in generated} != selected:
        raise ValueError("DeepSeek outputs do not cover the 35 selected events")
    if len(generated) != 70 or len(judged) != 70:
        raise ValueError("Expected 70 DeepSeek branches and judgments")
    ids = [int(row["original_row_id"]) for row in judged]
    if set(ids) != set(range(len(generated))):
        raise ValueError("DeepSeek judgment IDs do not cover the generated rows exactly once")
    for row, index in zip(judged, ids):
        if event_key(row["event"]) != event_key(generated[index]["event"]):
            raise ValueError(f"DeepSeek judgment {index} does not match its generated event")
    scores = pd.to_numeric(pd.Series([row["score_avg_all"] for row in judged]), errors="raise")
    return pd.DataFrame([{
        "selected_events": len(events),
        "generated_branches": len(generated),
        "matched_judgments": len(judged),
        "approved": sum(row["status"] == "APPROVED" for row in judged),
        "rejected": sum(row["status"] == "REJECTED" for row in judged),
        "mean_score_avg_all": round(scores.mean(), 2),
    }])


def run(root: Path) -> dict[str, pd.DataFrame]:
    root = root.resolve()
    events = read_csv(root / "data/atomic_dataset/selected_events_atomic.csv")
    if len(events) != 35 or len({event_key(row["event"]) for row in events}) != 35:
        raise ValueError("Expected 35 distinct selected events")

    summaries = []
    labels = {}
    for name in ("with_extra_examples", "without_extra_examples"):
        summary, labels[name] = audit_variant(root, name, events)
        summaries.append(summary)
    overlap = []
    for event in sorted(labels["with_extra_examples"].keys() & labels["without_extra_examples"].keys()):
        with_examples = labels["with_extra_examples"][event]
        without_examples = labels["without_extra_examples"][event]
        overlap.append({
            "event": next(row["event"] for row in events if event_key(row["event"]) == event),
            "with_examples_pairs": len(with_examples),
            "without_examples_pairs": len(without_examples),
            "shared_pairs": len(with_examples & without_examples),
            "jaccard": round(len(with_examples & without_examples) / len(with_examples | without_examples), 4),
            "same_pair_set": with_examples == without_examples,
        })

    tables = {
        "prompt_variant_summary": pd.DataFrame(summaries),
        "common_success_label_agreement": pd.DataFrame(overlap),
        "deepseek_judgment_summary": audit_deepseek(root, events),
    }
    variant_dir = root / "results/phi4_mini/generation/prompt_variants"
    judged_dir = root / "results/phi4_mini/generation/judged"
    for name, path in (
        ("prompt_variant_summary", variant_dir / "summary.csv"),
        ("common_success_label_agreement", variant_dir / "common_success_label_agreement.csv"),
        ("deepseek_judgment_summary", judged_dir / "deepseek_summary.csv"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        tables[name].to_csv(path, index=False, encoding="utf-8-sig")
    return tables
