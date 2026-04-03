import asyncio
import json
import csv
import os
from config.settings import settings
from config.prompts import JUDGE_PROMPT, REWRITE_PROMPT, JUDGE_SYSTEM_PROMPT
from core.generator import UnifiedGenerator
from core.logger import log
from json_repair import repair_json


class MultiJudgeSystem:
    """
    Implements a multi-agent evaluation system.
    It queries multiple LLMs (OpenAI, Anthropic, Gemini) to validate generated content.
    If the content is rejected and ENABLE_REWRITE is True, it attempts to rewrite it
    using specific feedback.

    Test mode (USE_SINGLE_JUDGE_PROVIDER=True):
        All three judge slots are routed through the same provider/model defined by
        SINGLE_JUDGE_PROVIDER and SINGLE_JUDGE_MODEL. This lets you verify that the
        pipeline logic and prompts work correctly without burning credits on three
        different APIs.
    """

    def __init__(self, generator: UnifiedGenerator, judgement_file: str = None):
        self.gen = generator

        # Allow overriding the judgement log path at runtime (e.g. per-chunk logging).
        # Falls back to the value defined in settings if not provided.
        self.judgement_file = judgement_file or settings.JUDGEMENT_FILE

        # Build the judge panel at init time so the rest of the logic is unchanged.
        # In single-provider mode all three slots point to the same provider/model.
        if settings.USE_SINGLE_JUDGE_PROVIDER:
            log.info(
                f"[JudgeSystem] Single-provider mode: all judges → "
                f"{settings.SINGLE_JUDGE_PROVIDER}/{settings.SINGLE_JUDGE_MODEL}"
            )
            self._judge_panel = [
                ("judge_a", settings.SINGLE_JUDGE_PROVIDER, settings.SINGLE_JUDGE_MODEL),
                ("judge_b", settings.SINGLE_JUDGE_PROVIDER, settings.SINGLE_JUDGE_MODEL),
                ("judge_c", settings.SINGLE_JUDGE_PROVIDER, settings.SINGLE_JUDGE_MODEL),
            ]
        else:
            self._judge_panel = [
                ("openai",    "openai",    settings.OPENAI_MODEL),
                ("anthropic", "anthropic", settings.ANTHROPIC_MODEL),
                ("gemini",    "gemini",    settings.GEMINI_MODEL),
            ]

        if not settings.ENABLE_REWRITE:
            log.info("[JudgeSystem] Rewrite loop is DISABLED (ENABLE_REWRITE=false).")

        # Per-provider semaphores to avoid hitting rate limits.
        # In single-provider mode we still key by the real provider name.
        self.semaphores = {
            "openai":     asyncio.Semaphore(settings.JUDGE_SEMAPHORE_LIMIT),
            "anthropic":  asyncio.Semaphore(settings.JUDGE_SEMAPHORE_LIMIT),
            "gemini":     asyncio.Semaphore(settings.JUDGE_SEMAPHORE_LIMIT),
            "openrouter": asyncio.Semaphore(settings.JUDGE_SEMAPHORE_LIMIT),
        }

        # Initialize the CSV log file for judgements
        if not os.path.exists(self.judgement_file):
            os.makedirs(os.path.dirname(self.judgement_file) or ".", exist_ok=True)
            with open(self.judgement_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "original_row_id",          # absolute index from the source CSV
                    "event", "status", "rewritten",
                    "score_avg_all",             # avg across all 3 judges
                    "score_avg_approvers",       # avg across judges who approved
                    "approvals_count",           # 0 / 1 / 2 / 3
                    "majority_vote",             # True if >= 2 approved
                    "judge1_provider", "judge1_vote", "judge1_score", "judge1_reason",
                    "judge2_provider", "judge2_vote", "judge2_score", "judge2_reason",
                    "judge3_provider", "judge3_vote", "judge3_score", "judge3_reason",
                ])

    async def _call_judge(self, label: str, provider: str, model: str, event: str, data: dict):
        """
        Calls a single judge provider to evaluate the content.
        Sends a compact payload with only the most discriminant fields.
        Returns a dictionary with the verdict.

        Args:
            label:    Human-readable name used in logs/CSV (e.g. "openai", "judge_a").
            provider: Actual API provider key recognised by UnifiedGenerator.
            model:    Model identifier for that provider.
            event:    Raw event string (used as fallback if resolved_event is missing).
            data:     Full annotation dict from reconstruct_json_from_row.
        """
        sem_key = provider if provider in self.semaphores else "openrouter"
        async with self.semaphores[sem_key]:
            try:
                # Build compact payload — only fields needed for a forensic verdict
                compact = {
                    "event":   data.get("resolved_event", event),
                    "crime":   f"{data.get('crime_category', '')} / {data.get('crime_subcategory', '')}",
                    "context": data.get("brief_context", ""),
                    "xIntent": data.get("xIntent", []),
                    "xAttr":   data.get("xAttr", []),
                    "xEffect": data.get("xEffect", []),
                    "oEffect": data.get("oEffect", []),
                }

                prompt = JUDGE_PROMPT.format(
                    event=compact["event"],
                    prediction=json.dumps(compact)
                )

                resp = await self.gen.generate(
                    provider,
                    model,
                    prompt,
                    system_prompt=JUDGE_SYSTEM_PROMPT
                )

                clean_resp = self.gen._clean_json(resp)
                result     = json.loads(repair_json(clean_resp))

                vote   = result.get("vote", "reject").lower()
                score  = int(result.get("score", 0))
                reason = result.get("reason", "No reason provided")

                return {"provider": label, "vote": vote, "score": score, "reason": reason}

            except Exception as e:
                log.warning(f"Judge '{label}' failed: {e}")
                return {"provider": label, "vote": "error", "score": 0, "reason": str(e)}

    async def evaluate_event(self, event: str, data: dict, original_row_id: int = -1):
        """
        Main evaluation workflow:

        Round 1 — Initial Voting
            Call the 3 judges in parallel.
            Pass if >= 2 approvals AND avg_score >= 60.

        Round 2 — Refinement (only when ENABLE_REWRITE=True)
            If rejected, ask the Rewriter to fix it based on aggregated feedback.

        Round 3 — Re-evaluation (only when ENABLE_REWRITE=True)
            Ask the other 2 judges to validate the rewritten content.
            Pass only if both approve.

        Args:
            event:           Raw event string.
            data:            Full annotation dict.
            original_row_id: Absolute row index from the source CSV (-1 if unknown).

        Returns: (bool is_valid, dict | None final_data)
        """

        # ROUND 1: Initial Voting
        tasks = [
            self._call_judge(label, provider, model, event, data)
            for label, provider, model in self._judge_panel
        ]
        results = await asyncio.gather(*tasks)

        approvals = [r for r in results if r["vote"] == "approve"]
        avg_score = sum(r["score"] for r in results) / len(results)

        if len(approvals) >= 2 and avg_score >= 60:
            self._log_verdict(original_row_id, event, "APPROVED", False, results)
            return True, data

        # Early exit when rewrite is disabled
        if not settings.ENABLE_REWRITE:
            log.info(
                f"Event '{event}' rejected ({len(approvals)}/{len(results)} approvals, "
                f"avg={avg_score:.1f}). Rewrite disabled → marking as REJECTED."
            )
            self._log_verdict(original_row_id, event, "REJECTED", False, results)
            return False, None

        # ROUND 2: Refinement (Rewrite)
        log.info(
            f"Event '{event}' rejected ({len(approvals)}/{len(results)} approvals). "
            f"Attempting rewrite..."
        )

        feedback_list = [
            f"{r['provider']}: {r['reason']}"
            for r in results if r["vote"] != "approve"
        ]
        feedback = "; ".join(feedback_list)

        try:
            rewriter_prov  = settings.REWRITER_PROVIDER
            rewriter_model = (
                settings.SINGLE_JUDGE_MODEL
                if settings.USE_SINGLE_JUDGE_PROVIDER
                else settings.OPENAI_MODEL
            )

            prompt_rewrite = REWRITE_PROMPT.format(
                event=event,
                json_data=json.dumps(data),
                feedback=feedback,
            )

            new_raw = await self.gen.generate(
                rewriter_prov,
                rewriter_model,
                prompt_rewrite,
                system_prompt="You are an expert Forensic Data Engineer.",
            )

            new_data = json.loads(repair_json(self.gen._clean_json(new_raw)))

            # ROUND 3: Verification of Rewrite
            check_tasks = []

            if settings.USE_SINGLE_JUDGE_PROVIDER:
                for suffix in ("_verify_1", "_verify_2"):
                    check_tasks.append(
                        self._call_judge(
                            f"{settings.SINGLE_JUDGE_PROVIDER}{suffix}",
                            settings.SINGLE_JUDGE_PROVIDER,
                            settings.SINGLE_JUDGE_MODEL,
                            event,
                            new_data,
                        )
                    )
            else:
                for label, provider, model in self._judge_panel:
                    if provider != rewriter_prov:
                        check_tasks.append(
                            self._call_judge(label, provider, model, event, new_data)
                        )

            check_results   = await asyncio.gather(*check_tasks)
            check_approvals = [r for r in check_results if r["vote"] == "approve"]

            if len(check_approvals) == len(check_tasks):
                self._log_verdict(original_row_id, event, "APPROVED", True, check_results)
                return True, new_data
            else:
                self._log_verdict(original_row_id, event, "REJECTED", True, check_results)
                return False, None

        except Exception as e:
            log.error(f"Rewrite failed for '{event}': {e}")
            return False, None

    def _log_verdict(self, original_row_id, event, status, rewritten, details):
        """Logs the final decision to the CSV file for auditing."""
        try:
            approvals   = [r for r in details if r["vote"] == "approve"]
            all_scores  = [r["score"] for r in details]
            appr_scores = [r["score"] for r in approvals]

            score_avg_all       = round(sum(all_scores)  / len(all_scores),  2) if all_scores  else 0
            score_avg_approvers = round(sum(appr_scores) / len(appr_scores), 2) if appr_scores else 0
            approvals_count     = len(approvals)
            majority_vote       = approvals_count >= 2

            row = [
                original_row_id, event, status, rewritten,
                score_avg_all, score_avg_approvers,
                approvals_count, majority_vote,
            ]

            for i in range(3):
                if i < len(details):
                    j = details[i]
                    row.extend([j.get("provider", ""), j.get("vote", ""),
                                j.get("score",    ""), j.get("reason", "")])
                else:
                    row.extend(["", "", "", ""])

            with open(self.judgement_file, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(row)

        except Exception as e:
            log.error(f"Failed to log verdict: {e}")