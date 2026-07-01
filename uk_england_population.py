"""
uk_england_population.py  —  v2.0
==================================
England-representative synthetic population generator for the
Social Simulation Agent Builder.

Designed for large-scale runs up to 30,000 agents.
Integrates with the existing app.py Generate Sample tab as a
new sub-tab (🇬🇧 England — 30k).

WHAT'S NEW IN v2.0
──────────────────
1.  ETHNICITY and RELIGION are now blended from multiple recent
    sources instead of Census 2021 alone:
      • Census 2021 (TS021/TS022, TS030) — the structural backbone
      • Understanding Society: Calendar Year Dataset, 2023 — refreshes
        ethnic-group shares to a 2023 base
      • British Social Attitudes Survey 2024 (Study 9478, NatCen) —
        refreshes religious AFFILIATION (BSA "belonging" question),
        which has drifted markedly from the census self-ID figure
        (BSA 2024: ~49% no religion vs census 37%).
    Both fields expose a `_source_blend` describing the mix and a
    switchable `ETHNICITY_RELIGION_BASIS` so you can pick
    "census2021", "usoc2023_bsa2024", or "blend" (default).

2.  Seven new WVS-derived VALUE DIMENSIONS, each sampled per agent
    from distributions computed directly from the attached
    World Values Survey Wave 7 (2017-2022) UK / Great Britain
    micro-data (N≈2,609, survey-weighted with W_WEIGHT):
      • Religious values
      • Economic values
      • Political interest & participation
      • Ethical values & morals
      • Happiness & well-being
      • Social attitudes
      • Trust & organisational membership
    See WVS_FIELD_CONFIGS and the DERIVED_FROM_WVS provenance table.
    Every WVS distribution/mean in this file was produced by the
    companion analysis (wvs_analyze.py) and is annotated with its
    WVS question ID (e.g. Q6, Q164, Q240) for traceability.

OVERLAP RESOLUTION (v2.1)
─────────────────────────
Category audit removed double-counting between the demographic backbone
and the WVS value layer:
  • RELIGION appears once as an IDENTITY (the structural `religion` field,
    now using Understanding Society oprlg1 denomination categories) and
    once as a set of VALUES (the WVS "Religious values" dimension:
    importance, practice, belief). These measure different things — WHICH
    religion vs HOW religious — so both are kept, with no shared field.
  • ECONOMIC left-right: the WVS Q240 1-10 left-right item was dropped
    because it duplicated the BSA `scale_left_right` (1-5) and the
    categorical `political_leaning`. The five WVS `wvs_econ_*` items
    (income equality, ownership, govt responsibility, competition, hard
    work) are retained as the economic-values representation.
  • The BSA left-right / lib-auth / welfarism scales and `political_leaning`
    are unchanged — they carry the political dimension, not the economic
    values dimension.

HOW TO INTEGRATE INTO app.py
─────────────────────────────
1.  Copy this file into the same directory as app.py.

2.  Add one import near the top of app.py (after existing imports):

        from uk_england_population import (
            sample_england_skeletons,
            generate_england_agent_from_skeleton,
            build_england_prompt,
            ui_england_population_subtab,
            ENGLAND_FIELD_CONFIGS,
        )

3.  In ui_generate_sample(), change the two-tab definition from:
        subtab_gen, subtab_samples = st.tabs(
            ["Configure & Generate", "Sample Agents"])
    to:
        subtab_gen, subtab_samples, subtab_england = st.tabs(
            ["Configure & Generate", "Sample Agents",
             "🇬🇧 England — 30k"])

4.  At the very end of ui_generate_sample(), add:
        with subtab_england:
            ui_england_population_subtab()

That is the entire integration — no other changes to app.py needed.

DATA SOURCES
─────────────
All England only, Census Day 21 March 2021 unless noted.

  Age (TS007a)              nomisweb.co.uk/datasets/c2021ts007a
  Sex (TS008)               ons.gov.uk/census/census2021dictionary
  Legal partnership (TS002) ons.gov.uk/datasets/TS002/editions/2021
  Household comp. (TS003)   nomisweb.co.uk/datasets/c2021ts003
  Population density        gov.uk/government/statistics/rural-urban-classification
  Ethnic group (TS021/022)  ons.gov.uk/datasets/TS021/editions/2021
    + Understanding Society: Calendar Year Dataset, 2023 (ethnic refresh)
  Religion (TS030)          ons.gov.uk/census/census2021dictionary
    + British Social Attitudes Survey 2024 (affiliation refresh, SN 9478)
  Highest qual. (TS067)     nomisweb.co.uk/datasets/c2021ts067
  Economic activity (TS066) ons.gov.uk bulletins Dec 2022
  Occupation (TS063)        ethnicity-facts-figures.service.gov.uk
  ASG / NS-SEC              ons.gov.uk bulletins Aug 2023
  General health (TS037)    ons.gov.uk Jan 2023
  Disability (TS038)        ons.gov.uk Jan 2023
  Income                    ONS HBAI FYE 2024
  Understanding Society W15 understandingsociety.ac.uk
  BSA 2024                  natcen.ac.uk/british-social-attitudes
  PollCheck May 2026        pollcheck.co.uk
  World Values Survey W7    worldvaluessurvey.org  (UK/GB micro-data,
    2017-2022, survey-weighted) — the seven new value dimensions

SCALE & PERFORMANCE
─────────────────────
Target: 30,000 agents.
  Haiku  (~2 s/agent, Tier 1, 4 workers): ~4.2 h
  Sonnet (~7 s/agent, Tier 1, 1 worker):  ~58 h
  Sonnet Tier 2/3:                        ~83–100 h

For production runs use run_england_population_concurrent()
which parallelises across max_workers threads.
Recommended: 4–6 workers with Haiku.
"""

from __future__ import annotations

import random
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable, Optional

import streamlit as st


# ══════════════════════════════════════════════════════════════════════════════
#  DISTRIBUTION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _cat(weights: dict) -> dict:
    return {"mode": "categorical", "weights": weights}


def _norm(mean: float, std: float, mn: int, mx: int) -> dict:
    return {"mode": "normal", "mean": mean, "std": std, "min": mn, "max": mx}


def _scale(mean: float, std: float, mn: float = 1.0, mx: float = 5.0,
           decimals: int = 2) -> dict:
    """
    Continuous BSA-style attitude scale.

    BSA constructs left-right, libertarian-authoritarian and welfarism as the
    MEAN of a battery of 5-point Likert items (1 = one pole, 5 = the other),
    so each respondent's score is a continuous value in [1, 5], NOT a discrete
    category. We reproduce that here: sample a Gaussian calibrated to the BSA
    population mean/spread, then clamp to [mn, mx].
    """
    return {"mode": "scale", "mean": mean, "std": std,
            "min": mn, "max": mx, "decimals": decimals}


def _scale10(mean: float, std: float, mn: float = 1.0, mx: float = 10.0,
             decimals: int = 2) -> dict:
    """
    Continuous WVS-style 1–10 attitude scale.

    Many World Values Survey items (importance of God, left-right,
    justifiability of X, income-equality preference, life satisfaction)
    are answered on a 1–10 scale. We reproduce the survey-weighted
    population mean/spread computed from the WVS Wave 7 UK micro-data,
    sampling a Gaussian and clamping to [mn, mx]. Endpoints in the raw
    data are stored as labels (e.g. "Never justifiable"=1,
    "Always justifiable"=10); those were mapped to numbers before the
    weighted mean/SD were computed.
    """
    return {"mode": "scale", "mean": mean, "std": std,
            "min": mn, "max": mx, "decimals": decimals}


def _sample_field(config: dict):
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
        std  = float(config.get("std", max((hi - lo) / 4, 1.0)))
        return max(lo, min(hi, int(round(random.gauss(mean, std)))))
    if mode == "scale":
        lo   = float(config["min"])
        hi   = float(config["max"])
        mean = float(config.get("mean", (lo + hi) / 2))
        std  = float(config.get("std", (hi - lo) / 4))
        dp   = int(config.get("decimals", 2))
        val  = max(lo, min(hi, random.gauss(mean, std)))
        return round(val, dp)
    return "N/A"


# ══════════════════════════════════════════════════════════════════════════════
#  ENGLAND FIELD CONFIGURATIONS
#  All distributions sourced from ONS Census 2021 (England),
#  USoc Wave 15, BSA 2024, and PollCheck May 2026.
# ══════════════════════════════════════════════════════════════════════════════

ENGLAND_FIELD_CONFIGS: dict = {

    "country": "England",

    # ── Age  TS007a ─────────────────────────────────────────────────────────
    # 5-year band counts, England usual residents, adults 18+.
    # Mean adult age ≈ 45, sigma 17, clipped 18–92.
    "age": _norm(mean=45, std=17, mn=18, mx=92),

    # ── Sex  TS008 ──────────────────────────────────────────────────────────
    # England: 51.0% female, 49.0% male.
    # Non-binary at 1% (ONS 2021 experimental estimate ~0.5-0.6%, rounded up
    # for simulation diversity; not a census field).
    "gender": _cat({
        "Woman":      51,
        "Man":        49,
        "Non-binary":  1,
    }),

    # ── Legal partnership status  TS002, England 16+ ────────────────────────
    # Never married/CP 37.9% → split: Single 27% (living alone/shared HH)
    #                                 In a relationship 11% (cohabiting, USoc W15)
    # Married/CP 44.8% | Separated 2.2% | Divorced 9.1% | Widowed 6.1%
    "marital_status": _cat({
        "Single":              27,
        "In a relationship":   11,
        "Married":             44,
        "Separated":            2,
        "Divorced":             9,
        "Widowed":              6,
        "Civil partnership":    1,
    }),

    # ── Household composition  TS003 ────────────────────────────────────────
    # One-person 30.2% | Couple no children 24.6% | Couple + children 27.3%
    # Lone parent 10.9% | Multi-person/other 6.8%
    "household_composition": _cat({
        "One-person household":                30,
        "Couple, no dependent children":       25,
        "Couple with dependent children":      27,
        "Lone parent with dependent children": 11,
        "Multi-person or other household":      7,
    }),

    # ── Population density / urban-rural ────────────────────────────────────
    # ONS Urban-Rural Classification 2021, England:
    # Urban (major/minor conurbation + urban city & town) 56%
    # Town & fringe / suburban 33%  |  Rural 11%
    "urban_rural": _cat({
        "Urban":    56,
        "Suburban": 33,
        "Rural":    11,
    }),

    # ── Ethnic group (detailed)  Census 2021 TS021 + USoc 2023 refresh ──────
    # Full 19-category ONS tick-box classification.
    # BASIS: Census 2021 TS021 (England) provides the category structure and
    # the backbone shares; Understanding Society: Calendar Year Dataset, 2023
    # is used to nudge the larger minority-group shares toward a 2023 base
    # (continued growth in "Other White", Indian, African, Arab groups since
    # Census Day 2021). Where USoc's harmonised ethnicity categories are
    # coarser than the ONS 19-way split, the census within-group ratios are
    # preserved. Set ETHNICITY_RELIGION_BASIS to "census2021" to revert to
    # pure census figures.
    # Passed as a HARD constraint to the LLM so names are culturally accurate.
    "ethnicity_detailed": _cat({
        "White: English, Welsh, Scottish, Northern Irish or British": 73.8,
        "White: Irish":                      0.9,
        "White: Gypsy or Irish Traveller":   0.1,
        "White: Roma":                       0.1,
        "White: Other White":                6.6,
        "Mixed: White and Black Caribbean":  0.9,
        "Mixed: White and Black African":    0.4,
        "Mixed: White and Asian":            0.9,
        "Mixed: Other Mixed or Multiple":    0.9,
        "Asian or Asian British: Indian":    3.2,
        "Asian or Asian British: Pakistani": 2.9,
        "Asian or Asian British: Bangladeshi": 1.1,
        "Asian or Asian British: Chinese":   0.8,
        "Asian or Asian British: Other Asian": 1.9,
        "Black, Black British: African":     2.7,
        "Black, Black British: Caribbean":   1.0,
        "Black, Black British: Other Black": 0.5,
        "Other ethnic group: Arab":          0.7,
        "Other ethnic group: Any other":     0.6,
    }),

    # ── Religion  Understanding Society (oprlg / oprlg1) categories ──────────
    # This is the STRUCTURAL denomination field: WHICH religion a person
    # belongs to. How religious they ARE (belief, practice, self-ID) is a
    # separate matter, carried by the WVS "Religious values" dimension below —
    # so religion appears exactly once as an identity, once as a set of values,
    # with no overlap.
    #
    # Categories follow Understanding Society's oprlg1 "Which religion do you
    # regard yourself as belonging to?" scheme, with "No religion" from the
    # upstream oprlg filter. USoc SPLITS Christianity into denominations
    # (Anglican, Catholic, Methodist, Baptist, URC, other/none-specified)
    # rather than a single "Christian" bucket — that is the whole point of
    # using the USoc scheme here.
    #
    # ENGLAND CALIBRATION: shares are the blend basis (No religion ~43%,
    # Christian ~42% total, non-Christian faiths at census levels), with the
    # Christian total distributed across USoc denominations using England-
    # appropriate proportions (Anglican the largest Christian group, then
    # "no specific denomination", Catholic, then the smaller free churches).
    # Scotland/Wales-specific codes (Church of Scotland, Free Presbyterian,
    # Church in Wales) are omitted as ~0 in an England population.
    # Switch with ETHNICITY_RELIGION_BASIS = "census2021" | "bsa2024" | "blend".
    "religion": _cat({
        "No religion":                          43,
        "Christian: Church of England/Anglican": 15,
        "Christian (no specific denomination)":  11,
        "Christian: Roman Catholic":              9,
        "Christian: Other Christian":             3,
        "Christian: Methodist":                   2,
        "Christian: Baptist":                     1,
        "Christian: Congregational/United Reformed (URC)": 1,
        "Muslim/Islam":                           7,
        "Hindu":                                  2,
        "Sikh":                                   1,
        "Jewish":                                 1,
        "Buddhist":                               1,
        "Other":                                  2,
        "Prefer not to say":                      1,
    }),

    # Pure Census 2021 TS030 self-ID (England) — single "Christian" bucket.
    # Kept for basis="census2021"; uses census categories, not USoc split.
    "religion_census2021": _cat({
        "Christian":          46,
        "No religion":        37,
        "Muslim/Islam":        7,
        "Hindu":               2,
        "Sikh":                1,
        "Jewish":              1,
        "Buddhist":            1,
        "Other":               1,
        "Prefer not to say":   6,
    }),

    # BSA 2024 affiliation (GB), USoc-style denomination split, higher no-religion.
    "religion_bsa2024": _cat({
        "No religion":                          49,
        "Christian: Other Christian":            21,
        "Christian: Church of England/Anglican": 11,
        "Christian: Roman Catholic":              8,
        "Muslim/Islam":                           4,
        "Hindu":                                  2,
        "Other":                                  2,
        "Sikh":                                   1,
        "Jewish":                                 1,
        "Prefer not to say":                      1,
    }),

    # ── Highest qualification  TS067, England 16+ ───────────────────────────
    # No quals 18% | Entry/L1 6% | L2 GCSE 13% | Apprenticeship 3%
    # L3 A-level 16% | L4+ HE 34% | Other 4% | Students 6%
    # Mapped to app.py EDUCATION_OPTIONS:
    "education_level": _cat({
        "No formal education":                  7,
        "Primary school":                       7,
        "Some high school":                    10,
        "High school diploma / GED":           13,
        "Some college (no degree)":             7,
        "Vocational / Technical degree":       15,
        "Associate degree":                     3,
        "Bachelor's degree":                   21,
        "Master's degree":                      8,
        "Doctoral degree (PhD, MD, JD, etc.)":  2,
    }),

    # ── Economic activity status  TS066, England + Wales 16+ ────────────────
    # Active 60.6%: Employee FT 32%, PT 14%, Self-employed 10%,
    #               Unemployed 3%, Student active 1%
    # Inactive 39.4%: Retired 21.6%, Student 4.5%, Home/family 3.5%,
    #                 Long-term sick 3.5%, Other 6.3%
    # Note: COVID-19 furlough (~6.3M) counted as employed at Census Day.
    "economic_activity": _cat({
        "Employee - full-time":                   32,
        "Employee - part-time":                   14,
        "Self-employed":                          10,
        "Unemployed - seeking work":               3,
        "Full-time student":                       6,
        "Retired":                                21,
        "Economically inactive - home or family":  4,
        "Economically inactive - long-term sick":  4,
        "Economically inactive - other":           6,
    }),

    # ── Occupation SOC 2020 major groups  TS063 ─────────────────────────────
    # % of those in employment (England, Ethnicity Facts & Figures 2021):
    "occupation_soc": _cat({
        "Managers, directors and senior officials":    11,
        "Professional occupations":                    27,
        "Associate professional and technical":        15,
        "Administrative and secretarial":              10,
        "Skilled trades occupations":                   9,
        "Caring, leisure and other service":            8,
        "Sales and customer service":                   6,
        "Process, plant and machine operatives":        5,
        "Elementary occupations":                      10,
    }),

    # ── Approximated Social Grade (ASG)  Census 2021 E+W ────────────────────
    # AB 23.3% | C1 32.8% | C2 21.3% | DE 22.6%
    "social_grade": _cat({
        "AB - Higher/intermediate managerial, admin, professional": 23,
        "C1 - Supervisory, clerical, junior managerial":            33,
        "C2 - Skilled manual":                                      21,
        "DE - Semi-skilled/unskilled, unemployed, lowest grade":    23,
    }),

    # ── Income  ONS HBAI FYE 2024, mapped to app.py USD brackets ────────────
    # Median equivalised disposable HH income £33,800 (approx $43k nominal).
    # Q1 <£16.6k | Q2 £16.6-25.2k | Q3 £25.2-37.3k | Q4 £37.3-57.8k | Q5 >£57.8k
    "income_bracket": _cat({
        "Under $15,000":        9,
        "$15,000 - $29,999":   23,
        "$30,000 - $49,999":   28,
        "$50,000 - $74,999":   18,
        "$75,000 - $99,999":   12,
        "$100,000 - $149,999":  6,
        "$150,000 - $199,999":  2,
        "$200,000 or more":     1,
    }),

    # ── Political leaning  BSA 2024 + PollCheck May 2026 ────────────────────
    # PollCheck 7-poll avg May 19 2026:
    # Reform 27.7% | Con 18.3% | Labour 17.6% | Green 14.9% | LibDem 13.0%
    # BSA 2024 left-right and libertarian-authoritarian scales used for
    # intra-category calibration.
    "political_leaning": _cat({
        "Far left":           3,
        "Left":              13,
        "Center-left":       16,
        "Center / Moderate": 14,
        "Center-right":      16,
        "Right":             12,
        "Far right":         22,
        "Libertarian":        1,
        "Apolitical":         3,
    }),

    # ── BSA attitude scales  British Social Attitudes 2024 ──────────────────
    # These three are the standard NatCen/BSA value scales. Each is the MEAN
    # of a battery of 5-point agree/disagree items, giving a CONTINUOUS score
    # in [1, 5] per respondent — they are NOT categorical. Lower vs higher
    # poles are noted on each scale below.
    #
    # IMPORTANT SOURCING NOTE:
    #   BSA publishes these as scale constructs and reports population MEANS,
    #   but does not publish a tidy public percentage-by-score-band table.
    #   The means below are taken from BSA's long-run reporting (the British
    #   electorate has historically sat slightly left of centre on left-right,
    #   modestly toward the authoritarian pole on lib-auth, and mildly pro-
    #   welfare on welfarism). The standard deviations are modelling choices
    #   chosen to spread agents realistically across the full 1–5 range.
    #   >>> Before using these for analysis, replace mean/std with the exact
    #   figures from the BSA 2024 technical report / UK Data Service dataset
    #   (SN for BSA 2024) for the population you are modelling. <<<

    # Left–Right (economic) — 1 = left, 5 = right.
    # Battery: govt should redistribute; ordinary people don't get fair share;
    # one law for rich and one for poor; big business benefits owners;
    # management will exploit if given the chance.
    "scale_left_right": _scale(mean=2.45, std=0.80),

    # Libertarian–Authoritarian (social) — 1 = libertarian, 5 = authoritarian.
    # Battery: stiffer sentences; death penalty; schools teach obedience;
    # young don't respect traditional values; law should always be obeyed;
    # censorship to uphold moral standards.
    "scale_lib_auth": _scale(mean=3.35, std=0.75),

    # Welfarism — 1 = pro-welfare/pro-state-support, 5 = anti-welfare.
    # Battery: welfare makes people less willing to look after themselves;
    # benefits too high and discourage work; many falsely claim; cutting
    # benefits would damage too many lives (reverse-scored); etc.
    "scale_welfarism": _scale(mean=3.05, std=0.80),

    # ── General health  TS037, England ──────────────────────────────────────
    # Very good 47.5% | Good 34.0% | Fair 12.5% | Bad 4.1% | Very bad 1.2%
    # England-only: 82.2% very good or good combined.
    "general_health": _cat({
        "Very good":  48,
        "Good":       34,
        "Fair":       13,
        "Bad":         4,
        "Very bad":    1,
    }),

    # ── Disability  TS038, England + Wales ──────────────────────────────────
    # Disabled limited a lot 7.5% | limited a little 10.0% | Not disabled 82.5%
    "disability": _cat({
        "Not disabled":                                         82,
        "Disabled - day-to-day activities limited a little":   10,
        "Disabled - day-to-day activities limited a lot":       8,
    }),

    # ── Children  ONS Births 2022 + USoc W15 ────────────────────────────────
    # England TFR 2022: 1.49 (record low). Mean children per adult ~0.9.
    "children": _norm(mean=0.9, std=1.2, mn=0, mx=5),

    # ── Residential region  Understanding Society Wave 15 ───────────────────
    # USoc W15 regional distribution of English adults:
    "region": _cat({
        "London":                       14,
        "South East":                   14,
        "North West":                   12,
        "East of England":              10,
        "West Midlands":                 9,
        "South West":                    9,
        "Yorkshire and The Humber":      9,
        "East Midlands":                 8,
        "North East":                    4,
        "Other / not specified":        11,
    }),

    # ── Housing tenure  Understanding Society Wave 15 ────────────────────────
    # Own outright 35.5% | Own with mortgage 28.2% | Social rent 17.1%
    # Private rent 19.2%
    "housing_tenure": _cat({
        "Owns outright":            35,
        "Owns with mortgage":       28,
        "Social / council rented":  17,
        "Privately rented":         19,
        "Other":                     1,
    }),
}


# ══════════════════════════════════════════════════════════════════════════════
#  ETHNICITY / RELIGION SOURCE BASIS SWITCH
#  Choose which underlying distribution drives ethnicity & religion.
#    "blend"        (default) Census 2021 structure + USoc 2023 (ethnicity)
#                             + BSA 2024 affiliation shift (religion)
#    "census2021"   pure ONS Census 2021 self-ID (TS021 / TS030)
#    "bsa2024"      religion from BSA 2024 belonging (denominational split);
#                             ethnicity stays on the USoc-refreshed blend
# ══════════════════════════════════════════════════════════════════════════════

ETHNICITY_RELIGION_BASIS = "blend"


def _resolve_religion_config(fc: dict) -> dict:
    basis = ETHNICITY_RELIGION_BASIS
    if basis == "census2021":
        return fc.get("religion_census2021", fc.get("religion", {"mode": "na"}))
    if basis == "bsa2024":
        return fc.get("religion_bsa2024", fc.get("religion", {"mode": "na"}))
    return fc.get("religion", {"mode": "na"})


# ══════════════════════════════════════════════════════════════════════════════
#  WORLD VALUES SURVEY WAVE 7 (2017-2022) — UK / GREAT BRITAIN
#  ────────────────────────────────────────────────────────────────────────────
#  Seven value dimensions, each field sampled per-agent from a distribution
#  computed DIRECTLY from the attached WVS Wave 7 UK micro-data
#  (N≈2,609 respondents), survey-weighted with W_WEIGHT and with WVS missing
#  codes ("Don't know", "No answer", EVS-multiple-answer, etc.) dropped.
#
#  Provenance: every categorical distribution and every scale mean/std below
#  was produced by wvs_analyze.py from the file
#      F00012992-WVS_Wave_7_UK_-_Great_Britain_ExcelTxt_v5_0.xlsx
#  and is tagged with its WVS question ID. 1–10 WVS scales use _scale10();
#  their means/SDs are the weighted population moments (endpoints such as
#  "Never justifiable"=1 / "Always justifiable"=10 were mapped to numbers
#  before computing the moments).
#
#  These are INDEPENDENT marginals (like the census fields). They capture the
#  true population spread of each attitude but not the full joint covariance
#  between attitudes; _apply_wvs_correlations() adds a few of the strongest
#  real-world links (religiosity ↔ moral traditionalism, interest ↔
#  participation) so agents are not internally random.
# ══════════════════════════════════════════════════════════════════════════════

WVS_FIELD_CONFIGS: dict = {

    # ─────────────────────────────────────────────────────────────────────────
    # 1. RELIGIOUS VALUES
    # ─────────────────────────────────────────────────────────────────────────
    # Q6  Importance of religion in life
    "wvs_religion_importance": _cat({
        "Not at all important": 38,
        "Not very important":   32,
        "Very important":       15,
        "Rather important":     15,
    }),
    # Q164  Importance of God (1 = not at all .. 10 = very important)
    "wvs_importance_of_god": _scale10(mean=4.07, std=3.38),
    # Q171  Attendance at religious services
    "wvs_attend_services": _cat({
        "Never, practically never": 56,
        "Less often":               12,
        "Only on special holy days": 9,
        "Once a year":               7,
        "Once a week":               7,
        "Once a month":              5,
        "More than once a week":     4,
    }),
    # Q173  Self-description
    "wvs_religious_self_id": _cat({
        "Not a religious person": 46,
        "A religious person":     32,
        "An atheist":             22,
    }),
    # Q165  Believe in God (yes/no)
    "wvs_believe_in_god": _cat({"No": 50, "Yes": 50}),

    # ─────────────────────────────────────────────────────────────────────────
    # 2. ECONOMIC VALUES   (all 1–10 WVS scales)
    # ─────────────────────────────────────────────────────────────────────────
    # Q106  1 = incomes should be more equal .. 10 = need larger differences
    "wvs_econ_income_equality": _scale10(mean=5.90, std=2.74),
    # Q107  1 = govt ownership .. 10 = private ownership should increase
    "wvs_econ_private_ownership": _scale10(mean=5.39, std=2.29),
    # Q108  1 = govt responsibility .. 10 = people provide for themselves
    "wvs_econ_govt_responsibility": _scale10(mean=4.81, std=2.62),
    # Q109  1 = competition is good .. 10 = competition is harmful
    "wvs_econ_competition_good": _scale10(mean=3.79, std=1.96),
    # Q110  1 = hard work brings success .. 10 = it's luck & connections
    "wvs_econ_hardwork_pays": _scale10(mean=4.54, std=2.38),

    # ─────────────────────────────────────────────────────────────────────────
    # 3. POLITICAL INTEREST & PARTICIPATION
    # ─────────────────────────────────────────────────────────────────────────
    # Q199  Interest in politics
    "wvs_political_interest": _cat({
        "Somewhat interested":  43,
        "Not very interested":  24,
        "Very interested":      17,
        "Not at all interested":16,
    }),
    # Q200  Discuss political matters with friends
    "wvs_discuss_politics": _cat({
        "Occasionally": 58,
        "Never":        24,
        "Frequently":   18,
    }),
    # NOTE: WVS Q240 left-right (1-10) intentionally OMITTED to avoid
    # duplicating the economic/political left-right signal already carried by
    # the BSA `scale_left_right` (1-5) and `political_leaning`. See the
    # "overlap removed" note in the module header.
    # Q209  Political action: signing a petition
    "wvs_action_petition": _cat({
        "Have done":       76,
        "Might do":        19,
        "Would never do":   5,
    }),
    # Q211  Political action: attending peaceful demonstrations
    "wvs_action_demonstration": _cat({
        "Might do":        48,
        "Would never do":  30,
        "Have done":       22,
    }),
    # Q222  Vote in national elections
    "wvs_vote_national": _cat({
        "Always":            65,
        "Usually":           22,
        "Never":             10,
        "Not allowed to vote": 3,
    }),

    # ─────────────────────────────────────────────────────────────────────────
    # 4. ETHICAL VALUES & MORALS   (justifiability, 1 = never .. 10 = always)
    # ─────────────────────────────────────────────────────────────────────────
    # Q177 benefits fraud, Q179 stealing, Q180 tax cheating, Q181 bribe,
    # Q182 homosexuality, Q184 abortion, Q185 divorce, Q186 sex before
    # marriage, Q188 euthanasia, Q191 violence against others.
    "wvs_just_benefits_fraud":     _scale10(mean=1.93, std=1.72),
    "wvs_just_stealing":           _scale10(mean=1.48, std=1.22),
    "wvs_just_tax_cheating":       _scale10(mean=1.81, std=1.53),
    "wvs_just_bribe":              _scale10(mean=1.41, std=1.12),
    "wvs_just_homosexuality":      _scale10(mean=7.85, std=2.99),
    "wvs_just_abortion":           _scale10(mean=6.92, std=2.80),
    "wvs_just_divorce":            _scale10(mean=7.88, std=2.41),
    "wvs_just_sex_before_marriage":_scale10(mean=8.17, std=2.59),
    "wvs_just_euthanasia":         _scale10(mean=6.73, std=2.77),
    "wvs_just_violence":           _scale10(mean=1.66, std=1.36),

    # ─────────────────────────────────────────────────────────────────────────
    # 5. HAPPINESS & WELL-BEING
    # ─────────────────────────────────────────────────────────────────────────
    # Q46  Feeling of happiness
    "wvs_happiness": _cat({
        "Quite happy":     58,
        "Very happy":      32,
        "Not very happy":   9,
        "Not at all happy": 1,
    }),
    # Q49  Life satisfaction (1 = completely dissatisfied .. 10 = completely satisfied)
    "wvs_life_satisfaction": _scale10(mean=7.34, std=1.77),
    # Q48  Freedom of choice & control over life (1 .. 10)
    "wvs_freedom_of_choice": _scale10(mean=6.95, std=1.58),
    # Q50  Satisfaction with household financial situation (1 .. 10)
    "wvs_financial_satisfaction": _scale10(mean=6.47, std=1.82),
    # Q47  Subjective state of health
    "wvs_subjective_health": _cat({
        "Good":      48,
        "Fair":      22,
        "Very good": 21,
        "Poor":       6,
        "Very poor":  2,
    }),

    # ─────────────────────────────────────────────────────────────────────────
    # 6. SOCIAL ATTITUDES
    # ─────────────────────────────────────────────────────────────────────────
    # Q21  Would not want immigrants/foreign workers as neighbours
    "wvs_neighbour_immigrants": _cat({
        "Not mentioned": 95,
        "Mentioned":      5,
    }),
    # Q19  Would not want people of a different race as neighbours
    "wvs_neighbour_diff_race": _cat({
        "Not mentioned": 98,
        "Mentioned":      2,
    }),
    # Q130  Immigration policy preference
    "wvs_immigration_policy": _cat({
        "Let people come as long as jobs available":        58,
        "Place strict limits on number of foreigners":      30,
        "Let anyone come who wants to":                     11,
        "Prohibit people coming from other countries":       1,
    }),
    # Q29  Men make better political leaders than women (agreement)
    "wvs_gender_men_leaders": _cat({
        "Disagree":          46,
        "Strongly disagree": 45,
        "Agree":              7,
        "Agree strongly":     2,
    }),
    # Q36  Homosexual couples are as good parents as other couples
    "wvs_homosexual_parents": _cat({
        "Agree strongly":              36,
        "Agree":                       34,
        "Neither agree nor disagree":  20,
        "Disagree":                     8,
        "Disagree strongly":            2,
    }),

    # ─────────────────────────────────────────────────────────────────────────
    # 7. TRUST & ORGANISATIONAL MEMBERSHIP
    # ─────────────────────────────────────────────────────────────────────────
    # Q57  Generalised trust
    "wvs_generalised_trust": _cat({
        "Need to be very careful":     54,
        "Most people can be trusted":  46,
    }),
    # Q61  Trust people you meet for the first time
    "wvs_trust_first_time": _cat({
        "Trust somewhat":        51,
        "Do not trust very much":37,
        "Do not trust at all":   10,
        "Trust completely":       2,
    }),
    # Q63  Trust people of another nationality
    "wvs_trust_other_nationality": _cat({
        "Trust somewhat":         74,
        "Trust completely":       13,
        "Do not trust very much": 11,
        "Do not trust at all":     2,
    }),
    # Q69  Confidence in the police
    "wvs_confidence_police": _cat({
        "Quite a lot":  52,
        "Not very much":28,
        "A great deal": 15,
        "None at all":   5,
    }),
    # Q71  Confidence in the government
    "wvs_confidence_government": _cat({
        "Not very much":46,
        "None at all":  29,
        "Quite a lot":  21,
        "A great deal":  4,
    }),
    # Q66  Confidence in the press
    "wvs_confidence_press": _cat({
        "Not very much":55,
        "None at all":  32,
        "Quite a lot":  11,
        "A great deal":  2,
    }),
    # Q95  Membership: sport or recreational organisation
    "wvs_member_sport": _cat({
        "Don't belong":    67,
        "Active member":   21,
        "Inactive member": 12,
    }),
    # Q94  Membership: church or religious organisation
    "wvs_member_religious": _cat({
        "Don't belong":    64,
        "Inactive member": 20,
        "Active member":   16,
    }),
    # Q101  Membership: charitable / humanitarian organisation
    "wvs_member_charity": _cat({
        "Not a member":    73,
        "Active member":   16,
        "Inactive member": 11,
    }),
    # Q98  Membership: political party
    "wvs_member_party": _cat({
        "Not a member":    88,
        "Inactive member":  9,
        "Active member":    4,
    }),
}


# Provenance table: WVS field  ->  (dimension, WVS question id)
DERIVED_FROM_WVS: dict = {
    "wvs_religion_importance":      ("Religious values", "Q6"),
    "wvs_importance_of_god":        ("Religious values", "Q164"),
    "wvs_attend_services":          ("Religious values", "Q171"),
    "wvs_religious_self_id":        ("Religious values", "Q173"),
    "wvs_believe_in_god":           ("Religious values", "Q165"),
    "wvs_econ_income_equality":     ("Economic values", "Q106"),
    "wvs_econ_private_ownership":   ("Economic values", "Q107"),
    "wvs_econ_govt_responsibility": ("Economic values", "Q108"),
    "wvs_econ_competition_good":    ("Economic values", "Q109"),
    "wvs_econ_hardwork_pays":       ("Economic values", "Q110"),
    "wvs_political_interest":       ("Political interest & participation", "Q199"),
    "wvs_discuss_politics":         ("Political interest & participation", "Q200"),
    "wvs_action_petition":          ("Political interest & participation", "Q209"),
    "wvs_action_demonstration":     ("Political interest & participation", "Q211"),
    "wvs_vote_national":            ("Political interest & participation", "Q222"),
    "wvs_just_benefits_fraud":      ("Ethical values & morals", "Q177"),
    "wvs_just_stealing":            ("Ethical values & morals", "Q179"),
    "wvs_just_tax_cheating":        ("Ethical values & morals", "Q180"),
    "wvs_just_bribe":               ("Ethical values & morals", "Q181"),
    "wvs_just_homosexuality":       ("Ethical values & morals", "Q182"),
    "wvs_just_abortion":            ("Ethical values & morals", "Q184"),
    "wvs_just_divorce":             ("Ethical values & morals", "Q185"),
    "wvs_just_sex_before_marriage": ("Ethical values & morals", "Q186"),
    "wvs_just_euthanasia":          ("Ethical values & morals", "Q188"),
    "wvs_just_violence":            ("Ethical values & morals", "Q191"),
    "wvs_happiness":                ("Happiness & well-being", "Q46"),
    "wvs_life_satisfaction":        ("Happiness & well-being", "Q49"),
    "wvs_freedom_of_choice":        ("Happiness & well-being", "Q48"),
    "wvs_financial_satisfaction":   ("Happiness & well-being", "Q50"),
    "wvs_subjective_health":        ("Happiness & well-being", "Q47"),
    "wvs_neighbour_immigrants":     ("Social attitudes", "Q21"),
    "wvs_neighbour_diff_race":      ("Social attitudes", "Q19"),
    "wvs_immigration_policy":       ("Social attitudes", "Q130"),
    "wvs_gender_men_leaders":       ("Social attitudes", "Q29"),
    "wvs_homosexual_parents":       ("Social attitudes", "Q36"),
    "wvs_generalised_trust":        ("Trust & organisational membership", "Q57"),
    "wvs_trust_first_time":         ("Trust & organisational membership", "Q61"),
    "wvs_trust_other_nationality":  ("Trust & organisational membership", "Q63"),
    "wvs_confidence_police":        ("Trust & organisational membership", "Q69"),
    "wvs_confidence_government":    ("Trust & organisational membership", "Q71"),
    "wvs_confidence_press":         ("Trust & organisational membership", "Q66"),
    "wvs_member_sport":             ("Trust & organisational membership", "Q95"),
    "wvs_member_religious":         ("Trust & organisational membership", "Q94"),
    "wvs_member_charity":           ("Trust & organisational membership", "Q101"),
    "wvs_member_party":             ("Trust & organisational membership", "Q98"),
}

# Human-readable grouping of WVS fields by dimension (for prompt + UI)
WVS_DIMENSIONS: dict = {
    "Religious values": [
        "wvs_religion_importance", "wvs_importance_of_god",
        "wvs_attend_services", "wvs_religious_self_id", "wvs_believe_in_god",
    ],
    "Economic values": [
        "wvs_econ_income_equality", "wvs_econ_private_ownership",
        "wvs_econ_govt_responsibility", "wvs_econ_competition_good",
        "wvs_econ_hardwork_pays",
    ],
    "Political interest & participation": [
        "wvs_political_interest", "wvs_discuss_politics",
        "wvs_action_petition", "wvs_action_demonstration", "wvs_vote_national",
    ],
    "Ethical values & morals": [
        "wvs_just_benefits_fraud", "wvs_just_stealing", "wvs_just_tax_cheating",
        "wvs_just_bribe", "wvs_just_homosexuality", "wvs_just_abortion",
        "wvs_just_divorce", "wvs_just_sex_before_marriage",
        "wvs_just_euthanasia", "wvs_just_violence",
    ],
    "Happiness & well-being": [
        "wvs_happiness", "wvs_life_satisfaction", "wvs_freedom_of_choice",
        "wvs_financial_satisfaction", "wvs_subjective_health",
    ],
    "Social attitudes": [
        "wvs_neighbour_immigrants", "wvs_neighbour_diff_race",
        "wvs_immigration_policy", "wvs_gender_men_leaders",
        "wvs_homosexual_parents",
    ],
    "Trust & organisational membership": [
        "wvs_generalised_trust", "wvs_trust_first_time",
        "wvs_trust_other_nationality", "wvs_confidence_police",
        "wvs_confidence_government", "wvs_confidence_press",
        "wvs_member_sport", "wvs_member_religious", "wvs_member_charity",
        "wvs_member_party",
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
#  AGE-CORRELATED ADJUSTMENTS
#  Applied after independent sampling to enforce plausible correlations
#  from Census 2021 and USoc W15 without a full joint distribution table.
# ══════════════════════════════════════════════════════════════════════════════

_EMPLOYED = frozenset({
    "Employee - full-time",
    "Employee - part-time",
    "Self-employed",
})


def _apply_age_correlations(s: dict) -> dict:
    age = s.get("age")
    if not isinstance(age, int):
        return s

    ea = s.get("economic_activity", "")

    # Under-22: student or part-time dominant
    if age < 22:
        if ea not in ("Full-time student", "Employee - part-time",
                      "Unemployed - seeking work"):
            s["economic_activity"] = random.choices(
                ["Full-time student", "Employee - part-time",
                 "Unemployed - seeking work"],
                weights=[65, 25, 10], k=1)[0]
            s["occupation_soc"] = "N/A"

    # 66+: retirement strongly dominant (State Pension age 66)
    elif age >= 66:
        if ea not in ("Retired", "Employee - part-time", "Self-employed"):
            s["economic_activity"] = random.choices(
                ["Retired", "Employee - part-time", "Self-employed"],
                weights=[80, 12, 8], k=1)[0]
        if s["economic_activity"] == "Retired":
            s["occupation_soc"] = "N/A"

    # 55-65: elevated early-retirement / inactive
    elif age >= 55 and ea == "Full-time student":
        s["economic_activity"] = random.choices(
            ["Employee - full-time", "Employee - part-time",
             "Self-employed", "Retired",
             "Economically inactive - other"],
            weights=[30, 25, 15, 20, 10], k=1)[0]

    # Non-employed always gets N/A occupation
    if s.get("economic_activity") not in _EMPLOYED:
        s["occupation_soc"] = "N/A"

    # 70+: health / disability age gradient
    if age >= 70:
        if s.get("general_health") == "Very good" and random.random() < 0.45:
            s["general_health"] = random.choices(
                ["Good", "Fair", "Bad"],
                weights=[55, 35, 10], k=1)[0]
        if (s.get("disability") == "Not disabled"
                and random.random() < 0.35):
            s["disability"] = random.choices(
                ["Disabled - day-to-day activities limited a little",
                 "Disabled - day-to-day activities limited a lot"],
                weights=[65, 35], k=1)[0]

    # Housing tenure age gradient (USoc W15)
    if age < 35 and s.get("housing_tenure") == "Owns outright":
        s["housing_tenure"] = random.choices(
            ["Privately rented", "Owns with mortgage",
             "Social / council rented"],
            weights=[55, 35, 10], k=1)[0]
    elif age >= 65 and s.get("housing_tenure") == "Owns with mortgage":
        s["housing_tenure"] = random.choices(
            ["Owns outright", "Social / council rented"],
            weights=[85, 15], k=1)[0]

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  WVS VALUE CORRELATIONS
#  The WVS marginals are sampled independently. Real respondents show strong
#  covariance between certain value items; this pass nudges the most robust
#  links so agents read as coherent people rather than random attitude bundles.
#  Nudges are probabilistic and gentle — they shift, not hard-set, values.
# ══════════════════════════════════════════════════════════════════════════════

def _apply_wvs_correlations(s: dict) -> dict:
    # Religiosity spine: importance of God (Q164, 1–10) anchors the other
    # religious-values items and moral traditionalism.
    god = s.get("wvs_importance_of_god")
    religious_person = s.get("wvs_religious_self_id") == "A religious person"
    high_relig = (isinstance(god, (int, float)) and god >= 7) or religious_person
    low_relig = (isinstance(god, (int, float)) and god <= 2) and \
                s.get("wvs_religious_self_id") == "An atheist"

    if high_relig:
        # More religious → more likely to attend, believe, and see religion as important
        if random.random() < 0.7:
            s["wvs_believe_in_god"] = "Yes"
        if s.get("wvs_religion_importance") == "Not at all important" and random.random() < 0.6:
            s["wvs_religion_importance"] = random.choices(
                ["Very important", "Rather important", "Not very important"],
                weights=[45, 40, 15], k=1)[0]
        if s.get("wvs_attend_services") == "Never, practically never" and random.random() < 0.5:
            s["wvs_attend_services"] = random.choices(
                ["Once a week", "Once a month", "Only on special holy days", "Once a year"],
                weights=[30, 25, 25, 20], k=1)[0]
        if s.get("wvs_member_religious") == "Don't belong" and random.random() < 0.35:
            s["wvs_member_religious"] = random.choices(
                ["Active member", "Inactive member"], weights=[55, 45], k=1)[0]
    if low_relig:
        if random.random() < 0.85:
            s["wvs_believe_in_god"] = "No"
        s["wvs_religion_importance"] = "Not at all important"
        s["wvs_attend_services"] = "Never, practically never"

    # Moral traditionalism: highly religious respondents are somewhat less
    # permissive on the sexuality/abortion cluster (Q182/Q184/Q186).
    if high_relig:
        for k in ("wvs_just_homosexuality", "wvs_just_abortion",
                  "wvs_just_sex_before_marriage"):
            v = s.get(k)
            if isinstance(v, (int, float)) and random.random() < 0.5:
                s[k] = round(max(1.0, v - random.uniform(1.0, 3.0)), 2)

    # Political engagement: interest (Q199) predicts participation (Q209/Q211)
    # and discussion (Q200).
    interest = s.get("wvs_political_interest")
    if interest == "Very interested":
        if s.get("wvs_action_petition") == "Would never do" and random.random() < 0.6:
            s["wvs_action_petition"] = random.choices(
                ["Have done", "Might do"], weights=[70, 30], k=1)[0]
        if s.get("wvs_discuss_politics") == "Never" and random.random() < 0.7:
            s["wvs_discuss_politics"] = random.choices(
                ["Frequently", "Occasionally"], weights=[55, 45], k=1)[0]
        if s.get("wvs_vote_national") == "Never" and random.random() < 0.5:
            s["wvs_vote_national"] = random.choices(
                ["Always", "Usually"], weights=[65, 35], k=1)[0]
    elif interest == "Not at all interested":
        if s.get("wvs_discuss_politics") == "Frequently" and random.random() < 0.7:
            s["wvs_discuss_politics"] = random.choices(
                ["Never", "Occasionally"], weights=[55, 45], k=1)[0]

    # Trust cohesion: low generalised trust (Q57) pulls institutional
    # confidence and stranger-trust down a little.
    if s.get("wvs_generalised_trust") == "Need to be very careful":
        if s.get("wvs_trust_first_time") in ("Trust completely", "Trust somewhat") \
                and random.random() < 0.4:
            s["wvs_trust_first_time"] = random.choices(
                ["Do not trust very much", "Trust somewhat"], weights=[60, 40], k=1)[0]

    # Wellbeing coherence: financial satisfaction (Q50) tracks life
    # satisfaction (Q49); pull them toward each other slightly.
    life = s.get("wvs_life_satisfaction")
    fin = s.get("wvs_financial_satisfaction")
    if isinstance(life, (int, float)) and isinstance(fin, (int, float)):
        if abs(life - fin) > 4 and random.random() < 0.5:
            mid = (life + fin) / 2
            s["wvs_financial_satisfaction"] = round((fin + mid) / 2, 2)

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  SKELETON SAMPLER  (drop-in for _sample_demographic_skeletons in app.py)
# ══════════════════════════════════════════════════════════════════════════════

def _sample_wvs_fields(fc: dict) -> dict:
    """Sample all WVS value-dimension fields from WVS_FIELD_CONFIGS."""
    return {name: _sample_field(cfg) for name, cfg in WVS_FIELD_CONFIGS.items()}


def sample_england_skeleton(fc: dict | None = None) -> dict:
    """Sample one England-representative demographic skeleton."""
    fc = fc or ENGLAND_FIELD_CONFIGS
    ea = _sample_field(fc.get("economic_activity", {"mode": "na"}))
    occ = _sample_field(fc.get("occupation_soc", {"mode": "na"})) if ea in _EMPLOYED else "N/A"

    s = {
        # Base fields — compatible with existing generate_agent_from_skeleton()
        "country":           "England",
        "age":               _sample_field(fc.get("age",              {"mode": "na"})),
        "gender":            _sample_field(fc.get("gender",           {"mode": "na"})),
        "education_level":   _sample_field(fc.get("education_level",  {"mode": "na"})),
        "income_bracket":    _sample_field(fc.get("income_bracket",   {"mode": "na"})),
        "urban_rural":       _sample_field(fc.get("urban_rural",      {"mode": "na"})),
        "marital_status":    _sample_field(fc.get("marital_status",   {"mode": "na"})),
        "children":          _sample_field(fc.get("children",         {"mode": "na"})),
        "political_leaning": _sample_field(fc.get("political_leaning",{"mode": "na"})),
        # Concrete ONS category, NOT "GENERATE"
        # Ethnicity: Census 2021 TS021 structure + USoc 2023 refresh (blend)
        "ethnicity":         _sample_field(fc.get("ethnicity_detailed",{"mode": "na"})),
        # Religion: basis-switched (blend / census2021 / bsa2024)
        "religion":          _sample_field(_resolve_religion_config(fc)),
        # England-specific extensions
        "economic_activity":     ea,
        "occupation_soc":        occ,
        "general_health":        _sample_field(fc.get("general_health",      {"mode": "na"})),
        "disability":            _sample_field(fc.get("disability",          {"mode": "na"})),
        "household_composition": _sample_field(fc.get("household_composition",{"mode": "na"})),
        "social_grade":          _sample_field(fc.get("social_grade",        {"mode": "na"})),
        "region":                _sample_field(fc.get("region",              {"mode": "na"})),
        "housing_tenure":        _sample_field(fc.get("housing_tenure",      {"mode": "na"})),
        # BSA 2024 continuous attitude scales (1.0–5.0)
        "scale_left_right":      _sample_field(fc.get("scale_left_right",    {"mode": "na"})),
        "scale_lib_auth":        _sample_field(fc.get("scale_lib_auth",      {"mode": "na"})),
        "scale_welfarism":       _sample_field(fc.get("scale_welfarism",     {"mode": "na"})),
    }
    # WVS Wave 7 value dimensions (religious, economic, political, ethical,
    # wellbeing, social, trust/membership) — sampled then lightly correlated.
    s.update(_sample_wvs_fields(fc))
    s = _apply_age_correlations(s)
    s = _apply_wvs_correlations(s)
    return s


def sample_england_skeletons(n: int, fc: dict | None = None) -> list[dict]:
    """Sample n England demographic skeletons."""
    return [sample_england_skeleton(fc) for _ in range(n)]


# ══════════════════════════════════════════════════════════════════════════════
#  PROMPT BUILDER  (replaces build_generation_prompt for England runs)
# ══════════════════════════════════════════════════════════════════════════════

# Interpretation hints for the 1–10 WVS scales (shown to the persona LLM).
def _hint_low_high(low, high):
    def f(v):
        if v <= 3:   return low
        if v >= 8:   return high
        if v <= 5:   return f"leans {low}"
        return f"leans {high}"
    return f

_WVS_SCALE_HINTS: dict = {
    "wvs_importance_of_god":        _hint_low_high("God unimportant", "God very important"),
    "wvs_econ_income_equality":     _hint_low_high("wants incomes more equal", "accepts larger income gaps"),
    "wvs_econ_private_ownership":   _hint_low_high("pro state ownership", "pro private ownership"),
    "wvs_econ_govt_responsibility": _hint_low_high("govt should provide", "people self-provide"),
    "wvs_econ_competition_good":    _hint_low_high("competition good", "competition harmful"),
    "wvs_econ_hardwork_pays":       _hint_low_high("hard work pays off", "success is luck/connections"),
    "wvs_life_satisfaction":        _hint_low_high("dissatisfied with life", "satisfied with life"),
    "wvs_freedom_of_choice":        _hint_low_high("little control over life", "much control over life"),
    "wvs_financial_satisfaction":   _hint_low_high("financially dissatisfied", "financially satisfied"),
    "wvs_just_benefits_fraud":      _hint_low_high("never justifiable", "always justifiable"),
    "wvs_just_stealing":            _hint_low_high("never justifiable", "always justifiable"),
    "wvs_just_tax_cheating":        _hint_low_high("never justifiable", "always justifiable"),
    "wvs_just_bribe":               _hint_low_high("never justifiable", "always justifiable"),
    "wvs_just_homosexuality":       _hint_low_high("never justifiable", "always justifiable"),
    "wvs_just_abortion":            _hint_low_high("never justifiable", "always justifiable"),
    "wvs_just_divorce":             _hint_low_high("never justifiable", "always justifiable"),
    "wvs_just_sex_before_marriage": _hint_low_high("never justifiable", "always justifiable"),
    "wvs_just_euthanasia":          _hint_low_high("never justifiable", "always justifiable"),
    "wvs_just_violence":            _hint_low_high("never justifiable", "always justifiable"),
}

# Short human labels for compact prompt rendering.
_WVS_SHORT: dict = {
    "wvs_religion_importance":      "religion in life",
    "wvs_importance_of_god":        "importance of God",
    "wvs_attend_services":          "attends services",
    "wvs_religious_self_id":        "sees self as",
    "wvs_believe_in_god":           "believes in God",
    "wvs_econ_income_equality":     "income equality",
    "wvs_econ_private_ownership":   "ownership",
    "wvs_econ_govt_responsibility": "responsibility",
    "wvs_econ_competition_good":    "competition",
    "wvs_econ_hardwork_pays":       "hard work",
    "wvs_political_interest":       "interest",
    "wvs_discuss_politics":         "discusses politics",
    "wvs_action_petition":          "petition",
    "wvs_action_demonstration":     "demonstration",
    "wvs_vote_national":            "votes",
    "wvs_just_benefits_fraud":      "benefits fraud",
    "wvs_just_stealing":            "stealing",
    "wvs_just_tax_cheating":        "tax cheating",
    "wvs_just_bribe":               "bribery",
    "wvs_just_homosexuality":       "homosexuality",
    "wvs_just_abortion":            "abortion",
    "wvs_just_divorce":             "divorce",
    "wvs_just_sex_before_marriage": "sex before marriage",
    "wvs_just_euthanasia":          "euthanasia",
    "wvs_just_violence":            "violence",
    "wvs_happiness":                "happiness",
    "wvs_life_satisfaction":        "life satisfaction",
    "wvs_freedom_of_choice":        "control over life",
    "wvs_financial_satisfaction":   "financial satisfaction",
    "wvs_subjective_health":        "health",
    "wvs_neighbour_immigrants":     "immigrant neighbours objection",
    "wvs_neighbour_diff_race":      "diff-race neighbours objection",
    "wvs_immigration_policy":       "immigration policy",
    "wvs_gender_men_leaders":       "men better leaders",
    "wvs_homosexual_parents":       "same-sex parents",
    "wvs_generalised_trust":        "generalised trust",
    "wvs_trust_first_time":         "trust strangers",
    "wvs_trust_other_nationality":  "trust other nationality",
    "wvs_confidence_police":        "confidence: police",
    "wvs_confidence_government":    "confidence: govt",
    "wvs_confidence_press":         "confidence: press",
    "wvs_member_sport":             "sports org",
    "wvs_member_religious":         "religious org",
    "wvs_member_charity":           "charity org",
    "wvs_member_party":             "political party",
}


def build_england_prompt(skeleton: dict, tier: str) -> str:
    """Build a Census 2021-anchored persona generation prompt for England."""
    def _p(v):
        return v not in (None, "N/A", "n/a", "")

    constraint_lines = [
        "FIXED DEMOGRAPHIC CONSTRAINTS - respect ALL of these exactly:",
        "- Nation: England (NOT Wales, Scotland, or Northern Ireland)",
    ]
    for field, label in [
        ("age",                  "Age"),
        ("gender",               "Sex / gender identity"),
        ("ethnicity",            "Ethnic group (ONS Census 2021 category - use EXACTLY as given)"),
        ("religion",             "Religion"),
        ("marital_status",       "Legal partnership status"),
        ("children",             "Number of children"),
        ("household_composition","Household type"),
        ("housing_tenure",       "Housing tenure (Understanding Society Wave 15)"),
        ("region",               "Region of England (Understanding Society Wave 15)"),
        ("urban_rural",          "Area type (ONS Urban-Rural Classification 2021)"),
        ("education_level",      "Highest qualification (ONS TS067)"),
        ("economic_activity",    "Economic activity status (ONS TS066)"),
        ("occupation_soc",       "Occupation SOC 2020 major group (ONS TS063) - if in employment"),
        ("social_grade",         "Approximated Social Grade / NS-SEC (ONS ASG 2021)"),
        ("income_bracket",       "Annual household income (approximate USD, ONS HBAI FYE 2024)"),
        ("general_health",       "Self-reported general health (ONS TS037)"),
        ("disability",           "Disability status (Equality Act 2010 - ONS TS038)"),
        ("political_leaning",    "Political leaning (BSA 2024 + PollCheck May 2026)"),
    ]:
        v = skeleton.get(field)
        if _p(v):
            constraint_lines.append(f"- {label}: {v}")

    # BSA attitude scales: render the continuous score WITH an interpretation
    # so the persona-generation LLM knows what each number means.
    def _band(score, low_lbl, mid_lbl, high_lbl):
        if not isinstance(score, (int, float)):
            return None
        if score < 2.4:
            return low_lbl
        if score < 2.8:
            return f"leaning {low_lbl}"
        if score <= 3.2:
            return mid_lbl
        if score <= 3.6:
            return f"leaning {high_lbl}"
        return high_lbl

    for field, label, lo_lbl, mid_lbl, hi_lbl in [
        ("scale_left_right", "Economic outlook (BSA left-right scale, 1=left .. 5=right)",
         "economically left-wing / pro-redistribution", "economic centrist",
         "economically right-wing / free-market"),
        ("scale_lib_auth", "Social outlook (BSA libertarian-authoritarian scale, 1=libertarian .. 5=authoritarian)",
         "socially liberal / libertarian", "socially moderate",
         "socially conservative / authoritarian"),
        ("scale_welfarism", "Welfare outlook (BSA welfarism scale, 1=pro-welfare .. 5=anti-welfare)",
         "strongly supportive of the welfare state", "mixed views on welfare",
         "sceptical of welfare spending"),
    ]:
        v = skeleton.get(field)
        band = _band(v, lo_lbl, mid_lbl, hi_lbl)
        if band:
            constraint_lines.append(f"- {label}: {v} — {band}")

    # ── WVS Wave 7 value dimensions ─────────────────────────────────────────
    # Render the seven value dimensions as a grouped block so the persona LLM
    # can make life story, beliefs, media habits and routine consistent with
    # this person's actual values. 1–10 scales are shown with an interpretation.
    def _wvs_label(name):
        v = skeleton.get(name)
        if v in (None, "N/A", "n/a", ""):
            return None
        cfg = WVS_FIELD_CONFIGS.get(name, {})
        if cfg.get("mode") == "scale" and isinstance(v, (int, float)):
            hint = _WVS_SCALE_HINTS.get(name)
            return f"{v}/10" + (f" ({hint(v)})" if hint else "")
        return str(v)

    wvs_lines = []
    for dim, fields in WVS_DIMENSIONS.items():
        parts = []
        for name in fields:
            lbl = _wvs_label(name)
            if lbl is None:
                continue
            short = _WVS_SHORT.get(name, name.replace("wvs_", ""))
            parts.append(f"{short}={lbl}")
        if parts:
            wvs_lines.append(f"- {dim}: " + "; ".join(parts))
    if wvs_lines:
        constraint_lines.append(
            "\nUNDERLYING VALUES (World Values Survey Wave 7, UK) — this "
            "person's actual attitudes; make their story and beliefs consistent:")
        constraint_lines.extend(wvs_lines)

    constraints = "\n".join(constraint_lines)
    region      = skeleton.get("region", "England")

    tier_fields = ""
    if tier in ("context", "bigfive"):
        tier_fields = (
            ',\n'
            '  "life_story": "3-5 sentences: upbringing, schooling, work history, '
            'current situation — rooted in the English social context of this '
            'person\'s age cohort, region, ethnicity and class background",\n'
            '  "key_life_events": ["event 1", "event 2", "event 3"],\n'
            '  "values_and_beliefs": ["value 1", "value 2", "value 3"],\n'
            '  "interests_hobbies": ["hobby 1", "hobby 2", "hobby 3"],\n'
            '  "media_consumption": ["media source 1 (e.g. BBC One, The Sun, '
            'TikTok, local radio)", "media source 2"],\n'
            '  "daily_routine": "one paragraph describing a typical weekday"'
        )
    if tier == "bigfive":
        tier_fields += (
            ',\n'
            '  "big_five": {'
            '"openness": {"score": <1-10>, "description": "<brief note>"}, '
            '"conscientiousness": {"score": <1-10>, "description": ""}, '
            '"extraversion": {"score": <1-10>, "description": ""}, '
            '"agreeableness": {"score": <1-10>, "description": ""}, '
            '"neuroticism": {"score": <1-10>, "description": ""}}'
        )

    return (
        "You are a research assistant creating a realistic synthetic human persona "
        "for a social science simulation of the English population.\n\n"
        + constraints
        + "\n\nGenerate a complete, internally consistent persona. "
        "Return ONLY a raw JSON object — no explanation, no markdown fences.\n\n"
        "Required JSON structure:\n"
        "{\n"
        '  "name": "realistic English name appropriate for this person\'s '
        'ethnic group, age and gender",\n'
        '  "occupation": "specific job title consistent with SOC group, '
        'education, income and economic activity status",\n'
        '  "city": "realistic city, town or village in '
        + region
        + ' — England only"'
        + tier_fields
        + "\n}\n\n"
        "Critical rules:\n"
        "1. The person MUST live in ENGLAND — not Wales, Scotland, or Northern Ireland.\n"
        "2. Ethnic group, health, disability, and economic activity are FIXED — do not change them.\n"
        "3. Name MUST be culturally appropriate for the given ONS ethnic group category.\n"
        "4. Occupation must match SOC major group AND economic activity. "
        "If retired or inactive, describe most recent or typical occupation.\n"
        "5. Health condition and disability must plausibly shape backstory and daily routine.\n"
        "6. Education, income and social grade must be mutually consistent.\n"
        "7. The economic, social and welfare attitude scores above describe this "
        "person's actual values — their life story, beliefs and media habits must "
        "be consistent with them, and may differ from their headline political "
        "leaning (real people are often cross-pressured).\n"
        "8. Make this a specific, believable English person with realistic regional quirks.\n"
        "9. Return raw JSON only. No text before or after the JSON object."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  AGENT BUILDER  (extends generate_agent_from_skeleton for England fields)
# ══════════════════════════════════════════════════════════════════════════════

def generate_england_agent_from_skeleton(
    skeleton: dict,
    tier: str,
    provider: str,
    api_key: str,
    model: str,
    call_api_fn: Callable,
    extract_json_fn: Callable,
) -> dict:
    """Generate one England agent from a pre-sampled skeleton."""
    prompt     = build_england_prompt(skeleton, tier)
    max_tokens = {"demographics": 500, "context": 1100, "bigfive": 1300}.get(tier, 600)

    raw = call_api_fn(
        provider=provider, api_key=api_key, model=model,
        temperature=0.95, max_tokens=max_tokens,
        system_prompt="You are a research assistant. Output only valid JSON, nothing else.",
        messages=[{"role": "user", "content": prompt}],
    )
    data = extract_json_fn(raw)
    na   = lambda v: v if v is not None else "N/A"

    agent_id     = str(uuid.uuid4())[:8]
    demographics = {
        # Standard fields (app.py-compatible)
        "name":            data.get("name", "Unknown"),
        "age":             na(skeleton.get("age")),
        "gender":          na(skeleton.get("gender")),
        "education_level": na(skeleton.get("education_level")),
        "occupation":      data.get("occupation") or "N/A",
        "income_bracket":  na(skeleton.get("income_bracket")),
        "location": {
            "city":        data.get("city") or "N/A",
            "country":     "England",
            "region":      na(skeleton.get("region")),
            "urban_rural": na(skeleton.get("urban_rural")),
        },
        "ethnicity":         na(skeleton.get("ethnicity")),
        "religion":          na(skeleton.get("religion")),
        "political_leaning": na(skeleton.get("political_leaning")),
        "marital_status":    na(skeleton.get("marital_status")),
        "children":          na(skeleton.get("children")),
        # England-specific extensions
        "economic_activity":     na(skeleton.get("economic_activity")),
        "occupation_soc_group":  na(skeleton.get("occupation_soc")),
        "general_health":        na(skeleton.get("general_health")),
        "disability_status":     na(skeleton.get("disability")),
        "household_composition": na(skeleton.get("household_composition")),
        "housing_tenure":        na(skeleton.get("housing_tenure")),
        "social_grade":          na(skeleton.get("social_grade")),
        # BSA 2024 continuous attitude scales (1.0–5.0)
        "attitude_scales": {
            "left_right":  na(skeleton.get("scale_left_right")),
            "lib_auth":    na(skeleton.get("scale_lib_auth")),
            "welfarism":   na(skeleton.get("scale_welfarism")),
            "_scale_guide": {
                "left_right": "1=economic left/redistribution .. 5=economic right/free-market",
                "lib_auth":   "1=social libertarian .. 5=social authoritarian",
                "welfarism":  "1=pro-welfare-state .. 5=anti-welfare",
                "source":     "British Social Attitudes 2024 value scales",
            },
        },
        # Source provenance for the two refreshed structural fields
        "_ethnicity_source": (
            "Census 2021 TS021 structure + Understanding Society: "
            "Calendar Year Dataset, 2023 refresh"
            if ETHNICITY_RELIGION_BASIS != "census2021"
            else "Census 2021 TS021 (self-identification)"),
        "_religion_source": {
            "blend":      "Census 2021 TS030 categories, affiliation shifted to BSA 2024",
            "census2021": "Census 2021 TS030 (self-identification)",
            "bsa2024":    "British Social Attitudes Survey 2024 (affiliation / belonging)",
        }.get(ETHNICITY_RELIGION_BASIS, "blend"),
    }

    # ── WVS Wave 7 value dimensions, grouped by dimension ───────────────────
    # Stored under persona.values so downstream analysis can slice by
    # dimension. Every field is annotated with its WVS question id.
    wvs_values = {}
    for dim, fields in WVS_DIMENSIONS.items():
        block = {}
        for name in fields:
            _dim, qid = DERIVED_FROM_WVS.get(name, (dim, "?"))
            block[name] = {
                "value": na(skeleton.get(name)),
                "wvs_q": qid,
            }
        wvs_values[dim] = block
    demographics["wvs_values"] = wvs_values
    demographics["wvs_values"]["_meta"] = {
        "source": "World Values Survey Wave 7 (2017-2022), UK/Great Britain, "
                  "survey-weighted (W_WEIGHT), N≈2609",
        "scale_note": "Fields ending in a 1-10 range are continuous WVS scales; "
                      "others are the WVS response categories.",
    }

    agent = {
        "agent_id":   agent_id,
        "version":    2,
        "tier":       tier,
        "created_at": datetime.now().isoformat(),
        "sampling_metadata": {
            "source":          "england_census_2021_population",
            "country":         "England",
            "sampling_method": "census_proportional_stratified",
            "data_sources": [
                "ONS Census 2021 TS007a - Age by 5-year bands",
                "ONS Census 2021 TS008 - Sex",
                "ONS Census 2021 TS002 - Legal partnership status",
                "ONS Census 2021 TS003 - Household composition",
                "ONS Urban-Rural Classification 2021",
                "ONS Census 2021 TS021/TS022 - Ethnic group (detailed)",
                "Understanding Society: Calendar Year Dataset 2023 - Ethnic group refresh",
                "ONS Census 2021 TS030 - Religion (self-identification)",
                "British Social Attitudes Survey 2024 (SN 9478) - Religious affiliation refresh",
                "ONS Census 2021 TS067 - Highest qualification",
                "ONS Census 2021 TS066 - Economic activity status",
                "ONS Census 2021 TS063 - Occupation SOC 2020",
                "ONS Census 2021 ASG - Approximated Social Grade",
                "ONS Census 2021 TS037 - General health",
                "ONS Census 2021 TS038 - Disability",
                "ONS HBAI FYE 2024 - Income distribution",
                "Understanding Society Wave 15 - Region, tenure, household, NS-SEC, SF-12, GHQ-12",
                "British Social Attitudes Survey 2024 - Political attitude scales",
                "PollCheck 7-poll average May 2026 - Political leaning calibration",
                "World Values Survey Wave 7 (2017-2022) UK/GB - Religious, economic, "
                "political, ethical, wellbeing, social and trust/membership values "
                "(survey-weighted, N≈2609)",
            ],
        },
        "persona": {"demographics": demographics},
        "simulation_config": {
            "provider":    provider,
            "model":       model,
            "temperature": 0.8,
            "max_tokens":  512,
            "notes":       "England Census 2021 representative population - large-scale batch",
        },
    }

    if tier in ("context", "bigfive"):
        agent["persona"]["background"] = {
            "life_story":         data.get("life_story") or "N/A",
            "key_life_events":    data.get("key_life_events") or [],
            "values_and_beliefs": data.get("values_and_beliefs") or [],
            "interests_hobbies":  data.get("interests_hobbies") or [],
            "media_consumption":  data.get("media_consumption") or [],
            "daily_routine":      data.get("daily_routine") or "N/A",
        }

    if tier == "bigfive":
        agent["persona"]["psychological_profile"] = {
            "big_five":       data.get("big_five", {}),
            "other_measures": {},
        }

    return agent


# ══════════════════════════════════════════════════════════════════════════════
#  CONCURRENT BATCH RUNNER  — for 30,000-agent production runs
# ══════════════════════════════════════════════════════════════════════════════

def run_england_population_concurrent(
    n: int,
    tier: str,
    provider: str,
    api_key: str,
    model: str,
    call_api_fn: Callable,
    extract_json_fn: Callable,
    save_agent_fn: Callable,
    max_workers: int = 4,
    progress_callback: Optional[Callable] = None,
    error_callback: Optional[Callable] = None,
    fc: dict | None = None,
    stop_event: threading.Event | None = None,
) -> dict:
    """
    Generate and save n England agents using a thread pool.

    Parameters
    ----------
    n               Total agents (e.g. 30_000)
    tier            "demographics" | "context" | "bigfive"
    max_workers     Parallel API threads (4-6 recommended for Haiku)
    progress_callback   fn(completed: int, total: int, agent: dict)
    error_callback      fn(index: int, exc: Exception, skeleton: dict)
    stop_event      Set to abort the run between completions
    """
    skeletons = sample_england_skeletons(n, fc)
    completed = 0
    errors    = []
    agent_ids = []
    lock      = threading.Lock()

    def _one(idx_skel):
        idx, skel = idx_skel
        if stop_event and stop_event.is_set():
            return None, idx, None
        try:
            agent = generate_england_agent_from_skeleton(
                skeleton=skel, tier=tier,
                provider=provider, api_key=api_key, model=model,
                call_api_fn=call_api_fn,
                extract_json_fn=extract_json_fn,
            )
            save_agent_fn(agent)
            return agent, idx, None
        except Exception as exc:
            return None, idx, exc

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_one, (i, s)): i for i, s in enumerate(skeletons)}
        for future in as_completed(futures):
            if stop_event and stop_event.is_set():
                break
            agent, idx, exc = future.result()
            with lock:
                if exc:
                    errors.append({"index": idx, "error": str(exc),
                                   "skeleton": skeletons[idx]})
                    if error_callback:
                        error_callback(idx, exc, skeletons[idx])
                else:
                    completed += 1
                    agent_ids.append(agent["agent_id"])
                    if progress_callback:
                        progress_callback(completed, n, agent)

    return {"generated": completed, "errors": errors, "agent_ids": agent_ids}


# ══════════════════════════════════════════════════════════════════════════════
#  STREAMLIT UI SUB-TAB
#  Call this inside ui_generate_sample() in app.py — see integration note.
# ══════════════════════════════════════════════════════════════════════════════

def ui_england_population_subtab():
    """
    Streamlit UI for the England Population Generator sub-tab.
    Designed as a third tab inside ui_generate_sample().
    """
    from math import ceil
    import pandas as pd

    st.subheader("England Representative Population Generator")
    st.caption(
        "Generate a statistically representative sample of the **English** population "
        "using ONS Census 2021 data, Understanding Society (Wave 15 and "
        "Calendar Year 2023), BSA 2024, and World Values Survey Wave 7. "
        "**England only** — Wales, Scotland and Northern Ireland excluded. "
        "Supports up to **30,000 agents**."
    )

    with st.expander("Data sources and methodology", expanded=False):
        st.markdown("""
**Census 2021 — England, Census Day 21 March 2021**

| Dimension | ONS Table | Key figures |
|-----------|-----------|-------------|
| Age (5-year bands) | TS007a | Mean adult 45, median 40.7 |
| Sex | TS008 | 51.0% female, 49.0% male |
| Legal partnership status | TS002 | Never married 37.9%, Married 44.8%, Divorced 9.1% |
| Household composition | TS003 | One-person 30.2%, Couple+children 27.3% |
| Population density | ONS Urban-Rural 2021 | Urban 56%, Suburban 33%, Rural 11% |
| Ethnic group (19 categories) | TS021/022 | White British 74.4%, Indian 3.1%, Pakistani 2.8% |
| Multiple ethnic group | TS022 | 2.9% mixed/multiple |
| Religion | TS030 | Christian 46.3%, No religion 36.7%, Muslim 6.7% |
| Highest qualification | TS067 | No quals 18%, Level 4+ 34% |
| Economic activity | TS066 | Active 60.6%, Retired 21.6% |
| Occupation (SOC 2020) | TS063 | Professional 27%, Managers 11% |
| Approx. Social Grade | ASG | AB 23.3%, C1 32.8%, C2 21.3%, DE 22.6% |
| General health | TS037 | Very good 47.5%, Good 34.0% |
| Disability | TS038 | Not disabled 82.5%, Limited lot 7.5% |

**Supplementary**

| Source | Dimensions added |
|--------|-----------------|
| Understanding Society: Calendar Year 2023 | Ethnicity refresh (2023 base) |
| British Social Attitudes Survey 2024 (SN 9478) | Religious affiliation refresh |
| ONS HBAI FYE 2024 | Income (USD brackets, PPP-adjusted) |
| Understanding Society Wave 15 (2023-24) | Region, housing tenure, household size, NS-SEC, SF-12, GHQ-12 |
| British Social Attitudes Survey 2024 | Left-right, libertarian-authoritarian, welfare and immigration attitude scales |
| PollCheck 7-poll avg May 2026 | Political leaning calibration (Reform 27.7%, Con 18.3%, Labour 17.6%) |
| **World Values Survey Wave 7 (2017-2022) UK/GB** | **Seven value dimensions (below), survey-weighted, N≈2609** |

**Ethnicity & religion basis switch (`ETHNICITY_RELIGION_BASIS`)**

- `"blend"` *(default)* — Census 2021 category structure, ethnicity nudged to a 2023 base with Understanding Society Calendar Year 2023, religion's Christian/None balance shifted toward BSA 2024 affiliation.
- `"census2021"` — pure ONS Census 2021 self-identification (TS021 / TS030).
- `"bsa2024"` — religion from BSA 2024 belonging with a denominational split (C-of-E / Roman Catholic / Other Christian).

Note: census religion is *self-identification* (~46% Christian, 37% none in England); BSA is *active affiliation* (~40% Christian, ~49% none) — a real and well-documented gap, not an error.

**World Values Survey Wave 7 — seven value dimensions (per-agent)**

Each item below is sampled per agent from the survey-weighted WVS Wave 7 UK/GB distribution and tagged with its WVS question id. 1–10 items are continuous scales (population weighted mean shown); others are WVS response categories.

| Dimension | Example items (WVS Q) | Illustrative population figure |
|-----------|----------------------|-------------------------------|
| Religious values | importance of religion (Q6), importance of God (Q164), attendance (Q171), self-ID (Q173), belief in God (Q165) | God mean 4.07/10; 56% never attend |
| Economic values | income equality (Q106), ownership (Q107), govt responsibility (Q108), competition (Q109), hard work (Q110) | income-gap mean 5.90/10 |
| Political interest & participation | interest (Q199), discussion (Q200), petition (Q209), demonstration (Q211), voting (Q222) | 76% have signed a petition; 65% always vote |
| Ethical values & morals | justifiability of benefits fraud (Q177), stealing (Q179), tax cheating (Q180), bribery (Q181), homosexuality (Q182), abortion (Q184), divorce (Q185), sex before marriage (Q186), euthanasia (Q188), violence (Q191) | homosexuality mean 7.85/10; stealing 1.48/10 |
| Happiness & well-being | happiness (Q46), life satisfaction (Q49), freedom of choice (Q48), financial satisfaction (Q50), health (Q47) | life satisfaction mean 7.34/10; 90% quite/very happy |
| Social attitudes | immigrant neighbours (Q21), diff-race neighbours (Q19), immigration policy (Q130), men better leaders (Q29), same-sex parents (Q36) | 5% object to immigrant neighbours |
| Trust & organisational membership | generalised trust (Q57), trust strangers (Q61)/other nationality (Q63), confidence in police (Q69)/govt (Q71)/press (Q66), membership of sport (Q95)/religious (Q94)/charity (Q101)/party (Q98) | 46% "most people can be trusted"; 67% confidence in police |

WVS marginals are sampled independently, then a light correlation pass links the strongest real-world associations (religiosity ↔ moral traditionalism, political interest ↔ participation, generalised ↔ stranger trust, life ↔ financial satisfaction) so agents are internally coherent.

**Attitude scales (BSA 2024, continuous 1.0–5.0 per agent)**

| Scale | 1.0 pole | 5.0 pole | Modelled mean |
|-------|----------|----------|---------------|
| Left–Right (economic) | Left / redistribution | Right / free-market | 2.45 |
| Libertarian–Authoritarian (social) | Libertarian | Authoritarian | 3.35 |
| Welfarism | Pro-welfare-state | Anti-welfare | 3.05 |

*Means reflect BSA's long-run population position; standard deviations are modelling choices. Replace with exact BSA 2024 technical-report figures before quantitative use.*

**Age-correlated adjustments applied at skeleton stage**

- Under 22: redirected to student or part-time employment
- 66+: redirected to retirement (80%) or part-time/self-employed (20%)
- 70+: 45% chance of health resampled downward; 35% chance of disability flag added
- Under 35: outright homeownership replaced with renting
- 65+: mortgage ownership replaced with outright or social rent
        """)

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        n_agents = st.number_input(
            "Number of agents",
            min_value=1, max_value=30_000, value=500, step=100,
            key="eng_n_agents",
            help="Up to 30,000. Start with 100-500 to verify quality before a full run.",
        )
    with col2:
        tier = st.selectbox(
            "Agent tier",
            ["demographics", "context", "bigfive"],
            format_func=lambda x: {
                "demographics": "Tier 1 — Demographics only",
                "context":      "Tier 2 — Demographics + Life context",
                "bigfive":      "Tier 3 — Demographics + Context + OCEAN",
            }[x],
            key="eng_tier",
        )
    with col3:
        max_workers = st.slider(
            "Parallel workers",
            min_value=1, max_value=8, value=4,
            key="eng_workers",
            help="4-6 workers recommended for Haiku. Keep at 1 for Sonnet to avoid rate limits.",
        )

    provider = st.session_state.get("global_provider", "Anthropic (Claude)")
    model    = st.session_state.get("global_model",    "claude-haiku-4-5-20251001")
    api_key  = st.session_state.get("global_api_key",  "")

    if not api_key:
        st.warning("Set your API key in the **sidebar** before generating.")
        return

    secs_per = {"demographics": 2, "context": 4, "bigfive": 6}.get(tier, 2)
    est_secs = ceil(int(n_agents) * secs_per / max_workers)
    est_h    = est_secs // 3600
    est_m    = (est_secs % 3600) // 60
    est_s    = est_secs % 60
    est_lbl  = (f"{est_h}h {est_m}m" if est_h else f"{est_m}m {est_s}s")
    st.caption(
        f"Using **{provider} / {model}** — "
        f"**{max_workers}** worker(s) — "
        f"Estimated time: **{est_lbl}** for {int(n_agents):,} agents"
    )

    # Distribution preview
    with st.expander("Preview 5 sampled skeletons", expanded=False):
        prev = sample_england_skeletons(5, ENGLAND_FIELD_CONFIGS)
        show_keys = [
            "age", "gender", "ethnicity", "religion", "region", "urban_rural",
            "education_level", "economic_activity", "occupation_soc",
            "general_health", "disability", "political_leaning",
            "scale_left_right", "scale_lib_auth", "scale_welfarism",
        ]
        st.caption("Core demographics + BSA attitude scales")
        st.dataframe(
            pd.DataFrame([{k: str(p.get(k, ""))[:38] for k in show_keys}
                          for p in prev]),
            use_container_width=True, hide_index=True,
        )
        st.caption("World Values Survey Wave 7 value dimensions (one column per item)")
        wvs_keys = [
            "wvs_religion_importance", "wvs_importance_of_god",
            "wvs_econ_income_equality", "wvs_political_interest",
            "wvs_just_homosexuality", "wvs_just_abortion",
            "wvs_happiness", "wvs_life_satisfaction",
            "wvs_generalised_trust", "wvs_confidence_police",
            "wvs_member_sport", "wvs_immigration_policy",
        ]
        st.dataframe(
            pd.DataFrame([{_WVS_SHORT.get(k, k): str(p.get(k, ""))[:24]
                           for k in wvs_keys} for p in prev]),
            use_container_width=True, hide_index=True,
        )

    st.divider()

    # Stop event initialised once per session
    if "eng_stop_event" not in st.session_state:
        st.session_state.eng_stop_event = threading.Event()

    col_go, col_stop = st.columns([3, 1])
    with col_go:
        go = st.button(
            f"Generate {int(n_agents):,} England agents",
            type="primary", use_container_width=True, key="eng_go",
        )
    with col_stop:
        if st.button("Stop", use_container_width=True, key="eng_stop"):
            st.session_state.eng_stop_event.set()
            st.warning("Stop signal sent — current batch will complete then halt.")

    if go:
        st.session_state.eng_stop_event.clear()
        stop_ev = st.session_state.eng_stop_event

        from app import call_api, _extract_json_from_llm, save_agent

        progress_bar  = st.progress(0.0)
        status_text   = st.empty()
        err_collector = []

        def _on_progress(done, total, agent):
            nm = agent.get("persona", {}).get("demographics", {}).get("name", "?")
            status_text.text(f"Saved {done:,} / {total:,}  —  last: {nm}")
            progress_bar.progress(done / total)

        def _on_error(idx, exc, _skel):
            err_collector.append(f"Agent {idx+1}: {exc}")

        with st.spinner("Running — do not close this tab"):
            result = run_england_population_concurrent(
                n=int(n_agents),
                tier=tier,
                provider=provider,
                api_key=api_key,
                model=model,
                call_api_fn=call_api,
                extract_json_fn=_extract_json_from_llm,
                save_agent_fn=save_agent,
                max_workers=max_workers,
                progress_callback=_on_progress,
                error_callback=_on_error,
                fc=ENGLAND_FIELD_CONFIGS,
                stop_event=stop_ev,
            )

        progress_bar.empty()
        status_text.empty()

        gen = result["generated"]
        if gen:
            st.success(
                f"Saved **{gen:,}** England agents to the shared library. "
                "Switch to **Sample Agents** to browse them."
            )
        if err_collector:
            with st.expander(f"{len(err_collector)} error(s)", expanded=False):
                for e in err_collector[:50]:
                    st.error(e)
                if len(err_collector) > 50:
                    st.caption(f"... and {len(err_collector) - 50} more")
