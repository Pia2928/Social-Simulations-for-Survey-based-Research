"""
Social Simulation Agent Builder  v2.2
======================================
Multi-user research tool for synthetic human agent simulation.

Agents are demographics-only: each carries census-aligned demographic
attributes (no life-context or Big Five / OCEAN tiers).

New in v2.1:
  - Multi-question survey builder (up to 50 Qs: open-ended, T/F, Likert, MC single, MC multi)
  - Expanded agent filters (age range, education, income, occupation, ethnicity,
    religion, urban/rural, political leaning, marital status)
  - Fixed semantic search with richer agent summaries
  - Generate Sample: preset census distributions (10 countries) + AI-generated distributions
  - Distribution preview/approval before generating large batches
"""

import streamlit as st
import json
import uuid
import random
import re
import csv
import io
import pandas as pd
from datetime import datetime

# ─── Auth & DB ────────────────────────────────────────────────────────────────

from auth import (
    require_login,
    current_user,
    current_display_name,
    owner_badge_html,
    DISPLAY_NAMES,
    USER_COLORS,
)
import db as _db
from db import load_all_agents, delete_agent, update_agent_data
from census_data import COUNTRY_PRESETS

# ─── New integrations ──────────────────────────────────────────────────────────
# agent_library_v2: usage-cluster + demographic-cluster Agent Library tab
# uk_england_population: England census-representative Generate Sample sub-tab
# survey_question_types / survey_response_engine: redesigned Survey Mode

from agent_library_v2 import ui_agent_library_v2
from uk_england_population import (
    ENGLAND_FIELD_CONFIGS,
    sample_england_skeletons,
    generate_england_agent_from_skeleton,
    ui_england_population_subtab,
    apply_all_correlations,
)
import survey_question_types as sqt
import survey_response_engine as sre

# ─── Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Social Simulation Agent Builder",
    page_icon="👤",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Constants ────────────────────────────────────────────────────────────────

EDUCATION_OPTIONS = [
    "No formal education",
    "Primary school",
    "Some high school",
    "High school diploma / GED",
    "Some college (no degree)",
    "Vocational / Technical degree",
    "Associate degree",
    "Bachelor's degree",
    "Master's degree",
    "Doctoral degree (PhD, MD, JD, etc.)",
]

# Annual GROSS household income, GBP (£). Bands calibrated to the UK
# household income distribution (ONS "Average household income, UK: FYE 2024";
# median gross household income ~£40k, median disposable ~£36.7k).
INCOME_OPTIONS = [
    "Prefer not to say",
    "Under £15,000",
    "£15,000 – £24,999",
    "£25,000 – £34,999",
    "£35,000 – £49,999",
    "£50,000 – £74,999",
    "£75,000 – £99,999",
    "£100,000 – £149,999",
    "£150,000 or more",
]

POLITICAL_OPTIONS = [
    "Not specified",
    "Far left",
    "Left",
    "Center-left",
    "Center / Moderate",
    "Center-right",
    "Right",
    "Far right",
    "Libertarian",
    "Apolitical",
    "Prefer not to say",
]

MARITAL_OPTIONS = ["Single", "In a relationship", "Married", "Separated", "Divorced", "Widowed"]
URBAN_OPTIONS   = ["Urban", "Suburban", "Rural"]
GENDER_OPTIONS  = ["Woman", "Man", "Non-binary", "Other", "Prefer not to say"]

# ── England-sample-mirroring fields ────────────────────────────────────────────
# Build Agent's manual form uses the SAME category vocabularies as the
# Generate Sample > England (Census-representative) sub-tab, so manually built
# and auto-generated agents are directly comparable / filterable together.
ETHNICITY_DETAILED_OPTIONS = list(ENGLAND_FIELD_CONFIGS["ethnicity_detailed"]["weights"].keys())
RELIGION_DETAILED_OPTIONS  = list(ENGLAND_FIELD_CONFIGS["religion"]["weights"].keys())
ECONOMIC_ACTIVITY_OPTIONS  = list(ENGLAND_FIELD_CONFIGS["economic_activity"]["weights"].keys())
OCCUPATION_SOC_OPTIONS     = list(ENGLAND_FIELD_CONFIGS["occupation_soc"]["weights"].keys())
SOCIAL_GRADE_OPTIONS       = list(ENGLAND_FIELD_CONFIGS["social_grade"]["weights"].keys())
GENERAL_HEALTH_OPTIONS     = list(ENGLAND_FIELD_CONFIGS["general_health"]["weights"].keys())
DISABILITY_OPTIONS         = list(ENGLAND_FIELD_CONFIGS["disability"]["weights"].keys())
HOUSEHOLD_COMPOSITION_OPTIONS = list(ENGLAND_FIELD_CONFIGS["household_composition"]["weights"].keys())
REGION_OPTIONS              = list(ENGLAND_FIELD_CONFIGS["region"]["weights"].keys())
HOUSING_TENURE_OPTIONS      = list(ENGLAND_FIELD_CONFIGS["housing_tenure"]["weights"].keys())


QUESTION_TYPE_LABELS = {
    "open_ended": "Open-ended",
    "true_false": "True / False",
    "likert":     "Likert Scale",
    "mc_single":  "Multiple Choice (pick one)",
    "mc_multi":   "Multiple Choice (select all that apply)",
}

PROVIDER_MODELS = {
    "Anthropic (Claude)": {
        "key_label":       "Anthropic API Key",
        "key_placeholder": "sk-ant-api03-...",
        "key_help":        "Get yours at console.anthropic.com",
        "models":          ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
        "default":         "claude-sonnet-4-6",
        "model_help":      "Sonnet = best balance. Opus = most nuanced. Haiku = cheapest/fastest.",
    },
    "OpenAI (ChatGPT)": {
        "key_label":       "OpenAI API Key",
        "key_placeholder": "sk-...",
        "key_help":        "Get yours at platform.openai.com",
        "models":          ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default":         "gpt-4o",
        "model_help":      "GPT-4o = best balance. GPT-4o-mini = cheaper. GPT-4-turbo = thorough.",
    },
    "Google (Gemini)": {
        "key_label":       "Google AI API Key",
        "key_placeholder": "AIza...",
        "key_help":        "Get yours for free at aistudio.google.com",
        "models":          ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"],
        "default":         "gemini-1.5-pro",
        "model_help":      "1.5 Pro = most capable. Flash = faster and cheaper.",
    },
}

# ─── DB convenience wrappers ──────────────────────────────────────────────────

def save_agent(agent: dict) -> None:
    _db.save_agent(agent, current_user())


@st.cache_data(show_spinner="Loading agents...", ttl=600)
def _fetch_agents():
    return load_all_agents()

def load_agents(force_reload: bool = False) -> list:
    if force_reload:
        st.cache_data.clear()
    return _fetch_agents()


# ─── Utility Functions ────────────────────────────────────────────────────────

def _is_present(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str) and v.strip() in ("", "N/A", "n/a"):
        return False
    return True


def _safe_age(agent: dict):
    """Return agent age as int, or None if not set."""
    age = agent.get("persona", {}).get("demographics", {}).get("age")
    if age is None or str(age) in ("N/A", "n/a", ""):
        return None
    try:
        return int(age)
    except (ValueError, TypeError):
        return None


def generate_system_prompt(agent: dict) -> str:
    p    = agent.get("persona", {})
    d    = p.get("demographics", {})
    name = d.get("name") or "this person"

    lines = []
    lines += [f"You are {name}.", ""]

    demo_parts = []
    if _is_present(d.get("age")):
        demo_parts.append(f"Age: {d['age']}")
    if _is_present(d.get("gender")):
        demo_parts.append(f"Gender: {d['gender']}")

    loc = d.get("location", {})
    city_or_region = loc.get("city") or loc.get("region")
    place = ", ".join(filter(None, [city_or_region, loc.get("country")]))
    if place:
        urban = loc.get("urban_rural", "")
        demo_parts.append(f"Location: {place}" + (f" ({urban} area)" if urban else ""))

    if _is_present(d.get("ethnicity")):
        demo_parts.append(f"Ethnicity: {d['ethnicity']}")
    if _is_present(d.get("religion")):
        demo_parts.append(f"Religion/spirituality: {d['religion']}")
    if _is_present(d.get("education_level")):
        demo_parts.append(f"Education: {d['education_level']}")
    if _is_present(d.get("occupation")):
        demo_parts.append(f"Occupation: {d['occupation']}")
    if _is_present(d.get("income_bracket")):
        demo_parts.append(f"Household income: {d['income_bracket']}")
    if _is_present(d.get("marital_status")):
        demo_parts.append(f"Marital status: {d['marital_status']}")
    children = d.get("children")
    if children is not None and str(children) not in ("", "N/A", "n/a"):
        demo_parts.append(f"Children: {children}")
    pol = d.get("political_leaning", "")
    if _is_present(pol) and pol not in ("Not specified", "Prefer not to say"):
        demo_parts.append(f"Political leaning: {pol}")
    if _is_present(d.get("diet")):
        demo_parts.append(f"Diet: {d['diet']}")

    # ── England-extension fields (present only on agents that set them) ──────
    if _is_present(d.get("economic_activity")):
        demo_parts.append(f"Employment status: {d['economic_activity']}")
    if _is_present(d.get("occupation_soc")):
        demo_parts.append(f"Occupation category: {d['occupation_soc']}")
    if _is_present(d.get("social_grade")):
        demo_parts.append(f"Social grade: {d['social_grade']}")
    if _is_present(d.get("general_health")):
        demo_parts.append(f"General health: {d['general_health']}")
    if _is_present(d.get("disability")):
        demo_parts.append(f"Disability status: {d['disability']}")
    if _is_present(d.get("household_composition")):
        demo_parts.append(f"Household composition: {d['household_composition']}")
    if _is_present(d.get("housing_tenure")):
        demo_parts.append(f"Housing tenure: {d['housing_tenure']}")
    if _is_present(loc.get("region")):
        demo_parts.append(f"Region: {loc['region']}")
    if _is_present(loc.get("local_authority")):
        demo_parts.append(f"Local authority: {loc['local_authority']}")

    if demo_parts:
        lines += ["## Who You Are"]
        lines += [f"- {p_}" for p_ in demo_parts]
        lines += [""]

    lines += [
        "## Rules You Must Follow",
        "1. You ARE this person. Respond only from their perspective. Never break character.",
        "2. Do NOT say you are an AI, a language model, or an assistant.",
        "3. Keep your answers consistent with your profile throughout the conversation.",
        "4. Use vocabulary and sentence complexity that fits your education level.",
        "5. When asked an opinion question, give YOUR honest opinion as this person would — "
           "including biases, inconsistencies, and blind spots that a real person might have.",
        "6. If you don't know something, respond naturally: 'I'm not sure', "
           "'I haven't really thought about that', or 'That's outside my area' are all fine.",
        "7. For survey-style questions, answer directly and concisely first, then elaborate if it feels natural.",
        "8. Only the information explicitly listed in your profile is part of who you are. "
           "For anything not mentioned, respond with genuine uncertainty — never invent background details.",
    ]

    return "\n".join(lines)


# ─── Multi-provider API caller ────────────────────────────────────────────────

def call_api(provider: str, api_key: str, model: str, temperature: float,
             max_tokens: int, system_prompt: str, messages: list) -> str:
    if provider == "Anthropic (Claude)":
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system_prompt, messages=messages,
        )
        return resp.content[0].text

    elif provider == "OpenAI (ChatGPT)":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        openai_messages = [{"role": "system", "content": system_prompt}] + messages
        resp = client.chat.completions.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            messages=openai_messages,
        )
        return resp.choices[0].message.content

    elif provider == "Google (Gemini)":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        history = []
        for msg in messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})
        last_user_msg = messages[-1]["content"] if messages else ""
        model_obj = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens, temperature=temperature,
            ),
        )
        chat = model_obj.start_chat(history=history)
        return chat.send_message(last_user_msg).text

    else:
        raise ValueError(f"Unknown provider: {provider}")


# ─── Sampling & Generation ────────────────────────────────────────────────────

def _sample_field_value(config):
    mode = config.get("mode", "na")
    if mode == "na":
        return "N/A"
    if mode == "fixed":
        return config["value"]
    if mode == "categorical":
        w = config.get("weights", {})
        if not w:
            return "N/A"
        return random.choices(list(w.keys()), weights=list(w.values()), k=1)[0]
    if mode == "uniform":
        lo, hi = int(config["min"]), int(config["max"])
        return random.randint(min(lo, hi), max(lo, hi))
    if mode == "normal":
        lo   = int(config["min"])
        hi   = int(config["max"])
        mean = float(config.get("mean", (lo + hi) / 2))
        std  = float(config.get("std",  max((hi - lo) / 4, 1.0)))
        return max(lo, min(hi, int(round(random.gauss(mean, std)))))
    if mode == "scale":
        # Continuous BSA-style attitude score in [min, max] (e.g. 1.0–5.0).
        lo   = float(config["min"])
        hi   = float(config["max"])
        mean = float(config.get("mean", (lo + hi) / 2))
        std  = float(config.get("std",  (hi - lo) / 4))
        dp   = int(config.get("decimals", 2))
        return round(max(lo, min(hi, random.gauss(mean, std))), dp)
    return "N/A"


def _sample_demographic_skeletons(n, field_configs):
    country = field_configs.get("country", "N/A")

    # England extension fields beyond the original 11. Imported lazily so app.py
    # keeps working even if census_data is an older build without them.
    try:
        from census_data import ENGLAND_EXTENSION_FIELDS
    except Exception:
        ENGLAND_EXTENSION_FIELDS = ()

    def _maybe(field):
        """Sample a field config, staying backwards-compatible with the old
        boolean flag: True -> "GENERATE" (LLM fills it), False/None -> "N/A",
        a distribution dict -> sampled value."""
        cfg = field_configs.get(field)
        if cfg is None or cfg is False:
            return "N/A"
        if cfg is True:
            return "GENERATE"
        return _sample_field_value(cfg)

    skeletons = []
    for _ in range(n):
        s = {
            "country":           country,
            "age":               _sample_field_value(field_configs.get("age",              {"mode": "na"})),
            "gender":            _sample_field_value(field_configs.get("gender",           {"mode": "na"})),
            "education_level":   _sample_field_value(field_configs.get("education_level",  {"mode": "na"})),
            "income_bracket":    _sample_field_value(field_configs.get("income_bracket",   {"mode": "na"})),
            "urban_rural":       _sample_field_value(field_configs.get("urban_rural",      {"mode": "na"})),
            "political_leaning": _sample_field_value(field_configs.get("political_leaning",{"mode": "na"})),
            "marital_status":    _sample_field_value(field_configs.get("marital_status",   {"mode": "na"})),
            "children":          _sample_field_value(field_configs.get("children",         {"mode": "na"})),
            # Distribution-aware now (was hard-coded "GENERATE"):
            "ethnicity":         _maybe("ethnicity"),
            "religion":          _maybe("religion"),
        }
        # Carry through any England extension fields the preset supplies.
        for field in ENGLAND_EXTENSION_FIELDS:
            if field in field_configs:
                s[field] = _maybe(field)
        # Apply the full England correlation cascade (age, socioeconomic,
        # health, tenure, marital, ethnicity, attitudes, WVS) when the preset
        # includes an employment status (the England presets do). This mirrors
        # the England sub-tab exactly, so an England preset generated through
        # this general path gets the same internal coherence — no teenage
        # widows, no PhD elementary workers, ethnicity-consistent religion, etc.
        # Every pass no-ops on fields the skeleton lacks, so it is safe here.
        # Pure non-England presets (no economic_activity) are left untouched.
        if s.get("economic_activity") not in (None, "N/A", ""):
            s = apply_all_correlations(s)
            # Consistency gate: validate the finished agent and, on the rare
            # hard contradiction, re-apply the correlation cascade (which ends
            # in a deterministic sweep) until it passes or we exhaust attempts.
            # The base pass rate is ~100%, so this almost never loops.
            try:
                from agent_validator import validate_agent
                res = validate_agent(s)
                _tries = 0
                while not res.ok and _tries < 3:
                    s = apply_all_correlations(s)
                    res = validate_agent(s)
                    _tries += 1
                s["_validation_score"] = res.score()
                s["_validation_ok"] = res.ok
            except Exception:
                pass  # validator optional; never block generation
        skeletons.append(s)
    return skeletons


def _repair_truncated_json(s: str):
    """Best-effort repair of a JSON object cut off by max_tokens.

    Walks the string tracking string/escape state and brace/bracket depth, cuts
    back to the last position where the structure was valid up to a complete
    value, then closes any still-open brackets and braces. Returns a repaired
    JSON string, or None if nothing recoverable.
    """
    depth_stack = []
    in_string = False
    escape = False
    last_safe = None  # index just after a completed pair/element

    for i, ch in enumerate(s):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            depth_stack.append(ch)
        elif ch in "}]":
            if depth_stack:
                depth_stack.pop()
            if not depth_stack:
                last_safe = i + 1
        elif ch == "," and depth_stack:
            last_safe = i

    if last_safe is None:
        return None

    head = s[:last_safe].rstrip().rstrip(",")

    # Recompute what is still open at the end of head.
    stack = []
    in_string = False
    escape = False
    for ch in head:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack:
            stack.pop()

    if in_string:  # truncation landed mid-string — not cleanly recoverable
        return None

    closers = "".join("}" if c == "{" else "]" for c in reversed(stack))
    return head + closers


def _extract_json_from_llm(text):
    """Extract a JSON object from an LLM response.

    Handles code fences and — crucially — responses TRUNCATED by max_tokens,
    which the previous version failed on with an opaque "No JSON object found"
    error. When the object is cut off mid-way, it attempts a structural repair
    (closing open braces) so partial agents are recovered rather than lost.
    Raises ValueError with an explicit 'truncated' reason otherwise, so the real
    cause (max_tokens too low) is obvious.
    """
    if not text or not text.strip():
        raise ValueError("Empty LLM response")

    s = text.strip()

    # Strip code fences (```json ... ``` or ``` ... ```). If no closing fence
    # (truncated), just drop a leading ```json line.
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if fence:
        s = fence.group(1).strip()
    else:
        s = re.sub(r"^```(?:json)?\s*", "", s).strip()

    start = s.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in LLM response: {text[:200]!r}")
    s = s[start:]

    # Straight parse.
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Repair a truncated object.
    repaired = _repair_truncated_json(s)
    if repaired is not None:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    looks_truncated = not s.rstrip().endswith("}")
    reason = ("response appears TRUNCATED (no closing brace) — raise max_tokens"
              if looks_truncated else "malformed JSON")
    raise ValueError(f"Could not parse LLM JSON ({reason}): {text[:200]!r}")


# ─── Survey helpers ───────────────────────────────────────────────────────────

def build_batch_survey_prompt(questions: list) -> str:
    """Build a single user message asking the agent all survey questions at once."""
    lines = [
        "Answer each question below as yourself. Follow the format instruction for each question exactly.\n"
    ]
    for i, q in enumerate(questions):
        n = i + 1
        lines.append(f"Q{n}: {q['text']}")
        q_type = q.get("type", "open_ended")
        if q_type == "true_false":
            lines.append("  → Answer ONLY with: 1 (True) or 0 (False)")
        elif q_type == "likert":
            scale    = q.get("scale", 5)
            lo_label = q.get("label_low", "Strongly disagree")
            hi_label = q.get("label_high", "Strongly agree")
            lines.append(f"  → Answer ONLY with an integer from 1 to {scale}  [1 = {lo_label}, {scale} = {hi_label}]")
        elif q_type == "mc_single":
            opts = q.get("options", [])
            for j, o in enumerate(opts):
                lines.append(f"     {j+1}. {o}")
            lines.append("  → Answer ONLY with the number of your chosen option")
        elif q_type == "mc_multi":
            opts = q.get("options", [])
            for j, o in enumerate(opts):
                lines.append(f"     {j+1}. {o}")
            lines.append("  → Answer with comma-separated numbers of ALL options that apply (e.g. 1,3)")
        else:  # open_ended
            lines.append("  → Give your honest, natural response (1–3 sentences)")
        lines.append("")

    lines.append("Format your ENTIRE response EXACTLY like this, one line per question:")
    lines.append("Q1: <your answer>")
    lines.append("Q2: <your answer>")
    lines.append("(and so on for every question)")
    lines.append("Do not add any other text before, between, or after the answers.")

    return "\n".join(lines)


def parse_batch_response(response: str, questions: list) -> dict:
    """Parse a batched survey response into per-question values."""
    results = {}
    n = len(questions)

    for i, q in enumerate(questions):
        q_num  = i + 1
        next_n = q_num + 1

        if i < n - 1:
            pattern = rf'Q{q_num}:\s*(.+?)(?=\nQ{next_n}:)'
        else:
            pattern = rf'Q{q_num}:\s*(.+?)$'

        m   = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        raw = m.group(1).strip() if m else ""

        q_type = q.get("type", "open_ended")
        key    = f"q{q_num}"

        if q_type == "open_ended":
            results[key] = raw
        elif q_type == "true_false":
            m2 = re.search(r'[01]', raw)
            results[key] = int(m2.group()) if m2 else None
        elif q_type in ("likert", "mc_single"):
            m2 = re.search(r'\d+', raw)
            results[key] = int(m2.group()) if m2 else None
        elif q_type == "mc_multi":
            nums = re.findall(r'\d+', raw)
            results[key] = ",".join(nums) if nums else ""

    return results


def _estimate_survey_tokens(questions: list) -> int:
    """Estimate max_tokens needed for a batched survey response."""
    per_q = sum(250 if q.get("type") == "open_ended" else 20 for q in questions)
    return min(per_q + 300, 4000)


# ─── Shared UI helpers ────────────────────────────────────────────────────────

def _apply_filters(
    agents: list,
    country: str = "",
    genders: list = None,
    owner_display: str = "Anyone",
    age_min: int = None,
    age_max: int = None,
    education_levels: list = None,
    income_brackets: list = None,
    occupation_search: str = "",
    ethnicity_search: str = "",
    religion_search: str = "",
    urban_rural: list = None,
    political_leanings: list = None,
    marital_statuses: list = None,
) -> list:
    """Filter a list of agents by the given criteria."""
    f = agents

    if country:
        f = [a for a in f
             if country.lower() in
             a.get("persona", {}).get("demographics", {}).get("location", {}).get("country", "").lower()]

    if genders:
        f = [a for a in f
             if a.get("persona", {}).get("demographics", {}).get("gender") in genders]

    if owner_display and owner_display != "Anyone":
        username = next((u for u, d in DISPLAY_NAMES.items() if d == owner_display), None)
        if username:
            f = [a for a in f if a.get("_owner") == username]

    if age_min is not None:
        f = [a for a in f if _safe_age(a) is not None and _safe_age(a) >= age_min]

    if age_max is not None:
        f = [a for a in f if _safe_age(a) is not None and _safe_age(a) <= age_max]

    if education_levels:
        f = [a for a in f
             if a.get("persona", {}).get("demographics", {}).get("education_level") in education_levels]

    if income_brackets:
        f = [a for a in f
             if a.get("persona", {}).get("demographics", {}).get("income_bracket") in income_brackets]

    if occupation_search:
        f = [a for a in f
             if occupation_search.lower() in
             a.get("persona", {}).get("demographics", {}).get("occupation", "").lower()]

    if ethnicity_search:
        f = [a for a in f
             if ethnicity_search.lower() in
             a.get("persona", {}).get("demographics", {}).get("ethnicity", "").lower()]

    if religion_search:
        f = [a for a in f
             if religion_search.lower() in
             a.get("persona", {}).get("demographics", {}).get("religion", "").lower()]

    if urban_rural:
        f = [a for a in f
             if a.get("persona", {}).get("demographics", {}).get("location", {}).get("urban_rural") in urban_rural]

    if political_leanings:
        f = [a for a in f
             if a.get("persona", {}).get("demographics", {}).get("political_leaning") in political_leanings]

    if marital_statuses:
        f = [a for a in f
             if a.get("persona", {}).get("demographics", {}).get("marital_status") in marital_statuses]

    return f


def _agent_short_label(ag: dict) -> str:
    d    = ag.get("persona", {}).get("demographics", {})
    loc  = d.get("location", {})
    name = d.get("name", "?")
    parts = []
    if d.get("age") not in ("N/A", None, ""):
        parts.append(f"{d['age']}yo")
    if d.get("gender") not in ("N/A", None, ""):
        parts.append(str(d["gender"]))
    city = loc.get("city", "")
    if city and city != "N/A":
        parts.append(city)
    owner  = DISPLAY_NAMES.get(ag.get("_owner", ""), "")
    suffix = f" [{owner}]" if owner else ""
    return f"{name} ({', '.join(parts)}){suffix}" if parts else f"{name}{suffix}"


def semantic_search_agents(query: str, agents: list, api_key: str, top_n: int = 30) -> list:
    """Use Claude Haiku to rank agents by semantic match to a natural-language description."""
    if not agents:
        return []

    summaries = []
    for ag in agents:
        d     = ag.get("persona", {}).get("demographics", {})
        loc   = d.get("location", {})

        parts = [
            f"ID:{ag['agent_id']}",
            f"Name:{d.get('name','?')}",
            f"Age:{d.get('age','?')}yo",
            f"Gender:{d.get('gender','?')}",
            f"Occupation:{d.get('occupation','?')}",
            f"Education:{d.get('education_level','?')}",
            f"Income:{d.get('income_bracket','?')}",
            f"Country:{loc.get('country','?')}",
            f"Region:{loc.get('region','?')}",
            f"LocalAuthority:{loc.get('local_authority','?')}",
            f"Area:{loc.get('urban_rural','?')}",
            f"Ethnicity:{d.get('ethnicity','?')}",
            f"Religion:{d.get('religion','?')}",
            f"Politics:{d.get('political_leaning','?')}",
            f"Marital:{d.get('marital_status','?')}",
            f"Children:{d.get('children','?')}",
        ]

        summaries.append(" | ".join(parts))

    want = min(top_n, len(agents))
    prompt = (
        f'Find the {want} synthetic research agents that BEST match this description:\n'
        f'"{query}"\n\n'
        f'Agents (each starts with its unique ID after "ID:"):\n\n'
        + "\n".join(f"Agent {i+1}: {s}" for i, s in enumerate(summaries))
        + f'\n\nRank by relevance — consider demographics, occupation, political views, '
        f'and any other attributes mentioned in the description. '
        f'Return ONLY a JSON array of the matching agent IDs (the string right after "ID:"), '
        f'ordered best-to-worst. Example: ["abc12345", "def67890"]. '
        f'Raw JSON array only, no other text.'
    )

    raw = call_api(
        provider="Anthropic (Claude)",
        api_key=api_key,
        model="claude-haiku-4-5-20251001",
        temperature=0.0,
        max_tokens=600,
        system_prompt="You are a research assistant. Return only valid JSON arrays. No explanation.",
        messages=[{"role": "user", "content": prompt}],
    )

    raw = raw.strip()
    raw = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    m = re.search(r'\[[\s\S]*\]', raw)
    ids = json.loads(m.group() if m else raw)
    agent_map = {ag["agent_id"]: ag for ag in agents}
    return [agent_map[aid] for aid in ids if aid in agent_map]


# ─── Generate Sample helpers ──────────────────────────────────────────────────

def generate_distributions_from_llm(description: str, api_key: str, provider: str, model: str) -> dict:
    """Ask the LLM to generate realistic demographic distributions for a population description."""
    edu_str    = " | ".join(EDUCATION_OPTIONS)
    income_str = " | ".join(o for o in INCOME_OPTIONS if o != "Prefer not to say")

    prompt = f"""You are a demographic research expert. Generate realistic census-approximate distributions for this population:

"{description}"

Return ONLY a raw JSON object with this exact structure (no markdown, no extra text):
{{
  "country_name": "<country or region this represents>",
  "age_mean": <typical mean age, integer>,
  "age_std": <standard deviation, typically 12-18, integer>,
  "age_min": <minimum age, usually 18 for adult samples, integer>,
  "age_max": <maximum age, integer>,
  "gender": {{"Woman": <weight>, "Man": <weight>, "Non-binary": <weight>}},
  "education_level": {{
    <use ONLY these exact strings: {edu_str}>: <relative weight number>
  }},
  "income_bracket": {{
    <annual GROSS household income in GBP (£); use ONLY these exact strings: {income_str}>: <relative weight number>
  }},
  "urban_rural": {{"Urban": <weight>, "Suburban": <weight>, "Rural": <weight>}},
  "marital_status": {{"Single": <weight>, "In a relationship": <weight>, "Married": <weight>, "Separated": <weight>, "Divorced": <weight>, "Widowed": <weight>}},
  "political_leaning": {{"Far left": <w>, "Left": <w>, "Center-left": <w>, "Center / Moderate": <w>, "Center-right": <w>, "Right": <w>, "Far right": <w>, "Libertarian": <w>, "Apolitical": <w>}},
  "children_mean": <average number of children, float>,
  "children_std": <std dev, float>,
  "children_max": <max children, integer>
}}

Weights are relative (don't need to sum to 100). Base everything on real demographic data."""

    raw = call_api(
        provider=provider, api_key=api_key, model=model,
        temperature=0.2, max_tokens=900,
        system_prompt="You are a demographic expert. Return only valid JSON, nothing else.",
        messages=[{"role": "user", "content": prompt}],
    )

    data = _extract_json_from_llm(raw)

    def _safe_weights(d):
        return {k: float(v) for k, v in d.items()} if isinstance(d, dict) else {}

    return {
        "country":          data.get("country_name", "Unknown"),
        "age":              {"mode": "normal",
                             "mean": int(data.get("age_mean", 38)),
                             "std":  float(data.get("age_std", 17)),
                             "min":  int(data.get("age_min", 18)),
                             "max":  int(data.get("age_max", 90))},
        "gender":           {"mode": "categorical", "weights": _safe_weights(data.get("gender", {}))},
        "education_level":  {"mode": "categorical", "weights": _safe_weights(data.get("education_level", {}))},
        "income_bracket":   {"mode": "categorical", "weights": _safe_weights(data.get("income_bracket", {}))},
        "urban_rural":      {"mode": "categorical", "weights": _safe_weights(data.get("urban_rural", {}))},
        "marital_status":   {"mode": "categorical", "weights": _safe_weights(data.get("marital_status", {}))},
        "political_leaning":{"mode": "categorical", "weights": _safe_weights(data.get("political_leaning", {}))},
        "children":         {"mode": "normal",
                             "mean": float(data.get("children_mean", 1.0)),
                             "std":  float(data.get("children_std", 1.3)),
                             "min":  0,
                             "max":  int(data.get("children_max", 6))},
        "ethnicity":        True,
        "religion":         True,
    }


def format_distribution_summary(field_configs: dict, n: int) -> list:
    """Return a list of [Field, Distribution] rows for displaying a preview table."""
    rows = []
    rows.append(["Country",    field_configs.get("country", "N/A")])
    rows.append(["# Agents",   str(n)])

    age = field_configs.get("age", {"mode": "na"})
    if age.get("mode") == "normal":
        rows.append(["Age", f"~{age['mean']} ± {age.get('std', '?')} yrs (range {age.get('min', 18)}–{age.get('max', 90)})"])
    elif age.get("mode") == "uniform":
        rows.append(["Age", f"Uniform {age.get('min', 18)}–{age.get('max', 90)}"])
    elif age.get("mode") == "fixed":
        rows.append(["Age", str(age.get("value", "?"))])
    else:
        rows.append(["Age", "N/A"])

    for field, label in [
        ("gender",          "Gender"),
        ("education_level", "Education"),
        ("income_bracket",  "Income"),
        ("urban_rural",     "Area type"),
        ("marital_status",  "Marital status"),
        ("political_leaning","Political leaning"),
    ]:
        cfg = field_configs.get(field, {"mode": "na"})
        if cfg.get("mode") == "categorical":
            weights = cfg.get("weights", {})
            total   = sum(weights.values()) or 1
            top     = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
            parts   = [f"{k} ({v/total*100:.0f}%)" for k, v in top]
            if len(weights) > 3:
                parts.append("…")
            rows.append([label, " · ".join(parts)])
        elif cfg.get("mode") == "fixed":
            rows.append([label, str(cfg.get("value", "?"))])
        else:
            rows.append([label, "N/A"])

    chi = field_configs.get("children", {"mode": "na"})
    if chi.get("mode") == "normal":
        rows.append(["Children", f"~{chi.get('mean', 1):.1f} avg (σ {chi.get('std', 1.3):.1f})"])
    else:
        rows.append(["Children", "N/A"])

    def _summarise(cfg):
        """Render any field config (categorical / scale / bool flag) for preview."""
        if cfg is True:
            return "AI-generated"
        if cfg is False or cfg is None:
            return "N/A"
        if isinstance(cfg, dict):
            mode = cfg.get("mode")
            if mode == "categorical":
                weights = cfg.get("weights", {})
                total   = sum(weights.values()) or 1
                top     = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
                parts   = [f"{k} ({v/total*100:.0f}%)" for k, v in top]
                if len(weights) > 3:
                    parts.append("…")
                return " · ".join(parts)
            if mode == "scale":
                return (f"scale {cfg.get('min',1)}–{cfg.get('max',5)} "
                        f"(mean {cfg.get('mean','?')})")
            if mode == "normal":
                return f"~{cfg.get('mean','?')} ± {cfg.get('std','?')}"
            if mode == "fixed":
                return str(cfg.get("value", "?"))
        return "N/A"

    rows.append(["Ethnicity", _summarise(field_configs.get("ethnicity"))])
    rows.append(["Religion",  _summarise(field_configs.get("religion"))])

    # England extension fields, only shown when the full-parity preset is loaded.
    for field, label in [
        ("economic_activity",     "Economic activity"),
        ("occupation_soc",        "Occupation (SOC)"),
        ("social_grade",          "Social grade"),
        ("general_health",        "General health"),
        ("disability",            "Disability"),
        ("household_composition", "Household type"),
        ("region",                "Region"),
        ("housing_tenure",        "Housing tenure"),
        ("scale_left_right",      "BSA left–right"),
        ("scale_lib_auth",        "BSA lib–auth"),
        ("scale_welfarism",       "BSA welfarism"),
    ]:
        if field in field_configs:
            rows.append([label, _summarise(field_configs.get(field))])

    return rows


# ─── Tab 1 — Build Agent ──────────────────────────────────────────────────────

def ui_build_agent():
    st.header("Build a New Agent")

    if "form_id" not in st.session_state:
        st.session_state.form_id = 0
    if "current_agent_id" not in st.session_state:
        st.session_state.current_agent_id = str(uuid.uuid4())[:8]

    fid = st.session_state.form_id

    if st.button("+ New Blank Agent", key="new_agent_btn"):
        st.session_state.form_id         += 1
        st.session_state.current_agent_id = str(uuid.uuid4())[:8]
        st.session_state.pop("build_preview_prompt", None)
        st.rerun()

    st.divider()

    col_form, col_json = st.columns([3, 2], gap="large")

    with col_form:
        # Build Agent produces demographics-only agents that match the
        # Generate Sample categories — no life-context or Big Five.

        st.subheader("Demographics")
        st.caption(
            "Every field must have a value. Select **N/A** or leave a text field blank "
            "for anything unavailable — those fields will be excluded from the agent's role-play profile."
        )
        c1, c2 = st.columns(2)

        with c1:
            name    = st.text_input("Full name *", placeholder="e.g. María García", key=f"name_{fid}")
            age_na  = st.checkbox("Age — N/A", key=f"age_na_{fid}")
            age_val = st.number_input("Age", min_value=10, max_value=110, value=35,
                                       key=f"age_{fid}", disabled=age_na,
                                       label_visibility="collapsed" if age_na else "visible")
            age       = "N/A" if age_na else age_val
            gender    = st.selectbox("Gender", ["N/A"] + GENDER_OPTIONS, key=f"gender_{fid}")
            education = st.selectbox("Education level", ["N/A"] + EDUCATION_OPTIONS, key=f"edu_{fid}")
            occupation = st.text_input("Occupation", placeholder="e.g. High school teacher", key=f"occ_{fid}")

        with c2:
            income = st.selectbox(
                "Household income (annual)",
                ["N/A"] + [o for o in INCOME_OPTIONS if o != "Prefer not to say"],
                key=f"income_{fid}",
            )
            city        = st.text_input("City / Town", placeholder="e.g. Chicago", key=f"city_{fid}")
            country     = st.text_input("Country", placeholder="e.g. United States", key=f"country_{fid}")
            urban_rural = st.selectbox("Area type", ["N/A"] + URBAN_OPTIONS, key=f"urban_{fid}")
            ethnicity   = st.text_input("Ethnicity", placeholder="e.g. Hispanic / Latino", key=f"ethnicity_{fid}")

        c3, c4 = st.columns(2)
        with c3:
            religion  = st.text_input("Religion", placeholder="e.g. Catholic, Atheist, None", key=f"religion_{fid}")
            political = st.selectbox(
                "Political leaning",
                ["N/A"] + [o for o in POLITICAL_OPTIONS if o not in ("Not specified", "Prefer not to say")],
                key=f"political_{fid}",
            )
        with c4:
            marital = st.selectbox("Marital status", ["N/A"] + MARITAL_OPTIONS, key=f"marital_{fid}")
            chi_na  = st.checkbox("Children — N/A", key=f"chi_na_{fid}")
            children_val = st.number_input(
                "Number of children", min_value=0, max_value=20, value=0,
                key=f"children_{fid}", disabled=chi_na,
                label_visibility="collapsed" if chi_na else "visible",
            )
            children = "N/A" if chi_na else children_val

        with st.expander("Additional census-aligned fields (optional — mirrors Generate Sample > England)", expanded=False):
            st.caption(
                "Filling these in lets this hand-built agent be filtered and compared "
                "alongside auto-generated England-sample agents on the same dimensions."
            )
            ec1, ec2 = st.columns(2)
            with ec1:
                ethnicity_detailed = st.selectbox(
                    "Detailed ethnicity (ONS categories)", ["N/A"] + ETHNICITY_DETAILED_OPTIONS,
                    key=f"eng_eth_{fid}",
                    help="If set, overrides the free-text Ethnicity field above in filters/clustering.",
                )
                economic_activity = st.selectbox(
                    "Economic activity status", ["N/A"] + ECONOMIC_ACTIVITY_OPTIONS, key=f"eng_ea_{fid}",
                )
                occupation_soc = st.selectbox(
                    "Occupation category (SOC 2020)", ["N/A"] + OCCUPATION_SOC_OPTIONS, key=f"eng_occsoc_{fid}",
                )
                social_grade = st.selectbox(
                    "Social grade (ABC1C2DE)", ["N/A"] + SOCIAL_GRADE_OPTIONS, key=f"eng_sg_{fid}",
                )
                region = st.selectbox(
                    "Region", ["N/A"] + REGION_OPTIONS, key=f"eng_region_{fid}",
                )
            with ec2:
                general_health = st.selectbox(
                    "General health", ["N/A"] + GENERAL_HEALTH_OPTIONS, key=f"eng_health_{fid}",
                )
                disability = st.selectbox(
                    "Disability status", ["N/A"] + DISABILITY_OPTIONS, key=f"eng_dis_{fid}",
                )
                household_composition = st.selectbox(
                    "Household composition", ["N/A"] + HOUSEHOLD_COMPOSITION_OPTIONS, key=f"eng_hh_{fid}",
                )
                housing_tenure = st.selectbox(
                    "Housing tenure", ["N/A"] + HOUSING_TENURE_OPTIONS, key=f"eng_tenure_{fid}",
                )

        # ── Assemble agent dict ──────────────────────────────────────────────
        agent = {
            "agent_id":   st.session_state.current_agent_id,
            "version":    1,
            "created_at": datetime.now().isoformat(),
            "persona": {
                "demographics": {
                    "name":              name,
                    "age":               age,
                    "gender":            gender,
                    "education_level":   education,
                    "occupation":        occupation.strip() or "N/A",
                    "income_bracket":    income,
                    "location": {
                        "city":        city.strip() or "N/A",
                        "country":     country.strip() or "N/A",
                        "urban_rural": urban_rural,
                        "region":      region,
                    },
                    "economic_activity":      economic_activity,
                    "occupation_soc":         occupation_soc,
                    "social_grade":           social_grade,
                    "general_health":         general_health,
                    "disability":             disability,
                    "household_composition":  household_composition,
                    "housing_tenure":         housing_tenure,
                    "ethnicity":         (ethnicity_detailed if ethnicity_detailed != "N/A"
                                          else (ethnicity.strip() or "N/A")),
                    "religion":          religion.strip() or "N/A",
                    "political_leaning": political,
                    "marital_status":    marital,
                    "children":          children,
                }
            },
            "simulation_config": {"temperature": 0.8, "max_tokens": 512, "notes": ""},
        }

        st.divider()
        cb1, cb2 = st.columns(2)
        with cb1:
            if st.button("Save Agent", type="primary", use_container_width=True, key=f"save_{fid}"):
                if not name:
                    st.error("Please enter a name for the agent.")
                else:
                    save_agent(agent)
                    st.success(f"Saved **{name}** (ID: `{agent['agent_id']}`). Click **+ New Blank Agent** to start another.")
                    st.balloons()
        with cb2:
            if st.button("Preview System Prompt", use_container_width=True, key=f"preview_{fid}"):
                st.session_state["build_preview_prompt"] = generate_system_prompt(agent)

        if "build_preview_prompt" in st.session_state:
            with st.expander("Generated System Prompt", expanded=True):
                st.code(st.session_state["build_preview_prompt"], language="markdown")

    with col_json:
        st.subheader("Live JSON Preview")
        st.caption("Updates automatically as you fill in the form")
        st.json(agent)


# ─── Tab 2 — My Agents ───────────────────────────────────────────────────────

def ui_my_agents():
    st.header("Agent Library")
    st.caption("All agents created by the whole team. Everyone can view, edit, and delete.")

    agents = load_agents()
    if not agents:
        st.info("No agents yet. Go to **Build Agent** or **Generate Sample** to create your first one.")
        return

    col_info, col_filter, col_export = st.columns([2, 3, 1])
    with col_info:
        st.caption(f"**{len(agents)} agent(s)** in the shared library")
    with col_filter:
        mine_only = st.toggle("Show only my agents", key="ma_mine_only")
    with col_export:
        st.download_button(
            "Export all (JSON)",
            data=json.dumps(agents, indent=2, ensure_ascii=False),
            file_name="agent_library.json",
            mime="application/json",
            use_container_width=True,
        )

    display_agents = [a for a in agents if a.get("_owner") == current_user()] if mine_only else agents

    if not display_agents:
        st.info("No agents found. Toggle off 'Show only my agents' to see the full library.")
        return

    PAGE_SIZE = 20
    total_pages = max(1, (len(display_agents) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1,
                           help=f"{len(display_agents)} agents — {PAGE_SIZE} per page")
    start = (page-1)*PAGE_SIZE
    st.caption(f"Showing {start+1}–{min(start+PAGE_SIZE, len(display_agents))} of {len(display_agents)} agents")
    display_agents = display_agents[start:start+PAGE_SIZE]

    for ag in display_agents:
        d    = ag.get("persona", {}).get("demographics", {})
        name = d.get("name", "Unnamed")
        age  = d.get("age", "?")
        occ  = d.get("occupation", "")
        loc  = d.get("location", {})
        _la  = loc.get("local_authority")
        _la  = _la if (_la and _la not in ("N/A", loc.get("city"))) else None
        place = ", ".join(filter(None, [loc.get("city"), _la, loc.get("country")]))
        cfg   = ag.get("simulation_config", {})
        owner = ag.get("_owner", "")

        header = f"**{name}** — {age} y.o. — {occ}{(' — ' + place) if place else ''}"

        with st.expander(header):
            st.markdown(f"Created by: {owner_badge_html(owner)}", unsafe_allow_html=True)

            row1, row2, row3, row4 = st.columns(4)
            with row1:
                st.download_button(
                    "Download JSON",
                    data=json.dumps(ag, indent=2, ensure_ascii=False),
                    file_name=f"agent_{ag['agent_id']}.json",
                    mime="application/json",
                    key=f"dl_{ag['agent_id']}",
                )
            with row2:
                if st.button("Show System Prompt", key=f"sp_{ag['agent_id']}"):
                    key = f"show_sp_{ag['agent_id']}"
                    st.session_state[key] = not st.session_state.get(key, False)
            with row3:
                if st.button("Edit JSON", key=f"edit_btn_{ag['agent_id']}"):
                    key = f"show_edit_{ag['agent_id']}"
                    st.session_state[key] = not st.session_state.get(key, False)
            with row4:
                if st.button("Delete", key=f"rm_{ag['agent_id']}", type="secondary"):
                    delete_agent(ag["agent_id"])
                    st.cache_data.clear()
                    import os as _os
                    for _f in [".agent_cache.json",".survey_sample.json"]:
                        if _os.path.exists(_f): _os.remove(_f)
                    st.rerun()

            if st.session_state.get(f"show_sp_{ag['agent_id']}"):
                st.code(generate_system_prompt(ag), language="markdown")

            if st.session_state.get(f"show_edit_{ag['agent_id']}"):
                edited = st.text_area(
                    "Edit JSON — click Save to apply",
                    value=json.dumps(ag, indent=2, ensure_ascii=False),
                    height=350,
                    key=f"edit_json_{ag['agent_id']}",
                )
                if st.button("Save Changes", key=f"edit_save_{ag['agent_id']}"):
                    try:
                        new_ag = json.loads(edited)
                        new_ag.pop("_owner", None)
                        update_agent_data(new_ag)
                        st.success("Saved.")
                        st.rerun()
                    except json.JSONDecodeError as exc:
                        st.error(f"Invalid JSON — not saved: {exc}")

            st.caption(
                f"ID: `{ag['agent_id']}` | "
                f"Temp: {cfg.get('temperature','?')} | "
                f"Max tokens: {cfg.get('max_tokens','?')}"
            )
            st.json(ag, expanded=False)


# ─── Tab 3 — Chat with Agent ─────────────────────────────────────────────────

def ui_chat():
    st.header("Chat with an Agent")
    st.caption("Test agents in a one-on-one conversation.")

    agents = load_agents()
    if not agents:
        st.info("No agents yet. Create one first in the **Build Agent** tab.")
        return

    agent_options = {
        ag["agent_id"]: f"{ag.get('persona',{}).get('demographics',{}).get('name', ag['agent_id'])} [{DISPLAY_NAMES.get(ag.get('_owner',''),'?')}]"
        for ag in agents
    }
    selected_id = st.selectbox(
        "Select agent",
        options=list(agent_options.keys()),
        format_func=lambda x: agent_options[x],
    )
    selected = next(ag for ag in agents if ag["agent_id"] == selected_id)
    d   = selected.get("persona", {}).get("demographics", {})
    cfg = selected.get("simulation_config", {})

    provider = cfg.get("provider", "Anthropic (Claude)")
    if provider not in PROVIDER_MODELS:
        provider = "Anthropic (Claude)"
    pinfo = PROVIDER_MODELS[provider]

    col_info, col_override = st.columns([2, 1])
    with col_info:
        owner = selected.get("_owner", "")
        st.markdown(
            f"Agent: **{d.get('name','?')}** | "
            f"Created by: {owner_badge_html(owner)}",
            unsafe_allow_html=True,
        )
    with col_override:
        override_provider = st.selectbox(
            "Override provider",
            options=list(PROVIDER_MODELS.keys()),
            index=list(PROVIDER_MODELS.keys()).index(provider),
            label_visibility="collapsed",
        )

    active_provider = override_provider
    active_pinfo    = PROVIDER_MODELS[active_provider]

    if override_provider != provider:
        active_model = st.selectbox(f"Model ({active_provider})", active_pinfo["models"])
    else:
        saved_model  = cfg.get("model", active_pinfo["default"])
        active_model = saved_model if saved_model in active_pinfo["models"] else active_pinfo["default"]

    api_key = st.text_input(
        active_pinfo["key_label"], type="password",
        placeholder=active_pinfo["key_placeholder"],
        help=active_pinfo["key_help"] + " — your key is never saved to disk.",
    )
    if not api_key:
        st.warning(f"Enter your {active_provider} API key to enable the chat.")
        return

    with st.expander("Simulation Parameters"):
        sp1, sp2 = st.columns(2)
        with sp1:
            active_temperature = st.slider("Temperature", 0.0, 1.0, float(cfg.get("temperature", 0.8)), 0.05, key="chat_temp")
        with sp2:
            active_max_tokens = st.number_input("Max tokens per response", 64, 4096, int(cfg.get("max_tokens", 512)), key="chat_tokens")

    if st.button("Show this agent's system prompt"):
        with st.expander("System Prompt", expanded=True):
            st.code(generate_system_prompt(selected), language="markdown")

    st.divider()

    chat_key = f"{selected_id}_{active_provider}_{active_model}"
    if st.session_state.get("chat_key") != chat_key:
        st.session_state.messages = []
        st.session_state.chat_key = chat_key

    for msg in st.session_state.get("messages", []):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input(f"Ask {d.get('name','the agent')} something…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner(f"{d.get('name','Agent')} is thinking…"):
                try:
                    reply = call_api(
                        provider=active_provider, api_key=api_key, model=active_model,
                        temperature=active_temperature, max_tokens=int(active_max_tokens),
                        system_prompt=generate_system_prompt(selected),
                        messages=st.session_state.messages,
                    )
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                except ImportError as e:
                    missing = str(e).split("'")[1] if "'" in str(e) else str(e)
                    st.error(f"Missing package: `{missing}`. Run `pip install {missing}` then restart.")
                except Exception as e:
                    st.error(f"API error: {e}")

    if st.session_state.get("messages"):
        if st.button("Clear conversation history"):
            st.session_state.messages = []
            st.rerun()


# ─── Tab 4 — Survey Mode ─────────────────────────────────────────────────────

def _render_filter_panel(agents: list, key_prefix: str):
    """Render the expanded agent filter panel and return filtered agents."""
    with st.expander("🔍 Filter agents", expanded=True):
        row1c1, row1c2, row1c3 = st.columns(3)
        with row1c1:
            f_country = st.text_input("Country contains", key=f"{key_prefix}_fc")
            f_marital = st.multiselect("Marital status", MARITAL_OPTIONS, key=f"{key_prefix}_fmar")
        with row1c2:
            f_gender = st.multiselect("Gender", GENDER_OPTIONS, key=f"{key_prefix}_fg")
            f_owner  = st.selectbox(
                "Created by", ["Anyone"] + list(DISPLAY_NAMES.values()),
                key=f"{key_prefix}_fo",
            )
        with row1c3:
            f_urban = st.multiselect("Area type", URBAN_OPTIONS, key=f"{key_prefix}_fur")
            f_pol   = st.multiselect(
                "Political leaning",
                [o for o in POLITICAL_OPTIONS if o not in ("Not specified", "Prefer not to say")],
                key=f"{key_prefix}_fpol",
            )

        row2c1, row2c2, row2c3 = st.columns(3)
        with row2c1:
            age_col1, age_col2 = st.columns(2)
            with age_col1:
                f_age_min = st.number_input("Min age", min_value=10, max_value=110, value=10,
                                             key=f"{key_prefix}_famin", step=1)
            with age_col2:
                f_age_max = st.number_input("Max age", min_value=10, max_value=110, value=110,
                                             key=f"{key_prefix}_famax", step=1)
        with row2c2:
            f_edu    = st.multiselect("Education level", EDUCATION_OPTIONS, key=f"{key_prefix}_fedu")
            f_income = st.multiselect(
                "Income bracket",
                [o for o in INCOME_OPTIONS if o != "Prefer not to say"],
                key=f"{key_prefix}_finc",
            )
        with row2c3:
            f_occ  = st.text_input("Occupation contains", key=f"{key_prefix}_focc")
            f_eth  = st.text_input("Ethnicity contains",  key=f"{key_prefix}_feth")
            f_rel  = st.text_input("Religion contains",   key=f"{key_prefix}_frel")

    age_min_val = int(f_age_min) if f_age_min > 10  else None
    age_max_val = int(f_age_max) if f_age_max < 110 else None

    return _apply_filters(
        agents,
        country          = f_country,
        genders          = f_gender,
        owner_display    = f_owner,
        age_min          = age_min_val,
        age_max          = age_max_val,
        education_levels = f_edu or None,
        income_brackets  = f_income or None,
        occupation_search= f_occ,
        ethnicity_search = f_eth,
        religion_search  = f_rel,
        urban_rural      = f_urban or None,
        political_leanings=f_pol or None,
        marital_statuses = f_marital or None,
    )


def ui_survey():
    st.header("Survey Mode")
    st.caption(
        "Build a survey, choose how it's delivered to agents (item-by-item, in chunks, "
        "or all at once), pick which agents answer it — specific agents or a "
        "demographic group — and run it. Results export in long format "
        "(one row per agent × question × repetition)."
    )

    agents = load_agents()
    if not agents:
        st.info("No agents yet. Create some in **Build Agent** or **Generate Sample**.")
        return

    setup_tab, results_tab = st.tabs(["Setup & Run", "Results"])

    # ─── SETUP TAB ──────────────────────────────────────────────────────────
    with setup_tab:

        with st.expander("📚 Designing a benchmark-grade survey — guidance from the literature", expanded=False):
            st.markdown("""
These are **design principles for you, the researcher** — they are deliberately
*not* added to the agents' prompts. Telling an agent about survey-awareness or
distributional benchmarking would make it act like it's being tested, which is
the failure mode the literature warns against. Use these when building and
running the survey instead.

**1. Use validated instrument wording — don't paraphrase.**
LLM responses are sensitive to formatting and exact wording. For comparability
with real human baselines (OPN, BSA, WVS, etc.), paste the *original* item text
and response options verbatim rather than rewording them. The CSV/JSON upload is
the easiest way to keep a canonical instrument file.

**2. Span multiple topic domains in one instrument.**
Single-domain surveys can't reveal whether an agent stays psychologically
consistent moving across topics (e.g. economic attitudes → social policy →
wellbeing). If you're benchmarking, deliberately mix domains in one survey so
cross-domain coherence is observable.

**3. Manage question ordering & survey-awareness.**
Sending the whole instrument at once is the condition most likely to make a model
notice it's being surveyed and smooth its answers. Use **Per item** or **Chunked**
delivery (Section 4) to approximate how a human answers — one question at a time,
without seeing the whole instrument's shape in advance.

**4. Separate sensitive items for extra scrutiny.**
Internal-consistency problems are most acute on sensitive topics. Flag those items
(checkbox per question) so you can weight or filter them differently in analysis,
and consider giving them extra repetitions.

**5. Use repeated sampling if distributional accuracy matters.**
A single answer per agent can't show whether agents reproduce the *distribution*
of human responses, only a point value. Use **Repetitions > 1** at non-zero
**temperature** (Section 4), and/or many agents per demographic cell, to make
response variance observable and comparable to human variance.

**6. Keep some open-ended items.**
Reducing everything to Likert/MC loses the texture of lived experience. Even in a
mostly quantitative survey, keep a few open-ended items as a qualitative arm.
            """)

        # ── Section 1: Survey Builder ───────────────────────────────────────
        st.subheader("1. Build Your Survey")

        if "sqe_q_ids" not in st.session_state:
            st.session_state.sqe_q_ids = []
        if "sqe_q_counter" not in st.session_state:
            st.session_state.sqe_q_counter = 0

        n_qs = len(st.session_state.sqe_q_ids)
        btn_c, cnt_c = st.columns([1, 4])
        with btn_c:
            if st.button("+ Add Question", disabled=n_qs >= 50, key="sqe_add_q"):
                st.session_state.sqe_q_counter += 1
                st.session_state.sqe_q_ids.append(f"sqe_{st.session_state.sqe_q_counter}")
                st.rerun()
        with cnt_c:
            st.caption(f"{n_qs} / 50 questions")

        # ── Upload a questionnaire (CSV or JSON) ────────────────────────────
        def _load_questions_into_builder(questions: list, replace: bool):
            """Populate the manual-builder session_state from parsed Questions so
            imported items appear as normal, editable question rows."""
            if replace:
                for qid in list(st.session_state.get("sqe_q_ids", [])):
                    for k in list(st.session_state.keys()):
                        if k.startswith(f"sqe_") and k.endswith(f"_{qid}"):
                            st.session_state.pop(k, None)
                st.session_state.sqe_q_ids = []

            for q in questions:
                if len(st.session_state.sqe_q_ids) >= 50:
                    break
                st.session_state.sqe_q_counter += 1
                qid = f"sqe_{st.session_state.sqe_q_counter}"
                st.session_state.sqe_q_ids.append(qid)
                st.session_state[f"sqe_text_{qid}"] = q.text
                st.session_state[f"sqe_type_{qid}"] = q.type
                st.session_state[f"sqe_decline_{qid}"] = q.allow_decline
                st.session_state[f"sqe_sensitive_{qid}"] = q.sensitive
                if q.type == "open_ended":
                    st.session_state[f"sqe_maxw_{qid}"] = q.max_words or 0
                elif q.type == "likert":
                    st.session_state[f"sqe_scale_{qid}"] = q.scale
                    st.session_state[f"sqe_low_{qid}"] = q.label_low
                    st.session_state[f"sqe_high_{qid}"] = q.label_high
                elif q.type in ("mc_single", "mc_multi", "ranked_choice"):
                    st.session_state[f"sqe_opts_{qid}"] = "\n".join(q.options)
                elif q.type == "grid":
                    st.session_state[f"sqe_gscale_{qid}"] = q.scale
                    st.session_state[f"sqe_glow_{qid}"] = q.label_low
                    st.session_state[f"sqe_ghigh_{qid}"] = q.label_high
                    st.session_state[f"sqe_rows_{qid}"] = "\n".join(r["text"] for r in q.rows)
                elif q.type == "numeric":
                    st.session_state[f"sqe_nmin_{qid}"] = q.min_value if q.min_value is not None else 0
                    st.session_state[f"sqe_nmax_{qid}"] = q.max_value if q.max_value is not None else 120

        with st.expander("Upload a questionnaire (CSV or JSON) instead of building by hand"):
            st.caption(
                "CSV is best for flat questions (Excel-friendly); JSON preserves full "
                "fidelity for grids, ranked-choice, and scenarios. In CSV, separate "
                "multiple options or grid statements within a cell using a pipe `|`."
            )
            up_c1, up_c2 = st.columns([3, 2])
            with up_c1:
                uploaded = st.file_uploader(
                    "Questionnaire file", type=["csv", "json"], key="sqe_upload",
                    label_visibility="collapsed",
                )
                replace_existing = st.checkbox(
                    "Replace current questions (otherwise append)",
                    value=True, key="sqe_upload_replace",
                )
                if st.button("Import questions", key="sqe_do_import", disabled=uploaded is None):
                    try:
                        parsed = sqt.import_questions(uploaded.getvalue(), uploaded.name)
                        _load_questions_into_builder(parsed, replace=replace_existing)
                        st.success(f"Imported {len(parsed)} question(s) from {uploaded.name}.")
                        st.rerun()
                    except sqt.QuestionnaireImportError as e:
                        st.error(f"Couldn't import: {e}")
                    except Exception as e:
                        st.error(f"Unexpected error reading file: {e}")
            with up_c2:
                st.download_button(
                    "Download CSV template", data=sqt.SAMPLE_CSV_TEMPLATE,
                    file_name="questionnaire_template.csv", mime="text/csv",
                    use_container_width=True, key="sqe_tmpl_csv",
                )
                st.download_button(
                    "Download JSON template", data=sqt.SAMPLE_JSON_TEMPLATE,
                    file_name="questionnaire_template.json", mime="application/json",
                    use_container_width=True, key="sqe_tmpl_json",
                )

        if not st.session_state.sqe_q_ids:
            st.info("Click **+ Add Question** to start building your survey.")
        else:
            for i, qid in enumerate(list(st.session_state.sqe_q_ids)):
                with st.container():
                    r1c1, r1c2, r1c3, r1c4 = st.columns([0.35, 3.3, 2.2, 0.4])
                    with r1c1:
                        st.markdown(f"**Q{i+1}**")
                    with r1c2:
                        st.text_input(
                            "Question text", key=f"sqe_text_{qid}",
                            placeholder="Enter question…", label_visibility="collapsed",
                        )
                    with r1c3:
                        st.selectbox(
                            "Type", list(sqt.QUESTION_TYPE_LABELS.keys()),
                            format_func=lambda x: sqt.QUESTION_TYPE_LABELS[x],
                            key=f"sqe_type_{qid}", label_visibility="collapsed",
                        )
                    with r1c4:
                        if st.button("✕", key=f"sqe_del_{qid}", help="Remove question"):
                            st.session_state.sqe_q_ids.remove(qid)
                            st.rerun()

                    q_type = st.session_state.get(f"sqe_type_{qid}", "open_ended")

                    if q_type == "open_ended":
                        oc1, oc2 = st.columns([1, 3])
                        with oc1:
                            st.number_input(
                                "Max words (0 = no cap, default 1-3 sentences)",
                                min_value=0, max_value=500, value=0, key=f"sqe_maxw_{qid}",
                                help="Set ~20 for a vignette-style short response; leave 0 for the default 1-3 sentence open answer.",
                            )

                    elif q_type == "likert":
                        lc1, lc2, lc3 = st.columns([1, 2, 2])
                        with lc1:
                            st.selectbox("Scale", [3, 4, 5, 6, 7, 10, 11], index=2, key=f"sqe_scale_{qid}")
                        with lc2:
                            st.text_input("Low-end label", key=f"sqe_low_{qid}", placeholder="e.g. Strongly disagree")
                        with lc3:
                            st.text_input("High-end label", key=f"sqe_high_{qid}", placeholder="e.g. Strongly agree")

                    elif q_type in ("mc_single", "mc_multi", "ranked_choice"):
                        st.text_area(
                            "Answer options (one per line)", key=f"sqe_opts_{qid}", height=80,
                            placeholder="Option A\nOption B\nOption C",
                        )

                    elif q_type == "grid":
                        gc1, gc2, gc3 = st.columns([1, 2, 2])
                        with gc1:
                            st.selectbox("Scale", [2, 3, 4, 5, 6, 7, 10, 11], index=3, key=f"sqe_gscale_{qid}")
                        with gc2:
                            st.text_input("Low-end label", key=f"sqe_glow_{qid}", placeholder="e.g. Strongly disagree")
                        with gc3:
                            st.text_input("High-end label", key=f"sqe_ghigh_{qid}", placeholder="e.g. Strongly agree")
                        st.text_area(
                            "Statement rows (one per line) — this is BSA/WVS-style: one shared "
                            "scale applied to several statements in one breath",
                            key=f"sqe_rows_{qid}", height=90,
                            placeholder="Most unemployed people could find a job if they wanted one\n"
                                        "Many people who get benefits don't really deserve help",
                        )

                    elif q_type == "numeric":
                        nc1, nc2 = st.columns(2)
                        with nc1:
                            st.number_input("Min value", value=0, key=f"sqe_nmin_{qid}")
                        with nc2:
                            st.number_input("Max value", value=120, key=f"sqe_nmax_{qid}")

                    fc1, fc2 = st.columns(2)
                    with fc1:
                        st.checkbox(
                            "Allow decline (don't know / prefer not to answer)",
                            value=True, key=f"sqe_decline_{qid}",
                            disabled=(q_type == "open_ended"),
                        )
                    with fc2:
                        st.checkbox(
                            "Flag as sensitive item (for review, doesn't change delivery)",
                            value=False, key=f"sqe_sensitive_{qid}",
                        )

                    st.markdown("---")

        def _collect_questions():
            qs = []
            for qid in st.session_state.get("sqe_q_ids", []):
                text = st.session_state.get(f"sqe_text_{qid}", "").strip()
                q_type = st.session_state.get(f"sqe_type_{qid}", "open_ended")
                if not text:
                    continue
                kwargs = dict(
                    id="", text=text, type=q_type,
                    allow_decline=st.session_state.get(f"sqe_decline_{qid}", True) and q_type != "open_ended",
                    sensitive=st.session_state.get(f"sqe_sensitive_{qid}", False),
                )
                if q_type == "open_ended":
                    maxw = st.session_state.get(f"sqe_maxw_{qid}", 0)
                    kwargs["max_words"] = maxw if maxw and maxw > 0 else None
                elif q_type == "likert":
                    kwargs["scale"] = st.session_state.get(f"sqe_scale_{qid}", 5)
                    kwargs["label_low"] = st.session_state.get(f"sqe_low_{qid}", "Strongly disagree") or "Strongly disagree"
                    kwargs["label_high"] = st.session_state.get(f"sqe_high_{qid}", "Strongly agree") or "Strongly agree"
                elif q_type in ("mc_single", "mc_multi", "ranked_choice"):
                    raw = st.session_state.get(f"sqe_opts_{qid}", "")
                    kwargs["options"] = [o.strip() for o in raw.split("\n") if o.strip()]
                elif q_type == "grid":
                    kwargs["scale"] = st.session_state.get(f"sqe_gscale_{qid}", 5)
                    kwargs["label_low"] = st.session_state.get(f"sqe_glow_{qid}", "Strongly disagree") or "Strongly disagree"
                    kwargs["label_high"] = st.session_state.get(f"sqe_ghigh_{qid}", "Strongly agree") or "Strongly agree"
                    raw_rows = st.session_state.get(f"sqe_rows_{qid}", "")
                    statements = [s.strip() for s in raw_rows.split("\n") if s.strip()]
                    kwargs["rows"] = [{"id": f"r{i+1}", "text": s} for i, s in enumerate(statements)]
                elif q_type == "numeric":
                    kwargs["min_value"] = st.session_state.get(f"sqe_nmin_{qid}")
                    kwargs["max_value"] = st.session_state.get(f"sqe_nmax_{qid}")
                qs.append(sqt.Question(**kwargs))
            return qs

        current_questions = _collect_questions()

        st.divider()

        # ── Section 2: Survey instructions / preamble ───────────────────────
        st.subheader("2. Instructions for Agents (optional)")
        st.caption(
            "A preamble shown once to every agent before they answer, at the top "
            "of the questionnaire — e.g. framing, context, or how to interpret the "
            "scale. Leave blank for no preamble."
        )
        survey_preamble = st.text_area(
            "Questionnaire instructions",
            key="sqe_preamble", height=90,
            placeholder=(
                "e.g. The following questions ask about your views on society and "
                "government. There are no right or wrong answers — please answer "
                "honestly based on your own situation and beliefs."
            ),
            label_visibility="collapsed",
        )

        st.divider()

        # ── Section 3: Optional Scenario / Vignette ─────────────────────────
        st.subheader("3. Optional Scenario / Vignette Stimulus")
        st.caption(
            "For experimental designs (e.g. norm-conformity vignettes): agents read a "
            "narrative before answering the questions above. Each agent is assigned "
            "exactly one branch/condition."
        )
        use_scenario = st.checkbox("Use a scenario for this survey", key="sqe_use_scenario")
        scenario_obj = None
        scenario_assignment_mode = "random"
        scenario_fixed_branch_id = None

        if use_scenario:
            sc_intro = st.text_area("Shared intro text (shown to all agents)", height=90, key="sqe_sc_intro")
            sc_outcome = st.text_area("Shared outcome text (shown after the branch, optional)", height=70, key="sqe_sc_outcome")

            if "sqe_branch_ids" not in st.session_state:
                st.session_state.sqe_branch_ids = []
            if "sqe_branch_counter" not in st.session_state:
                st.session_state.sqe_branch_counter = 0

            if st.button("+ Add Branch / Condition", key="sqe_add_branch"):
                st.session_state.sqe_branch_counter += 1
                st.session_state.sqe_branch_ids.append(f"br_{st.session_state.sqe_branch_counter}")
                st.rerun()

            branches = []
            for bi, bid in enumerate(list(st.session_state.sqe_branch_ids)):
                bcol1, bcol2 = st.columns([1, 4])
                with bcol1:
                    label = st.text_input(f"Branch {bi+1} label", key=f"sqe_blabel_{bid}", placeholder="e.g. Manager + AI norm")
                with bcol2:
                    text = st.text_area(f"Branch {bi+1} narrative", key=f"sqe_btext_{bid}", height=80)
                if label.strip() and text.strip():
                    branches.append(sqt.ScenarioBranch(id=bid, label=label.strip(), text=text.strip()))

            if branches:
                scenario_obj = sqt.Scenario(
                    id="", title="Survey scenario",
                    intro_text=sc_intro, branches=branches, outcome_text=sc_outcome,
                )
                scenario_assignment_mode = st.radio(
                    "Condition assignment",
                    ["random", "round_robin", "fixed"],
                    horizontal=True, key="sqe_assign_mode",
                    format_func=lambda x: {
                        "random": "Random per agent (true between-subjects)",
                        "round_robin": "Round-robin (balanced cell sizes)",
                        "fixed": "Fixed — same branch for every agent",
                    }[x],
                )
                if scenario_assignment_mode == "fixed":
                    branch_choice = st.selectbox(
                        "Fixed branch", [b.id for b in branches],
                        format_func=lambda bid_: next(b.label for b in branches if b.id == bid_),
                        key="sqe_fixed_branch",
                    )
                    scenario_fixed_branch_id = branch_choice
            else:
                st.info("Add at least one branch with a label and narrative text to enable the scenario.")

        st.divider()

        # ── Section 3: Select Agents ─────────────────────────────────────────
        st.subheader("3. Select Agents")
        st.caption(
            "Run against **all** agents matching a demographic filter, or hand-pick "
            "**specific** agents from that filtered pool."
        )

        filtered = _render_filter_panel(agents, "sqe")

        sem_q = st.text_input(
            "Semantic search (describe the people you want)",
            placeholder='e.g. "elderly rural conservative man"', key="sqe_sem",
            help="Uses Claude Haiku to rank the filtered agents by relevance.",
        )
        sidebar_key = st.session_state.get("global_api_key", "")
        if sem_q and st.button("Search semantically", key="sqe_sem_btn"):
            if not sidebar_key:
                st.warning("Set your Anthropic API key in the sidebar to use semantic search.")
            else:
                with st.spinner("Ranking agents by relevance…"):
                    try:
                        filtered = semantic_search_agents(sem_q, filtered, sidebar_key)
                        st.success(f"Found **{len(filtered)}** matching agents.")
                    except Exception as e:
                        st.error(f"Search error: {e}")

        st.caption(f"{len(filtered)} agent(s) match your filters")

        selection_scope = st.radio(
            "Apply to",
            ["All filtered agents", "Specific agents from the filtered list"],
            horizontal=True, key="sqe_scope",
        )

        if selection_scope == "All filtered agents":
            selected_agents = filtered
        else:
            selected_ids = st.multiselect(
                "Select specific agents",
                options=[ag["agent_id"] for ag in filtered],
                format_func=lambda aid: _agent_short_label(
                    next((a for a in filtered if a["agent_id"] == aid), {})
                ),
                key="sqe_selected_ids",
            )
            selected_agents = [a for a in filtered if a["agent_id"] in selected_ids]

        if selected_agents:
            st.success(f"**{len(selected_agents)}** agent(s) will be surveyed")
        else:
            st.warning("No agents selected yet.")

        st.divider()

        # ── Section 4: Delivery, Sampling & Run ──────────────────────────────
        st.subheader("4. Delivery, Sampling & Run")

        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1:
            delivery_mode = st.radio(
                "Delivery mode",
                ["full_survey", "chunked", "per_item"],
                key="sqe_delivery",
                format_func=lambda x: {
                    "full_survey": "Full survey (1 call/agent — all questions at once)",
                    "chunked":     "Chunked (N questions per call)",
                    "per_item":    "Per item (1 call per question — most independent, slowest)",
                }[x],
            )
        with dcol2:
            chunk_size = st.number_input(
                "Chunk size", min_value=1, max_value=20, value=5, key="sqe_chunk_size",
                disabled=(delivery_mode != "chunked"),
            )
        with dcol3:
            repetitions = st.number_input(
                "Repetitions per agent", min_value=1, max_value=20, value=1, key="sqe_repetitions",
                help="Re-ask the same agent the same question N times at the configured "
                     "temperature, to surface within-agent response variance (distinct "
                     "from between-agent variance across different personas).",
            )

        surv_temp = st.slider("Temperature", 0.0, 1.0, 0.7, 0.05, key="sqe_temp")

        provider = st.session_state.get("global_provider", "Anthropic (Claude)")
        model    = st.session_state.get("global_model",    PROVIDER_MODELS[provider]["default"])
        api_key  = st.session_state.get("global_api_key",  "")
        if not api_key:
            st.warning("Set your API key in the **sidebar** before running.")

        n_q = len(current_questions)
        if delivery_mode == "full_survey":
            n_calls_per_agent = 1
        elif delivery_mode == "chunked":
            n_calls_per_agent = -(-n_q // max(int(chunk_size), 1))
        else:
            n_calls_per_agent = n_q
        total_calls = n_calls_per_agent * len(selected_agents) * int(repetitions)

        ready = bool(selected_agents and current_questions and api_key)
        if current_questions:
            st.caption(
                f"**{n_q} question(s)** · **{len(selected_agents)} agent(s)** · "
                f"**{repetitions} repetition(s)** · ~**{total_calls} API call(s)** total"
            )

        if st.button(
            f"▶ Run survey ({total_calls} calls)" if ready else "▶ Run Survey",
            type="primary", use_container_width=True, disabled=not ready, key="sqe_run",
        ):
            prog = st.progress(0.0)
            status = st.empty()

            def _on_progress(done, total, ag, rep):
                nm = ag.get("persona", {}).get("demographics", {}).get("name", "?")
                status.text(f"{nm} — repetition {rep}  ({done}/{total} batches)")
                prog.progress(done / total)

            results = sre.run_survey(
                agents=selected_agents,
                questions=current_questions,
                provider=provider, api_key=api_key, model=model,
                call_api_fn=call_api,
                generate_system_prompt_fn=generate_system_prompt,
                delivery_mode=delivery_mode,
                chunk_size=int(chunk_size),
                temperature=surv_temp,
                repetitions=int(repetitions),
                scenario=scenario_obj,
                scenario_assignment_mode=scenario_assignment_mode,
                scenario_fixed_branch_id=scenario_fixed_branch_id,
                preamble=st.session_state.get("sqe_preamble", ""),
                progress_callback=_on_progress,
            )

            prog.empty()
            status.empty()

            st.session_state["sqe_results"] = results
            st.session_state["sqe_questions"] = current_questions
            st.session_state["sqe_model"] = f"{provider} / {model}"
            st.session_state["sqe_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            st.success(f"Done! {len(results)} response row(s). Switch to **Results**.")

    # ─── RESULTS TAB ────────────────────────────────────────────────────────
    with results_tab:
        if "sqe_results" not in st.session_state:
            st.info("Run a survey in **Setup & Run** to see results here.")
            return

        results = st.session_state["sqe_results"]
        questions = st.session_state.get("sqe_questions", [])
        saved_mdl = st.session_state.get("sqe_model", "")
        saved_ts = st.session_state.get("sqe_timestamp", "")

        n_agents = len({r["agent_id"] for r in results})
        n_reps = max((r["repetition"] for r in results), default=1)
        st.caption(
            f"{len(results)} response row(s) · {n_agents} agent(s) · "
            f"{n_reps} repetition(s) · {len(questions)} question(s) · "
            f"{saved_mdl} · {saved_ts}"
        )

        if questions:
            with st.expander("Question reference", expanded=False):
                for i, q in enumerate(questions):
                    label = sqt.QUESTION_TYPE_LABELS.get(q.type, q.type)
                    sens = " ⚠️ sensitive" if q.sensitive else ""
                    st.markdown(f"**Q{i+1}** ({label}{sens}): {q.text}")

        df = pd.DataFrame(results)

        long_csv_buf = io.StringIO()
        df.to_csv(long_csv_buf, index=False)

        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button(
                "Export long-format CSV",
                data=long_csv_buf.getvalue(),
                file_name=f"survey_long_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv", use_container_width=True,
            )
        with dl2:
            wide_rows = sre.results_to_wide_summary(results)
            wide_buf = io.StringIO()
            pd.DataFrame(wide_rows).to_csv(wide_buf, index=False)
            st.download_button(
                "Export wide-summary CSV",
                data=wide_buf.getvalue(),
                file_name=f"survey_wide_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv", use_container_width=True,
            )
        with dl3:
            if st.button("Clear results", key="sqe_clear", use_container_width=True):
                for k in ["sqe_results", "sqe_questions", "sqe_model", "sqe_timestamp"]:
                    st.session_state.pop(k, None)
                st.rerun()

        decline_rate = (sum(1 for r in results if r.get("is_decline")) / len(results) * 100) if results else 0
        st.caption(f"Decline rate (don't know / prefer not to answer) across all answered items: **{decline_rate:.1f}%**")

        st.divider()
        st.dataframe(df, use_container_width=True, hide_index=True)


# ─── Tab 6 — Generate Sample ─────────────────────────────────────────────────

def ui_generate_sample():
    st.header("Generate a Random Sample")
    st.caption(
        "Generate a statistically realistic population of agents. "
        "Choose a preset country (census-approximate), describe your population in plain English, "
        "or configure distributions manually."
    )

    subtab_gen, subtab_samples, subtab_england = st.tabs(
        ["Configure & Generate", "Sample Agents", "🇬🇧 England — Census (up to 30k)"]
    )

    with subtab_gen:

        # ── Step 1: Basic setup ───────────────────────────────────────────────
        st.subheader("Step 1 — Basic Setup")
        n_agents = st.number_input("Number of agents to generate", 1, 500, 50, key="samp_n")

        # Pre-API consistency gate: only spend tokens on skeletons whose
        # coherence score meets this threshold. 0.00 blocks only hard-invalid
        # agents (the default); raise it to also exclude ones with soft tensions.
        st.slider(
            "Minimum consistency score (checked before any API cost)",
            min_value=0.0, max_value=1.0, value=0.0, step=0.05,
            key="samp_min_score",
            help="Every agent is validated for internal consistency BEFORE it is "
                 "sent to the API. Skeletons below this score are regenerated "
                 "(free) so no tokens are spent on incoherent profiles. 0.00 "
                 "blocks only hard contradictions; 0.95+ also excludes soft "
                 "tensions like an unusual-but-possible pairing.",
        )

        samp_provider = st.session_state.get("global_provider", list(PROVIDER_MODELS.keys())[0])
        samp_model    = st.session_state.get("global_model",    PROVIDER_MODELS[samp_provider]["models"][0])
        samp_api_key  = st.session_state.get("global_api_key",  "")

        if not samp_api_key:
            st.warning("Set your API key in the **sidebar** before generating.")
        else:
            st.caption(f"Using: **{samp_provider}** / **{samp_model}**")

        st.divider()

        # ── Step 2: Population definition ─────────────────────────────────────
        st.subheader("Step 2 — Define Population")

        pop_mode = st.radio(
            "How do you want to define the population?",
            ["🌍  Preset country (census-approximate)",
             "💬  Describe population (AI-generated distributions)",
             "⚙️  Manual setup (advanced)"],
            key="samp_pop_mode",
        )

        # Initialise stored field_configs
        if "samp_field_configs" not in st.session_state:
            st.session_state.samp_field_configs = None

        # ── Preset country ────────────────────────────────────────────────────
        if "Preset" in pop_mode:
            preset_names = list(COUNTRY_PRESETS.keys())
            selected_preset = st.selectbox("Select country", preset_names, key="samp_preset")
            if st.button("Load preset distributions", key="samp_load_preset", type="primary"):
                cfg = dict(COUNTRY_PRESETS[selected_preset])
                st.session_state.samp_field_configs = cfg
                st.success(f"Loaded **{selected_preset}** census distributions.")
                st.rerun()

        # ── AI-described population ───────────────────────────────────────────
        elif "Describe" in pop_mode:
            pop_desc = st.text_area(
                "Describe the population",
                placeholder=(
                    "e.g. Working-age adults in rural France, ages 30–55\n"
                    "e.g. Young urban professionals in Brazil\n"
                    "e.g. Retired adults in Japan"
                ),
                height=100,
                key="samp_pop_desc",
            )
            st.caption(
                "The AI will generate realistic demographic distributions based on your description, "
                "then show you a summary to approve before any agents are created."
            )
            if st.button(
                "Generate Distributions",
                type="primary",
                key="samp_gen_dist",
                disabled=not (pop_desc.strip() and samp_api_key),
            ):
                with st.spinner("Generating distributions (one LLM call)…"):
                    try:
                        cfg = generate_distributions_from_llm(pop_desc, samp_api_key, samp_provider, samp_model)
                        st.session_state.samp_field_configs = cfg
                        st.success("Distributions generated — review the preview below.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error generating distributions: {e}")

        # ── Manual setup ──────────────────────────────────────────────────────
        else:
            st.caption("Set each demographic distribution manually. Weights are relative (don't need to sum to 100).")
            col_config, col_guide = st.columns([3, 2], gap="large")

            with col_guide:
                st.markdown("""
**Fixed** — every agent gets the same value  
**N/A** — field excluded  
**Uniform** — equally likely integers in [Min, Max]  
**Normal** — bell curve centred on Mean  
**Distributed** — pick categories and relative weights  
Name, occupation, and city are always LLM-generated.
                """)

            with col_config:
                country_raw = st.text_input("Country (same for all agents)", key="samp_country")
                country_val = country_raw.strip() or "N/A"

                st.markdown("**Age**")
                age_cfg = _num_config_widget("Age", 10, 110, 35, "samp_age")
                st.markdown("**Gender**")
                gender_cfg = _cat_config_widget("Gender", GENDER_OPTIONS, "samp_gender")
                st.markdown("**Education level**")
                edu_cfg = _cat_config_widget("Education level", EDUCATION_OPTIONS, "samp_edu")
                st.markdown("**Household income**")
                income_options_clean = [o for o in INCOME_OPTIONS if o != "Prefer not to say"]
                income_cfg = _cat_config_widget("Household income", income_options_clean, "samp_income")
                st.markdown("**Area type**")
                ur_cfg = _cat_config_widget("Area type", URBAN_OPTIONS, "samp_ur")
                st.markdown("**Political leaning**")
                pol_options_clean = [o for o in POLITICAL_OPTIONS if o not in ("Not specified", "Prefer not to say")]
                pol_cfg = _cat_config_widget("Political leaning", pol_options_clean, "samp_pol", default_mode="N/A")
                st.markdown("**Marital status**")
                mar_cfg = _cat_config_widget("Marital status", MARITAL_OPTIONS, "samp_mar", default_mode="N/A")
                st.markdown("**Number of children**")
                chi_cfg = _num_config_widget("Children", 0, 20, 0, "samp_chi")

                st.markdown("**LLM-generated fields**")
                lg1, lg2 = st.columns(2)
                with lg1:
                    gen_eth = st.checkbox("Ethnicity", value=True, key="samp_eth")
                    gen_rel = st.checkbox("Religion",  value=True, key="samp_rel")
                with lg2:
                    st.caption("Name, occupation, city are always generated.")

                manual_configs = {
                    "country": country_val,
                    "age": age_cfg, "gender": gender_cfg, "education_level": edu_cfg,
                    "income_bracket": income_cfg, "urban_rural": ur_cfg,
                    "political_leaning": pol_cfg, "marital_status": mar_cfg,
                    "children": chi_cfg, "ethnicity": gen_eth, "religion": gen_rel,
                }

                if st.button("Use these distributions →", key="samp_manual_set", type="primary"):
                    st.session_state.samp_field_configs = manual_configs
                    st.rerun()

        st.divider()

        # ── Step 3: Preview & Approve ─────────────────────────────────────────
        field_configs = st.session_state.get("samp_field_configs")

        if field_configs:
            st.subheader("Step 3 — Preview & Approve")

            summary_rows = format_distribution_summary(field_configs, int(n_agents))
            df = pd.DataFrame(summary_rows, columns=["Field", "Distribution"])
            st.dataframe(df, use_container_width=True, hide_index=True)

            if int(n_agents) > 20:
                est_secs = int(n_agents) * 7
                st.info(f"Estimated time: ~{est_secs // 60}m {est_secs % 60}s for {int(n_agents)} agents (one LLM call each).")

            col_reset, col_go = st.columns([1, 2])
            with col_reset:
                if st.button("Reset / Change distributions", key="samp_reset", use_container_width=True):
                    st.session_state.samp_field_configs = None
                    st.rerun()
            with col_go:
                if st.button(
                    f"✓ Approve & Generate {int(n_agents)} Agents",
                    type="primary",
                    use_container_width=True,
                    key="samp_go",
                    disabled=not samp_api_key,
                ):
                    skeletons    = _sample_demographic_skeletons(int(n_agents), field_configs)
                    progress_bar = st.progress(0.0)
                    status_text  = st.empty()
                    results, errors, skipped = [], [], []

                    # ── Pre-API consistency gate ────────────────────────────
                    # Validate every skeleton BEFORE spending any API tokens on
                    # it. The skeleton sampler already re-tries the correlation
                    # cascade on failures, so anything still marked invalid here
                    # is a genuinely incoherent agent — skip it rather than pay
                    # to turn a contradictory profile into a persona. Skeletons
                    # without a validation verdict (e.g. non-England presets that
                    # aren't validated) pass through unchanged.
                    _min_score = float(st.session_state.get("samp_min_score", 0.0))
                    gated = []
                    for sk in skeletons:
                        ok = sk.get("_validation_ok", True)
                        score = sk.get("_validation_score", 1.0)
                        if ok and score >= _min_score:
                            gated.append(sk)
                        else:
                            skipped.append(sk)
                    skeletons = gated

                    if skipped:
                        # Top up: sample replacement skeletons (also validated,
                        # still no API cost) so the user gets the count they
                        # asked for, without paying to generate incoherent ones.
                        _need = len(skipped)
                        _attempts = 0
                        while _need > 0 and _attempts < 10:
                            extra = _sample_demographic_skeletons(_need, field_configs)
                            good = [e for e in extra
                                    if e.get("_validation_ok", True)
                                    and e.get("_validation_score", 1.0) >= _min_score]
                            skeletons.extend(good)
                            _need -= len(good)
                            _attempts += 1
                        st.warning(
                            f"Replaced **{len(skipped)}** skeleton(s) that failed the "
                            f"consistency check before any API cost "
                            f"(min score {_min_score:.2f}); "
                            f"regenerated coherent substitutes so no tokens were "
                            f"spent on incoherent profiles."
                        )

                    # All sample agents are built via the England builder at the
                    # demographics level — it preserves every sampled field
                    # (including ONS ethnicity/religion and the BSA scales when
                    # present) and produces no life-context or Big Five data.
                    for i, skeleton in enumerate(skeletons):
                        status_text.text(f"Generating agent {i+1} / {len(skeletons)}…")
                        try:
                            agent = generate_england_agent_from_skeleton(
                                skeleton=skeleton, tier="demographics",
                                provider=samp_provider, api_key=samp_api_key, model=samp_model,
                                call_api_fn=call_api, extract_json_fn=_extract_json_from_llm,
                            )
                            # Carry the pre-API coherence verdict onto the agent
                            # so it's stored and visible in the library.
                            if "_validation_score" in skeleton:
                                agent["_validation_score"] = skeleton["_validation_score"]
                                agent["_validation_ok"] = skeleton.get("_validation_ok", True)
                            save_agent(agent)
                            results.append(agent)
                        except Exception as exc:
                            errors.append(f"Agent {i+1}: {exc}")
                        progress_bar.progress((i + 1) / max(len(skeletons), 1))

                    status_text.empty()
                    progress_bar.empty()

                    if results:
                        names     = [r["persona"]["demographics"].get("name", "?") for r in results]
                        name_list = ", ".join(f"**{nm}**" for nm in names[:8])
                        suffix    = f" … and {len(names) - 8} more" if len(names) > 8 else ""
                        st.success(f"Saved **{len(results)}** agent(s): {name_list}{suffix}")
                        st.info("Switch to the **Sample Agents** tab to view them.")
                    if errors:
                        with st.expander(f"{len(errors)} error(s)"):
                            for e in errors:
                                st.error(e)
        else:
            st.info("Complete Step 2 to see a distribution preview before generating.")

    # ── Sample Agents sub-tab ────────────────────────────────────────────────
    with subtab_samples:
        st.subheader("Sample Agents")
        all_agents  = load_agents()
        samp_agents = [ag for ag in all_agents if ag.get("sampling_metadata")]

        if not samp_agents:
            st.info("No sample agents yet. Use Configure & Generate to create some.")
            return

        st.caption(f"{len(samp_agents)} sample agent(s) across all team members.")

        for ag in samp_agents:
            d       = ag.get("persona", {}).get("demographics", {})
            name    = d.get("name", "Unnamed")
            age     = d.get("age", "?")
            gender  = d.get("gender", "?")
            loc     = d.get("location", {})
            country = loc.get("country", "?")
            owner   = ag.get("_owner", "")

            with st.expander(f"**{name}** — {age}yo, {gender}, {country}"):
                col_meta, col_del = st.columns([4, 1])
                with col_meta:
                    st.markdown(
                        f"Created by: {owner_badge_html(owner)} | ID: `{ag['agent_id']}` | {ag.get('created_at','?')[:10]}",
                        unsafe_allow_html=True,
                    )
                with col_del:
                    if st.button("Delete", key=f"samp_rm_{ag['agent_id']}", type="secondary"):
                        delete_agent(ag["agent_id"])
                        st.rerun()

                edited = st.text_area(
                    "JSON (edit and click Save to apply changes)",
                    value=json.dumps(ag, indent=2, ensure_ascii=False),
                    height=320,
                    key=f"samp_edit_{ag['agent_id']}",
                )
                if st.button("Save Changes", key=f"samp_save_{ag['agent_id']}"):
                    try:
                        new_ag = json.loads(edited)
                        new_ag.pop("_owner", None)
                        update_agent_data(new_ag)
                        st.success("Saved.")
                        st.rerun()
                    except json.JSONDecodeError as exc:
                        st.error(f"Invalid JSON — not saved: {exc}")

    # ── England (census-representative) sub-tab ───────────────────────────────
    with subtab_england:
        ui_england_population_subtab()


# ─── Generate Sample widget helpers (used by manual mode) ─────────────────────

def _num_config_widget(label, min_v, max_v, default_val, key_prefix):
    mode = st.radio(
        label, ["Fixed", "Uniform range", "Normal distribution", "N/A"],
        horizontal=True, key=f"{key_prefix}_mode", label_visibility="collapsed",
    )
    if mode == "N/A":
        return {"mode": "na"}
    if mode == "Fixed":
        val = st.number_input("Value", min_value=min_v, max_value=max_v, value=default_val,
                               key=f"{key_prefix}_val", label_visibility="collapsed")
        return {"mode": "fixed", "value": int(val)}
    if mode == "Uniform range":
        c1, c2 = st.columns(2)
        with c1:
            mn = st.number_input("Min", min_value=min_v, max_value=max_v, value=min_v, key=f"{key_prefix}_min")
        with c2:
            mx = st.number_input("Max", min_value=min_v, max_value=max_v, value=max_v, key=f"{key_prefix}_max")
        return {"mode": "uniform", "min": int(mn), "max": int(mx)}
    c1, c2, c3 = st.columns(3)
    with c1:
        mn = st.number_input("Min", min_value=min_v, max_value=max_v, value=min_v, key=f"{key_prefix}_min")
    with c2:
        mx = st.number_input("Max", min_value=min_v, max_value=max_v, value=max_v, key=f"{key_prefix}_max")
    with c3:
        mean = st.number_input("Mean", min_value=min_v, max_value=max_v,
                                value=(min_v + max_v) // 2, key=f"{key_prefix}_mean")
    return {"mode": "normal", "min": int(mn), "max": int(mx), "mean": float(mean)}


def _cat_config_widget(label, options, key_prefix, default_mode="Distributed"):
    mode = st.radio(
        label, ["Fixed", "Distributed", "N/A"],
        horizontal=True,
        index=["Fixed", "Distributed", "N/A"].index(default_mode),
        key=f"{key_prefix}_mode",
        label_visibility="collapsed",
    )
    if mode == "N/A":
        return {"mode": "na"}
    if mode == "Fixed":
        val = st.selectbox("Value", options, key=f"{key_prefix}_val", label_visibility="collapsed")
        return {"mode": "fixed", "value": val}
    selected = st.multiselect("Categories", options, default=options,
                               key=f"{key_prefix}_cats", label_visibility="collapsed")
    if not selected:
        st.warning("Select at least one category, or switch to N/A.")
        return {"mode": "na"}
    weights = {}
    if len(selected) == 1:
        weights = {selected[0]: 1.0}
        st.caption(f"All agents will have: **{selected[0]}**")
    else:
        st.caption("Relative weights — equal weights = uniform random.")
        for opt in selected:
            wc1, wc2 = st.columns([4, 1])
            with wc1:
                st.markdown(f"**{opt}**")
            with wc2:
                weights[opt] = st.number_input("w", min_value=0.01, value=1.0, step=0.1,
                                                key=f"{key_prefix}_w_{opt}", label_visibility="collapsed")
    return {"mode": "categorical", "weights": weights}


# ─── Tab 7 — Guide ───────────────────────────────────────────────────────────

def ui_guide():
    st.header("Architecture & Usage Guide")

    st.subheader("What this app does")
    st.markdown("""
This tool lets you build **synthetic human agents** — LLM personas grounded in structured
demographic and psychological profiles — for social science research.

| Tab | Purpose |
|-----|---------|
| **Build Agent** | Create a single agent manually from a structured form |
| **Agent Library** | Browse, inspect, edit, or delete all agents across the team |
| **Chat with Agent** | One-on-one conversation with any saved agent |
| **Survey Mode** | Send up to 50 questions to many agents at once — results exportable as CSV |
| **Generate Sample** | Auto-generate agents from census distributions or AI-described populations |
| **Guide & Architecture** | This page |
    """)

    st.divider()
    st.subheader("Survey Mode — Question Types")
    st.markdown("""
| Type | Stored as | Notes |
|------|-----------|-------|
| Open-ended | Text string | Natural response; optional word cap |
| True / False | 1 or 0 | 1 = True, 0 = False |
| Likert Scale | Integer 1–N | You set scale (3/5/7/10) and low/high labels |
| Multiple Choice (single) | Integer 1–N | Agent picks exactly one option |
| Multiple Choice (multi) | Comma-separated integers | Agent picks all that apply (e.g. "1,3") |
| Grid / Battery | rowid=value map | One shared scale across several statements (BSA/WVS style) |
| Ranked Choice | first/second map | First and second pick from a shared option list |
| Numeric | Number | Bounded numeric field (e.g. household size) |

Questionnaires can be **uploaded as CSV or JSON** or built by hand. Delivery is
configurable per run: **full survey** (all at once), **chunked** (N per call), or
**per item** (one question per call). Results export in **long format** (one row
per agent × question × repetition) and a **wide** summary.
    """)

    st.divider()
    st.subheader("Generate Sample — Population Modes")
    st.markdown("""
| Mode | When to use |
|------|-------------|
| **Preset country** | You want census-accurate distributions for one of 10 supported countries |
| **AI-described** | You want distributions for any country/subgroup by describing it in plain English |
| **Manual** | You want full control over every distribution parameter |

In all modes, you see a **distribution preview** before any agents are generated.
Correlations between variables (e.g. education ↔ income) are handled at the persona generation
step — the LLM that creates each agent ensures internal consistency.
    """)

    st.divider()
    st.subheader("Agent Filters")
    st.markdown("""
Survey Mode includes an expanded filter panel:
**country, created by, gender, age range, education level, income bracket,
occupation (text search), ethnicity (text search), religion (text search),
urban/rural area, political leaning, marital status.**

Semantic search uses Claude Haiku to rank agents by how well they match
a plain-English description — e.g. "working-class middle-aged woman skeptical of government".
    """)

    st.divider()
    st.subheader("Agent Model")
    st.markdown("""
Agents are **demographics-only**. Each agent carries census-aligned attributes —
age, gender, education, occupation, income, location, ethnicity, religion,
political leaning, marital status, children — plus the England census extension
fields (economic activity, social grade, health, disability, household, housing,
region) and the BSA attitude scales when generated from the England sample.

There are no life-context or Big Five / OCEAN personality layers: the platform
is built for census- and survey-grounded simulation, where each response should
follow from demographics rather than an invented personality.
    """)

    st.divider()
    st.subheader("Designing benchmark-grade surveys — guidance from the literature")
    st.markdown("""
These are **design principles for the researcher**, drawn from the validation
literature on LLM survey simulation. They are deliberately **kept out of the
agent prompt**: telling an agent about survey-awareness or distributional
benchmarking makes it behave as if it's being tested — the very failure mode the
literature warns against. The agent prompt stays minimal on purpose; these
principles shape how *you* build and run the study. Each maps to a concrete
feature below.

| Principle | Why | Feature that supports it |
|-----------|-----|--------------------------|
| **Use validated instrument wording** | LLM answers are sensitive to exact phrasing; verbatim items keep comparability to human baselines (OPN, BSA, WVS) | CSV/JSON upload — keep a canonical instrument file rather than retyping |
| **Span multiple topic domains** | Reveals whether an agent stays consistent across topics, not just within one | Build one instrument mixing domains (up to 50 items) |
| **Manage ordering & survey-awareness** | Showing the whole instrument at once invites the model to notice it's a test and smooth answers | Delivery mode: **per item** or **chunked** approximates one-at-a-time human answering |
| **Separate sensitive items** | Internal-consistency problems are most acute on sensitive topics | Per-question **sensitive** flag → carried into results for weighting/filtering |
| **Repeated sampling for distribution** | A single answer can't show whether agents reproduce the human *distribution* | **Repetitions > 1** at non-zero **temperature**, and/or many agents per cell |
| **Keep some open-ended items** | All-Likert/MC loses the texture of lived experience | Open-ended type with optional word cap |

**On answer-conditioning:** the survey prompt addendum is intentionally
light-touch — it asks agents to answer honestly as themselves and not to hedge or
smooth toward the expected answer, but it does **not** coach them on *how* a
demographic "should" respond. Whether this produces human-like response
distributions is the empirical question your validation is meant to answer; the
design removes known artefacts (sycophancy, batch-coherence) but does not certify
human-likeness.
    """)

    st.divider()
    st.subheader("Designing a Valid Survey — Research Guidance")
    st.caption(
        "Guidance for building studies that can be compared against real human "
        "baselines, drawn from the validation literature on LLM survey simulation. "
        "These are principles for you as the researcher — they are deliberately "
        "NOT injected into the agent prompt, since telling an agent it is being "
        "benchmarked tends to make its answers less human, not more."
    )
    st.markdown("""
**1. Use validated instrument wording.** LLM answers are sensitive to phrasing,
so for comparability paste question text verbatim from the original instrument
(OPN, BSA, WVS, etc.) rather than paraphrasing. The questionnaire **upload**
feature helps here: keep a canonical instrument file with exact wording instead
of retyping. *The builder does not enforce this — it is your responsibility.*

**2. Span multiple topic domains in one survey.** Benchmarking value comes from
checking whether the same agent stays coherent moving across domains (e.g.
economic attitudes → social policy → personal wellbeing), not from one theme in
isolation. Deliberately mix domains within a single survey instance. *Not tracked
by the tool — a composition choice you make.*

**3. Manage question ordering and length (survey-awareness).** Models can detect
they are being surveyed when the whole instrument is visible at once, and drift
toward performatively smoothed answers. Use **Delivery mode → Per item** (Section 4)
for the most human-like, one-question-at-a-time condition, especially for your
primary benchmark run. Full-survey delivery is cheaper but most exposed to this
effect. *Supported: this is a run-time setting.*

**4. Give sensitive items extra scrutiny.** Internal-consistency problems are
worst on sensitive topics. Flag those items (the **sensitive** checkbox / CSV
column) so you can filter them in results, and consider running them with extra
repetitions or per-item delivery. *Partially supported: flagging works and is
carried into results; the tool does not yet change delivery for flagged items.*

**5. Use repeated sampling, not single-shot, for distributional accuracy.**
Reproducing the *distribution* of human responses (not just the mean) requires
variance. Set **Repetitions > 1** at non-zero **temperature** (Section 4), and/or
rely on many agents per demographic cell from Generate Sample. *Supported.*

**6. Keep some open-ended items.** Reducing every item to Likert/MC for parsing
convenience loses the texture the qualitative literature cares about. Retain a
few **open-ended** questions even in a mainly quantitative survey. *Supported:
the open-ended type is always available.*

---
*A caution: these steps remove known artefacts (sycophancy, batch-coherence,
single-shot flatness). They do not by themselves make agents answer like humans —
that remains an empirical claim to validate against your real benchmark data.*
    """)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    require_login()

    with st.sidebar:
        st.markdown(
            f"Signed in as **{current_display_name()}** "
            f"{owner_badge_html(current_user())}",
            unsafe_allow_html=True,
        )
        if st.button("Sign out", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        st.divider()
        st.header("API Settings")
        st.caption("Used by Survey and Generate Sample. Chat allows per-session overrides.")
        global_provider = st.selectbox("Provider", list(PROVIDER_MODELS.keys()), key="global_provider")
        gp_info = PROVIDER_MODELS[global_provider]
        st.selectbox("Model", gp_info["models"], index=0, key="global_model", help=gp_info["model_help"])
        st.text_input(
            gp_info["key_label"], type="password",
            placeholder=gp_info["key_placeholder"],
            help=gp_info["key_help"] + " — never saved to disk.",
            key="global_api_key",
        )

    st.title("Social Simulation Agent Builder")
    st.caption("Build, manage, and simulate synthetic human agents for social research.")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Build Agent", "Agent Library", "Chat with Agent",
        "Survey Mode", "Generate Sample", "Guide & Architecture",
    ])

    with tab1: ui_build_agent()
    with tab2:
        ui_agent_library_v2(
            load_agents, update_agent_data, delete_agent,
            generate_system_prompt, owner_badge_html, current_user,
            DISPLAY_NAMES,
        )
    with tab3: ui_chat()
    with tab4: ui_survey()
    with tab5: ui_generate_sample()
    with tab6: ui_guide()


if __name__ == "__main__":
    main()
