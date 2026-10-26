"""Human and LLM judgment statistics for the historical and unified forms."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


THRESHOLDS = (50, 60)
KEY = ["original_row_id", "event"]


def repository_root() -> Path:
    for path in (Path.cwd(), *Path.cwd().parents):
        if (path / "data/judged_log.csv").is_file() and (path / "pyproject.toml").is_file():
            return path
    raise FileNotFoundError("Run from inside the forensic_atomic repository.")


def require_columns(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")


def read_judgments(root: Path) -> pd.DataFrame:
    frame = pd.read_csv(root / "data/judged_log.csv", dtype={"original_row_id": "string"}, low_memory=False)
    require_columns(frame, KEY + ["status", "score_avg_all", "approvals_count"], "judged_log.csv")
    frame["status"] = frame["status"].astype("string").str.strip().str.upper()
    frame["score_avg_all"] = pd.to_numeric(frame["score_avg_all"], errors="coerce")
    frame["llm_approved"] = frame["status"].map({"APPROVED": True, "REJECTED": False}).astype("boolean")
    if frame["llm_approved"].isna().any():
        raise ValueError("judged_log.csv contains an unknown status")
    return frame


def unique_judgments(judged: pd.DataFrame) -> pd.DataFrame:
    counts = judged.groupby(KEY, dropna=False).size().rename("matching_log_rows").reset_index()
    unique = judged.merge(counts, on=KEY, validate="m:1")
    return unique.loc[unique["matching_log_rows"].eq(1), KEY + ["status", "score_avg_all", "llm_approved"]]


def read_historical(root: Path, judged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = root / "data/form_results/global_comparison_results.csv"
    frame = pd.read_csv(path, dtype={"original_row_id": "string", "form_id": "string"})
    require_columns(frame, ["form_id"] + KEY + ["human_score", "human_approval_pct", "status", "score_avg_all"], path.name)
    frame["status"] = frame["status"].astype("string").str.strip().str.upper()
    for column in ("human_score", "human_approval_pct", "score_avg_all"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["llm_approved"] = frame["status"].map({"APPROVED": True, "REJECTED": False}).astype("boolean")
    matched = frame.merge(unique_judgments(judged).rename(columns={"status": "log_status", "score_avg_all": "log_score", "llm_approved": "log_approved"}), on=KEY, how="left", validate="m:1")
    audit = pd.DataFrame([{
        "source_rows": len(frame),
        "unique_events": frame[KEY].drop_duplicates().shape[0],
        "matched_log_rows": int(matched["log_status"].notna().sum()),
        "unmatched_or_nonunique_log_rows": int(matched["log_status"].isna().sum()),
        "status_disagreements": int((matched["log_status"].notna() & matched["status"].ne(matched["log_status"])).fillna(False).sum()),
        "score_disagreements_above_0_11": int((matched["score_avg_all"] - matched["log_score"]).abs().gt(0.11).sum()),
    }])
    return frame, audit


def read_unified(root: Path, judged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = root / "data/form_results/unified_human_judgments.csv"
    frame = pd.read_csv(path, dtype={"original_row_id": "string", "form_id": "string"}, low_memory=False)
    require_columns(frame, KEY + ["human_score", "human_approval_pct", "individual_responses_json"], path.name)
    if frame.duplicated(KEY).any():
        raise ValueError("Unified forms contain duplicate event keys")
    frame = frame.merge(unique_judgments(judged), on=KEY, how="left", validate="1:1")
    if frame["status"].isna().any():
        raise ValueError("Some unified form rows do not have a unique LLM log match")
    for column in ("human_score", "human_approval_pct"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["human_score", "human_approval_pct"]].isna().any().any():
        raise ValueError("Unified forms contain missing human scores")
    audit = pd.DataFrame([{
        "source_rows": len(frame),
        "unique_events": frame[KEY].drop_duplicates().shape[0],
        "matched_log_rows": int(frame["status"].notna().sum()),
        "unmatched_or_nonunique_log_rows": int(frame["status"].isna().sum()),
        "status_disagreements": 0,
        "score_disagreements_above_0_11": 0,
    }])
    return frame, audit


def comparison(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for measure in ("human_score", "human_approval_pct", "human_score_and_approval_pct_ge_50"):
        for threshold in THRESHOLDS:
            columns = ["human_score", "human_approval_pct"] if measure == "human_score_and_approval_pct_ge_50" else [measure]
            valid = frame[columns + ["llm_approved"]].dropna()
            if measure == "human_score_and_approval_pct_ge_50":
                human = (valid["human_score"].ge(threshold) & valid["human_approval_pct"].ge(50)).to_numpy(dtype=bool)
            else:
                human = valid[measure].ge(threshold).to_numpy(dtype=bool)
            llm = valid["llm_approved"].to_numpy(dtype=bool)
            tp = int(np.sum(human & llm))
            tn = int(np.sum(~human & ~llm))
            fp = int(np.sum(~human & llm))
            fn = int(np.sum(human & ~llm))
            n = len(valid)
            agreement = (tp + tn) / n if n else np.nan
            expected = (human.mean() * llm.mean() + (1 - human.mean()) * (1 - llm.mean())) if n else np.nan
            precision = tp / (tp + fp) if tp + fp else np.nan
            recall = tp / (tp + fn) if tp + fn else np.nan
            f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else np.nan
            rows.append({
                "human_measure": measure, "threshold": threshold, "n": n,
                "human_approval_pct": round(100 * human.mean(), 2) if n else np.nan,
                "llm_approval_pct": round(100 * llm.mean(), 2) if n else np.nan,
                "agreement_pct": round(100 * agreement, 2) if n else np.nan,
                "cohen_kappa": round((agreement - expected) / (1 - expected), 3) if n and expected < 1 else np.nan,
                "precision_vs_human": round(precision, 3), "recall_vs_human": round(recall, 3),
                "f1_vs_human": round(f1, 3), "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            })
    return pd.DataFrame(rows)


def form_observations(unified: pd.DataFrame) -> pd.DataFrame:
    observations = []
    for row in unified.itertuples(index=False):
        for response in json.loads(row.individual_responses_json):
            number = response.get("form_number")
            if number is None:
                continue
            score = pd.to_numeric(response.get("score_0_10"), errors="coerce")
            decision = str(response.get("decision", "")).strip().upper()
            observations.append({
                "form_number": number, "original_row_id": row.original_row_id, "event": row.event,
                "human_score": float(score) * 10 if pd.notna(score) else np.nan,
                "decision": decision if decision in {"APPROVE", "REJECT"} else None,
                "llm_approved": row.llm_approved,
            })
    data = pd.DataFrame(observations)
    if data.empty:
        raise ValueError("Unified forms contain no individual responses")
    group = ["form_number"] + KEY
    per_event = data.groupby(group, dropna=False).agg(
        human_score=("human_score", "mean"),
        approvals=("decision", lambda values: sum(v == "APPROVE" for v in values)),
        decisions=("decision", lambda values: sum(v in {"APPROVE", "REJECT"} for v in values)),
        responses=("decision", "size"),
        llm_approved=("llm_approved", "first"),
    ).reset_index()
    per_event["human_approval_pct"] = np.where(per_event["decisions"].gt(0), 100 * per_event["approvals"] / per_event["decisions"], np.nan)
    return per_event


def by_form(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    rows = []
    for form, subset in frame.groupby(column, dropna=False):
        for record in comparison(subset).to_dict("records"):
            rows.append({"form_id": form, "event_rows": len(subset), **record})
    return pd.DataFrame(rows)


def by_category(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for category, subset in frame.dropna(subset=["crime_category"]).groupby("crime_category"):
        for record in comparison(subset).to_dict("records"):
            rows.append({"crime_category": category, "event_rows": len(subset), **record})
    return pd.DataFrame(rows)


def historical_categories(root: Path, historical: pd.DataFrame) -> pd.DataFrame:
    atomic = pd.read_csv(root / "data/forensic_atomic.csv", dtype={"original_row_id": "string"}, usecols=KEY + ["crime_category"])
    groups = atomic.groupby(KEY, dropna=False)["crime_category"].agg(["nunique", "first"]).reset_index()
    groups.loc[groups["nunique"].ne(1), "first"] = pd.NA
    return historical.merge(groups[KEY + ["first"]].rename(columns={"first": "crime_category"}), on=KEY, how="left", validate="m:1")


def summary(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    valid = frame[["human_score", "score_avg_all"]].dropna()
    return pd.DataFrame([{
        "cohort": name, "rows": len(frame), "unique_events": frame[KEY].drop_duplicates().shape[0],
        "mean_human_score": round(frame["human_score"].mean(), 2),
        "mean_llm_score": round(frame["score_avg_all"].mean(), 2),
        "mean_absolute_score_difference": round((valid["human_score"] - valid["score_avg_all"]).abs().mean(), 2),
        "llm_approval_pct": round(100 * frame["llm_approved"].dropna().astype(bool).mean(), 2),
    }])


def style_figure(fig: plt.Figure) -> None:
    """Keep exported figures readable regardless of the notebook theme."""
    dark = "#202124"
    fig.patch.set_facecolor("white")
    for ax in fig.axes:
        ax.set_facecolor("white")
        ax.title.set_color(dark)
        ax.xaxis.label.set_color(dark)
        ax.yaxis.label.set_color(dark)
        ax.tick_params(colors=dark)
        for spine in ax.spines.values():
            spine.set_color(dark)
        legend = ax.get_legend()
        if legend is not None:
            legend.get_frame().set_facecolor("white")
            legend.get_frame().set_edgecolor("#b0b0b0")
            for label in legend.get_texts():
                label.set_color(dark)
    if fig._suptitle is not None:
        fig._suptitle.set_color(dark)


def save_figure(table: pd.DataFrame, destination: Path, label: str) -> None:
    measures = (
        ("human_score", "Human score"),
        ("human_approval_pct", "Human approval (%)"),
        ("human_score_and_approval_pct_ge_50", "Score and approval >= 50%"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, (measure, title) in zip(axes, measures):
        subset = table.loc[table["human_measure"].eq(measure)]
        positions = np.arange(len(subset))
        ax.bar(positions - 0.18, subset["human_approval_pct"], width=0.36, label="Human", color="#2a6fbb")
        ax.bar(positions + 0.18, subset["llm_approval_pct"], width=0.36, label="LLM", color="#c05a21")
        ax.set_xticks(positions, subset["threshold"].astype(str))
        ax.set_ylim(0, 100)
        ax.set_xlabel("Threshold")
        ax.set_ylabel("Approval (%)")
        ax.set_title(title)
        ax.legend()
    fig.suptitle(label)
    style_figure(fig)
    fig.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=150, facecolor="white")
    plt.close(fig)


def save_confusion_figures(table: pd.DataFrame, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for row in table.itertuples(index=False):
        matrix = np.array([[row.tn, row.fp], [row.fn, row.tp]])
        fig, ax = plt.subplots(figsize=(5, 4))
        image = ax.imshow(matrix, cmap="Blues")
        ax.set_xticks([0, 1], ["Rejected", "Approved"])
        ax.set_yticks([0, 1], ["Not confirmed", "Confirmed"])
        ax.set_xlabel("LLM decision (official)")
        ax.set_ylabel("Human decision")
        if row.human_measure == "human_score_and_approval_pct_ge_50":
            ax.set_title(f"LLM vs human decisions\nScore >= {row.threshold} and approval >= 50%")
        else:
            ax.set_title(f"LLM vs human decisions\n{row.human_measure.replace('_', ' ').title()} >= {row.threshold}")
        for (i, j), value in np.ndenumerate(matrix):
            red, green, blue, _ = image.cmap(image.norm(value))
            luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            ax.text(j, i, str(int(value)), ha="center", va="center",
                    color="#202124" if luminance > 0.5 else "white")
        style_figure(fig)
        fig.tight_layout()
        fig.savefig(destination / f"confusion_{row.human_measure}_{row.threshold}.png", dpi=150, facecolor="white")
        plt.close(fig)


def save_scores_figure(frame: pd.DataFrame, destination: Path, label: str) -> None:
    data = frame[["human_score", "score_avg_all"]].dropna()
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(data["human_score"], data["score_avg_all"], s=12, alpha=0.35, color="#2a6fbb")
    ax.plot([0, 100], [0, 100], color="black", linewidth=1)
    ax.set(xlim=(0, 100), ylim=(0, 100), xlabel="Mean human score", ylabel="Mean LLM score", title=label)
    style_figure(fig)
    fig.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=150, facecolor="white")
    plt.close(fig)


def run(root: Path | None = None) -> dict[str, pd.DataFrame]:
    root = root or repository_root()
    judged = read_judgments(root)
    historical, historical_audit = read_historical(root, judged)
    unified, unified_audit = read_unified(root, judged)
    if len(historical) != 550 or len(unified) != 671:
        raise ValueError("The source cohort sizes differ from the documented 550 and 671 rows")
    total = pd.DataFrame([{
        "log_rows": len(judged),
        "approved": int(judged["llm_approved"].sum()),
        "rejected": int((~judged["llm_approved"]).sum()),
        "mean_llm_score": round(judged["score_avg_all"].mean(), 2),
    }])
    votes = judged.groupby("approvals_count", dropna=False).size().rename("rows").reset_index()
    policy = pd.DataFrame([{
        "threshold": threshold,
        "majority_and_score_approval_rows": int((judged["approvals_count"].ge(2) & judged["score_avg_all"].ge(threshold)).sum()),
        "score_only_approval_rows": int(judged["score_avg_all"].ge(threshold).sum()),
        "recorded_approval_rows": int(judged["llm_approved"].sum()),
        "total_rows": len(judged),
    } for threshold in THRESHOLDS])
    provider_rows = []
    for slot in (1, 2, 3):
        provider_col, vote_col, score_col = (f"judge{slot}_provider", f"judge{slot}_vote", f"judge{slot}_score")
        if {provider_col, vote_col, score_col}.issubset(judged.columns):
            part = judged[[provider_col, vote_col, score_col]].rename(columns={provider_col: "provider", vote_col: "vote", score_col: "score"})
            provider_rows.append(part)
    providers = pd.concat(provider_rows, ignore_index=True)
    providers["score"] = pd.to_numeric(providers["score"], errors="coerce")
    providers["vote"] = providers["vote"].astype("string").str.strip().str.lower()
    provider_stats = providers.groupby("provider", dropna=False).agg(
        votes=("vote", "size"), approvals=("vote", lambda v: int(v.eq("approve").sum())),
        mean_score=("score", "mean"),
    ).reset_index()
    provider_stats["mean_score"] = provider_stats["mean_score"].round(2)
    form_events = form_observations(unified)
    historical_with_categories = historical_categories(root, historical)
    historical_audit["category_mapped_rows"] = int(historical_with_categories["crime_category"].notna().sum())
    unified_audit["category_mapped_rows"] = int(unified["crime_category"].notna().sum())
    tables = {
        "llm_overview": total,
        "llm_votes": votes,
        "llm_policy_50_60": policy,
        "llm_provider_statistics": provider_stats,
        "historical/summary": summary(historical, "historical"),
        "historical/comparison_50_60": comparison(historical),
        "historical/by_form_50_60": by_form(historical, "form_id"),
        "historical/by_category_50_60": by_category(historical_with_categories),
        "historical/match_audit": historical_audit,
        "unified/summary": summary(unified, "unified"),
        "unified/comparison_50_60": comparison(unified),
        "unified/by_form_50_60": by_form(form_events, "form_number"),
        "unified/by_category_50_60": by_category(unified),
        "unified/form_event_observations": form_events,
        "unified/match_audit": unified_audit,
    }
    output = root / "results/human_llm"
    for name, table in tables.items():
        path = output / f"{name}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False, encoding="utf-8-sig")
    for name in ("historical", "unified"):
        save_figure(tables[f"{name}/comparison_50_60"], output / name / "approval_50_60.png", f"{name.title()} human and LLM decisions")
        save_confusion_figures(tables[f"{name}/comparison_50_60"], output / name / "figures")
        save_scores_figure(historical if name == "historical" else unified, output / name / "score_comparison.png", f"{name.title()} score comparison")
    return tables


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()
    tables = run(args.root)
    print(pd.concat([tables["historical/summary"], tables["unified/summary"]], ignore_index=True).to_string(index=False))
