"""
survey_response_engine.py
===========================
Handles the actual process of getting agents to answer a survey: agent/group
selection, delivery-mode batching, scenario condition assignment, repeated
sampling, and result collection in long format.

This module is deliberately decoupled from app.py — it takes call_api_fn and
generate_system_prompt_fn as parameters rather than importing app.py at
module load time, to avoid circular imports (same pattern used by
uk_england_population.py).

Delivery modes
--------------
  "per_item" — one API call per question per agent. Slowest and most
               expensive, but preserves item independence: the agent never
               sees the rest of the instrument, which is the condition
               under which "survey-awareness" (the model detecting it is
               being tested and smoothing its answers toward apparent
               coherence) is least likely to occur. Closest to a human
               reading one question, answering, and moving to the next.
  "chunked"  — N questions per API call (configurable chunk_size). A
               middle ground: reduces API calls substantially versus
               per_item while limiting how much of the instrument the
               agent sees in any single pass.
  "full_survey" — every question in one call (the original app.py
               behaviour). Cheapest and fastest; most exposed to
               survey-awareness / batch-coherence effects. Verified here
               to handle up to 50 questions per agent in a single pass
               (this was already supported; this module keeps that
               capacity and exposes max_tokens estimation accordingly).

Agent / group selection
------------------------
Callers can pass either:
  - `agent_ids`: a specific list of one or more agent_id values, or
  - `group_filter`: a dict of demographic filter criteria (reuses the same
    filter vocabulary as app.py's _apply_filters / agent_library_v2's
    demographic clusters) that gets resolved against the full agent pool
    at run time.
Both can be combined: a filter narrows the pool, then specific IDs (if any)
further restrict within it.

Repeated sampling
------------------
`repetitions` (default 1) re-asks the same agent the same question N times
at the configured temperature, to surface within-agent response variance —
distinct from between-agent variance, which comes from running multiple
distinct agents. See run-level docstrings for how results are tagged.

Scenario / vignette support
-----------------------------
If a Scenario object is attached to a question set, each agent is assigned
exactly one branch (condition) either randomly or via a fixed assignment
map, and that branch's narrative text is prepended to the question batch
as stimulus material (not itself an answerable item).
"""

from __future__ import annotations

import random
import re
from dataclasses import asdict
from datetime import datetime
from typing import Callable, Optional

from survey_question_types import (
    Question, Scenario, ScenarioBranch,
    build_question_instruction, parse_answer, DECLINE_TOKEN,
    QUESTION_TYPE_LABELS,
)

# ─────────────────────────────────────────────────────────────────────────────
# Agent selection
# ─────────────────────────────────────────────────────────────────────────────

def _get(d: dict, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p, default)
    return cur


def resolve_agent_selection(
    all_agents: list,
    agent_ids: Optional[list] = None,
    group_filter: Optional[dict] = None,
) -> list:
    """
    Resolve the final list of agents to survey.

    group_filter keys (all optional, all AND-combined):
      country, tier, genders (list), age_min, age_max, education_levels (list),
      income_brackets (list), urban_rural (list), political_leanings (list),
      marital_statuses (list), occupation_search (str, substring),
      ethnicity_search (str, substring), religion_search (str, substring),
      clusters (list) — matches agent.get("clusters", []) tags from
      agent_library_v2.py, e.g. ["survey"].
    """
    pool = all_agents

    if group_filter:
        f = group_filter
        if f.get("country"):
            pool = [a for a in pool if f["country"].lower() in
                    (_get(a, "persona", "demographics", "location", "country", default="") or "").lower()]
        if f.get("tier") and f["tier"] != "All":
            pool = [a for a in pool if a.get("tier") == f["tier"]]
        if f.get("genders"):
            pool = [a for a in pool if _get(a, "persona", "demographics", "gender") in f["genders"]]
        if f.get("age_min") is not None or f.get("age_max") is not None:
            def _age_ok(a):
                age = _get(a, "persona", "demographics", "age")
                try:
                    age = int(age)
                except (TypeError, ValueError):
                    return False
                if f.get("age_min") is not None and age < f["age_min"]:
                    return False
                if f.get("age_max") is not None and age > f["age_max"]:
                    return False
                return True
            pool = [a for a in pool if _age_ok(a)]
        if f.get("education_levels"):
            pool = [a for a in pool if _get(a, "persona", "demographics", "education_level") in f["education_levels"]]
        if f.get("income_brackets"):
            pool = [a for a in pool if _get(a, "persona", "demographics", "income_bracket") in f["income_brackets"]]
        if f.get("urban_rural"):
            pool = [a for a in pool if _get(a, "persona", "demographics", "location", "urban_rural") in f["urban_rural"]]
        if f.get("political_leanings"):
            pool = [a for a in pool if _get(a, "persona", "demographics", "political_leaning") in f["political_leanings"]]
        if f.get("marital_statuses"):
            pool = [a for a in pool if _get(a, "persona", "demographics", "marital_status") in f["marital_statuses"]]
        if f.get("occupation_search"):
            pool = [a for a in pool if f["occupation_search"].lower() in
                    (_get(a, "persona", "demographics", "occupation", default="") or "").lower()]
        if f.get("ethnicity_search"):
            pool = [a for a in pool if f["ethnicity_search"].lower() in
                    (_get(a, "persona", "demographics", "ethnicity", default="") or "").lower()]
        if f.get("religion_search"):
            pool = [a for a in pool if f["religion_search"].lower() in
                    (_get(a, "persona", "demographics", "religion", default="") or "").lower()]
        if f.get("clusters"):
            pool = [a for a in pool if set(f["clusters"]) & set(a.get("clusters", []))]

    if agent_ids:
        wanted = set(agent_ids)
        pool = [a for a in pool if a["agent_id"] in wanted]

    return pool


# ─────────────────────────────────────────────────────────────────────────────
# Scenario / condition assignment
# ─────────────────────────────────────────────────────────────────────────────

def assign_conditions(
    agents: list,
    scenario: Scenario,
    mode: str = "random",                 # "random" | "fixed" | "round_robin"
    fixed_branch_id: Optional[str] = None,
) -> dict:
    """
    Return {agent_id: ScenarioBranch} mapping one branch per agent.

      "random"      — each agent independently randomized across branches
                       (mirrors a true between-subjects human study).
      "fixed"        — every agent gets the same branch (fixed_branch_id),
                       useful for isolating persona effects from condition
                       effects.
      "round_robin"  — branches cycled evenly across the agent list, useful
                       for guaranteeing balanced cell sizes.
    """
    assignment = {}
    branches = scenario.branches
    if mode == "fixed":
        branch = next((b for b in branches if b.id == fixed_branch_id), branches[0])
        for ag in agents:
            assignment[ag["agent_id"]] = branch
    elif mode == "round_robin":
        for i, ag in enumerate(agents):
            assignment[ag["agent_id"]] = branches[i % len(branches)]
    else:  # random
        for ag in agents:
            assignment[ag["agent_id"]] = random.choice(branches)
    return assignment


def build_scenario_stimulus(scenario: Scenario, branch: ScenarioBranch) -> str:
    """Compose the full narrative text (intro + assigned branch + outcome) for one agent."""
    parts = [scenario.intro_text.strip(), branch.text.strip()]
    if scenario.outcome_text.strip():
        parts.append(scenario.outcome_text.strip())
    return "\n\n".join(p for p in parts if p)


# ─────────────────────────────────────────────────────────────────────────────
# Lighter-touch system prompt addendum
# ─────────────────────────────────────────────────────────────────────────────
# Per the literature review: avoid over-prompting (model-specific, fragile,
# pushes toward performed rather than psychologically grounded answers) and
# explicitly counteract regression-to-the-mean / sycophancy rather than
# adding more character-roleplay rules.

SURVEY_ADDENDUM = (
    "\n## Answering This Survey\n"
    "Answer as yourself, based only on the profile above. There are no right "
    "or wrong answers — the goal is your honest view, whatever it is. Do not "
    "soften, hedge, or steer your answer toward what seems like the safe or "
    "expected response. Disagreement, ambivalence, or an unusual view are all "
    "valid outcomes. Read each item once and answer it directly without "
    "referring back to other items in this survey."
)


def build_survey_system_prompt(agent: dict, generate_system_prompt_fn: Callable) -> str:
    """Base persona system prompt + the lighter survey-specific addendum."""
    return generate_system_prompt_fn(agent) + SURVEY_ADDENDUM


# ─────────────────────────────────────────────────────────────────────────────
# Prompt assembly per delivery mode
# ─────────────────────────────────────────────────────────────────────────────

def _format_question_block(q: Question, q_index: int) -> str:
    instr = build_question_instruction(q)
    return f"Q{q_index} [{q.id}]: {q.text}\n  {instr}"


def build_user_message(questions: list, start_index: int, stimulus_text: str = "", preamble: str = "") -> str:
    """Build the user-turn message for one batch (1, N, or all questions)."""
    lines = []
    if preamble:
        lines += [preamble.strip(), ""]
    if stimulus_text:
        lines += [stimulus_text, ""]
    lines.append(
        "Answer each question below. Follow the format instruction for each "
        "question exactly. Do not add any text before, between, or after the answers."
    )
    for offset, q in enumerate(questions):
        lines.append("")
        lines.append(_format_question_block(q, start_index + offset))

    lines.append("")
    lines.append("Format your ENTIRE response EXACTLY like this, one line per question:")
    for offset, q in enumerate(questions):
        lines.append(f"Q{start_index + offset}: <your answer>")

    return "\n".join(lines)


def estimate_max_tokens(questions: list) -> int:
    per_q = 0
    for q in questions:
        if q.type == "open_ended":
            per_q += (q.max_words * 2 if q.max_words else 250)
        elif q.type == "grid":
            per_q += 15 * max(len(q.rows), 1)
        else:
            per_q += 20
    return min(per_q + 200, 4000)


def parse_batch_response(raw_response: str, questions: list, start_index: int) -> dict:
    """Parse a multi-question batch response into {question_id: parsed_value}."""
    results = {}
    n = len(questions)
    for offset, q in enumerate(questions):
        q_num = start_index + offset
        next_num = q_num + 1
        if offset < n - 1:
            pattern = rf"Q{q_num}:\s*(.+?)(?=\nQ{next_num}:)"
        else:
            pattern = rf"Q{q_num}:\s*(.+?)$"
        m = re.search(pattern, raw_response, re.DOTALL | re.IGNORECASE)
        raw_answer = m.group(1).strip() if m else ""
        results[q.id] = parse_answer(q, raw_answer)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Core run function
# ─────────────────────────────────────────────────────────────────────────────

def run_survey(
    agents: list,
    questions: list,
    provider: str,
    api_key: str,
    model: str,
    call_api_fn: Callable,
    generate_system_prompt_fn: Callable,
    delivery_mode: str = "full_survey",     # "per_item" | "chunked" | "full_survey"
    chunk_size: int = 5,
    temperature: float = 0.7,
    repetitions: int = 1,
    preamble: str = "",
    scenario: Optional[Scenario] = None,
    scenario_assignment_mode: str = "random",
    scenario_fixed_branch_id: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> list:
    """
    Run a survey across the given agents and return a LONG-format list of
    response rows, one row per (agent, question, repetition):

        {agent_id, agent_name, ...demographic columns..., repetition,
         question_id, question_text, question_type, raw_answer, parsed_answer,
         scenario_branch_id (if applicable)}

    Long format is used (rather than the wide one-row-per-agent format) so
    repeated sampling and grid sub-answers don't need to be flattened into an
    ever-growing column set — see the literature-driven rationale: a single
    deterministic call per agent can't reveal response distribution shape,
    so repetitions > 1 is a first-class case this format needs to support
    cleanly.
    """
    branch_assignment = {}
    if scenario:
        branch_assignment = assign_conditions(
            agents, scenario, mode=scenario_assignment_mode, fixed_branch_id=scenario_fixed_branch_id,
        )

    # Chunk the question list according to delivery mode.
    if delivery_mode == "per_item":
        batches = [[q] for q in questions]
    elif delivery_mode == "chunked":
        batches = [questions[i:i + chunk_size] for i in range(0, len(questions), chunk_size)]
    else:  # full_survey
        batches = [questions]

    total_ops = len(agents) * repetitions * len(batches)
    done_ops = 0
    rows = []

    for ag in agents:
        dm = ag.get("persona", {}).get("demographics", {})
        loc = dm.get("location", {})
        base_row = {
            "agent_id":   ag["agent_id"],
            "agent_name": dm.get("name", "?"),
            "age":        dm.get("age", "N/A"),
            "gender":     dm.get("gender", "N/A"),
            "country":    loc.get("country", "N/A"),
            "urban_rural": loc.get("urban_rural", "N/A"),
            "education":  dm.get("education_level", "N/A"),
            "income":     dm.get("income_bracket", "N/A"),
            "political":  dm.get("political_leaning", "N/A"),
            "ethnicity":  dm.get("ethnicity", "N/A"),
            "religion":   dm.get("religion", "N/A"),
        }

        branch = branch_assignment.get(ag["agent_id"])
        stimulus_text = build_scenario_stimulus(scenario, branch) if (scenario and branch) else ""

        system_prompt = build_survey_system_prompt(ag, generate_system_prompt_fn)

        for rep in range(1, repetitions + 1):
            q_index = 1
            for batch in batches:
                user_message = build_user_message(
                    batch, q_index,
                    stimulus_text=stimulus_text if q_index == 1 else "",
                    preamble=preamble if q_index == 1 else "",
                )
                max_tok = estimate_max_tokens(batch)

                try:
                    raw_reply = call_api_fn(
                        provider=provider, api_key=api_key, model=model,
                        temperature=temperature, max_tokens=max_tok,
                        system_prompt=system_prompt,
                        messages=[{"role": "user", "content": user_message}],
                    )
                    parsed = parse_batch_response(raw_reply, batch, q_index)
                except Exception as e:
                    parsed = {q.id: f"[ERROR: {e}]" for q in batch}
                    raw_reply = f"[ERROR: {e}]"

                for offset, q in enumerate(batch):
                    row = dict(base_row)
                    row.update({
                        "repetition":      rep,
                        "question_id":     q.id,
                        "question_text":   q.text,
                        "question_type":   QUESTION_TYPE_LABELS.get(q.type, q.type),
                        "sensitive":       q.sensitive,
                        "scenario_branch_id": branch.id if branch else "",
                        "scenario_branch_label": branch.label if branch else "",
                        "parsed_answer":   parsed.get(q.id),
                        "is_decline":      parsed.get(q.id) == DECLINE_TOKEN,
                    })
                    rows.append(row)

                q_index += len(batch)
                done_ops += 1
                if progress_callback:
                    progress_callback(done_ops, total_ops, ag, rep)

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Export helpers
# ─────────────────────────────────────────────────────────────────────────────

def results_to_long_csv_rows(results: list) -> list:
    """Already long-format — pass-through helper kept for symmetry/clarity."""
    return results


def results_to_wide_summary(results: list) -> list:
    """
    Collapse long-format results into one row per (agent, repetition), with
    one column per question_id. Loses grid sub-structure (stored as a dict
    string) — intended for quick human scanning, not analysis. Use the long
    format for anything quantitative.
    """
    grouped: dict = {}
    for r in results:
        key = (r["agent_id"], r["repetition"])
        if key not in grouped:
            grouped[key] = {
                "agent_id": r["agent_id"], "agent_name": r["agent_name"],
                "age": r["age"], "gender": r["gender"], "country": r["country"],
                "repetition": r["repetition"],
            }
        grouped[key][r["question_id"]] = r["parsed_answer"]
    return list(grouped.values())
