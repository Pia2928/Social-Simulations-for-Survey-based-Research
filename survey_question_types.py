"""
survey_question_types.py
=========================
Question schema for the Social Simulation Agent Builder, derived from a
side-by-side format analysis of the BFI-2, WVS Wave 7, BSA 2024, OPN, and a
vignette/scenario experimental design (Kornowicz et al., 2025).

This module is intentionally storage-format-only: it defines what a question
*is* (its type, its scale, its options, its delivery instruction) and how to
parse an answer back into structured data. It does not call any LLM and does
not know about agents — see survey_response_engine.py for that.

Design choices driven by the source-document analysis:
  - Every structured type carries a DECLINE option ("don't know" / "prefer
    not to say") because every real instrument inspected offers one. This
    also counteracts the sycophancy/over-compliance failure mode noted in
    the literature review — an agent should be able to legitimately decline
    rather than always producing a confident answer.
  - "grid" exists because BSA's Welfare/LeftRight/LibAuth batteries (and
    WVS Q1-Q6, Q58-Q89, etc.) are delivered as ONE shared scale applied to
    several statement rows in one breath, not as N independent questions.
  - "ranked_choice" exists for WVS-style "first choice / second choice from
    the same option list" items (Q152-Q157), which can't be represented as
    two independent mc_single questions (the same option can't be picked
    twice).
  - "numeric" exists for open demographic/numeric fields (birth year,
    household size) that open_ended would otherwise force into prose.
  - "open_ended" now carries a configurable max_words, because the vignette
    study's free-text items are ~20 words, sharply shorter than the
    1-3 sentence default used elsewhere — these are not the same shape.
  - "scenario" is a non-answerable stimulus block: narrative text shown to
    the agent before a set of follow-up questions. It is not itself
    answered, but it can have branches (conditions), exactly one of which
    is assigned to a given agent/run.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Universal decline / refusal handling
# ─────────────────────────────────────────────────────────────────────────────

DECLINE_TOKEN = "DECLINE"  # internal sentinel stored in parsed results
DECLINE_INSTRUCTION = (
    "If you genuinely don't have an opinion or would rather not answer, "
    "you may respond with exactly: DK (don't know) or PNA (prefer not to answer), "
    "instead of an answer. Use this sparingly and only when truly appropriate — "
    "most people do have at least a rough opinion."
)

_DECLINE_PATTERNS = re.compile(r"^\s*(DK|PNA|don'?t know|prefer not to (say|answer))\s*$", re.IGNORECASE)


def _is_decline(raw: str) -> bool:
    return bool(_DECLINE_PATTERNS.match(raw.strip()))


# ─────────────────────────────────────────────────────────────────────────────
# Question type registry
# ─────────────────────────────────────────────────────────────────────────────

QUESTION_TYPE_LABELS = {
    "open_ended":     "Open-ended",
    "true_false":     "True / False",
    "likert":         "Likert Scale",
    "mc_single":      "Multiple Choice (pick one)",
    "mc_multi":       "Multiple Choice (select all that apply)",
    "grid":           "Grid / Battery (shared scale, multiple statements)",
    "ranked_choice":  "Ranked Choice (first / second from shared list)",
    "numeric":        "Numeric (bounded)",
}

# Question types that allow a decline response.
DECLINE_ELIGIBLE = {"true_false", "likert", "mc_single", "mc_multi", "grid", "ranked_choice", "numeric"}


@dataclass
class Question:
    id: str
    text: str
    type: str
    options: list = field(default_factory=list)          # mc_single / mc_multi / ranked_choice
    scale: int = 5                                         # likert / grid
    label_low: str = "Strongly disagree"                   # likert / grid
    label_high: str = "Strongly agree"                     # likert / grid
    rows: list = field(default_factory=list)                # grid: list of {id, text}
    min_value: Optional[float] = None                       # numeric
    max_value: Optional[float] = None                       # numeric
    max_words: Optional[int] = None                         # open_ended length cap
    allow_decline: bool = True
    sensitive: bool = False                                  # flags item for extra-scrutiny handling
    scenario_id: Optional[str] = None                        # links question to a scenario block

    def __post_init__(self):
        if not self.id:
            self.id = f"q_{uuid.uuid4().hex[:8]}"


@dataclass
class ScenarioBranch:
    """One narrative variant of a scenario; one is assigned per agent/run."""
    id: str
    label: str         # short human label, e.g. "Manager + AI norm"
    text: str           # full narrative text shown to the agent


@dataclass
class Scenario:
    """
    A vignette/experimental stimulus block, e.g. the Kornowicz et al. design.
    Contains multiple branches (conditions). Exactly one branch is shown to
    a given agent on a given run; condition assignment happens at run time
    in survey_response_engine.py, not here.
    """
    id: str
    title: str
    intro_text: str               # shared text shown before any branch (common setup)
    branches: list                # list[ScenarioBranch]
    outcome_text: str = ""        # shared text shown after the branch (e.g. negative feedback)

    def __post_init__(self):
        if not self.id:
            self.id = f"sc_{uuid.uuid4().hex[:8]}"


# ─────────────────────────────────────────────────────────────────────────────
# Delivery instruction builder — per-question formatting text sent to the LLM
# ─────────────────────────────────────────────────────────────────────────────

def build_question_instruction(q: Question) -> str:
    """Return the type-specific formatting instruction appended under a question."""
    decline = f" {DECLINE_INSTRUCTION}" if (q.allow_decline and q.type in DECLINE_ELIGIBLE) else ""

    if q.type == "open_ended":
        if q.max_words:
            return f"Respond in approximately {q.max_words} words or fewer. Give your honest, natural response."
        return "Give your honest, natural response (1-3 sentences)."

    if q.type == "true_false":
        return f"Answer ONLY with: 1 (True) or 0 (False).{decline}"

    if q.type == "likert":
        return (f"Answer ONLY with an integer from 1 to {q.scale} "
                f"[1 = {q.label_low}, {q.scale} = {q.label_high}].{decline}")

    if q.type == "mc_single":
        opts = "\n".join(f"     {i+1}. {o}" for i, o in enumerate(q.options))
        return f"{opts}\n  Answer ONLY with the number of your chosen option.{decline}"

    if q.type == "mc_multi":
        opts = "\n".join(f"     {i+1}. {o}" for i, o in enumerate(q.options))
        return f"{opts}\n  Answer with comma-separated numbers of ALL options that apply (e.g. 1,3).{decline}"

    if q.type == "grid":
        rows = "\n".join(f"     {r['id']}. {r['text']}" for r in q.rows)
        return (f"For EACH statement below, answer with an integer from 1 to {q.scale} "
                f"[1 = {q.label_low}, {q.scale} = {q.label_high}].{decline}\n{rows}\n"
                f"  Answer in the format: rowid=value, rowid=value, ... "
                f"(e.g. {q.rows[0]['id']}=2, {q.rows[1]['id'] if len(q.rows) > 1 else 'r2'}=4)")

    if q.type == "ranked_choice":
        opts = "\n".join(f"     {i+1}. {o}" for i, o in enumerate(q.options))
        return (f"{opts}\n  Pick your FIRST choice and SECOND choice (must be different options). "
                f"Answer in the format: first=N, second=M (numbers only).{decline}")

    if q.type == "numeric":
        bounds = ""
        if q.min_value is not None and q.max_value is not None:
            bounds = f" (between {q.min_value} and {q.max_value})"
        return f"Answer with a number only{bounds}.{decline}"

    return "Respond naturally."


# ─────────────────────────────────────────────────────────────────────────────
# Per-question answer parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_answer(q: Question, raw: str):
    """
    Parse one question's raw answer text into a structured value.
    Returns DECLINE_TOKEN if the agent declined, None if unparseable,
    or a type-appropriate value otherwise (int, str, list, dict).
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    if q.allow_decline and q.type in DECLINE_ELIGIBLE and _is_decline(raw):
        return DECLINE_TOKEN

    if q.type == "open_ended":
        return raw

    if q.type == "true_false":
        m = re.search(r"[01]", raw)
        return int(m.group()) if m else None

    if q.type in ("likert", "mc_single"):
        m = re.search(r"\d+", raw)
        return int(m.group()) if m else None

    if q.type == "mc_multi":
        nums = re.findall(r"\d+", raw)
        return ",".join(nums) if nums else None

    if q.type == "numeric":
        m = re.search(r"-?\d+(\.\d+)?", raw)
        if not m:
            return None
        val = float(m.group())
        return int(val) if val.is_integer() else val

    if q.type == "grid":
        # Expected: "r1=2, r2=4, r3=1"
        result = {}
        for part in raw.split(","):
            part = part.strip()
            if "=" not in part:
                continue
            rid, val = part.split("=", 1)
            rid, val = rid.strip(), val.strip()
            if _is_decline(val):
                result[rid] = DECLINE_TOKEN
                continue
            m = re.search(r"\d+", val)
            if m:
                result[rid] = int(m.group())
        return result or None

    if q.type == "ranked_choice":
        first_m = re.search(r"first\s*=\s*(\d+)", raw, re.IGNORECASE)
        second_m = re.search(r"second\s*=\s*(\d+)", raw, re.IGNORECASE)
        if not first_m:
            return None
        return {
            "first": int(first_m.group(1)),
            "second": int(second_m.group(1)) if second_m else None,
        }

    return raw


# ─────────────────────────────────────────────────────────────────────────────
# Convenience constructors (used by import/conversion utilities)
# ─────────────────────────────────────────────────────────────────────────────

def make_grid_from_statements(text_intro: str, statements: list, scale: int = 5,
                               label_low: str = "Strongly disagree",
                               label_high: str = "Strongly agree",
                               sensitive: bool = False) -> Question:
    """
    Build a grid Question from a shared intro and a list of statement strings
    — the shape BSA's Welfare/LeftRight/LibAuth batteries and WVS Q1-Q6 use.
    """
    rows = [{"id": f"r{i+1}", "text": s} for i, s in enumerate(statements)]
    return Question(
        id="", text=text_intro, type="grid",
        scale=scale, label_low=label_low, label_high=label_high,
        rows=rows, sensitive=sensitive,
    )


def make_short_open(text: str, max_words: int = 20, sensitive: bool = False) -> Question:
    """Build a word-capped open-ended Question, matching the vignette-study convention."""
    return Question(id="", text=text, type="open_ended", max_words=max_words,
                     allow_decline=False, sensitive=sensitive)


# ─────────────────────────────────────────────────────────────────────────────
# Questionnaire import  (CSV and JSON)
# ─────────────────────────────────────────────────────────────────────────────
# Two upload formats are supported so users can choose fidelity vs. convenience:
#
#   JSON  — full fidelity. A list of question objects (and optional scenarios)
#           that mirror the Question/Scenario dataclasses exactly. Handles every
#           type including grids, ranked_choice, and scenario branches.
#
#   CSV   — convenient, Excel-friendly, flat. One row per question. Multi-value
#           cells (mc options, grid statement rows) use a PIPE "|" separator,
#           because commas already separate CSV columns. Columns are matched
#           case-insensitively; unknown columns are ignored; absent columns
#           fall back to the Question dataclass defaults.
#
# Both paths funnel through question_from_dict() so validation is identical.

import csv as _csv
import io as _io
import json as _json

# Canonical CSV column set (all optional except text & type).
CSV_COLUMNS = [
    "text", "type", "scale", "label_low", "label_high",
    "options", "rows", "min_value", "max_value", "max_words",
    "allow_decline", "sensitive",
]

# Human-friendly type aliases accepted on import, mapped to canonical types.
_TYPE_ALIASES = {
    "open": "open_ended", "open_ended": "open_ended", "text": "open_ended",
    "tf": "true_false", "true_false": "true_false", "boolean": "true_false",
    "likert": "likert", "scale_q": "likert",
    "mc": "mc_single", "mc_single": "mc_single", "single": "mc_single",
    "mc_multi": "mc_multi", "multi": "mc_multi", "checkbox": "mc_multi",
    "grid": "grid", "battery": "grid", "matrix": "grid",
    "ranked_choice": "ranked_choice", "ranked": "ranked_choice", "rank": "ranked_choice",
    "numeric": "numeric", "number": "numeric",
}


class QuestionnaireImportError(ValueError):
    """Raised when an uploaded questionnaire can't be parsed into Questions."""


def _coerce_bool(v, default=True):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "t"):
        return True
    if s in ("0", "false", "no", "n", "f"):
        return False
    return default


def _coerce_int(v, default=None):
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _coerce_float(v, default=None):
    if v is None or str(v).strip() == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _split_multi(v):
    """Split a CSV multi-value cell on '|' (preferred) or newlines."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v)
    sep = "|" if "|" in s else "\n"
    return [part.strip() for part in s.split(sep) if part.strip()]


def question_from_dict(d: dict) -> Question:
    """
    Build (and validate) a Question from a plain dict. Shared by both the JSON
    and CSV import paths. Raises QuestionnaireImportError on invalid input.
    """
    text = str(d.get("text", "")).strip()
    if not text:
        raise QuestionnaireImportError("Question is missing 'text'.")

    raw_type = str(d.get("type", "")).strip().lower()
    q_type = _TYPE_ALIASES.get(raw_type)
    if q_type is None:
        raise QuestionnaireImportError(
            f"Unknown question type {raw_type!r} for {text[:50]!r}. "
            f"Valid types: {', '.join(sorted(set(_TYPE_ALIASES.values())))}."
        )

    kwargs = dict(id=str(d.get("id", "")).strip(), text=text, type=q_type)
    kwargs["sensitive"] = _coerce_bool(d.get("sensitive"), default=False)

    # allow_decline: forced off for open_ended (matches manual builder behaviour).
    if q_type == "open_ended":
        kwargs["allow_decline"] = False
        kwargs["max_words"] = _coerce_int(d.get("max_words"), default=None)

    elif q_type == "likert":
        kwargs["allow_decline"] = _coerce_bool(d.get("allow_decline"), default=True)
        kwargs["scale"] = _coerce_int(d.get("scale"), default=5) or 5
        kwargs["label_low"] = str(d.get("label_low") or "Strongly disagree")
        kwargs["label_high"] = str(d.get("label_high") or "Strongly agree")

    elif q_type in ("mc_single", "mc_multi", "ranked_choice"):
        kwargs["allow_decline"] = _coerce_bool(d.get("allow_decline"), default=True)
        opts = _split_multi(d.get("options"))
        if len(opts) < 2:
            raise QuestionnaireImportError(
                f"{q_type} question {text[:50]!r} needs at least 2 options "
                f"(got {len(opts)}). In CSV, separate options with '|'."
            )
        kwargs["options"] = opts

    elif q_type == "grid":
        kwargs["allow_decline"] = _coerce_bool(d.get("allow_decline"), default=True)
        kwargs["scale"] = _coerce_int(d.get("scale"), default=5) or 5
        kwargs["label_low"] = str(d.get("label_low") or "Strongly disagree")
        kwargs["label_high"] = str(d.get("label_high") or "Strongly agree")
        # rows may be: list of {"id","text"}, list of strings, or a "|"-joined cell.
        raw_rows = d.get("rows")
        if isinstance(raw_rows, list) and raw_rows and isinstance(raw_rows[0], dict):
            rows = [{"id": r.get("id") or f"r{i+1}", "text": str(r.get("text", "")).strip()}
                    for i, r in enumerate(raw_rows) if str(r.get("text", "")).strip()]
        else:
            statements = _split_multi(raw_rows)
            rows = [{"id": f"r{i+1}", "text": s} for i, s in enumerate(statements)]
        if not rows:
            raise QuestionnaireImportError(
                f"grid question {text[:50]!r} needs at least 1 statement row. "
                f"In CSV, separate rows with '|'."
            )
        kwargs["rows"] = rows

    elif q_type == "numeric":
        kwargs["allow_decline"] = _coerce_bool(d.get("allow_decline"), default=True)
        kwargs["min_value"] = _coerce_float(d.get("min_value"), default=None)
        kwargs["max_value"] = _coerce_float(d.get("max_value"), default=None)

    elif q_type == "true_false":
        kwargs["allow_decline"] = _coerce_bool(d.get("allow_decline"), default=True)

    return Question(**kwargs)


def questions_from_json(text: str) -> list:
    """
    Parse a JSON questionnaire into a list[Question].

    Accepted shapes:
        [ {question}, {question}, ... ]
        { "questions": [ {question}, ... ] }
    Raises QuestionnaireImportError on malformed input.
    """
    try:
        data = _json.loads(text)
    except _json.JSONDecodeError as e:
        raise QuestionnaireImportError(f"Invalid JSON: {e}") from e

    if isinstance(data, dict):
        items = data.get("questions", [])
    elif isinstance(data, list):
        items = data
    else:
        raise QuestionnaireImportError("JSON must be a list of questions or an object with a 'questions' list.")

    if not items:
        raise QuestionnaireImportError("No questions found in JSON.")

    questions = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise QuestionnaireImportError(f"Question #{i+1} is not an object.")
        try:
            questions.append(question_from_dict(item))
        except QuestionnaireImportError as e:
            raise QuestionnaireImportError(f"Question #{i+1}: {e}") from e
    return questions


def questions_from_csv(text: str) -> list:
    """
    Parse a CSV questionnaire into a list[Question]. One row per question;
    headers matched case-insensitively. Multi-value cells use '|'.
    Raises QuestionnaireImportError on malformed input.
    """
    try:
        reader = _csv.DictReader(_io.StringIO(text))
        if reader.fieldnames is None:
            raise QuestionnaireImportError("CSV appears to be empty.")
        # Normalise headers to lowercase/stripped.
        field_map = {fn: (fn or "").strip().lower() for fn in reader.fieldnames}
        rows = list(reader)
    except _csv.Error as e:
        raise QuestionnaireImportError(f"Invalid CSV: {e}") from e

    if not rows:
        raise QuestionnaireImportError("CSV has a header but no question rows.")

    questions = []
    for i, raw_row in enumerate(rows):
        # Re-key the row with normalised header names.
        row = {field_map.get(k, k): v for k, v in raw_row.items()}
        # Skip fully-blank rows (trailing newlines in spreadsheets).
        if not any((v or "").strip() for v in row.values()):
            continue
        try:
            questions.append(question_from_dict(row))
        except QuestionnaireImportError as e:
            raise QuestionnaireImportError(f"Row #{i+2}: {e}") from e  # +2: header + 1-index
    if not questions:
        raise QuestionnaireImportError("No valid question rows found in CSV.")
    return questions


def import_questions(file_bytes: bytes, filename: str) -> list:
    """
    Dispatch to the right parser based on file extension and return list[Question].
    Falls back to sniffing JSON vs CSV if the extension is unrecognised.
    """
    try:
        text = file_bytes.decode("utf-8-sig")  # tolerate Excel BOM
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    name = (filename or "").lower()
    if name.endswith(".json"):
        return questions_from_json(text)
    if name.endswith(".csv"):
        return questions_from_csv(text)

    # Unknown extension: sniff.
    stripped = text.lstrip()
    if stripped[:1] in ("[", "{"):
        return questions_from_json(text)
    return questions_from_csv(text)


# Sample templates shown in the UI to guide users on format.
SAMPLE_CSV_TEMPLATE = (
    "text,type,scale,label_low,label_high,options,rows,min_value,max_value,max_words,allow_decline,sensitive\n"
    "How satisfied are you with your local area?,likert,5,Very dissatisfied,Very satisfied,,,,,,true,false\n"
    "Which issues matter most to you?,mc_multi,,,,Economy|Health|Immigration|Environment,,,,,true,false\n"
    "\"In your own words, what worries you about the future?\",open_ended,,,,,,,,20,false,false\n"
    "What is your household size?,numeric,,,,,,1,12,,true,false\n"
    "How much do you agree with each statement?,grid,5,Strongly disagree,Strongly agree,,"
    "Government should redistribute income|Big business benefits owners|Ordinary people get a fair share,,,,true,false\n"
)

SAMPLE_JSON_TEMPLATE = _json.dumps([
    {"text": "How satisfied are you with your local area?", "type": "likert",
     "scale": 5, "label_low": "Very dissatisfied", "label_high": "Very satisfied"},
    {"text": "Which issues matter most to you?", "type": "mc_multi",
     "options": ["Economy", "Health", "Immigration", "Environment"]},
    {"text": "What worries you about the future?", "type": "open_ended", "max_words": 20},
    {"text": "How much do you agree with each statement?", "type": "grid", "scale": 5,
     "label_low": "Strongly disagree", "label_high": "Strongly agree",
     "rows": ["Government should redistribute income",
              "Big business benefits its owners",
              "Ordinary working people get a fair share"]},
], indent=2)
