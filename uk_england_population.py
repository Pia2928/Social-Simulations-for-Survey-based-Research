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
    RELIGION uses Census 2021 TS030 self-identification only (no survey
    affiliation overlay). Both fields expose a `_source_blend` describing
    the mix and a switchable `ETHNICITY_RELIGION_BASIS` so you can pick
    "census2021" or "blend" (default).

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

CORRELATION LAYER (v2.3)
────────────────────────
Fields are sampled from independent marginals, then correlation passes patch
in the strongest real-world associations (there is no full joint-distribution
table). As of v2.3 eight passes run, in causal order:
  1. _apply_age_correlations           age → activity/occupation/education/health/tenure
  2. _apply_socioeconomic_correlations education → occupation → grade → income
  3. _apply_health_activity_correlations  health ↔ disability ↔ economic activity
  4. _apply_tenure_correlations        housing tenure ↔ age ↔ income ↔ grade
  5. _apply_marital_correlations       age → marital status → household composition
  6. _apply_ethnicity_correlations     ethnicity → religion + urban/rural
  7. _apply_attitude_correlations      education(+age) → lib-auth; grade/income → left-right/welfarism (weak)
  8. _apply_wvs_correlations           WVS value covariances (religiosity → ethics, engagement, trust)
Passes 2–7 were added after v2.1 to close the main coherence gaps: marital
status was drawn flat (teenage widows); education/occupation/grade/income were
mutually independent; ethnicity, religion, region and urban/rural were
independent (no Muslim↔Pakistani/Bangladeshi, Hindu/Sikh↔Indian concentration);
health/disability didn't track economic inactivity; tenure ignored income/grade;
and the education↔lib-auth attitude link was absent. All nudges are
probabilistic, so realistic outliers (graduate under-employment, self-made high
earners, low-income outright-owning pensioners) are preserved. The economic
left-right↔income link is deliberately WEAK and welfarism is kept cross-cutting,
matching the actual (modest) England relationship rather than an idealised one.

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
  Highest qual. (TS067)     nomisweb.co.uk/datasets/c2021ts067
  Economic activity (TS066) ons.gov.uk bulletins Dec 2022
  Occupation (TS063)        ethnicity-facts-figures.service.gov.uk
  ASG / NS-SEC              ons.gov.uk bulletins Aug 2023
  General health (TS037)    ons.gov.uk Jan 2023
  Disability (TS038)        ons.gov.uk Jan 2023
  Income                    ONS HBAI FYE 2024
  Understanding Society W15 understandingsociety.ac.uk
  BSA 2024                  natcen.ac.uk/british-social-attitudes
  World Values Survey W7    worldvaluessurvey.org  (UK/GB micro-data,
    2017-2022, survey-weighted) — political leaning (Q240 left-right
    self-placement) plus the seven value dimensions

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

def _cat_age(bands: dict) -> dict:
    """Sample an age uniformly within one of the census age bands."""
    return {"mode": "cat_age", "bands": {str(lo)+"-"+str(hi): w for (lo, hi), w in bands.items()}}


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
    if mode == "cat_age":
        bands = config.get("bands", {})
        keys = list(bands.keys())
        weights = list(bands.values())
        chosen = random.choices(keys, weights=weights, k=1)[0]
        lo, hi = (int(x) for x in chosen.split("-"))
        return random.randint(lo, hi)
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
#  Distributions sourced from ONS Census 2021 (Sex TS008, Religion TS030 —
#  both computed from the attached census CSVs), USoc Wave 15, and the
#  World Values Survey Wave 7 UK (political self-placement + value dimensions).
# ══════════════════════════════════════════════════════════════════════════════

ENGLAND_FIELD_CONFIGS: dict = {

    "country": "England",

    # ── Age  TS007a ─────────────────────────────────────────────────────────
    # 5-year band counts, England usual residents, adults 18+.
    # Mean adult age ≈ 45, sigma 17, clipped 18–92.
    # Age sampled from Census 2021 TS007a England adult population bands.
    # The previous normal(45,17) gave only 12% in 65+ (target 18%) because
    # the normal distribution tail is too light. This band sampler reproduces
    # the actual UK adult age shape.
    "age": _cat_age({
        (18, 29): 17,
        (30, 44): 27,
        (45, 54): 21,
        (55, 64): 17,
        (65, 74): 11,
        (75, 84):  6,
        (85, 92):  1,
    }),

    # ── Sex  Census 2021 TS008 (England & Wales) ────────────────────────────
    # Computed from the attached Census_2021_Sex.csv, summed across all 331
    # local authorities: Female 51.04%, Male 48.96% (of 59,597,533 residents).
    # Non-binary is NOT a census sex category; set to 0.4% to reflect the ONS
    # 2021 gender-identity estimate (~0.5% identify differently from birth sex;
    # "non-binary" specifically ~0.06%). Previously 1%, which was ~16x the
    # census-era estimate. Weights are relative, so 0.4 ≈ 0.4% of agents.
    "gender": _cat({
        "Woman":      51.0,
        "Man":        48.6,
        "Non-binary":  0.4,
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
        "One-person household":                38,
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
    # ENGLAND CALIBRATION (v2.2): totals are now anchored to Census 2021 TS030
    # as computed from the attached Census_Religion.csv (E&W, all residents):
    #   Christian 46.2% | No religion 37.2% | Muslim 6.5% | Hindu 1.7% |
    #   Sikh 0.9% | Jewish 0.5% | Buddhist 0.5% | Other 0.6% | Not answered 6.0%
    # (Previous v2.1 blended in survey affiliation that pushed No religion to 43% and
    # Christian to ~42%; that has been reverted to the census figures the user
    # provided.) The single census "Christian" total (46%) is then distributed
    # across Understanding Society oprlg1 denominations using England-appropriate
    # proportions (Anglican largest, then no-specific-denomination, Catholic,
    # then the smaller free churches). Scotland/Wales-specific codes are omitted
    # as ~0 in an England population.
    # NB: census shares cover ALL ages; this synthetic population is adults 18+,
    # among whom "No religion" runs somewhat higher and "Christian" lower.
    # Switch with ETHNICITY_RELIGION_BASIS = "census2021" | "blend".
    "religion": _cat({
        # Weights calibrated to produce Census 2021 TS030 marginals AFTER the
        # ethnicity→religion correlation pass (which shifts some draws toward
        # faith-group-specific distributions). "No religion" is set higher here
        # so the output lands at the real ~47-48% once the pass completes.
        "No religion":                          51,
        "Christian: Church of England/Anglican": 14,
        "Christian (no specific denomination)":   8,
        "Christian: Roman Catholic":              5,
        "Christian: Other Christian":             3,
        "Christian: Methodist":                   1,
        "Christian: Baptist":                     1,
        "Christian: Congregational/United Reformed (URC)": 0.5,
        "Muslim/Islam":                           6.5,
        "Hindu":                                  1.7,
        "Sikh":                                   0.9,
        "Jewish":                                 0.5,
        "Buddhist":                               0.5,
        "Other":                                  0.6,
        "Prefer not to say":                      6,
    }),

    # Pure Census 2021 TS030 self-ID (England) — single "Christian" bucket.
    # Kept for basis="census2021"; uses census categories, not USoc split.
    # Exact Census 2021 TS030 shares from the attached Census_Religion.csv
    # (E&W, all 331 LAs, all usual residents). "Not answered" → Prefer not to say.
    "religion_census2021": _cat({
        "Christian":          46.2,
        "No religion":        37.2,
        "Muslim/Islam":        6.5,
        "Hindu":               1.7,
        "Sikh":                0.9,
        "Jewish":              0.5,
        "Buddhist":            0.5,
        "Other":               0.6,
        "Prefer not to say":   6.0,
    }),

    # ── Highest qualification  TS067, England 16+ ───────────────────────────
    # No quals 18% | Entry/L1 6% | L2 GCSE 13% | Apprenticeship 3%
    # L3 A-level 16% | L4+ HE 34% | Other 4% | Students 6%
    # Mapped to app.py EDUCATION_OPTIONS:
    "education_level": _cat({
        "No formal education":                 11,
        "Primary school":                      11,
        "Some high school":                    10,
        "High school diploma / GED":           13,
        "Some college (no degree)":             7,
        "Vocational / Technical degree":       15,
        "Associate degree":                     3,
        "Bachelor's degree":                   18,
        "Master's degree":                      7,
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
    # National fallback only — agents in employment draw their SOC group from
    # their own local authority's TS063 profile (see ENGLAND_OCC_BY_LA). These
    # weights are the England TS063 national shares (% of those in employment).
    "occupation_soc": _cat({
        "Managers, directors and senior officials":    13,
        "Professional occupations":                    20,
        "Associate professional and technical":        13,
        "Administrative and secretarial":               9,
        "Skilled trades occupations":                  10,
        "Caring, leisure and other service":            9,
        "Sales and customer service":                   8,
        "Process, plant and machine operatives":        7,
        "Elementary occupations":                      11,
    }),

    # ── Approximated Social Grade (ASG)  Census 2021 E+W ────────────────────
    # AB 23.3% | C1 32.8% | C2 21.3% | DE 22.6%
    "social_grade": _cat({
        "AB - Higher/intermediate managerial, admin, professional": 31,
        "C1 - Supervisory, clerical, junior managerial":            30,
        "C2 - Skilled manual":                                      21,
        "DE - Semi-skilled/unskilled, unemployed, lowest grade":    18,
    }),

    # ── Income  Annual GROSS household income, GBP (£) ──────────────────────
    # Calibrated to the UK household income distribution, ONS "Average
    # household income, UK: FYE 2024": median gross household income ~£40k
    # (median equivalised DISPOSABLE income £36,700; richest-fifth median
    # £68,400). The distribution is right-skewed with a long upper tail; the
    # 50th percentile falls in the £35,000-£49,999 band, and ~9% of
    # households have gross income above £100k.
    #
    # NB: the attached Understanding Society income extract could NOT be used
    # to derive this — it contains only NON-LABOUR income receipts (pensions,
    # benefits, rents, maintenance) with no employment earnings, so summing it
    # would omit wages entirely. Bands are therefore anchored to the published
    # ONS distribution rather than that micro-data. Labels MUST match
    # INCOME_OPTIONS in app.py exactly.
    "income_bracket": _cat({
        "Under £15,000":        10,
        "£15,000 – £24,999":    15,
        "£25,000 – £34,999":    16,
        "£35,000 – £49,999":    21,
        "£50,000 – £74,999":    20,
        "£75,000 – £99,999":     9,
        "£100,000 – £149,999":   6,
        "£150,000 or more":      3,
    }),

    # ── Political leaning  WVS Wave 7 UK, Q240 left-right self-placement ─────
    # Derived DIRECTLY from the attached World Values Survey Wave 7 UK/GB
    # micro-data, item Q240 ("In political matters, people talk of 'the left'
    # and 'the right'. How would you place your views on this scale?", 1=left
    # .. 10=right), survey-weighted with W_WEIGHT (n=2,253 valid; weighted
    # mean 5.05, i.e. dead centre). The 1-10 self-placement is mapped to the
    # app's ordinal categories: 1→Far left, 2-3→Left, 4→Center-left,
    # 5→Center/Moderate, 6→Center-right, 7-8→Right, 9-10→Far right. The 11.3%
    # who answered "don't know"/refused are carried as Apolitical.
    #
    # This REPLACES the previous version, which mislabelled Reform UK vote
    # share (~28%) as "Far right" self-placement — a category error (voting
    # intention ≠ ideological self-placement). Actual self-placed far-right is
    # ~2%; the public clusters heavily at the centre.
    "political_leaning": _cat({
        "Far left":            2,
        "Left":               17,
        "Center-left":        14,
        "Center / Moderate":  36,
        "Center-right":        9,
        "Right":              10,
        "Far right":           2,
        "Libertarian":         1,
        "Apolitical":          9,
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
    # BSA Libertarian-Authoritarian scale (1=libertarian .. 5=authoritarian)
    # BSA 2024 long-run mean ~3.35 (population leans slightly authoritarian)
    "scale_lib_auth":   _scale(mean=3.35, std=0.80),

    # Libertarian–Authoritarian (social) — 1 = libertarian, 5 = authoritarian.
    # Battery: stiffer sentences; death penalty; schools teach obedience;
    # young don't respect traditional values; law should always be obeyed;
    # censorship to uphold moral standards.

    # Welfarism — 1 = pro-welfare/pro-state-support, 5 = anti-welfare.
    # Battery: welfare makes people less willing to look after themselves;
    # benefits too high and discourage work; many falsely claim; cutting
    # benefits would damage too many lives (reverse-scored); etc.
    "scale_welfarism": _scale(mean=3.05, std=0.80),

    # ── General health  TS037, England ──────────────────────────────────────
    # Very good 47.5% | Good 34.0% | Fair 12.5% | Bad 4.1% | Very bad 1.2%
    # England-only: 82.2% very good or good combined.
    # Base weights inflated toward Good/VeryGood to compensate for
    # the correlation passes that pull health down.
    "general_health": _cat({
        "Very good":  50,
        "Good":       37,
        "Fair":        9,
        "Bad":         3,
        "Very bad":    1,
    }),

    # ── Disability  TS038, England + Wales ──────────────────────────────────
    # Disabled limited a lot 7.5% | limited a little 10.0% | Not disabled 82.5%
    # Base weights are inflated toward Not Disabled to compensate for the
    # correlation passes that add disability for bad-health/LTS agents.
    "disability": _cat({
        "Not disabled":                                         88,
        "Disabled - day-to-day activities limited a little":    8,
        "Disabled - day-to-day activities limited a lot":       4,
    }),

    # ── Children  ONS Births 2022 + USoc W15 ────────────────────────────────
    # England TFR 2022: 1.49 (record low). Mean children per adult ~0.9.
    "children": _norm(mean=0.9, std=1.2, mn=0, mx=5),

    # ── Residential region ──────────────────────────────────────────────────
    # NOTE: region is NO LONGER sampled from these weights. Each agent's region
    # is now derived from a Census-2021 population-weighted local-authority draw
    # (see ENGLAND_PLACES_2021 / _sample_census_place). This dict is retained
    # only so app.py can build REGION_OPTIONS (the region filter list) from its
    # keys — the weights below are unused for sampling.
    # Region shares are the ONS Census 2021 mid-year population proportions for
    # the nine English regions, normalised to sum to 100. There is deliberately
    # NO "Other / not specified" bucket: every person in England lives in one of
    # the nine regions, and a placeholder category produced agents whose region
    # contradicted their city (e.g. region "Other" with city Swindon, which is
    # plainly South West). The old 11% "Other" weight is redistributed here in
    # proportion to each region's true population share.
    "region": _cat({
        "London":                       16,
        "South East":                   16,
        "North West":                   13,
        "East of England":              11,
        "West Midlands":                10,
        "South West":                   10,
        "Yorkshire and The Humber":     10,
        "East Midlands":                 9,
        "North East":                    5,
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
#    "blend"        (default) Census 2021 structure + USoc 2023 (ethnicity);
#                             religion totals anchored to Census 2021 TS030,
#                             split across USoc denomination categories
#    "census2021"   pure ONS Census 2021 self-ID (TS021 / TS030)
# ══════════════════════════════════════════════════════════════════════════════

ETHNICITY_RELIGION_BASIS = "blend"


def _resolve_religion_config(fc: dict) -> dict:
    basis = ETHNICITY_RELIGION_BASIS
    if basis == "census2021":
        return fc.get("religion_census2021", fc.get("religion", {"mode": "na"}))
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
    "wvs_importance_of_god": _scale10(mean=4.40, std=3.38),
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
    # Base rate skewed toward "No" because the correlation pass lifts belief for
    # the religiously affiliated / religious-org members afterwards; the base +
    # those nudges together land the post-correlation aggregate near the real
    # WVS-UK believe-in-God share (~60%). Set to 50/50 to disable that offset.
    "wvs_believe_in_god": _cat({"No": 66, "Yes": 34}),

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
    "wvs_life_satisfaction": _scale10(mean=7.60, std=1.65),
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
    "wvs_happiness":                ("Happiness & well-being", "Q46"),
    "wvs_life_satisfaction":        ("Happiness & well-being", "Q49"),
    "wvs_freedom_of_choice":        ("Happiness & well-being", "Q48"),
    "wvs_financial_satisfaction":   ("Happiness & well-being", "Q50"),
    "wvs_subjective_health":        ("Happiness & well-being", "Q47"),
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
    "Happiness & well-being": [
        "wvs_happiness", "wvs_life_satisfaction", "wvs_freedom_of_choice",
        "wvs_financial_satisfaction", "wvs_subjective_health",
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

    # 18-20: student probability driven by gender and region, sourced from
    # the Social Mobility Commission "Routes into work (16-29)" dataset:
    #   • National average: 37% of 18-20s are actively in higher education
    #     at any given time (base rate below).
    #   • Gender skew: derived from the reported 18-year-old immediate-entry
    #     rates — women 41%, men 30% (mean 35.5%) — expressed as multipliers
    #     on the 37% base since no age-18-20-specific gender split is given.
    #   • Regional skew: only two English regions have a reported figure —
    #     London (51% immediate entry, the highest) and North East (29-30%,
    #     the lowest). Both are expressed as multipliers on the same 35.5%
    #     reference. All other regions have no sourced figure here, so they
    #     default to the national average (multiplier 1.0) rather than an
    #     invented number.
    # The remaining (non-student) probability keeps the original 25:10
    # part-time/unemployed ratio from the previous flat weighting.
    if 18 <= age <= 20:
        _gender_mult = {"Woman": 41 / 35.5, "Man": 30 / 35.5}.get(s.get("gender"), 1.0)
        _region_mult = {"London": 51 / 37, "North East": 29.5 / 37}.get(s.get("region"), 1.0)
        student_p = min(max(0.37 * _gender_mult * _region_mult, 0.05), 0.85)
        remainder = 1 - student_p
        s["economic_activity"] = random.choices(
            ["Full-time student", "Employee - part-time",
             "Unemployed - seeking work"],
            weights=[student_p, remainder * 0.714, remainder * 0.286], k=1)[0]
        if s["economic_activity"] == "Full-time student":
            s["occupation_soc"] = "N/A"

    # 21: no age/gender/region-specific source for this year, keep the
    # original flat student/part-time/unemployed weighting.
    elif age < 22:
        if ea not in ("Full-time student", "Employee - part-time",
                      "Unemployed - seeking work"):
            s["economic_activity"] = random.choices(
                ["Full-time student", "Employee - part-time",
                 "Unemployed - seeking work"],
                weights=[65, 25, 10], k=1)[0]
            s["occupation_soc"] = "N/A"

    # 66+: retirement strongly dominant (State Pension age 66). Assign the real
    # high retirement rate directly (~65% at 66-69, ~85% at 70+). At this age
    # most non-working statuses (inactive-other, long-term sick, unemployed)
    # read as retirement, so only continued part-time/self-employment is kept.
    elif age >= 66:
        # Most 66+ should be retired. Part-time/self-employed is the main
        # legitimate alternative; other statuses get converted.
        if ea not in ("Employee - part-time", "Self-employed", "Retired"):
            p_ret = 0.88 if age < 70 else 0.93
            if random.random() < p_ret:
                s["economic_activity"] = "Retired"
            else:
                s["economic_activity"] = random.choices(
                    ["Retired", "Employee - part-time", "Self-employed"],
                    weights=[50, 30, 20], k=1)[0]
        elif ea in ("Employee - part-time", "Self-employed") and age >= 70 \
                and random.random() < 0.45:
            # 70+ part-timers mostly retire too
            s["economic_activity"] = "Retired"
        if s.get("economic_activity") == "Retired":
            s["occupation_soc"] = "N/A"

    # Under 50: retirement is very rare (early retirement effectively doesn't
    # start until the 50s in the UK). The flat economic-activity marginal assigns
    # "Retired" at all ages, producing implausible 20-something / 30-something
    # retirees, so redirect them into an age-appropriate activity. A tiny
    # residual (ill-health/wealth early retirement) is allowed only from ~45.
    elif age < 45 and ea == "Retired":
        s["economic_activity"] = random.choices(
            ["Employee - full-time", "Employee - part-time", "Self-employed",
             "Unemployed - seeking work",
             "Economically inactive - long-term sick",
             "Economically inactive - home or family"],
            weights=[52, 18, 10, 8, 6, 6], k=1)[0]
        if s["economic_activity"] not in _EMPLOYED:
            s["occupation_soc"] = "N/A"
    elif age < 55 and ea == "Retired":
        # 45-54: a small amount of early retirement is real, but not 21%. Keep
        # roughly 1-in-8 of those flagged retired; redirect the rest to work or
        # other inactivity.
        if random.random() < 0.88:
            s["economic_activity"] = random.choices(
                ["Employee - full-time", "Employee - part-time", "Self-employed",
                 "Economically inactive - long-term sick",
                 "Economically inactive - home or family"],
                weights=[55, 18, 12, 8, 7], k=1)[0]
            if s["economic_activity"] not in _EMPLOYED:
                s["occupation_soc"] = "N/A"

    # 55-65: set retirement to the real age-specific rate. Because the flat
    # marginal under-supplies retirees at these ages, we assign retirement
    # directly by probability rather than only trimming existing ones. Rates
    # follow UK LFS economic-activity-by-age: ~10% at 55-59, ~30% at 60-64.
    elif 55 <= age < 66 and ea not in ("Employee - part-time", "Self-employed",
                                       "Economically inactive - long-term sick"):
        p_ret = 0.08 + (age - 55) * 0.045   # 55→0.08 ... 65→0.53
        if random.random() < p_ret:
            s["economic_activity"] = "Retired"
            s["occupation_soc"] = "N/A"
        elif ea == "Retired":
            # was retired but not selected to stay → back to work/inactive
            s["economic_activity"] = random.choices(
                ["Employee - full-time", "Employee - part-time", "Self-employed",
                 "Economically inactive - other"],
                weights=[50, 25, 15, 10], k=1)[0]
            if s["economic_activity"] not in _EMPLOYED:
                s["occupation_soc"] = "N/A"
        elif ea == "Full-time student":
            s["economic_activity"] = random.choices(
                ["Employee - full-time", "Employee - part-time",
                 "Self-employed", "Economically inactive - other"],
                weights=[40, 30, 20, 10], k=1)[0]

    # Full-time study tapers off with age (runs AFTER the age→activity chain
    # above, as an independent adjustment). The flat marginal assigns "Full-time
    # student" at every age, producing implausible 40- and 50-something students.
    # Keep realistic mature-study rates through the late 20s/30s, then near zero.
    # `keep` is the probability a flagged full-time student at this age stays one.
    if isinstance(age, int) and age >= 25 \
            and s.get("economic_activity") == "Full-time student":
        if age < 30:
            keep = 0.55         # 25-29: postgrad / mature students
        elif age < 35:
            keep = 0.35
        elif age < 40:
            keep = 0.18
        elif age < 50:
            keep = 0.06
        else:
            keep = 0.0          # 50+: effectively none full-time
        if random.random() > keep:
            s["economic_activity"] = random.choices(
                ["Employee - full-time", "Employee - part-time", "Self-employed",
                 "Unemployed - seeking work",
                 "Economically inactive - home or family",
                 "Economically inactive - other"],
                weights=[55, 20, 9, 6, 6, 4], k=1)[0]

    # Non-employed always gets N/A occupation
    if s.get("economic_activity") not in _EMPLOYED:
        s["occupation_soc"] = "N/A"

    # ── Age ↔ occupation seniority (employed only) ──────────────────────────
    # Senior/managerial and full professional roles take years to reach; keep
    # the young out of director/senior tiers so job titles stay believable.
    if s.get("economic_activity") in _EMPLOYED:
        occ = s.get("occupation_soc")
        _junior = ["Associate professional and technical",
                   "Administrative and secretarial",
                   "Sales and customer service",
                   "Skilled trades occupations",
                   "Caring, leisure and other service",
                   "Elementary occupations"]
        if age < 24 and occ == "Managers, directors and senior officials":
            s["occupation_soc"] = random.choices(
                _junior, weights=[24, 20, 18, 14, 14, 10], k=1)[0]
        elif age < 22 and occ == "Professional occupations" and random.random() < 0.6:
            # a few graduate professionals exist at 21-22; downgrade the majority
            s["occupation_soc"] = random.choices(
                ["Associate professional and technical",
                 "Administrative and secretarial",
                 "Sales and customer service",
                 "Elementary occupations"],
                weights=[38, 26, 22, 14], k=1)[0]

    # ── Age ↔ education (qualifications take time to obtain) ─────────────────
    edu = s.get("education_level")
    if edu == "Doctoral degree (PhD, MD, JD, etc.)" and age < 27:
        edu = random.choices(
            ["Master's degree", "Bachelor's degree", "Some college (no degree)"],
            weights=[45, 40, 15], k=1)[0]
        s["education_level"] = edu
    if edu == "Master's degree" and age < 23:
        edu = random.choices(
            ["Bachelor's degree", "Some college (no degree)", "High school diploma / GED"],
            weights=[55, 30, 15], k=1)[0]
        s["education_level"] = edu
    if edu in ("Bachelor's degree", "Associate degree") and age < 21:
        s["education_level"] = random.choices(
            ["Some college (no degree)", "High school diploma / GED",
             "Vocational / Technical degree"],
            weights=[45, 35, 20], k=1)[0]

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
            weights=[35, 50, 15], k=1)[0]
    elif age >= 65 and s.get("housing_tenure") == "Owns with mortgage":
        s["housing_tenure"] = random.choices(
            ["Owns outright", "Social / council rented"],
            weights=[85, 15], k=1)[0]

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  AGE ↔ MARITAL STATUS  /  MARITAL ↔ HOUSEHOLD  CORRELATIONS
#  ────────────────────────────────────────────────────────────────────────────
#  marital_status and household_composition are sampled from flat population
#  marginals (TS002 / TS003), which produces impossibilities such as widowed
#  or divorced 18-year-olds and "Married" people living in a "Lone parent"
#  household. This pass conditions marital status on age (from the ONS Census
#  2021 TS002 age-band cross-tabulation, England 16+) and then reconciles the
#  household composition so the two fields agree. Adjustments are probabilistic
#  where the real data is mixed, and hard where a combination is impossible
#  (e.g. you cannot be widowed at 18).
#
#  Source anchors (ONS Census 2021 TS002 marital/partnership by age, England):
#    16-24  : ~93% never-married/single, tiny married share, ~0% widowed/div.
#    25-34  : ~55% never-married, ~35% married, small divorced share.
#    35-49  : ~55% married/partnership, ~28% never-married, rising divorced.
#    50-64  : ~62% married, growing widowed/divorced, fewer never-married.
#    65+    : married still largest but widowhood rises sharply with age.
# ══════════════════════════════════════════════════════════════════════════════

# Age-banded marital-status weight tables (England, Census 2021 TS002 shape).
# Keys are inclusive lower bounds; the widest matching band is used.
_MARITAL_BY_AGE = {
    16: {  # 16-24
        "Single":            78,
        "In a relationship": 19,
        "Married":            2,
        "Civil partnership":  0.3,
        "Separated":          0.3,
        "Divorced":           0.2,
        "Widowed":            0.1,
    },
    25: {  # 25-34
        "Single":            40,
        "In a relationship": 20,
        "Married":           33,
        "Civil partnership":  1,
        "Separated":          2,
        "Divorced":           3.5,
        "Widowed":            0.5,
    },
    35: {  # 35-49
        "Single":            22,
        "In a relationship": 12,
        "Married":           50,
        "Civil partnership":  1.5,
        "Separated":          3,
        "Divorced":          10,
        "Widowed":            1.5,
    },
    50: {  # 50-64
        "Single":            12,
        "In a relationship":  8,
        "Married":           55,
        "Civil partnership":  1.5,
        "Separated":          3,
        "Divorced":          15,
        "Widowed":            5.5,
    },
    65: {  # 65-79
        "Single":             8,
        "In a relationship":  4,
        "Married":           58,
        "Civil partnership":  1,
        "Separated":          1.5,
        "Divorced":          12,
        "Widowed":           15.5,
    },
    80: {  # 80+
        "Single":             6,
        "In a relationship":  2,
        "Married":           40,
        "Civil partnership":  0.5,
        "Separated":          0.5,
        "Divorced":           8,
        "Widowed":           43,
    },
}


def _marital_weights_for_age(age: int) -> dict:
    band_key = 16
    for lo in sorted(_MARITAL_BY_AGE):
        if age >= lo:
            band_key = lo
    return _MARITAL_BY_AGE[band_key]


def _apply_marital_correlations(s: dict) -> dict:
    """Condition marital status on age, then reconcile household composition."""
    age = s.get("age")
    if not isinstance(age, int):
        return s

    # ── Age ↔ number of children ────────────────────────────────────────────
    # The `children` field is sampled from a flat distribution with no age
    # signal, which produces impossibilities like an 18-year-old with three
    # dependent children AND far too many young parents overall (the flat draw
    # gives ~half of everyone at least one child regardless of age). Two
    # corrections: (a) probabilistically ZERO OUT children for the young, to
    # match real age-specific parenthood incidence (ONS: only a few % of under-
    # 20s are parents; parenthood rises steeply through the 20s and 30s), and
    # (b) CAP the count to what is plausible by age. Older ages are left alone.
    kids = s.get("children")
    if isinstance(kids, int) and kids > 0:
        # (a) Incidence: probability of KEEPING any children at this age.
        #     Below the numbers, most young "parents" are reset to zero.
        if age < 18:
            keep_p = 0.0
        elif age < 20:
            keep_p = 0.05      # ~a few % of 18-19s are parents
        elif age < 23:
            keep_p = 0.18
        elif age < 26:
            keep_p = 0.40
        elif age < 30:
            keep_p = 0.70
        else:
            keep_p = 1.0       # from 30+ leave the sampled count as-is
        if random.random() > keep_p:
            s["children"] = kids = 0

    if isinstance(s.get("children"), int) and s["children"] > 0:
        # (b) Count cap for those who do have children.
        if age < 20:
            cap = 1
        elif age < 23:
            cap = 2
        elif age < 27:
            cap = 3
        else:
            cap = 5
        if s["children"] > cap:
            # Land at the cap, occasionally one below, so the count is plausible.
            if cap <= 1:
                s["children"] = cap
            else:
                s["children"] = random.choices([cap - 1, cap], weights=[1, 3], k=1)[0]
        kids = s["children"]

    # ── Age ↔ marital status ────────────────────────────────────────────────
    # Resample marital status from the age-appropriate table. This replaces the
    # flat-marginal draw entirely, because the flat draw carries no age signal
    # and is the source of the implausible young-widow / young-divorcee cases.
    weights = _marital_weights_for_age(age)
    opts = list(weights.keys())
    s["marital_status"] = random.choices(opts, weights=[weights[o] for o in opts], k=1)[0]

    # Hard guards for combinations that are legally/temporally impossible or
    # vanishingly rare, independent of the sampled table.
    ms = s["marital_status"]
    if age < 16:
        s["marital_status"] = ms = "Single"
    if age < 18 and ms in ("Married", "Civil partnership", "Divorced", "Widowed", "Separated"):
        # Marriage under 18 in England & Wales ended in Feb 2023; treat as single.
        s["marital_status"] = ms = "Single"
    if age < 23 and ms == "Widowed":
        s["marital_status"] = ms = random.choices(
            ["Single", "In a relationship", "Married"], weights=[70, 22, 8], k=1)[0]
    if age < 22 and ms == "Divorced":
        s["marital_status"] = ms = random.choices(
            ["Single", "In a relationship"], weights=[75, 25], k=1)[0]

    # ── Marital status ↔ household composition ──────────────────────────────
    # Reconcile so the household a person lives in is consistent with their
    # partnership status. "Couple" households require a partner; a lone parent
    # cannot be currently married-and-cohabiting, etc. Only correct the clear
    # contradictions; leave plausible combinations untouched.
    hh = s.get("household_composition")
    coupled = ms in ("Married", "Civil partnership", "In a relationship")
    has_kids = isinstance(s.get("children"), int) and s["children"] > 0

    if coupled:
        # A partnered person should not be recorded in a lone-parent household.
        if hh == "Lone parent with dependent children":
            s["household_composition"] = (
                "Couple with dependent children" if has_kids
                else "Couple, no dependent children")
        # Partnered + living as a one-person household is contradictory for the
        # married/CP case; soften to a couple household. (Cohabiting "In a
        # relationship" people may live apart, so only correct part of these.)
        elif hh == "One-person household":
            if ms in ("Married", "Civil partnership") or random.random() < 0.5:
                s["household_composition"] = (
                    "Couple with dependent children" if has_kids
                    else "Couple, no dependent children")
    else:
        # Not partnered → should not be in a "Couple" household.
        if hh in ("Couple, no dependent children", "Couple with dependent children"):
            if has_kids:
                s["household_composition"] = "Lone parent with dependent children"
            else:
                s["household_composition"] = random.choices(
                    ["One-person household", "Multi-person or other household"],
                    weights=[70, 30], k=1)[0]
        # Lone-parent household but no children recorded → give it children or
        # reclassify, so the label and the child count agree. For the young
        # (who mostly won't have dependent children), reclassify instead of
        # inventing them — consistent with the age→children incidence above.
        if (s.get("household_composition") == "Lone parent with dependent children"
                and not has_kids):
            if age < 23:
                s["household_composition"] = random.choices(
                    ["One-person household", "Multi-person or other household"],
                    weights=[45, 55], k=1)[0]
            else:
                kidmax = 2 if age < 27 else 3
                opts = list(range(1, kidmax + 1))
                wts = [55, 33, 12][:len(opts)]
                s["children"] = random.choices(opts, weights=wts, k=1)[0]

    # Couple-with-children household but zero children → add children so the
    # household label is honoured (applies regardless of partnership branch).
    # Reclassify for the young rather than inventing dependent children.
    if (s.get("household_composition") == "Couple with dependent children"
            and not (isinstance(s.get("children"), int) and s["children"] > 0)):
        if age < 23:
            s["household_composition"] = "Couple, no dependent children"
        else:
            kidmax = 2 if age < 27 else 3
            opts = list(range(1, kidmax + 1))
            wts = [45, 38, 17][:len(opts)]
            s["children"] = random.choices(opts, weights=wts, k=1)[0]

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  SOCIO-ECONOMIC CORRELATIONS
#  education ↔ occupation ↔ social grade (NS-SEC/ASG) ↔ income
#  ────────────────────────────────────────────────────────────────────────────
#  These four fields were each sampled from their own marginal, so nothing tied
#  them together — a doctorate could land in an elementary occupation on the
#  lowest income band. Real populations show a strong (though far from perfect)
#  gradient linking them. This pass builds that gradient in the causal order
#  education → occupation → social grade → income, nudging each downstream field
#  toward what its upstream fields imply. Nudges are probabilistic so the
#  natural spread (over- and under-employment relative to qualifications)
#  survives; they are not deterministic look-ups.
#
#  Anchors: ONS Census 2021 TS067 (qualifications) × TS063 (occupation) cross
#  patterns; ONS NS-SEC/ASG derivation (occupation is the primary input to
#  Approximated Social Grade); ONS Annual Survey of Hours & Earnings 2023 gross
#  pay by SOC major group and by qualification level.
# ══════════════════════════════════════════════════════════════════════════════

# Broad education tiers used to gate occupation/grade/income.
_EDU_HIGH = frozenset({
    "Bachelor's degree", "Master's degree",
    "Doctoral degree (PhD, MD, JD, etc.)",
})
_EDU_MID = frozenset({
    "Some college (no degree)", "Vocational / Technical degree",
    "Associate degree", "High school diploma / GED",
})
_EDU_LOW = frozenset({
    "No formal education", "Primary school", "Some high school",
})

# SOC major groups grouped by the social grade they predominantly map to.
_OCC_AB = frozenset({
    "Managers, directors and senior officials",
    "Professional occupations",
})
_OCC_C1 = frozenset({
    "Associate professional and technical",
    "Administrative and secretarial",
})
_OCC_C2 = frozenset({
    "Skilled trades occupations",
})
_OCC_DE = frozenset({
    "Caring, leisure and other service",
    "Sales and customer service",
    "Process, plant and machine operatives",
    "Elementary occupations",
})

# Income-band ladder (must match income_bracket keys / app.py INCOME_OPTIONS).
_INCOME_LADDER = [
    "Under £15,000",
    "£15,000 – £24,999",
    "£25,000 – £34,999",
    "£35,000 – £49,999",
    "£50,000 – £74,999",
    "£75,000 – £99,999",
    "£100,000 – £149,999",
    "£150,000 or more",
]
_INCOME_INDEX = {band: i for i, band in enumerate(_INCOME_LADDER)}


def _nudge_income_floor(s: dict, floor_idx: int, prob: float) -> None:
    """With probability `prob`, lift income to at least the floor band."""
    cur = _INCOME_INDEX.get(s.get("income_bracket"))
    if cur is not None and cur < floor_idx and random.random() < prob:
        # Land somewhere from the floor up to two bands above, tapering off.
        top = min(floor_idx + 2, len(_INCOME_LADDER) - 1)
        choices = list(range(floor_idx, top + 1))
        wts = [max(1, 6 - (i - floor_idx) * 2) for i in choices]
        s["income_bracket"] = _INCOME_LADDER[random.choices(choices, weights=wts, k=1)[0]]


def _nudge_income_ceiling(s: dict, ceil_idx: int, prob: float) -> None:
    """With probability `prob`, pull income down to at most the ceiling band."""
    cur = _INCOME_INDEX.get(s.get("income_bracket"))
    if cur is not None and cur > ceil_idx and random.random() < prob:
        bottom = max(ceil_idx - 2, 0)
        choices = list(range(bottom, ceil_idx + 1))
        wts = [max(1, 6 - (ceil_idx - i) * 2) for i in choices]
        s["income_bracket"] = _INCOME_LADDER[random.choices(choices, weights=wts, k=1)[0]]


def _apply_socioeconomic_correlations(s: dict) -> dict:
    """Link education → occupation → social grade → income coherently."""
    edu = s.get("education_level")
    ea = s.get("economic_activity", "")
    employed = ea in _EMPLOYED
    occ = s.get("occupation_soc")

    # ── Education ↔ occupation (employed only) ──────────────────────────────
    # Degree-level education makes higher-skill occupations much more likely;
    # low education makes professional/managerial roles less likely. We nudge
    # rather than hard-set so graduate under-employment and non-graduate
    # progression both remain represented.
    if employed and occ and occ != "N/A":
        if edu in _EDU_HIGH:
            # Graduates disproportionately in professional/managerial/associate.
            if occ in ("Elementary occupations",
                       "Process, plant and machine operatives") \
                    and random.random() < 0.65:
                occ = random.choices(
                    ["Professional occupations",
                     "Associate professional and technical",
                     "Administrative and secretarial",
                     "Caring, leisure and other service"],
                    weights=[40, 35, 15, 10], k=1)[0]
            elif occ in ("Sales and customer service",
                         "Caring, leisure and other service") \
                    and random.random() < 0.4:
                occ = random.choices(
                    ["Professional occupations",
                     "Associate professional and technical",
                     "Managers, directors and senior officials"],
                    weights=[45, 40, 15], k=1)[0]
        elif edu in _EDU_LOW:
            # Low qualifications rarely reach full professional / senior roles.
            if occ == "Professional occupations" and random.random() < 0.9:
                occ = random.choices(
                    ["Skilled trades occupations",
                     "Caring, leisure and other service",
                     "Sales and customer service",
                     "Process, plant and machine operatives",
                     "Elementary occupations"],
                    weights=[24, 22, 20, 16, 18], k=1)[0]
            elif occ == "Managers, directors and senior officials" \
                    and random.random() < 0.45:
                occ = random.choices(
                    ["Skilled trades occupations",
                     "Administrative and secretarial",
                     "Sales and customer service",
                     "Elementary occupations"],
                    weights=[30, 25, 25, 20], k=1)[0]
        s["occupation_soc"] = occ

    # ── Occupation ↔ social grade (ASG) ─────────────────────────────────────
    # ASG is derived primarily FROM occupation (with employment status), so make
    # the recorded social grade agree with the occupation the person now holds.
    # Non-employed keep a marginal-sampled grade (pensioners, students, etc.).
    if employed and occ and occ != "N/A":
        if occ in _OCC_AB:
            grade_opts, grade_wts = (
                ["AB - Higher/intermediate managerial, admin, professional",
                 "C1 - Supervisory, clerical, junior managerial"], [80, 20])
        elif occ in _OCC_C1:
            grade_opts, grade_wts = (
                ["C1 - Supervisory, clerical, junior managerial",
                 "AB - Higher/intermediate managerial, admin, professional",
                 "C2 - Skilled manual"], [68, 17, 15])
        elif occ in _OCC_C2:
            grade_opts, grade_wts = (
                ["C2 - Skilled manual",
                 "C1 - Supervisory, clerical, junior managerial",
                 "DE - Semi-skilled/unskilled, unemployed, lowest grade"],
                [64, 18, 18])
        else:  # _OCC_DE
            grade_opts, grade_wts = (
                ["DE - Semi-skilled/unskilled, unemployed, lowest grade",
                 "C2 - Skilled manual",
                 "C1 - Supervisory, clerical, junior managerial"], [62, 20, 18])
        # Only overwrite when the current grade is inconsistent with occupation,
        # so we don't erase legitimately sampled variation.
        cur_grade = s.get("social_grade", "") or ""
        # A grade two or more tiers away from the occupation is not plausible
        # (e.g. an AB-tier professional on grade DE); always reconcile those.
        _tier = {"AB": 0, "C1": 1, "C2": 2, "DE": 3}
        occ_tier = (0 if occ in _OCC_AB else 1 if occ in _OCC_C1
                    else 2 if occ in _OCC_C2 else 3)
        cur_tier = next((t for pre, t in _tier.items() if cur_grade.startswith(pre)), None)
        far_apart = cur_tier is not None and abs(cur_tier - occ_tier) >= 2
        if cur_grade not in grade_opts[:1]:
            if far_apart or random.random() < 0.75:
                s["social_grade"] = random.choices(grade_opts, weights=grade_wts, k=1)[0]
    elif ea in ("Unemployed - seeking work",
                "Economically inactive - long-term sick"):
        # ASG places the long-term unemployed/sick in the DE grade.
        if random.random() < 0.7:
            s["social_grade"] = "DE - Semi-skilled/unskilled, unemployed, lowest grade"

    # ── Education / occupation / grade ↔ income ─────────────────────────────
    # Household income band is nudged toward what the person's position implies.
    # These are floors/ceilings, not fixed values — the long tails remain.
    grade = s.get("social_grade", "")

    if not employed:
        # Retired, students, inactive: pull income downward (pensions/benefits/
        # grants). Grade matters: a DE-grade non-employed person (low lifetime
        # earnings → modest pension/savings) should not sit in the top income
        # bands, while an AB-grade retiree plausibly holds pension/investment
        # wealth income and keeps a higher ceiling.
        de = grade.startswith("DE")
        ab = grade.startswith("AB")
        if ea == "Full-time student":
            _nudge_income_ceiling(s, _INCOME_INDEX["£25,000 – £34,999"], 0.7)
        elif ea == "Retired":
            # Retirees live on pensions/investments, scaled to former standing.
            if de:
                _nudge_income_ceiling(s, _INCOME_INDEX["£25,000 – £34,999"], 0.8)
            elif ab:
                _nudge_income_ceiling(s, _INCOME_INDEX["£75,000 – £99,999"], 0.5)
            else:
                _nudge_income_ceiling(s, _INCOME_INDEX["£50,000 – £74,999"], 0.7)
        else:  # unemployed / long-term sick / inactive-other / home-family
            if de:
                _nudge_income_ceiling(s, _INCOME_INDEX["£25,000 – £34,999"], 0.8)
            elif ab:
                _nudge_income_ceiling(s, _INCOME_INDEX["£50,000 – £74,999"], 0.6)
            else:
                _nudge_income_ceiling(s, _INCOME_INDEX["£35,000 – £49,999"], 0.7)
    else:
        age = s.get("age") if isinstance(s.get("age"), int) else None

        if occ in _OCC_AB or grade.startswith("AB"):
            _nudge_income_floor(s, _INCOME_INDEX["£35,000 – £49,999"], 0.7)
        if edu in _EDU_HIGH:
            _nudge_income_floor(s, _INCOME_INDEX["£25,000 – £34,999"], 0.5)
        if occ in _OCC_DE or grade.startswith("DE"):
            _nudge_income_ceiling(s, _INCOME_INDEX["£35,000 – £49,999"], 0.6)
        if edu in _EDU_LOW and occ in _OCC_DE:
            _nudge_income_ceiling(s, _INCOME_INDEX["£25,000 – £34,999"], 0.55)
        elif edu in _EDU_LOW:
            # Low education without a high-skill occupation rarely reaches the
            # top income bands, even in a mid-tier job.
            _nudge_income_ceiling(s, _INCOME_INDEX["£50,000 – £74,999"], 0.6)

        # ── Mid-tier occupations (C1/C2) rarely earn top-band household income
        # on their own. Without an AB occupation or a degree pushing them up,
        # cap them below the £75k+ bands. This closes the gap that let e.g. a
        # part-time trainee associate-professional keep a £75-99k draw.
        if occ not in _OCC_AB and edu not in _EDU_HIGH \
                and not grade.startswith("AB"):
            _nudge_income_ceiling(s, _INCOME_INDEX["£50,000 – £74,999"], 0.75)

        # ── Part-time work strongly caps *individual* earnings; even in a
        # higher household this pulls the band down for most part-timers.
        if ea == "Employee - part-time":
            _nudge_income_ceiling(s, _INCOME_INDEX["£25,000 – £34,999"], 0.8)

        # ── Young workers (esp. trainees/juniors) rarely sit in the top bands;
        # seniority and earnings both take time. A part-time 18-year-old in an
        # elementary job realistically earns well under £15k, so the youngest
        # part-timers get a much tighter ceiling than the previous £35-49k.
        if age is not None and age < 22:
            if ea == "Employee - part-time" or occ in _OCC_DE:
                _nudge_income_ceiling(s, _INCOME_INDEX["£15,000 – £24,999"], 0.9)
            else:
                _nudge_income_ceiling(s, _INCOME_INDEX["£25,000 – £34,999"], 0.85)
        elif age is not None and age < 25:
            if ea == "Employee - part-time":
                _nudge_income_ceiling(s, _INCOME_INDEX["£25,000 – £34,999"], 0.8)
            else:
                _nudge_income_ceiling(s, _INCOME_INDEX["£35,000 – £49,999"], 0.7)

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTH ↔ DISABILITY ↔ AGE ↔ ECONOMIC ACTIVITY
#  ────────────────────────────────────────────────────────────────────────────
#  The age pass already worsens health/disability with age. This adds the two
#  remaining links in the cluster: (a) internal consistency between general
#  health and disability (they are strongly positively associated — a disabled
#  person limited "a lot" rarely reports "Very good" health), and (b) the link
#  to economic activity — poor health/disability raises the chance of being
#  economically inactive through the long-term-sick route, and conversely the
#  "long-term sick" state implies poor health.
#  Source anchors: ONS Census 2021 TS037×TS038 (health×disability),
#  TS066 economic inactivity by reason ("long-term sick or disabled").
# ══════════════════════════════════════════════════════════════════════════════

_BAD_HEALTH = frozenset({"Bad", "Very bad"})
_DISABLED_LOT = "Disabled - day-to-day activities limited a lot"
_DISABLED_LITTLE = "Disabled - day-to-day activities limited a little"


def _apply_health_activity_correlations(s: dict) -> dict:
    age = s.get("age")
    health = s.get("general_health")
    disab = s.get("disability")
    ea = s.get("economic_activity", "")

    # ── Health ↔ disability internal consistency ────────────────────────────
    # "Limited a lot" should not co-occur with very good/good health most of the
    # time; pull health down to fair/bad/very bad.
    if disab == _DISABLED_LOT and health == "Very good" and random.random() < 0.95:
        # "Activities limited a lot" is incompatible with self-rated "Very good"
        # health — pull it down firmly.
        s["general_health"] = health = random.choices(
            ["Fair", "Bad", "Very bad"], weights=[45, 40, 15], k=1)[0]
    elif disab == _DISABLED_LOT and health == "Good" and random.random() < 0.40:
        # "Good" is a milder tension; correct most but leave some (a well-managed
        # limiting condition can still self-rate as good).
        s["general_health"] = health = random.choices(
            ["Fair", "Bad", "Good"], weights=[50, 30, 20], k=1)[0]
    elif disab == _DISABLED_LITTLE and health == "Very good" \
            and random.random() < 0.55:
        s["general_health"] = health = random.choices(
            ["Good", "Fair"], weights=[62, 38], k=1)[0]
    # Conversely, very bad/bad health raises the chance of a disability flag.
    if health in _BAD_HEALTH and disab == "Not disabled" and random.random() < 0.25:
        s["disability"] = disab = random.choices(
            [_DISABLED_LOT, _DISABLED_LITTLE], weights=[55, 45], k=1)[0]

    # ── The "long-term sick" state implies poor health/disability ───────────
    if ea == "Economically inactive - long-term sick":
        if s.get("general_health") == "Very good" and random.random() < 0.80:
            s["general_health"] = random.choices(
                ["Fair", "Bad", "Very bad"], weights=[50, 35, 15], k=1)[0]
        elif s.get("general_health") == "Good" and random.random() < 0.40:
            s["general_health"] = random.choices(
                ["Fair", "Bad"], weights=[75, 25], k=1)[0]
        if s.get("disability") == "Not disabled" and random.random() < 0.65:
            s["disability"] = random.choices(
                [_DISABLED_LOT, _DISABLED_LITTLE], weights=[55, 45], k=1)[0]

    # ── Poor health/disability → higher chance of economic inactivity ───────
    # Only for working-age people currently in work; the age pass already
    # handles retirement for 66+. Move a fraction of the badly-unwell into the
    # long-term-sick / other-inactive states.
    if isinstance(age, int) and 25 <= age < 66 and s.get("economic_activity") in _EMPLOYED:
        badly = (s.get("general_health") in _BAD_HEALTH) or (s.get("disability") == _DISABLED_LOT)
        if badly and random.random() < 0.25:
            s["economic_activity"] = random.choices(
                ["Economically inactive - long-term sick",
                 "Employee - part-time",
                 "Economically inactive - other"],
                weights=[55, 30, 15], k=1)[0]
            if s["economic_activity"] not in _EMPLOYED:
                s["occupation_soc"] = "N/A"

    # ── Marginal compensation for "Very good" health ────────────────────────
    # The disability/age reconciliations above only move health DOWN (a disabled
    # or elderly person shouldn't self-rate "Very good"), which erodes the
    # overall "Very good" share below its census marginal (~48%). Restore the
    # marginal WITHOUT weakening any correlation by lifting a fraction of the
    # people who SHOULD plausibly have very good health — young/working-age,
    # not disabled, good baseline health — from "Good"/"Fair" back up. This
    # touches only the healthy-profile population, so every correlated case
    # (disabled, long-term sick, elderly) is left exactly as reconciled.
    if isinstance(age, int) and age < 65 \
            and s.get("disability") == "Not disabled" \
            and s.get("economic_activity") not in (
                "Economically inactive - long-term sick",):
        h = s.get("general_health")
        if h == "Good" and random.random() < 0.35:
            s["general_health"] = "Very good"
        elif h == "Fair" and age < 45 and random.random() < 0.40:
            s["general_health"] = "Good"
        elif h == "Fair" and random.random() < 0.20:
            s["general_health"] = "Good"
        elif h == "Bad" and age < 50 and random.random() < 0.55:
            s["general_health"] = "Fair"
        elif h == "Very bad" and age < 60 and random.random() < 0.40:
            s["general_health"] = "Bad"

    # ── WVS subjective health (Q47) ↔ census general health ─────────────────
    # These are two measures of the SAME thing on parallel 5-point scales, so
    # they must agree in direction. The census field is the anchor (it drives
    # the disability/activity reconciliations above); align the WVS item to it,
    # allowing only a one-step difference for realistic self-report noise.
    #   census:  Very good / Good / Fair / Bad / Very bad
    #   WVS:     Very good / Good / Fair / Poor / Very poor
    _gh = s.get("general_health")
    _rank = {"Very good": 4, "Good": 3, "Fair": 2, "Bad": 1, "Very bad": 0}
    _wvs_by_rank = {4: "Very good", 3: "Good", 2: "Fair", 1: "Poor", 0: "Very poor"}
    if _gh in _rank and s.get("wvs_subjective_health") is not None:
        target_rank = _rank[_gh]
        cur = s.get("wvs_subjective_health")
        cur_rank = {"Very good": 4, "Good": 3, "Fair": 2,
                    "Poor": 1, "Very poor": 0}.get(cur)
        if cur_rank is None or abs(cur_rank - target_rank) > 1:
            r = random.random()
            if r < 0.7:
                new_rank = target_rank
            elif r < 0.85:
                new_rank = min(4, target_rank + 1)
            else:
                new_rank = max(0, target_rank - 1)
            s["wvs_subjective_health"] = _wvs_by_rank[new_rank]

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  HOUSING TENURE ↔ AGE ↔ INCOME ↔ SOCIAL GRADE
#  ────────────────────────────────────────────────────────────────────────────
#  The age pass already applies the age gradient (no outright ownership under
#  35; mortgages convert to outright at 65+). This adds the income/grade links:
#    • Social rent concentrates in lower income + DE grade.
#    • Outright/mortgaged ownership concentrates in higher income + AB/C1.
#    • Private rent skews younger and mid/low income.
#  Applied as probabilistic nudges after income and grade are settled.
#  Source anchors: ONS/USoc W15 tenure by income quintile and by NS-SEC.
# ══════════════════════════════════════════════════════════════════════════════

_LOW_INCOME = frozenset({"Under £15,000", "£15,000 – £24,999", "£25,000 – £34,999"})
_HIGH_INCOME = frozenset({"£50,000 – £74,999", "£75,000 – £99,999",
                          "£100,000 – £149,999", "£150,000 or more"})


def _apply_tenure_correlations(s: dict) -> dict:
    age = s.get("age")
    if not isinstance(age, int):
        return s
    income = s.get("income_bracket")
    grade = s.get("social_grade", "")
    tenure = s.get("housing_tenure")
    de = grade.startswith("DE")
    ab = grade.startswith("AB")

    # Low income / DE grade → shift owner-occupiers toward renting (esp. social).
    if (income in _LOW_INCOME or de) and tenure in ("Owns outright", "Owns with mortgage"):
        # Older low-income outright owners are real (paid-off pensioners), so
        # protect them; target mainly the mortgaged and the younger. Low-income
        # losers of ownership go disproportionately to SOCIAL rent (not private),
        # and the push is gentler, so the private-rent marginal isn't inflated.
        if tenure == "Owns with mortgage" and random.random() < 0.35:
            s["housing_tenure"] = random.choices(
                ["Social / council rented", "Privately rented", "Owns with mortgage"],
                weights=[55, 20, 25], k=1)[0]
        elif tenure == "Owns outright" and age < 55 and random.random() < 0.20:
            s["housing_tenure"] = random.choices(
                ["Social / council rented", "Privately rented", "Owns outright"],
                weights=[55, 20, 25], k=1)[0]

    # High income / AB grade → shift social renters toward ownership; unlikely
    # to be in council housing.
    if (income in _HIGH_INCOME or ab) and tenure == "Social / council rented" \
            and random.random() < 0.7:
        if age >= 40:
            s["housing_tenure"] = random.choices(
                ["Owns with mortgage", "Owns outright", "Privately rented"],
                weights=[55, 30, 15], k=1)[0]
        else:
            s["housing_tenure"] = random.choices(
                ["Owns with mortgage", "Privately rented"],
                weights=[60, 40], k=1)[0]

    # Private rent skews younger: nudge some older private renters with means
    # into ownership, matching the life-course transition into buying. Applied a
    # bit more strongly to keep the private-rent marginal near its census level.
    if tenure == "Privately rented" and age >= 45 \
            and (income in _HIGH_INCOME or ab) and random.random() < 0.55:
        s["housing_tenure"] = random.choices(
            ["Owns with mortgage", "Owns outright", "Privately rented"],
            weights=[50, 30, 20], k=1)[0]

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  ETHNICITY ↔ RELIGION ↔ REGION ↔ URBAN/RURAL
#  ────────────────────────────────────────────────────────────────────────────
#  These four are sampled independently, so this pass installs the strong,
#  well-evidenced associations:
#    • Religion given ethnicity — Muslim concentrated among Pakistani/
#      Bangladeshi and much of "Arab"/"Other"; Hindu/Sikh among Indian; Black
#      groups predominantly Christian; White British split Christian/none.
#    • Urban/rural given ethnicity — minority groups heavily urban; White
#      British over-represented in rural/suburban England.
#    • Region — most minority concentration is already captured because region
#      is drawn from a population-weighted local-authority table (London and the
#      big conurbations carry the minority population). We add a light nudge so
#      the most concentrated groups (e.g. Bangladeshi, Pakistani, Black African)
#      lean urban and toward high-diversity regions without overriding the
#      census place draw.
#  Religion is conditioned FIRST on ethnicity (the strongest link), then
#  urban/rural on ethnicity. The structural denomination categories match the
#  Understanding Society oprlg1 scheme used in the `religion` field.
#  Source anchors: ONS Census 2021 TS021×TS030 (ethnicity×religion),
#  ethnic-group geography (ONS "Ethnic group, England and Wales: Census 2021").
# ══════════════════════════════════════════════════════════════════════════════

# Religion mix by ethnic group. Weights are relative; sampled with random.choices.
# Christian denominations are collapsed here into representative buckets that
# exist in the `religion` field's category list.
_CHR_ANGLICAN = "Christian: Church of England/Anglican"
_CHR_CATHOLIC = "Christian: Roman Catholic"
_CHR_NONE_SPEC = "Christian (no specific denomination)"
_CHR_OTHER = "Christian: Other Christian"
_NO_REL = "No religion"

_RELIGION_BY_ETHNICITY = {
    "Asian or Asian British: Pakistani": {"Muslim/Islam": 92, _NO_REL: 3,
        _CHR_NONE_SPEC: 1, "Prefer not to say": 4},
    "Asian or Asian British: Bangladeshi": {"Muslim/Islam": 90, _NO_REL: 3,
        _CHR_NONE_SPEC: 1, "Prefer not to say": 6},
    "Asian or Asian British: Indian": {"Hindu": 49, "Sikh": 22,
        "Muslim/Islam": 14, _CHR_NONE_SPEC: 6, _NO_REL: 6, "Prefer not to say": 3},
    "Asian or Asian British: Chinese": {_NO_REL: 57, _CHR_NONE_SPEC: 19,
        "Buddhist": 15, "Prefer not to say": 9},
    "Asian or Asian British: Other Asian": {"Muslim/Islam": 46, "Hindu": 14,
        _CHR_NONE_SPEC: 16, _NO_REL: 15, "Buddhist": 5, "Prefer not to say": 4},
    "Black, Black British: African": {_CHR_NONE_SPEC: 40, _CHR_OTHER: 20,
        "Muslim/Islam": 20, _CHR_CATHOLIC: 10, _NO_REL: 6, "Prefer not to say": 4},
    "Black, Black British: Caribbean": {_CHR_NONE_SPEC: 42, _CHR_OTHER: 18,
        _CHR_ANGLICAN: 8, _NO_REL: 25, "Prefer not to say": 7},
    "Black, Black British: Other Black": {_CHR_NONE_SPEC: 42, _CHR_OTHER: 16,
        "Muslim/Islam": 12, _NO_REL: 24, "Prefer not to say": 6},
    "Other ethnic group: Arab": {"Muslim/Islam": 78, _CHR_NONE_SPEC: 8,
        _NO_REL: 8, "Prefer not to say": 6},
    "Other ethnic group: Any other": {"Muslim/Islam": 32, _CHR_NONE_SPEC: 22,
        _NO_REL: 30, "Hindu": 4, "Buddhist": 4, "Prefer not to say": 8},
    "Mixed: White and Black Caribbean": {_NO_REL: 45, _CHR_NONE_SPEC: 33,
        _CHR_ANGLICAN: 8, "Muslim/Islam": 5, "Prefer not to say": 9},
    "Mixed: White and Black African": {_NO_REL: 38, _CHR_NONE_SPEC: 34,
        "Muslim/Islam": 15, "Prefer not to say": 13},
    "Mixed: White and Asian": {_NO_REL: 46, _CHR_NONE_SPEC: 24,
        "Muslim/Islam": 12, "Hindu": 6, "Sikh": 3, "Prefer not to say": 9},
    "Mixed: Other Mixed or Multiple": {_NO_REL: 47, _CHR_NONE_SPEC: 27,
        "Muslim/Islam": 10, "Prefer not to say": 16},
    "White: Irish": {_CHR_CATHOLIC: 55, _NO_REL: 28, _CHR_ANGLICAN: 8,
        _CHR_NONE_SPEC: 4, "Prefer not to say": 5},
    "White: Other White": {_CHR_CATHOLIC: 34, _NO_REL: 34, _CHR_NONE_SPEC: 14,
        _CHR_OTHER: 6, "Muslim/Islam": 6, "Prefer not to say": 6},
    "White: Gypsy or Irish Traveller": {_CHR_CATHOLIC: 45, _CHR_ANGLICAN: 20,
        _NO_REL: 25, "Prefer not to say": 10},
    "White: Roma": {_CHR_CATHOLIC: 40, _CHR_NONE_SPEC: 20, _NO_REL: 30,
        "Prefer not to say": 10},
    # White British: keep close to the England adult marginal (more "no
    # religion" than the all-ages census, Anglican-led Christianity).
    "White: English, Welsh, Scottish, Northern Irish or British": {
        # Calibrated to produce the target aggregate (BSA/Understanding Society):
        # ~46% Christian, ~38% No religion, ~6% Muslim, ~2% Hindu, ~2% other.
        # White British drives ~74% of agents so this table sets the overall split.
        _NO_REL: 44, _CHR_ANGLICAN: 24, _CHR_NONE_SPEC: 14, _CHR_CATHOLIC: 8,
        "Christian: Methodist": 2, "Christian: Baptist": 1,
        _CHR_OTHER: 2, "Prefer not to say": 5},
}

# Urban/rural skew by ethnicity: multipliers on the base Urban/Suburban/Rural
# weights (56/33/11). Minority groups are strongly urban; White British is the
# only group meaningfully present in rural England.
_URBAN_SKEW_MINORITY = {"Urban": 82, "Suburban": 17, "Rural": 1}
_URBAN_SKEW_WHITE_BRITISH = {"Urban": 48, "Suburban": 37, "Rural": 15}

_MINORITY_ETHNICITIES = frozenset(k for k in _RELIGION_BY_ETHNICITY
                                  if not k.startswith("White: English"))


def _apply_ethnicity_correlations(s: dict) -> dict:
    eth = s.get("ethnicity")
    if not eth:
        return s

    # ── Religion | ethnicity ────────────────────────────────────────────────
    mix = _RELIGION_BY_ETHNICITY.get(eth)
    if mix:
        opts = list(mix.keys())
        s["religion"] = random.choices(opts, weights=[mix[o] for o in opts], k=1)[0]

    # ── Urban/rural | ethnicity ─────────────────────────────────────────────
    if eth.startswith("White: English"):
        skew = _URBAN_SKEW_WHITE_BRITISH
    elif eth in _MINORITY_ETHNICITIES:
        skew = _URBAN_SKEW_MINORITY
    else:
        skew = None
    if skew:
        # Nudge rather than hard-set, so the census place draw's signal survives.
        if random.random() < 0.7:
            s["urban_rural"] = random.choices(
                list(skew.keys()), weights=list(skew.values()), k=1)[0]

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  ATTITUDE CORRELATIONS
#  education ↔ libertarian-authoritarian (+ age);  economic left-right ↔
#  social grade / income ↔ welfarism (deliberately weak).
#  ────────────────────────────────────────────────────────────────────────────
#  The BSA scales are continuous (1.0–5.0) and sampled from population means.
#  Education is the single strongest predictor of the lib-auth axis in England
#  (graduates markedly more libertarian / socially liberal = LOWER scores),
#  reinforced by age (older = more authoritarian = higher). We shift the
#  sampled score by an education- and age-derived offset, then re-clamp.
#
#  For the economic cluster we implement only a WEAK link, matching the brief:
#  in England the economic left-right axis correlates only modestly with income/
#  grade, and welfarism cuts across it. So the nudges here are small and applied
#  with low probability — enough to be detectable in aggregate, not enough to
#  make income determine ideology.
# ══════════════════════════════════════════════════════════════════════════════

def _clamp(v: float, lo: float = 1.0, hi: float = 5.0) -> float:
    return round(min(hi, max(lo, v)), 2)


def _apply_attitude_correlations(s: dict) -> dict:
    age = s.get("age")
    edu = s.get("education_level")

    # ── Political leaning (categorical) ↔ left-right scale ──────────────────
    # The categorical `political_leaning` and the continuous `scale_left_right`
    # (1=left … 5=right) are sampled independently, so a self-labelled "Right"
    # agent can sit at a centrist/left scale value. Pull the scale toward the
    # region implied by the stated leaning. This is the DOMINANT influence on
    # the scale (a person's own left/right label predicts their scale position
    # far better than their income does), so it runs before the weak
    # grade/income tilt below and largely sets the value.
    lr = s.get("scale_left_right")
    leaning = s.get("political_leaning")
    # Target scale bands (1–5) for each leaning label.
    _LEANING_TARGET = {
        "Far left":          (1.0, 1.5),
        "Left":              (1.3, 2.0),
        "Center-left":       (1.7, 2.4),
        "Center / Moderate": (2.0, 2.8),
        "Center-right":      (2.6, 3.3),
        "Right":             (3.1, 3.9),
        "Far right":         (3.7, 5.0),
        # Libertarian / Apolitical have no clean economic-axis position; leave.
    }
    if isinstance(lr, (int, float)) and leaning in _LEANING_TARGET:
        lo, hi = _LEANING_TARGET[leaning]
        # If already inside the plausible band, keep it; otherwise pull into the
        # band. The bigger the mismatch, the harder the pull (a "Far right" at
        # 1.0 is a flat contradiction and must move most of the way), leaving a
        # little spread for genuine cross-pressured individuals.
        if not (lo <= lr <= hi):
            target = random.uniform(lo, hi)
            mid = (lo + hi) / 2
            gap = abs(lr - mid)
            # weight toward target grows with the size of the gap
            w = 0.65 if gap < 1.5 else 0.80
            if random.random() < 0.90:
                s["scale_left_right"] = _clamp(round(w * target + (1 - w) * lr, 2))
        lr = s.get("scale_left_right")

    # ── Economic left-right ↔ grade/income (WEAK) ───────────────────────────
    grade = s.get("social_grade", "")
    income = s.get("income_bracket")
    if isinstance(lr, (int, float)) and random.random() < 0.30:
        offset = 0.0
        if grade.startswith("AB") or income in _HIGH_INCOME:
            offset += random.uniform(0.05, 0.2)   # slightly more right/free-market
        elif grade.startswith("DE") or income in _LOW_INCOME:
            offset -= random.uniform(0.05, 0.15)  # slightly more left
        if offset:
            s["scale_left_right"] = _clamp(lr + offset)

    # ── Welfarism cuts across left-right — only a faint income tilt ─────────
    # Higher earners a touch more welfare-sceptical, but applied weakly and
    # independently of left-right so the two axes don't collapse together.
    welf = s.get("scale_welfarism")
    if isinstance(welf, (int, float)) and random.random() < 0.35:
        if income in _HIGH_INCOME:
            s["scale_welfarism"] = _clamp(welf + random.uniform(0.1, 0.3))
        elif income in _LOW_INCOME:
            s["scale_welfarism"] = _clamp(welf - random.uniform(0.1, 0.3))

    # ── Education + age → lib-auth (social libertarian↔authoritarian) ────────
    # This is one of England's strongest attitude correlations: graduates and
    # younger people score more libertarian (lower lib-auth). BSA mean 3.35.
    la = s.get("scale_lib_auth")
    if isinstance(la, (int, float)):
        offset = 0.0
        if edu in _EDU_HIGH:
            offset -= random.uniform(0.2, 0.6)   # graduates more libertarian
        elif edu in _EDU_LOW:
            offset += random.uniform(0.1, 0.4)   # low-edu more authoritarian
        if isinstance(age, int):
            if age < 35:
                offset -= random.uniform(0.1, 0.3)  # younger more libertarian
            elif age >= 65:
                offset += random.uniform(0.1, 0.25) # older more authoritarian
        if offset and random.random() < 0.75:
            s["scale_lib_auth"] = _clamp(la + offset)

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  NAME GENERATION  (randomly drawn in code — NOT invented by the LLM)
#  ────────────────────────────────────────────────────────────────────────────
#  Each persona's name is sampled here from curated forename/surname pools
#  matched to the agent's ONS ethnic group, gender, and (for European-heritage
#  names) birth cohort. Drawing names programmatically — rather than asking the
#  LLM to invent one — removes the model's tendency to reuse a handful of common
#  names, so a large batch shows genuine variety and little overlap. The chosen
#  name is passed to the LLM as a FIXED value it must use verbatim.
# ══════════════════════════════════════════════════════════════════════════════

# ── British given names by cohort tier ──────────────────────────────────────
_BM_CORE = ["James","John","David","Michael","Robert","Paul","Andrew","Mark","Peter","Thomas",
    "William","Richard","Stephen","Christopher","Daniel","Matthew","Simon","Anthony","Ian","Alan",
    "Kevin","Gary","Nigel","Graham","Philip","Colin","Brian","Keith","Roger","Neil"]
_BM_ELDER = ["George","Arthur","Frederick","Albert","Edward","Harold","Ronald","Kenneth","Derek",
    "Geoffrey","Raymond","Leslie","Norman","Stanley","Cyril","Reginald","Bernard","Douglas","Maurice",
    "Cecil","Walter","Roy","Terence","Trevor","Malcolm","Barry","Clive","Dennis","Victor","Gordon"]
_BM_MID = ["Craig","Wayne","Darren","Lee","Shaun","Dean","Nathan","Adrian","Jason","Carl","Martin",
    "Stuart","Russell","Damian","Gavin","Marcus","Ashley","Justin","Julian","Dominic","Toby","Roland",
    "Barnaby","Rupert","Gareth","Wesley","Spencer","Rory","Miles","Guy"]
_BM_YOUNG = ["Oliver","Harry","Jack","Charlie","George","Noah","Leo","Alfie","Freddie","Archie",
    "Oscar","Theo","Finley","Riley","Kai","Reuben","Jude","Louie","Max","Ethan","Dylan","Callum",
    "Kayden","Harrison","Elliot","Rufus","Seb","Corey","Bailey","Jayden"]

_BF_CORE = ["Sarah","Claire","Emma","Rebecca","Laura","Nicola","Rachel","Joanne","Helen","Louise",
    "Michelle","Karen","Julie","Susan","Katherine","Amanda","Elizabeth","Caroline","Victoria","Jane",
    "Andrea","Lisa","Deborah","Alison","Fiona","Samantha","Gemma","Hayley","Melanie","Tracy"]
_BF_ELDER = ["Margaret","Patricia","Barbara","Jean","Dorothy","Joan","Sheila","Brenda","Audrey",
    "Marjorie","Doreen","Betty","Iris","Vera","Edna","Mavis","Gladys","Pauline","Sylvia","Sandra",
    "Maureen","Beryl","Hazel","Gwendoline","Muriel","Norma","Rita","Eileen","Josephine","Valerie"]
_BF_MID = ["Donna","Sharon","Dawn","Kerry","Mandy","Tina","Wendy","Sonia","Denise","Angela",
    "Kirsty","Leanne","Stacey","Charlotte","Sophie","Natalie","Danielle","Kelly","Zoe","Bethan",
    "Verity","Imogen","Tamsin","Rowena","Bryony","Felicity","Miranda","Saskia","Camilla","Portia"]
_BF_YOUNG = ["Olivia","Amelia","Isla","Ava","Mia","Grace","Freya","Poppy","Lily","Ella","Evie",
    "Sophie","Ruby","Isabella","Daisy","Florence","Willow","Maya","Millie","Elsie","Rosie","Phoebe",
    "Maisie","Scarlett","Erin","Bella","Darcy","Lola","Tilly","Nieve"]

_BRIT_SURNAMES = ["Smith","Jones","Taylor","Brown","Williams","Wilson","Johnson","Davies","Robinson",
    "Wright","Thompson","Evans","Walker","White","Roberts","Green","Hall","Wood","Jackson","Clarke",
    "Watson","Harris","Turner","Martin","Cooper","Hill","Ward","Morris","Moore","Clark","Lee","King",
    "Baker","Harrison","Morgan","Allen","James","Scott","Phillips","Watts","Mitchell","Bell","Cook",
    "Carter","Richardson","Bailey","Collins","Bennett","Marshall","Gray","Fisher","Webb","Chapman",
    "Palmer","Holmes","Kelly","Shaw","Barnes","Knight","Lewis","Hughes","Edwards","Hunt","Stevens",
    "Murray","Rogers","Gibson","Ellis","Fletcher","Owen","Reynolds","Reid","Hart","Newman","Barker",
    "Nixon","Fox","Dixon","Graham","Freeman","Wells","Webster","Simpson","Kaur","Pearce","Berry",
    "Pearson","Lawrence","Cole","Grant","Warren","Dawson","Slater","Byrne","Ford","Marsh","Kent",
    "Lloyd","Ball","Sharp","Barrett","Wallace","Foster","Booth","Chambers","Nicholson","Gregory",
    "Lowe","Gilbert","Riley","Griffiths","Bradley","Buckley","Hammond","Wilkinson","Middleton","Perry",
    "Sutton","Osborne","Blake","Reeves","Doyle","Pratt","Rose","Vincent","Whittaker","Bird","Gordon",
    "Hudson","Poole","Norton","Stone","Curtis","Nash","Bond","Rowe","Frost","Pugh","Nelson","Bryant",
    "Bartlett","Weaver","Farrell","Snow","Mills","Field","Case","Sanders","Yates","Coleman","Todd",
    "Craig","Burns","Higgins","Elliott","Brady","Cross","Fowler","Sharpe","Gill","Wade","Dean","Page"]

# ── Irish ───────────────────────────────────────────────────────────────────
_IR_M = ["Liam","Sean","Conor","Cian","Oisin","Cormac","Declan","Padraig","Fergal","Ronan","Eoin",
    "Niall","Cillian","Fionn","Aidan","Brendan","Colm","Diarmuid","Ruairi","Tadhg","Seamus","Donal"]
_IR_F = ["Aoife","Saoirse","Niamh","Ciara","Sinead","Orla","Roisin","Aisling","Grainne","Caoimhe",
    "Sorcha","Maeve","Deirdre","Fionnuala","Siobhan","Brid","Aine","Clodagh","Sile","Eabha","Dervla"]
_IR_S = ["Murphy","Kelly","O'Sullivan","Walsh","O'Brien","Byrne","Ryan","O'Connor","O'Neill","Reilly",
    "Doyle","McCarthy","Gallagher","Doherty","Kennedy","Lynch","Murray","Quinn","Moore","McLoughlin",
    "O'Carroll","Connolly","Daly","O'Donnell","Duffy","Mahony","Brennan","Fitzgerald","Maguire","Nolan"]

# ── Eastern / other European ────────────────────────────────────────────────
_EU_M = ["Piotr","Tomasz","Krzysztof","Andrzej","Marcin","Jakub","Mateusz","Pawel","Lukasz","Grzegorz",
    "Andrei","Ionut","Gabriel","Stefan","Mihai","Nikolai","Dimitri","Milan","Luka","Marek","Vasile","Radu"]
_EU_F = ["Anna","Katarzyna","Agnieszka","Magdalena","Malgorzata","Ewa","Zofia","Aleksandra","Natalia",
    "Ioana","Elena","Maria","Andreea","Gabriela","Ana","Milena","Iryna","Oksana","Kristina","Lucia","Petra","Vera"]
_EU_S = ["Nowak","Kowalski","Wisniewski","Wojcik","Kowalczyk","Kaminski","Lewandowski","Zielinski",
    "Szymanski","Dabrowski","Popescu","Ionescu","Popa","Radu","Dumitru","Novak","Horvat","Kovac",
    "Petrov","Ivanov","Melnyk","Kovalenko","Toma","Marin","Stan","Barbu"]

# ── Indian (broad: Hindu / Sikh) ────────────────────────────────────────────
_IN_M = ["Arjun","Rohan","Aarav","Vikram","Raj","Sanjay","Amit","Deepak","Ravi","Anil","Vijay","Suresh",
    "Rahul","Karan","Nikhil","Ashwin","Harpreet","Gurpreet","Jaspreet","Manpreet","Amrit","Baljinder",
    "Dev","Kunal","Aditya","Sachin","Prakash","Naveen","Rishi","Tarun"]
_IN_F = ["Priya","Anita","Sunita","Kavita","Meena","Neha","Pooja","Divya","Anjali","Deepika","Aarti",
    "Simran","Harleen","Manjit","Jasmine","Rani","Lakshmi","Shreya","Nisha","Radha","Geeta","Sita",
    "Preeti","Vandana","Aditi","Kiran","Sonia","Reena","Ishita","Payal"]
_IN_S = ["Patel","Sharma","Singh","Kumar","Shah","Gupta","Mehta","Desai","Chauhan","Malhotra","Kapoor",
    "Reddy","Nair","Iyer","Rao","Joshi","Verma","Chowdhury","Bose","Das","Gill","Dhillon","Sandhu",
    "Grewal","Bhatt","Trivedi","Pandya","Menon","Pillai","Chopra"]

# ── South Asian Muslim (Pakistani / Bangladeshi) ────────────────────────────
_MU_M = ["Muhammad","Ahmed","Ali","Hassan","Hussain","Bilal","Usman","Imran","Kamran","Tariq","Asif",
    "Zeeshan","Faisal","Adnan","Salman","Rizwan","Junaid","Naveed","Shahid","Waqar","Abdul","Yasir",
    "Omar","Zain","Ibrahim","Rashid","Saeed","Kashif","Nadeem","Fahad"]
_MU_F = ["Aisha","Fatima","Zainab","Mariam","Sana","Ayesha","Nadia","Saima","Farah","Hina","Sadia",
    "Rabia","Bushra","Amina","Sumaya","Yasmin","Naila","Rukhsana","Shabnam","Nusrat","Humera","Mehreen",
    "Rukaiya","Samira","Iqra","Zara","Laila","Noor","Sabeen","Hafsa"]
_MU_S = ["Khan","Ali","Ahmed","Hussain","Malik","Shaikh","Iqbal","Mahmood","Rahman","Begum","Miah",
    "Islam","Chowdhury","Uddin","Akhtar","Aslam","Butt","Qureshi","Siddiqui","Bhatti","Ghani","Nawaz",
    "Zaman","Rashid","Sarwar","Anwar","Younis","Hafeez","Saleh","Farooq"]

# ── Chinese ─────────────────────────────────────────────────────────────────
_CN_M = ["Wei","Jun","Hao","Ming","Lei","Feng","Bo","Chen","Yang","Kai","Jian","Tao","Peng","Long",
    "Hui","Bin","Xin","Cheng","Gang","Zhi"]
_CN_F = ["Li","Mei","Ying","Xiu","Fang","Yan","Hong","Juan","Min","Lan","Na","Ling","Jing","Hua",
    "Qing","Yun","Xia","Ping","Zhen","Rui"]
_CN_S = ["Wang","Li","Zhang","Liu","Chen","Yang","Huang","Zhao","Wu","Zhou","Xu","Sun","Ma","Zhu",
    "Hu","Guo","Lin","He","Gao","Luo","Cheng","Tang","Deng","Feng","Ye","Tan"]

# ── African (West African + Somali) ─────────────────────────────────────────
_AF_M = ["Chidi","Emeka","Obinna","Ade","Tunde","Femi","Kwame","Kofi","Kwabena","Yaw","Abdi","Hassan",
    "Mohamed","Samuel","Emmanuel","Daniel","Joseph","Blessing","Chukwu","Ikenna","Oluwaseun","Babatunde",
    "Kojo","Nana","Sefu","Abdirahman","Ismail","Ayinde","Chinedu","Uche"]
_AF_F = ["Ada","Chiamaka","Ngozi","Amara","Adaeze","Ifeoma","Folake","Bisi","Yaa","Abena","Akosua",
    "Ama","Amina","Fatima","Halima","Blessing","Grace","Precious","Chidinma","Zainab","Nadia","Aaliyah",
    "Sade","Temi","Oluwakemi","Nneka","Chinwe","Efua","Ayesha","Halimo"]
_AF_S = ["Okafor","Okoye","Adebayo","Afolabi","Balogun","Oluwaseun","Mensah","Owusu","Boateng","Asante",
    "Osei","Farah","Abdi","Hassan","Ali","Mohamed","Eze","Nwosu","Okonkwo","Adeyemi","Ogunleye","Bello",
    "Ibrahim","Diallo","Njoku","Chukwu","Danso","Appiah","Yeboah","Obi"]

# ── Arab ────────────────────────────────────────────────────────────────────
_AR_M = ["Ahmad","Mohammed","Mahmoud","Omar","Khaled","Youssef","Karim","Sami","Tariq","Bassam","Hisham",
    "Nabil","Ziad","Fadi","Rami","Walid","Marwan","Ayman","Samir","Hassan","Amir","Jamal","Fares","Wael"]
_AR_F = ["Layla","Fatima","Noor","Huda","Rania","Dalia","Maha","Nour","Yara","Salma","Amira","Lina",
    "Hala","Reem","Dina","Rasha","Nada","Mona","Ghada","Sawsan","Farida","Aya","Zahra","Samar"]
_AR_S = ["Al-Sayed","Haddad","Khalil","Nasser","Aziz","Mansour","Saleh","Hariri","Najjar","Barakat",
    "Fakhoury","Khoury","Antar","Sabbagh","Younes","Salem","Darwish","Rahal","Halabi","Masri","Awad",
    "Suleiman","Kassab","Ghanem"]

_TIERS = ("elder","boomer","mid","young")

def _tier(born):
    if born is None: return "boomer"
    if born <= 1950: return "elder"
    if born <= 1975: return "boomer"
    if born <= 1997: return "mid"
    return "young"

_BRIT = {
 ("m","elder"): _BM_CORE+_BM_ELDER, ("m","boomer"): _BM_CORE+_BM_ELDER+_BM_MID,
 ("m","mid"): _BM_CORE+_BM_MID, ("m","young"): _BM_YOUNG+_BM_CORE[:8],
 ("f","elder"): _BF_CORE+_BF_ELDER, ("f","boomer"): _BF_CORE+_BF_ELDER+_BF_MID,
 ("f","mid"): _BF_CORE+_BF_MID, ("f","young"): _BF_YOUNG+_BF_CORE[:8],
}
_EURO = {"m":_EU_M,"f":_EU_F,"elderm":_EU_M}

def _g(gender):
    if gender == "Man": return "m"
    if gender == "Woman": return "f"
    return random.choice(("m","f"))

def _pick(fores, sur):
    return f"{random.choice(fores)} {random.choice(sur)}"

# ── Uniqueness registry ─────────────────────────────────────────────────────
# Guarantees each agent gets a distinct full name within a run. Thread-safe so
# it holds under concurrent generation. Call reset_used_names() at the start of
# a new batch if you want names to be unique per-batch rather than per-session.
_used_names: set = set()
_name_lock = threading.Lock()


def reset_used_names() -> None:
    """Clear the used-name registry (call at the start of a fresh batch)."""
    with _name_lock:
        _used_names.clear()


def pick_name(ethnicity: str, gender: str, born=None, unique: bool = True) -> str:
    """
    Draw a name from the ethnicity/gender/cohort pools. When unique=True
    (default) the returned full name is guaranteed not to collide with any
    name already handed out (until reset_used_names() is called). If a small
    pool is exhausted, a middle initial is added to expand the space rather
    than ever returning a duplicate.
    """
    if not unique:
        return _draw_name(ethnicity, gender, born)
    with _name_lock:
        # 1) plain random draws
        for _ in range(80):
            cand = _draw_name(ethnicity, gender, born)
            if cand not in _used_names:
                _used_names.add(cand)
                return cand
        # 2) pool crowded — insert a middle initial (26x more room)
        for _ in range(200):
            base = _draw_name(ethnicity, gender, born)
            first, _, last = base.partition(" ")
            cand = f"{first} {random.choice('ABCDEFGHJKLMNPRSTW')}. {last}"
            if cand not in _used_names:
                _used_names.add(cand)
                return cand
        # 3) absolute last resort — guarantee distinctness with a suffix
        base = _draw_name(ethnicity, gender, born)
        n = 2
        cand = base
        while cand in _used_names:
            cand = f"{base} {'I' * n}"  # e.g. "... III"
            n += 1
        _used_names.add(cand)
        return cand


def _draw_name(ethnicity: str, gender: str, born=None) -> str:
    e = ethnicity or ""
    g = _g(gender)
    tier = _tier(born)
    def brit(): return _pick(_BRIT[(g,tier)], _BRIT_SURNAMES)
    def irish(): return _pick(_IR_M if g=="m" else _IR_F, _IR_S)
    def euro(): return _pick(_EU_M if g=="m" else _EU_F, _EU_S)
    def indian(): return _pick(_IN_M if g=="m" else _IN_F, _IN_S)
    def muslim(): return _pick(_MU_M if g=="m" else _MU_F, _MU_S)
    def chinese(): return _pick(_CN_M if g=="m" else _CN_F, _CN_S)
    def african(): return _pick(_AF_M if g=="m" else _AF_F, _AF_S)
    def arab(): return _pick(_AR_M if g=="m" else _AR_F, _AR_S)
    def caribbean(): return _pick(_BRIT[(g,tier)], _BRIT_SURNAMES)  # English-derived

    if e.startswith("White: Irish"): return irish()
    if e.startswith("White: Roma") or "Other White" in e: return euro()
    if e.startswith("White"): return brit()
    if "Indian" in e: return indian()
    if "Pakistani" in e or "Bangladeshi" in e: return muslim()
    if "Chinese" in e: return chinese()
    if "Other Asian" in e: return random.choice([indian,muslim,chinese])()
    if "Caribbean" in e and "Mixed" not in e: return caribbean()
    if "African" in e and "Mixed" not in e: return african()
    if "Other Black" in e: return random.choice([african,caribbean])()
    if "Arab" in e: return arab()
    # Mixed groups: forename + surname blended across heritages
    if "White and Black Caribbean" in e:
        return _pick(_BRIT[(g,tier)], _BRIT_SURNAMES)
    if "White and Black African" in e:
        fores = _BRIT[(g,tier)] if random.random()<0.6 else (_AF_M if g=="m" else _AF_F)
        sur = _AF_S if random.random()<0.6 else _BRIT_SURNAMES
        return _pick(fores, sur)
    if "White and Asian" in e:
        fores = _BRIT[(g,tier)] if random.random()<0.5 else (_IN_M if g=="m" else _IN_F)
        sur = _IN_S if random.random()<0.5 else _BRIT_SURNAMES
        return _pick(fores, sur)
    if "Mixed" in e:
        return random.choice([brit,indian,african,arab,euro])()
    # Other / Any other
    return random.choice([brit,indian,muslim,african,arab,chinese])()

# ══════════════════════════════════════════════════════════════════════════════
#  WVS VALUE CORRELATIONS
#  The WVS marginals are sampled independently. Real respondents show strong
#  covariance between certain value items; this pass nudges the most robust
#  links so agents read as coherent people rather than random attitude bundles.
#  Nudges are probabilistic and gentle — they shift, not hard-set, values.
# ══════════════════════════════════════════════════════════════════════════════

def _apply_wvs_correlations(s: dict) -> dict:
    # ── Structural religion (identity) → religiosity (values) ────────────────
    # The `religion` field says WHICH religion; the WVS items say HOW religious.
    # These are deliberately distinct — nominal/cultural believers are real — so
    # this is a gentle nudge, NOT a hard coupling. But two things are fixed:
    #   (1) a stated active/affiliated faith modestly raises the religiosity
    #       items away from full atheism, and
    #   (2) flat contradictions (e.g. self-ID "atheist" while holding a religion
    #       AND saying God matters) are reconciled.
    # Someone can still be a Catholic who ticks "not a religious person" and
    # doesn't attend — that's a common, coherent pattern — but a Catholic who is
    # simultaneously an atheist non-believer who thinks God is unimportant is
    # not, and gets pulled toward at least nominal belief.
    religion = s.get("religion", "")
    has_faith = bool(religion) and religion not in (
        "No religion", "Prefer not to say", "", "N/A", None)
    # Faiths where non-belief is especially incoherent (minority faiths in
    # England are overwhelmingly practising); Christian denominations carry a
    # large nominal/cultural contingent, so they get a lighter touch.
    strong_faith = has_faith and not religion.startswith("Christian") \
        and religion not in ("Other",)

    if has_faith:
        # Don't let an affiliated person self-describe as an atheist very often.
        if s.get("wvs_religious_self_id") == "An atheist":
            p = 0.9 if strong_faith else 0.55
            if random.random() < p:
                s["wvs_religious_self_id"] = random.choices(
                    ["A religious person", "Not a religious person"],
                    weights=[60, 40] if strong_faith else [35, 65], k=1)[0]
        # Anyone STILL self-identifying as an atheist (affiliation notwithstanding)
        # should not rate God important or believe — reconcile both, so a nominal
        # Anglican who calls themselves an atheist is a coherent non-believer
        # rather than a devout atheist.
        if s.get("wvs_religious_self_id") == "An atheist":
            gcur = s.get("wvs_importance_of_god")
            if isinstance(gcur, (int, float)) and gcur > 3:
                s["wvs_importance_of_god"] = round(random.uniform(1.0, 3.0), 2)
            if s.get("wvs_believe_in_god") == "Yes" and random.random() < 0.9:
                s["wvs_believe_in_god"] = "No"
        # Nudge importance-of-God upward for the affiliated (more so for strong
        # faiths), without forcing devotion — a floor, applied probabilistically.
        # Kept light for Christian denominations, which carry a large nominal /
        # cultural-believer contingent in England (affiliation ≠ active belief),
        # so the overall believe-in-God marginal isn't over-inflated.
        god0 = s.get("wvs_importance_of_god")
        if isinstance(god0, (int, float)):
            if strong_faith and god0 < 6 and random.random() < 0.8:
                s["wvs_importance_of_god"] = round(random.uniform(6.0, 9.5), 2)
            elif not strong_faith and god0 < 2 and random.random() < 0.25:
                s["wvs_importance_of_god"] = round(random.uniform(2.5, 5.5), 2)
        # Even an affiliated person who explicitly self-IDs as "not a religious
        # person" shouldn't rate God at the very top of the scale — that's the
        # nominal/cultural believer, so cap the extreme. (They can still hold
        # moderate belief; we only pull down the 8-10 devotion range.)
        gcur = s.get("wvs_importance_of_god")
        if s.get("wvs_religious_self_id") == "Not a religious person" \
                and isinstance(gcur, (int, float)) and gcur >= 8 \
                and random.random() < 0.9:
            s["wvs_importance_of_god"] = round(random.uniform(3.0, 6.5), 2)
        # An affiliated person who is a MEMBER of a religious organisation
        # should not also be a hard non-believer — active/inactive membership
        # implies at least nominal belief regardless of denomination.
        if s.get("wvs_member_religious") in ("Active member", "Inactive member") \
                and s.get("wvs_believe_in_god") == "No" and random.random() < 0.9:
            s["wvs_believe_in_god"] = "Yes"
    else:
        # No stated religion (or undisclosed): active membership of a religious
        # organisation is mostly incoherent. Allow a small cultural remainder
        # (community choirs, cultural attendance) but drop most to "Don't belong".
        if s.get("wvs_member_religious") in ("Active member", "Inactive member") \
                and random.random() < 0.85:
            s["wvs_member_religious"] = "Don't belong"

        # No religion but HIGH religiosity is the inverse contradiction (a "not
        # religious"/atheist person who rates God's importance ~9/10 and firmly
        # believes). Pull the religiosity items DOWN — but not to zero: many
        # unaffiliated people are agnostic, spiritual, or believe in a higher
        # power, which is real and stays. We cap the *extreme* devotion, scaled
        # by self-ID.
        #
        # Order matters: reconcile the self-ID FIRST (a no-religion person who
        # ticked "a religious person" is itself inconsistent → mostly relabel to
        # "not a religious person"), THEN run the god/belief reductions, so the
        # newly-relabelled people are also caught. Doing it the other way round
        # leaves relabelled cases sitting at god ~9 (the Robert bug).
        if s.get("wvs_religious_self_id") == "A religious person" and random.random() < 0.75:
            s["wvs_religious_self_id"] = "Not a religious person"

        self_id = s.get("wvs_religious_self_id")
        godv = s.get("wvs_importance_of_god")
        # A self-described atheist who believes in God is a direct contradiction,
        # independent of the God-importance score — reconcile belief first.
        if self_id == "An atheist" and s.get("wvs_believe_in_god") == "Yes" \
                and random.random() < 0.9:
            s["wvs_believe_in_god"] = "No"
        if isinstance(godv, (int, float)):
            if self_id == "An atheist" and godv > 3 and random.random() < 0.9:
                # A self-described atheist shouldn't rate God important.
                s["wvs_importance_of_god"] = round(random.uniform(1.0, 3.0), 2)
            elif self_id == "Not a religious person" and godv > 6 and random.random() < 0.95:
                # "Not religious" is compatible with mild/moderate belief, not
                # devotion. Pull god-importance down; the higher it started, the
                # more certainly (a "not religious" person at 9-10/10 like the
                # Robert case is the clearest contradiction).
                ceiling = 5.5 if godv < 8 else 4.5
                s["wvs_importance_of_god"] = round(random.uniform(2.0, ceiling), 2)
                if godv >= 8 and s.get("wvs_believe_in_god") == "Yes" \
                        and random.random() < 0.5:
                    s["wvs_believe_in_god"] = "No"
        # Extreme leftover: any non-religious self-ID still at god >= 8 (e.g. the
        # 0.95 above didn't fire) is the hard Robert case — sweep it down. Read
        # the CURRENT god value, not the captured one.
        if self_id in ("An atheist", "Not a religious person") \
                and isinstance(s.get("wvs_importance_of_god"), (int, float)) \
                and s["wvs_importance_of_god"] >= 8 and random.random() < 0.95:
            s["wvs_importance_of_god"] = round(random.uniform(2.0, 5.0), 2)
        # A firmly non-religious person who also says religion is "very
        # important" to them is contradictory; soften it.
        if self_id in ("An atheist", "Not a religious person") \
                and s.get("wvs_religion_importance") == "Very important" \
                and random.random() < 0.7:
            s["wvs_religion_importance"] = random.choices(
                ["Not at all important", "Not very important", "Rather important"],
                weights=[45, 40, 15], k=1)[0]

    # Religiosity spine: importance of God (Q164, 1–10) anchors the other
    # religious-values items and moral traditionalism. For people with no stated
    # religion, self-ID "a religious person" is itself inconsistent, so we don't
    # treat a leftover high God score as grounds to re-inflate their religiosity
    # (the else branch above already pulled the clear contradictions down).
    god = s.get("wvs_importance_of_god")
    religious_person = s.get("wvs_religious_self_id") == "A religious person"
    high_relig = ((isinstance(god, (int, float)) and god >= 7) or religious_person) \
        and (has_faith or religious_person)
    low_relig = (isinstance(god, (int, float)) and god <= 2) and \
                s.get("wvs_religious_self_id") == "An atheist" and not has_faith

    if high_relig and religion not in ("No religion", "Prefer not to say", None, ""):
        # More religious → more likely to attend, believe, and see religion as important
        if random.random() < 0.7:
            s["wvs_believe_in_god"] = "Yes"
        if s.get("wvs_religion_importance") == "Not at all important" and random.random() < 0.6:
            s["wvs_religion_importance"] = random.choices(
                ["Very important", "Rather important", "Not very important"],
                weights=[45, 40, 15], k=1)[0]
        # Only pull attendance up for genuinely high-god agents (≥7.5)
        # to preserve the 56% never-attend marginal
        if s.get("wvs_attend_services") == "Never, practically never" \
                and isinstance(god, (int, float)) and god >= 7.5 \
                and random.random() < 0.45:
            s["wvs_attend_services"] = random.choices(
                ["Once a week", "Once a month", "Only on special holy days", "Once a year"],
                weights=[30, 25, 25, 20], k=1)[0]
        if s.get("wvs_member_religious") == "Don't belong" and random.random() < 0.35:
            s["wvs_member_religious"] = random.choices(
                ["Active member", "Inactive member"], weights=[55, 45], k=1)[0]
    if low_relig or religion in ("No religion",):
        if random.random() < 0.85:
            s["wvs_believe_in_god"] = "No"
        s["wvs_religion_importance"] = "Not at all important"
        s["wvs_attend_services"] = "Never, practically never"

    # Moral traditionalism: religious respondents are less permissive across
    # the full ethical cluster (Q182 homosexuality, Q184 abortion, Q185 divorce,
    # Q186 sex-before-marriage, Q188 euthanasia). Strength is graded — the
    # sexuality/abortion/euthanasia items move most, divorce least — and scales
    # with how religious the person is. This is one of the strongest real
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
    elif interest in ("Not at all interested", "Not very interested"):
        # Low interest predicts LOW participation. Pull down the high-effort /
        # high-engagement markers that sit oddly with disengagement: frequent
        # discussion, always-voting, and having demonstrated. Stronger effect
        # for "not at all" than "not very".
        strong = interest == "Not at all interested"
        if s.get("wvs_discuss_politics") == "Frequently" and random.random() < (0.75 if strong else 0.5):
            s["wvs_discuss_politics"] = random.choices(
                ["Never", "Occasionally"], weights=[55, 45], k=1)[0]
        if s.get("wvs_vote_national") == "Always" and random.random() < (0.20 if strong else 0.08):
            s["wvs_vote_national"] = random.choices(
                ["Usually", "Never"], weights=[60, 40], k=1)[0]
        if s.get("wvs_action_demonstration") == "Have done" and random.random() < (0.65 if strong else 0.4):
            s["wvs_action_demonstration"] = random.choices(
                ["Might do", "Would never do"], weights=[55, 45], k=1)[0]

    # Participation ladder: signing a petition is lower-effort than attending a
    # demonstration, so "have demonstrated" but "would never sign a petition" is
    # backwards. If someone has demonstrated, they should not rule out the
    # easier act — upgrade the petition response.
    if s.get("wvs_action_demonstration") == "Have done" \
            and s.get("wvs_action_petition") == "Would never do":
        s["wvs_action_petition"] = random.choices(
            ["Have done", "Might do"], weights=[80, 20], k=1)[0]

    # Trust cohesion: low generalised trust (Q57) pulls institutional
    # confidence and stranger-trust down a little.
    if s.get("wvs_generalised_trust") == "Need to be very careful":
        if s.get("wvs_trust_first_time") in ("Trust completely", "Trust somewhat") \
                and random.random() < 0.4:
            s["wvs_trust_first_time"] = random.choices(
                ["Do not trust very much", "Trust somewhat"], weights=[60, 40], k=1)[0]

    # ── Economic values as an internal cluster ──────────────────────────────
    # The five WVS economic items load (imperfectly) onto a single left-right
    # economic dimension and are positively intercorrelated in WVS/ISSP work.
    # Sampled independently they can contradict (wanting more income equality AND
    # more private ownership AND less government responsibility at once). We nudge
    # them toward a shared latent "economic right-ness" without collapsing them —
    # keeping the imperfect loadings the literature reports, not a lockstep.
    #
    # Scale directions differ, so we align each to right-ness (higher = more
    # economically right) before combining:
    #   income_equality      1 equal(L)     .. 10 differences(R)  -> as-is
    #   private_ownership    1 govt(L)      .. 10 private(R)      -> as-is
    #   govt_responsibility  1 govt(L)      .. 10 self(R)         -> as-is
    #   competition_good     1 good(R)      .. 10 harmful(L)      -> REVERSED
    #   hardwork_pays        1 hardwork(R)  .. 10 luck(L)         -> REVERSED
    def _rightness(s_):
        vals = []
        for k, rev in (("wvs_econ_income_equality", False),
                       ("wvs_econ_private_ownership", False),
                       ("wvs_econ_govt_responsibility", False),
                       ("wvs_econ_competition_good", True),
                       ("wvs_econ_hardwork_pays", True)):
            v = s_.get(k)
            if isinstance(v, (int, float)):
                vals.append(11 - v if rev else v)
        return sum(vals) / len(vals) if vals else None

    latent = _rightness(s)
    if latent is not None:
        # Pull each item a fraction of the way toward the latent factor. The
        # pull is modest (loading ~0.35) so individual items keep their own
        # variance and the cluster stays imperfect, as in the data.
        load = 0.35
        for k, rev in (("wvs_econ_income_equality", False),
                       ("wvs_econ_private_ownership", False),
                       ("wvs_econ_govt_responsibility", False),
                       ("wvs_econ_competition_good", True),
                       ("wvs_econ_hardwork_pays", True)):
            v = s.get(k)
            if isinstance(v, (int, float)):
                target = (11 - latent) if rev else latent
                newv = (1 - load) * v + load * target
                # small jitter so items don't converge to identical values
                newv += random.uniform(-0.6, 0.6)
                s[k] = round(min(10.0, max(1.0, newv)), 2)

    # Wellbeing coherence: financial satisfaction (Q50) tracks life
    # satisfaction (Q49) with r~+0.4 in WVS data. Pull them toward each other.
    life = s.get("wvs_life_satisfaction")
    fin = s.get("wvs_financial_satisfaction")
    if isinstance(life, (int, float)) and isinstance(fin, (int, float)):
        # Moderate pull toward each other in all cases, not just extremes
        if abs(life - fin) > 2 and random.random() < 0.65:
            mid = (life + fin) / 2
            s["wvs_financial_satisfaction"] = round((fin + mid) / 2, 2)
            s["wvs_life_satisfaction"] = round((life + mid) / 2, 2)
        elif abs(life - fin) > 4 and random.random() < 0.85:
            mid = (life + fin) / 2
            s["wvs_financial_satisfaction"] = round((fin + mid) / 2, 2)
            s["wvs_life_satisfaction"] = round((life + mid) / 2, 2)

    # Happiness (Q46, categorical) and life satisfaction (Q49, 1–10) measure
    # closely related things and should not flatly contradict. A "very happy"
    # person with life satisfaction ~2/10 is incoherent. Reconcile the extremes:
    #   • very/quite happy but very low life-sat  → lift life-sat into a
    #     plausible range for that happiness level.
    #   • not-at-all/not-very happy but very high life-sat → pull life-sat down.
    happy = s.get("wvs_happiness")
    if isinstance(life, (int, float)) and happy:
        if happy == "Very happy" and life < 5:
            s["wvs_life_satisfaction"] = round(random.uniform(7.0, 9.5), 2)
        elif happy == "Quite happy" and life < 4:
            s["wvs_life_satisfaction"] = round(random.uniform(5.5, 8.0), 2)
        elif happy == "Not at all happy" and life > 6:
            s["wvs_life_satisfaction"] = round(random.uniform(1.5, 4.0), 2)
        elif happy == "Not very happy" and life > 7:
            s["wvs_life_satisfaction"] = round(random.uniform(3.0, 6.0), 2)

    # ── Final religiosity consistency sweep ─────────────────────────────────
    # Later branches above can set membership/belief independently, so do one
    # last pass to remove the residual hard contradiction of being an
    # active/inactive member of a religious organisation while stating outright
    # non-belief in God. (Belonging without belief is a real but rare edge; we
    # allow a small remainder rather than zeroing it.)
    if s.get("wvs_member_religious") in ("Active member", "Inactive member") \
            and s.get("wvs_believe_in_god") == "No" and random.random() < 0.9:
        s["wvs_believe_in_god"] = "Yes"

    # A self-described ATHEIST who believes in God is a direct contradiction,
    # regardless of affiliation. Run this LAST so the high-religiosity and
    # member sweeps above can't re-introduce belief on an atheist. Resolve by
    # dropping belief (mostly) or softening the self-ID (a minority mislabel
    # themselves); an atheist who is also a religious-org member is doubly
    # inconsistent, so drop that membership too.
    if s.get("wvs_religious_self_id") == "An atheist":
        if s.get("wvs_believe_in_god") == "Yes":
            if random.random() < 0.85:
                s["wvs_believe_in_god"] = "No"
            else:
                s["wvs_religious_self_id"] = "Not a religious person"
        if s.get("wvs_religious_self_id") == "An atheist" \
                and s.get("wvs_member_religious") in ("Active member", "Inactive member"):
            s["wvs_member_religious"] = "Don't belong"

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  CENSUS 2021 PLACE / REGION DISTRIBUTION
#  ────────────────────────────────────────────────────────────────────────────
#  Places (specific local authority districts) and their region are NO LONGER
#  assigned randomly / by the LLM. Each agent's local authority is drawn with
#  probability PROPORTIONAL TO ITS CENSUS-2021 ADULT (18+) POPULATION, and the
#  region is then taken from that local authority — so the geographic
#  distribution reflects the ONS Census 2021 population, not an arbitrary pick.
#
#  Source: ONS mid-2021 population estimates (rebased on Census 2021), single
#  year of age, England lower-tier local authorities only (Unitary Authority,
#  London Borough, Metropolitan District, Non-metropolitan District — a
#  non-overlapping tiling of England). Weight = sum of ages 18-90+ (both sexes).
#  296 places, total 18+ population ≈ 44,792,013. Region names match
#  ENGLAND_FIELD_CONFIGS["region"] exactly. LAD→region via ONS LAD/RGN lookup.
#
#  Format: (local_authority_name, region, adult_population_weight)
# ══════════════════════════════════════════════════════════════════════════════

ENGLAND_PLACES_2021: list = [
    # ── East Midlands ──
    ("Amber Valley", "East Midlands", 102760),
    ("Ashfield", "East Midlands", 100224),
    ("Bassetlaw", "East Midlands", 95343),
    ("Blaby", "East Midlands", 81621),
    ("Bolsover", "East Midlands", 64871),
    ("Boston", "East Midlands", 56193),
    ("Broxtowe", "East Midlands", 90276),
    ("Charnwood", "East Midlands", 148275),
    ("Chesterfield", "East Midlands", 84049),
    ("Derby", "East Midlands", 202648),
    ("Derbyshire Dales", "East Midlands", 59670),
    ("East Lindsey", "East Midlands", 119323),
    ("Erewash", "East Midlands", 91230),
    ("Gedling", "East Midlands", 94062),
    ("Harborough", "East Midlands", 78588),
    ("High Peak", "East Midlands", 73862),
    ("Hinckley and Bosworth", "East Midlands", 91598),
    ("Leicester", "East Midlands", 280137),
    ("Lincoln", "East Midlands", 83769),
    ("Mansfield", "East Midlands", 87972),
    ("Melton", "East Midlands", 41855),
    ("Newark and Sherwood", "East Midlands", 99639),
    ("North East Derbyshire", "East Midlands", 83476),
    ("North Kesteven", "East Midlands", 95943),
    ("North Northamptonshire", "East Midlands", 281232),
    ("North West Leicestershire", "East Midlands", 84099),
    ("Nottingham", "East Midlands", 253993),
    ("Oadby and Wigston", "East Midlands", 45905),
    ("Rushcliffe", "East Midlands", 95304),
    ("Rutland", "East Midlands", 33356),
    ("South Derbyshire", "East Midlands", 85277),
    ("South Holland", "East Midlands", 77406),
    ("South Kesteven", "East Midlands", 115202),
    ("West Lindsey", "East Midlands", 77436),
    ("West Northamptonshire", "East Midlands", 334657),
    # ── East of England ──
    ("Babergh", "East of England", 75647),
    ("Basildon", "East of England", 144330),
    ("Bedford", "East of England", 144294),
    ("Braintree", "East of England", 123482),
    ("Breckland", "East of England", 115639),
    ("Brentwood", "East of England", 61144),
    ("Broadland", "East of England", 108269),
    ("Broxbourne", "East of England", 77215),
    ("Cambridge", "East of England", 121510),
    ("Castle Point", "East of England", 72507),
    ("Central Bedfordshire", "East of England", 231529),
    ("Chelmsford", "East of England", 143835),
    ("Colchester", "East of England", 152102),
    ("Dacorum", "East of England", 120363),
    ("East Cambridgeshire", "East of England", 69864),
    ("East Hertfordshire", "East of England", 117983),
    ("East Suffolk", "East of England", 202246),
    ("Epping Forest", "East of England", 106918),
    ("Fenland", "East of England", 82965),
    ("Great Yarmouth", "East of England", 80915),
    ("Harlow", "East of England", 70959),
    ("Hertsmere", "East of England", 83766),
    ("Huntingdonshire", "East of England", 145220),
    ("Ipswich", "East of England", 108475),
    ("King's Lynn and West Norfolk", "East of England", 126463),
    ("Luton", "East of England", 166180),
    ("Maldon", "East of England", 54308),
    ("Mid Suffolk", "East of England", 84644),
    ("North Hertfordshire", "East of England", 105183),
    ("North Norfolk", "East of England", 87604),
    ("Norwich", "East of England", 117555),
    ("Peterborough", "East of England", 162725),
    ("Rochford", "East of England", 69160),
    ("South Cambridgeshire", "East of England", 127418),
    ("South Norfolk", "East of England", 114617),
    ("Southend-on-Sea", "East of England", 142630),
    ("St Albans", "East of England", 112740),
    ("Stevenage", "East of England", 69112),
    ("Tendring", "East of England", 122507),
    ("Three Rivers", "East of England", 72752),
    ("Thurrock", "East of England", 131842),
    ("Uttlesford", "East of England", 71865),
    ("Watford", "East of England", 78734),
    ("Welwyn Hatfield", "East of England", 94673),
    ("West Suffolk", "East of England", 145280),
    # ── London ──
    ("Barking and Dagenham", "London", 155339),
    ("Barnet", "London", 299795),
    ("Bexley", "London", 190100),
    ("Brent", "London", 266217),
    ("Bromley", "London", 257409),
    ("Camden", "London", 174394),
    ("City of London", "London", 8035),
    ("Croydon", "London", 300677),
    ("Ealing", "London", 286629),
    ("Enfield", "London", 248087),
    ("Greenwich", "London", 223840),
    ("Hackney", "London", 204322),
    ("Hammersmith and Fulham", "London", 151490),
    ("Haringey", "London", 209951),
    ("Harrow", "London", 203054),
    ("Havering", "London", 203540),
    ("Hillingdon", "London", 233964),
    ("Hounslow", "London", 222118),
    ("Islington", "London", 180446),
    ("Kensington and Chelsea", "London", 121387),
    ("Kingston upon Thames", "London", 131557),
    ("Lambeth", "London", 263366),
    ("Lewisham", "London", 235570),
    ("Merton", "London", 168440),
    ("Newham", "London", 267396),
    ("Redbridge", "London", 233789),
    ("Richmond upon Thames", "London", 151530),
    ("Southwark", "London", 249492),
    ("Sutton", "London", 160638),
    ("Tower Hamlets", "London", 248342),
    ("Waltham Forest", "London", 215566),
    ("Wandsworth", "London", 269038),
    ("Westminster", "London", 175152),
    # ── North East ──
    ("County Durham", "North East", 422486),
    ("Darlington", "North East", 85967),
    ("Gateshead", "North East", 157671),
    ("Hartlepool", "North East", 72711),
    ("Middlesbrough", "North East", 110463),
    ("Newcastle upon Tyne", "North East", 240956),
    ("North Tyneside", "North East", 167302),
    ("Northumberland", "North East", 263131),
    ("Redcar and Cleveland", "North East", 109429),
    ("South Tyneside", "North East", 118226),
    ("Stockton-on-Tees", "North East", 153857),
    ("Sunderland", "North East", 220326),
    # ── North West ──
    ("Blackburn with Darwen", "North West", 115203),
    ("Blackpool", "North West", 113157),
    ("Bolton", "North West", 224758),
    ("Burnley", "North West", 72988),
    ("Bury", "North West", 150099),
    ("Cheshire East", "North West", 322093),
    ("Cheshire West and Chester", "North West", 288320),
    ("Chorley", "North West", 94009),
    ("Cumberland", "North West", 222676),
    ("Fylde", "North West", 67962),
    ("Halton", "North West", 101047),
    ("Hyndburn", "North West", 63597),
    ("Knowsley", "North West", 121137),
    ("Lancaster", "North West", 116251),
    ("Liverpool", "North West", 392220),
    ("Manchester", "North West", 423856),
    ("Oldham", "North West", 180259),
    ("Pendle", "North West", 72869),
    ("Preston", "North West", 115000),
    ("Ribble Valley", "North West", 50233),
    ("Rochdale", "North West", 169456),
    ("Rossendale", "North West", 55772),
    ("Salford", "North West", 212190),
    ("Sefton", "North West", 226697),
    ("South Ribble", "North West", 89180),
    ("St. Helens", "North West", 146718),
    ("Stockport", "North West", 232761),
    ("Tameside", "North West", 180082),
    ("Trafford", "North West", 180845),
    ("Warrington", "North West", 168148),
    ("West Lancashire", "North West", 95478),
    ("Westmorland and Furness", "North West", 187727),
    ("Wigan", "North West", 261763),
    ("Wirral", "North West", 255162),
    ("Wyre", "North West", 92274),
    # ── South East ──
    ("Adur", "South East", 51608),
    ("Arun", "South East", 136751),
    ("Ashford", "South East", 104017),
    ("Basingstoke and Deane", "South East", 146433),
    ("Bracknell Forest", "South East", 97372),
    ("Brighton and Hove", "South East", 229329),
    ("Buckinghamshire", "South East", 431651),
    ("Canterbury", "South East", 128497),
    ("Cherwell", "South East", 127740),
    ("Chichester", "South East", 102734),
    ("Crawley", "South East", 90859),
    ("Dartford", "South East", 87967),
    ("Dover", "South East", 93750),
    ("East Hampshire", "South East", 101267),
    ("Eastbourne", "South East", 82325),
    ("Eastleigh", "South East", 107791),
    ("Elmbridge", "South East", 105992),
    ("Epsom and Ewell", "South East", 62704),
    ("Fareham", "South East", 93650),
    ("Folkestone and Hythe", "South East", 89638),
    ("Gosport", "South East", 65669),
    ("Gravesham", "South East", 81965),
    ("Guildford", "South East", 116274),
    ("Hart", "South East", 78704),
    ("Hastings", "South East", 72714),
    ("Havant", "South East", 100398),
    ("Horsham", "South East", 117864),
    ("Isle of Wight", "South East", 117249),
    ("Lewes", "South East", 81302),
    ("Maidstone", "South East", 139021),
    ("Medway", "South East", 216086),
    ("Mid Sussex", "South East", 120104),
    ("Milton Keynes", "South East", 218677),
    ("Mole Valley", "South East", 70488),
    ("New Forest", "South East", 145686),
    ("Oxford", "South East", 131781),
    ("Portsmouth", "South East", 165672),
    ("Reading", "South East", 137037),
    ("Reigate and Banstead", "South East", 117265),
    ("Rother", "South East", 77946),
    ("Runnymede", "South East", 70653),
    ("Rushmoor", "South East", 79045),
    ("Sevenoaks", "South East", 93950),
    ("Slough", "South East", 114711),
    ("South Oxfordshire", "South East", 118993),
    ("Southampton", "South East", 198284),
    ("Spelthorne", "South East", 81179),
    ("Surrey Heath", "South East", 71793),
    ("Swale", "South East", 118979),
    ("Tandridge", "South East", 68815),
    ("Test Valley", "South East", 104591),
    ("Thanet", "South East", 112417),
    ("Tonbridge and Malling", "South East", 102448),
    ("Tunbridge Wells", "South East", 89812),
    ("Vale of White Horse", "South East", 109696),
    ("Waverley", "South East", 100652),
    ("Wealden", "South East", 130615),
    ("West Berkshire", "South East", 127269),
    ("West Oxfordshire", "South East", 92174),
    ("Winchester", "South East", 101947),
    ("Windsor and Maidenhead", "South East", 120046),
    ("Woking", "South East", 80691),
    ("Wokingham", "South East", 137102),
    ("Worthing", "South East", 90294),
    # ── South West ──
    ("Bath and North East Somerset", "South West", 156706),
    ("Bournemouth, Christchurch and Poole", "South West", 326855),
    ("Bristol, City of", "South West", 379644),
    ("Cheltenham", "South West", 95892),
    ("Cornwall", "South West", 467102),
    ("Cotswold", "South West", 74715),
    ("Dorset", "South West", 315262),
    ("East Devon", "South West", 125483),
    ("Exeter", "South West", 107833),
    ("Forest of Dean", "South West", 70984),
    ("Gloucester", "South West", 104016),
    ("Isles of Scilly", "South West", 1928),
    ("Mid Devon", "South West", 66624),
    ("North Devon", "South West", 80764),
    ("North Somerset", "South West", 174547),
    ("Plymouth", "South West", 213139),
    ("Somerset", "South West", 463711),
    ("South Gloucestershire", "South West", 231646),
    ("South Hams", "South West", 73637),
    ("Stroud", "South West", 97930),
    ("Swindon", "South West", 182342),
    ("Teignbridge", "South West", 111121),
    ("Tewkesbury", "South West", 75829),
    ("Torbay", "South West", 114258),
    ("Torridge", "South West", 56576),
    ("West Devon", "South West", 47466),
    ("Wiltshire", "South West", 410153),
    # ── West Midlands ──
    ("Birmingham", "West Midlands", 856789),
    ("Bromsgrove", "West Midlands", 78960),
    ("Cannock Chase", "West Midlands", 80407),
    ("Coventry", "West Midlands", 267631),
    ("Dudley", "West Midlands", 255134),
    ("East Staffordshire", "West Midlands", 97933),
    ("Herefordshire, County of", "West Midlands", 153738),
    ("Lichfield", "West Midlands", 86713),
    ("Malvern Hills", "West Midlands", 65705),
    ("Newcastle-under-Lyme", "West Midlands", 100254),
    ("North Warwickshire", "West Midlands", 52719),
    ("Nuneaton and Bedworth", "West Midlands", 105728),
    ("Redditch", "West Midlands", 68190),
    ("Rugby", "West Midlands", 89817),
    ("Sandwell", "West Midlands", 256988),
    ("Shropshire", "West Midlands", 266274),
    ("Solihull", "West Midlands", 169753),
    ("South Staffordshire", "West Midlands", 91397),
    ("Stafford", "West Midlands", 111133),
    ("Staffordshire Moorlands", "West Midlands", 78878),
    ("Stoke-on-Trent", "West Midlands", 199716),
    ("Stratford-on-Avon", "West Midlands", 110828),
    ("Tamworth", "West Midlands", 62131),
    ("Telford and Wrekin", "West Midlands", 144434),
    ("Walsall", "West Midlands", 216107),
    ("Warwick", "West Midlands", 120422),
    ("Wolverhampton", "West Midlands", 202254),
    ("Worcester", "West Midlands", 83201),
    ("Wychavon", "West Midlands", 108400),
    ("Wyre Forest", "West Midlands", 82636),
    # ── Yorkshire and The Humber ──
    ("Barnsley", "Yorkshire and The Humber", 194794),
    ("Bradford", "Yorkshire and The Humber", 406353),
    ("Calderdale", "Yorkshire and The Humber", 161793),
    ("Doncaster", "Yorkshire and The Humber", 244600),
    ("East Riding of Yorkshire", "Yorkshire and The Humber", 281664),
    ("Kingston upon Hull, City of", "Yorkshire and The Humber", 207462),
    ("Kirklees", "Yorkshire and The Humber", 335683),
    ("Leeds", "Yorkshire and The Humber", 638840),
    ("North East Lincolnshire", "Yorkshire and The Humber", 124168),
    ("North Lincolnshire", "Yorkshire and The Humber", 135856),
    ("North Yorkshire", "Yorkshire and The Humber", 504917),
    ("Rotherham", "Yorkshire and The Humber", 209824),
    ("Sheffield", "Yorkshire and The Humber", 442613),
    ("Wakefield", "Yorkshire and The Humber", 280119),
    ("York", "Yorkshire and The Humber", 167159),
]

# Pre-split for weighted sampling (kept module-level so it is built once).
_ENGLAND_PLACE_NAMES   = [p[0] for p in ENGLAND_PLACES_2021]
_ENGLAND_PLACE_REGIONS = [p[1] for p in ENGLAND_PLACES_2021]
_ENGLAND_PLACE_WEIGHTS = [p[2] for p in ENGLAND_PLACES_2021]


def _sample_census_place() -> tuple:
    """
    Draw one (local_authority, region) pair proportional to Census-2021 adult
    population. Replaces random/LLM place assignment with a census-weighted one.
    """
    idx = random.choices(range(len(ENGLAND_PLACES_2021)),
                         weights=_ENGLAND_PLACE_WEIGHTS, k=1)[0]
    return _ENGLAND_PLACE_NAMES[idx], _ENGLAND_PLACE_REGIONS[idx]


# ══════════════════════════════════════════════════════════════════════════════
#  CENSUS 2021 OCCUPATION DISTRIBUTION BY PLACE  (ONS Census 2021, TS063)
#  ────────────────────────────────────────────────────────────────────────────
#  For agents IN EMPLOYMENT the SOC-2020 major group is NOT drawn from a single
#  national distribution — it is drawn from the occupation profile of the
#  agent's own local authority (TS063, "Occupation (current)", 9 major groups,
#  excluding the "Does not apply" / not-in-employment category). This makes
#  occupation covary with place (e.g. more Professional occupations in London
#  boroughs, more Skilled-trades / Elementary in post-industrial districts).
#
#  Keyed by local-authority NAME (matches ENGLAND_PLACES_2021). The four 2023
#  unitaries that did not exist at Census 2021 (Cumberland, Westmorland and
#  Furness, North Yorkshire, Somerset) use their region's aggregated TS063 mix.
#  Weight order = _OCC_SOC_CATS below (person counts, reduced by a common factor).
# ══════════════════════════════════════════════════════════════════════════════

_OCC_SOC_CATS: list = [
    "Managers, directors and senior officials",
    "Professional occupations",
    "Associate professional and technical",
    "Administrative and secretarial",
    "Skilled trades occupations",
    "Caring, leisure and other service",
    "Sales and customer service",
    "Process, plant and machine operatives",
    "Elementary occupations",
]

ENGLAND_OCC_BY_LA: dict = {
    'Adur': (3733, 5345, 4216, 2823, 3820, 3115, 2411, 1807, 2555),
    'Amber Valley': (7635, 10404, 7440, 5461, 7697, 5428, 4428, 5454, 6224),
    'Arun': (9715, 10532, 8549, 6840, 9244, 8594, 5833, 5525, 8359),
    'Ashfield': (5645, 8128, 6422, 5599, 7766, 6339, 5161, 5640, 7730),
    'Ashford': (9171, 11751, 8251, 5811, 7322, 5812, 4895, 4350, 6253),
    'Babergh': (6371, 7361, 5784, 4144, 5688, 3946, 3085, 2671, 3907),
    'Barking and Dagenham': (7786, 15185, 9279, 8798, 10957, 10934, 7686, 8964, 15000),
    'Barnet': (31481, 50534, 25626, 16520, 14478, 14342, 10663, 8394, 14137),
    'Barnsley': (11251, 15595, 12169, 9891, 14042, 11382, 10172, 11579, 15599),
    'Basildon': (10880, 15369, 11530, 10680, 9967, 7924, 6581, 6499, 9581),
    'Basingstoke and Deane': (13857, 21125, 14431, 9512, 9272, 8282, 6553, 5349, 8592),
    'Bassetlaw': (6836, 7967, 5934, 4581, 6525, 5745, 4164, 6039, 7128),
    'Bath and North East Somerset': (13076, 22044, 12201, 7921, 8841, 7631, 5875, 4102, 8121),
    'Bedford': (11797, 18284, 12254, 8152, 8798, 8128, 6498, 6134, 10820),
    'Bexley': (14498, 23417, 16138, 15535, 12291, 10333, 8186, 7430, 10155),
    'Birmingham': (40972, 93314, 50205, 41168, 36872, 45362, 36475, 38618, 59431),
    'Blaby': (6656, 9936, 7193, 5417, 6194, 4448, 3623, 3398, 4581),
    'Blackburn with Darwen': (5966, 10409, 6781, 6291, 6744, 7201, 6277, 6470, 7417),
    'Blackpool': (6200, 7502, 6001, 6631, 6480, 8632, 5743, 4715, 7458),
    'Bolsover': (3841, 5001, 3924, 3409, 4661, 4388, 3206, 3863, 5810),
    'Bolton': (13286, 21197, 15019, 12357, 12663, 12393, 12227, 11486, 14810),
    'Boston': (2843, 3598, 2475, 2550, 3702, 3403, 2631, 6272, 6157),
    'Bournemouth, Christchurch and Poole': (24266, 36384, 24034, 16486, 20154, 19901, 16046, 11031, 17728),
    'Bracknell Forest': (10132, 13742, 10767, 6650, 6604, 5981, 4304, 2967, 5251),
    'Bradford': (22188, 37854, 25366, 21385, 23080, 23590, 20131, 20912, 26631),
    'Braintree': (10693, 12192, 10303, 7892, 9669, 7290, 5565, 5335, 7343),
    'Breckland': (8022, 8545, 7596, 5767, 8759, 7031, 4997, 6821, 8100),
    'Brent': (18700, 31402, 19463, 13311, 15838, 13901, 13423, 12932, 22027),
    'Brentwood': (7010, 8922, 6046, 4613, 3263, 2536, 1878, 1496, 2137),
    'Brighton and Hove': (19701, 36478, 23620, 10344, 10753, 12075, 10144, 5135, 11042),
    'Bristol, City of': (24219, 64929, 35165, 20448, 19912, 19568, 16410, 13017, 24845),
    'Broadland': (8232, 11298, 8134, 6743, 8066, 6117, 5035, 3832, 5132),
    'Bromley': (27845, 43321, 25707, 17733, 12787, 11212, 8498, 5867, 9152),
    'Bromsgrove': (8088, 11774, 6463, 4697, 4735, 3672, 2569, 2120, 3169),
    'Broxbourne': (6696, 7767, 6405, 5835, 5806, 4033, 3455, 3637, 4672),
    'Broxtowe': (5830, 12754, 6868, 4992, 5181, 3961, 3873, 3320, 5137),
    'Buckinghamshire': (50441, 61466, 40954, 25760, 25403, 21485, 16538, 12757, 18432),
    'Burnley': (3652, 5577, 4284, 3490, 4778, 4775, 3536, 4088, 5858),
    'Bury': (11113, 18354, 12059, 9075, 8038, 8482, 7351, 6042, 7971),
    'Calderdale': (11521, 18183, 12703, 9120, 10426, 8829, 6895, 7165, 8539),
    'Cambridge': (7446, 29962, 8532, 4096, 3577, 4824, 3444, 2374, 6343),
    'Camden': (18247, 35269, 19193, 6330, 3781, 6279, 5152, 2963, 5299),
    'Cannock Chase': (5429, 6719, 5789, 4675, 6953, 4814, 4112, 4597, 5788),
    'Canterbury': (8502, 14588, 8689, 5530, 6890, 6524, 5248, 3466, 6727),
    'Castle Point': (5373, 5837, 5381, 5352, 5501, 3806, 3106, 3152, 3498),
    'Central Bedfordshire': (22832, 29383, 22805, 15297, 16739, 12379, 9605, 9246, 12791),
    'Charnwood': (11078, 17495, 11622, 7932, 9048, 7449, 6172, 5826, 8178),
    'Chelmsford': (13598, 20713, 13126, 9815, 8348, 6873, 5736, 4399, 7254),
    'Cheltenham': (7892, 14593, 7823, 6836, 4921, 4702, 4264, 2805, 5322),
    'Cherwell': (11634, 16522, 11364, 7778, 8701, 6661, 6674, 6628, 9010),
    'Cheshire East': (31910, 41211, 26358, 17063, 17214, 15574, 13131, 11778, 18249),
    'Cheshire West and Chester': (23721, 34739, 22261, 14966, 15809, 14821, 13851, 11667, 17253),
    'Chesterfield': (4995, 7994, 5317, 4528, 5337, 5679, 4290, 3865, 5527),
    'Chichester': (9565, 11241, 8152, 4530, 6561, 5243, 3640, 2478, 4956),
    'Chorley': (8036, 11870, 7928, 5443, 5815, 5299, 3877, 3793, 5183),
    'City of London': (1104, 2349, 1027, 267, 97, 152, 122, 50, 178),
    'Colchester': (11921, 18906, 13059, 8486, 9315, 9682, 6866, 5425, 8355),
    'Cornwall': (32386, 39181, 28474, 20774, 39684, 28356, 20800, 17293, 27300),
    'Cotswold': (8540, 8375, 5834, 3804, 5403, 3585, 2872, 1972, 3694),
    'County Durham': (22537, 37179, 26917, 21178, 26099, 23112, 19432, 20568, 25193),
    'Coventry': (12956, 28834, 17300, 13652, 13277, 14380, 12570, 13271, 23905),
    'Crawley': (5955, 8798, 7254, 5770, 5330, 6828, 5601, 5531, 7836),
    'Croydon': (24114, 43348, 26739, 19333, 15968, 18250, 13735, 10765, 17155),
    'Cumberland': (381840, 642942, 422030, 323044, 334817, 334933, 281990, 253570, 366575),
    'Dacorum': (12798, 16172, 11749, 7353, 7396, 6181, 4949, 3979, 6622),
    'Darlington': (5230, 8463, 5973, 4961, 5042, 4895, 4657, 3847, 6228),
    'Dartford': (7555, 12101, 7748, 6827, 6203, 4860, 4068, 4062, 5400),
    'Derby': (10517, 21692, 13293, 9880, 10981, 11704, 9862, 11558, 16713),
    'Derbyshire Dales': (5537, 6783, 3701, 2802, 4545, 2650, 1875, 2275, 3062),
    'Doncaster': (14029, 17657, 14672, 12123, 16094, 14191, 12211, 14155, 22724),
    'Dorset': (24133, 29063, 21194, 15632, 23230, 17212, 11930, 9525, 15858),
    'Dover': (5998, 7795, 7505, 4774, 5860, 6303, 3913, 3737, 5041),
    'Dudley': (15322, 24346, 17362, 15388, 17996, 14043, 12177, 12838, 15169),
    'Ealing': (24147, 39697, 23951, 14223, 15555, 12912, 12773, 11767, 20000),
    'East Cambridgeshire': (6481, 9649, 6118, 4221, 5026, 4144, 2585, 2804, 3667),
    'East Devon': (9434, 11683, 8240, 5925, 9147, 7043, 5259, 3597, 6399),
    'East Hampshire': (10897, 13136, 8701, 5745, 6989, 5778, 3536, 2617, 4333),
    'East Hertfordshire': (13957, 17041, 12088, 7727, 7108, 5869, 4148, 3418, 5168),
    'East Lindsey': (7297, 6788, 5789, 4710, 8050, 6604, 4795, 4720, 6826),
    'East Riding of Yorkshire': (21363, 28215, 19406, 14215, 19462, 14891, 11084, 11365, 16118),
    'East Staffordshire': (7247, 9179, 6301, 5218, 6264, 4862, 4302, 6532, 9415),
    'East Suffolk': (13786, 16909, 13244, 10157, 13291, 11322, 8480, 8182, 10995),
    'Eastbourne': (4928, 7784, 5138, 3906, 4792, 6068, 3769, 2554, 4893),
    'Eastleigh': (9404, 14903, 9932, 7344, 7603, 6187, 5050, 3863, 5229),
    'Elmbridge': (16432, 17652, 10820, 5545, 4189, 4495, 3001, 1828, 3018),
    'Enfield': (18297, 29475, 17729, 13804, 14397, 13986, 10695, 9440, 16041),
    'Epping Forest': (12368, 13155, 9395, 7991, 6959, 4587, 3561, 3371, 4409),
    'Epsom and Ewell': (7020, 10663, 5958, 4095, 3242, 3304, 2031, 1404, 2192),
    'Erewash': (6133, 9102, 6609, 5418, 6881, 5028, 4547, 4747, 6502),
    'Exeter': (5846, 14748, 7326, 5305, 5353, 5803, 5109, 3654, 6555),
    'Fareham': (7953, 11632, 9159, 6154, 5586, 4593, 3940, 2611, 4003),
    'Fenland': (5028, 5248, 5157, 4115, 6175, 4963, 3505, 6615, 6302),
    'Folkestone and Hythe': (6167, 7610, 6934, 4324, 5592, 5681, 3962, 3132, 4415),
    'Forest of Dean': (5126, 6221, 4875, 3797, 5815, 4347, 2677, 3192, 3942),
    'Fylde': (5208, 7685, 4893, 3623, 3503, 3423, 2478, 1953, 2946),
    'Gateshead': (8448, 16612, 11006, 8949, 8581, 8793, 8710, 6950, 9469),
    'Gedling': (7026, 11693, 7670, 5625, 6236, 5203, 4385, 3360, 4989),
    'Gloucester': (6245, 10844, 8019, 7174, 7208, 7580, 5648, 5576, 7327),
    'Gosport': (4077, 5272, 5804, 4031, 4766, 4610, 3170, 2593, 4161),
    'Gravesham': (6005, 7846, 6125, 5188, 5590, 4639, 3797, 4387, 6184),
    'Great Yarmouth': (4037, 4911, 4127, 3743, 5220, 5347, 3722, 4277, 5752),
    'Greenwich': (18826, 35907, 21127, 11610, 10735, 13290, 9173, 7183, 15083),
    'Guildford': (12141, 18410, 11207, 5849, 5682, 5465, 4077, 2338, 4605),
    'Hackney': (18646, 40040, 27603, 9468, 6468, 9742, 7191, 4530, 10624),
    'Halton': (5870, 8767, 7260, 5877, 5667, 5585, 6143, 5884, 7653),
    'Hammersmith and Fulham': (18326, 29279, 18574, 6900, 4493, 6803, 5004, 2711, 6006),
    'Harborough': (8799, 10831, 6993, 4486, 5046, 3500, 2903, 2358, 3856),
    'Haringey': (17168, 33738, 21842, 9189, 11265, 10419, 8084, 6027, 16651),
    'Harlow': (4808, 6889, 5202, 4968, 5411, 4800, 3669, 4302, 5932),
    'Harrow': (17524, 31409, 14526, 12204, 12184, 8624, 9061, 7806, 11702),
    'Hart': (9507, 11749, 8737, 4762, 4544, 3698, 2774, 1769, 2905),
    'Hartlepool': (3348, 5838, 4497, 3391, 4736, 4381, 3613, 3622, 4323),
    'Hastings': (4437, 6752, 5489, 3816, 5063, 5531, 3410, 2558, 3843),
    'Havant': (6844, 9199, 6950, 5286, 7625, 6126, 4696, 4018, 5624),
    'Havering': (15438, 24339, 16717, 16701, 14375, 10294, 8162, 8058, 10697),
    'Herefordshire, County of': (11979, 14131, 9965, 7964, 12927, 8686, 6212, 6943, 9700),
    'Hertsmere': (9198, 12243, 7478, 5665, 4607, 4296, 2997, 2583, 3699),
    'High Peak': (5873, 8839, 5598, 3694, 5209, 4453, 3120, 3593, 4235),
    'Hillingdon': (18524, 30087, 18036, 14401, 13152, 12044, 10772, 10752, 15035),
    'Hinckley and Bosworth': (7756, 10160, 7534, 5742, 6364, 4821, 3701, 4050, 5761),
    'Horsham': (12689, 15238, 11458, 6842, 7090, 6338, 4557, 2994, 4961),
    'Hounslow': (17914, 27755, 17668, 12160, 12138, 11345, 11117, 10067, 18636),
    'Huntingdonshire': (13200, 18416, 13493, 9425, 9129, 7496, 6112, 6414, 7706),
    'Hyndburn': (3346, 4984, 3955, 3297, 4671, 4414, 3263, 3847, 3850),
    'Ipswich': (6066, 11334, 7906, 6253, 6834, 7133, 6370, 6347, 8783),
    'Isle of Wight': (7243, 8981, 6602, 4850, 8084, 7591, 5104, 3588, 5870),
    'Isles of Scilly': (191, 139, 124, 75, 191, 150, 84, 65, 94),
    'Islington': (17439, 39312, 22879, 7333, 4945, 6756, 5601, 3496, 7211),
    'Kensington and Chelsea': (18485, 19186, 12294, 4117, 2221, 5064, 3182, 1678, 3214),
    "King's Lynn and West Norfolk": (8301, 9525, 7527, 6143, 9702, 7568, 5225, 6888, 8344),
    'Kingston upon Hull, City of': (8253, 14557, 11961, 9378, 15820, 13117, 11993, 14573, 18137),
    'Kingston upon Thames': (14674, 23933, 13140, 7171, 5769, 5947, 5296, 2854, 5364),
    'Kirklees': (22814, 34891, 24630, 17154, 20975, 17830, 15809, 16929, 19055),
    'Knowsley': (6008, 10581, 7912, 7654, 7330, 8359, 6612, 6685, 8350),
    'Lambeth': (25695, 55140, 34580, 12564, 9463, 13130, 8956, 6187, 17104),
    'Lancaster': (6581, 12488, 7430, 4961, 7340, 7516, 5024, 4483, 6578),
    'Leeds': (41589, 85081, 52009, 35774, 32376, 34684, 29948, 22576, 40027),
    'Leicester': (11006, 24074, 13678, 12354, 12069, 15552, 14761, 22261, 29181),
    'Lewes': (6557, 8783, 6518, 3919, 5301, 4522, 2991, 2322, 3594),
    'Lewisham': (20155, 41888, 27269, 11892, 10473, 13363, 9774, 6369, 14530),
    'Lichfield': (8452, 10500, 6694, 4780, 5392, 3775, 3261, 2983, 4635),
    'Lincoln': (3745, 7225, 5172, 3728, 4649, 5323, 4922, 4893, 7061),
    'Liverpool': (17700, 42403, 24736, 21341, 16279, 21874, 19228, 15241, 26948),
    'Luton': (8547, 15550, 9938, 8433, 9659, 10526, 7854, 11485, 16729),
    'Maidstone': (12732, 15817, 12106, 8635, 9423, 7124, 5894, 5939, 8737),
    'Maldon': (5186, 4980, 4132, 3538, 4224, 2414, 2192, 1974, 2615),
    'Malvern Hills': (5950, 7718, 4400, 3280, 4441, 3133, 2248, 1849, 2781),
    'Manchester': (20368, 55875, 31626, 18837, 15576, 23595, 21720, 15035, 31651),
    'Mansfield': (4976, 6575, 5462, 4363, 6299, 5826, 4337, 5093, 8436),
    'Medway': (14826, 21929, 17307, 13910, 15896, 12828, 10137, 11111, 14666),
    'Melton': (3880, 4183, 3095, 2303, 3236, 2370, 1653, 2156, 2590),
    'Merton': (17692, 29411, 16337, 9159, 9115, 8623, 7030, 5202, 9496),
    'Mid Devon': (5312, 6482, 4430, 3586, 6041, 3907, 3127, 3277, 4121),
    'Mid Suffolk': (7402, 8948, 6776, 4940, 6553, 4341, 3235, 3403, 4426),
    'Mid Sussex': (13156, 17539, 11989, 7231, 6878, 6923, 4567, 3009, 5280),
    'Middlesbrough': (4409, 8996, 6109, 4856, 5906, 7578, 5394, 5577, 7609),
    'Milton Keynes': (18299, 30540, 19938, 13825, 11004, 11017, 11353, 9345, 18057),
    'Mole Valley': (8321, 10140, 6392, 4063, 4156, 3429, 2168, 1285, 2387),
    'New Forest': (11997, 13956, 9927, 7715, 9971, 8252, 5386, 4498, 7000),
    'Newark and Sherwood': (7801, 9033, 7048, 4909, 6617, 5750, 4283, 4817, 6859),
    'Newcastle upon Tyne': (11448, 30729, 15060, 11029, 10037, 11694, 12573, 7906, 14602),
    'Newcastle-under-Lyme': (6024, 10116, 6659, 5220, 6606, 5791, 4861, 4433, 6972),
    'Newham': (15522, 32704, 19608, 12621, 16496, 14189, 14529, 11822, 25954),
    'North Devon': (5749, 6898, 5067, 3618, 7162, 4874, 3406, 3237, 5152),
    'North East Derbyshire': (6028, 8011, 5492, 4610, 5813, 4639, 3731, 3527, 4712),
    'North East Lincolnshire': (6058, 8490, 7328, 5865, 8108, 7344, 5685, 10396, 9577),
    'North Hertfordshire': (10803, 17135, 10326, 5895, 5838, 4991, 4105, 3290, 4778),
    'North Kesteven': (7665, 9946, 8580, 6036, 6556, 5561, 3753, 3915, 4880),
    'North Lincolnshire': (8279, 10321, 8278, 6393, 9215, 7323, 6003, 10070, 10341),
    'North Norfolk': (5718, 5304, 4227, 3403, 6875, 4957, 3607, 2753, 4815),
    'North Northamptonshire': (21751, 26861, 20376, 16768, 19477, 15814, 13354, 17639, 26815),
    'North Somerset': (14625, 20359, 13585, 10134, 10436, 10139, 7377, 6711, 9336),
    'North Tyneside': (9927, 21780, 13362, 10743, 8704, 8832, 9443, 5848, 8627),
    'North Warwickshire': (4243, 4816, 3928, 3331, 3752, 2721, 2218, 2814, 3931),
    'North West Leicestershire': (7305, 8940, 6845, 4828, 5962, 4407, 3642, 4481, 5551),
    'North Yorkshire': (275517, 445153, 302217, 222603, 272789, 239674, 204820, 207068, 291534),
    'Northumberland': (17405, 24722, 17034, 13435, 16928, 15432, 12010, 9968, 13843),
    'Norwich': (5633, 14691, 8202, 5095, 5904, 6762, 6275, 4545, 8613),
    'Nottingham': (10297, 24432, 14343, 10112, 10634, 14291, 12113, 11229, 21415),
    'Nuneaton and Bedworth': (6264, 9985, 7477, 6311, 6608, 6224, 4976, 6108, 9161),
    'Oadby and Wigston': (2997, 5815, 3255, 2784, 2437, 2439, 2093, 1793, 2376),
    'Oldham': (9616, 14988, 11314, 9555, 11144, 10613, 8596, 9362, 13019),
    'Oxford': (6732, 26873, 8620, 4723, 4607, 5985, 4221, 3724, 7844),
    'Pendle': (4070, 5701, 4083, 3159, 5373, 4135, 3673, 4558, 4871),
    'Peterborough': (9979, 15830, 11291, 9118, 8947, 9135, 8723, 11152, 16793),
    'Plymouth': (10874, 20138, 15675, 11406, 15496, 13823, 11112, 9029, 13465),
    'Portsmouth': (9806, 18084, 12207, 8982, 10663, 10674, 8481, 7288, 11602),
    'Preston': (6171, 12745, 7639, 6669, 6043, 7165, 6057, 5574, 8571),
    'Reading': (9390, 22757, 11993, 7062, 6953, 8079, 6736, 5095, 10803),
    'Redbridge': (18627, 34456, 17250, 14551, 12846, 9843, 10747, 9229, 14078),
    'Redcar and Cleveland': (4801, 8411, 6605, 4983, 6800, 7430, 4760, 5345, 6488),
    'Redditch': (4719, 6675, 5027, 4125, 5060, 3832, 3569, 4678, 5007),
    'Reigate and Banstead': (13005, 18485, 11393, 7387, 6461, 6726, 4104, 2957, 4607),
    'Ribble Valley': (5125, 6818, 3989, 2681, 3772, 2522, 1645, 1662, 2171),
    'Richmond upon Thames': (23031, 30417, 17549, 6935, 4478, 5468, 3749, 2187, 3752),
    'Rochdale': (9745, 15229, 10969, 9242, 10016, 10293, 7893, 8665, 12407),
    'Rochford': (5903, 7360, 6021, 5392, 4730, 3317, 2677, 2329, 2929),
    'Rossendale': (4316, 6256, 4366, 2762, 3993, 3508, 2598, 2448, 2869),
    'Rother': (5866, 6478, 4725, 3745, 5289, 4322, 2671, 1827, 3011),
    'Rotherham': (11944, 17917, 13092, 11147, 14872, 12344, 11216, 11374, 13895),
    'Rugby': (7546, 11798, 7302, 5262, 4954, 4137, 3762, 4483, 8862),
    'Runnymede': (7078, 9235, 6344, 4175, 4010, 3716, 2756, 1872, 3271),
    'Rushcliffe': (9946, 17011, 8403, 4947, 4264, 3644, 3103, 1975, 3685),
    'Rushmoor': (6008, 9262, 8137, 5072, 5452, 5980, 4017, 3118, 5968),
    'Rutland': (3426, 3567, 3063, 1583, 1897, 1577, 1051, 1021, 1598),
    'Salford': (13594, 26141, 18314, 13174, 10448, 11882, 11281, 7786, 14987),
    'Sandwell': (11162, 19323, 14486, 13569, 15431, 14996, 12778, 17351, 21976),
    'Sefton': (14013, 23148, 15549, 14788, 12126, 13734, 10716, 8653, 11870),
    'Sevenoaks': (10668, 12361, 8215, 5812, 5892, 4078, 3208, 2463, 3685),
    'Sheffield': (22723, 56141, 29427, 21533, 23579, 23309, 21710, 16095, 27493),
    'Shropshire': (21180, 26819, 18664, 13271, 21109, 15219, 10852, 10178, 15132),
    'Slough': (7303, 13888, 8098, 6736, 6230, 6884, 6122, 7650, 10790),
    'Solihull': (14975, 23824, 12966, 10523, 8318, 7498, 6395, 5550, 7890),
    'Somerset': (344165, 513706, 344902, 250258, 326016, 266923, 202353, 173764, 270244),
    'South Cambridgeshire': (12816, 26002, 11201, 6957, 7037, 5938, 3902, 3129, 5285),
    'South Derbyshire': (7651, 10303, 6889, 5007, 5736, 4688, 3607, 4674, 5350),
    'South Gloucestershire': (17918, 31300, 19437, 17372, 16114, 12405, 10669, 8855, 13542),
    'South Hams': (6738, 8286, 5137, 3261, 6131, 3274, 2680, 1729, 3346),
    'South Holland': (5190, 4964, 4162, 4082, 5993, 4130, 3254, 6976, 6485),
    'South Kesteven': (9865, 11819, 8785, 6339, 7790, 6337, 4913, 5193, 7153),
    'South Norfolk': (9422, 14379, 8817, 6436, 8206, 6212, 4541, 4116, 5620),
    'South Oxfordshire': (13483, 18786, 11387, 6773, 7522, 5575, 4061, 3325, 5564),
    'South Ribble': (6556, 10836, 7565, 6042, 6115, 5029, 4207, 3791, 4570),
    'South Staffordshire': (7795, 9821, 6626, 5573, 6343, 4038, 3345, 3039, 4119),
    'South Tyneside': (5586, 10192, 7793, 6794, 7005, 6809, 6132, 5662, 6537),
    'Southampton': (10223, 23404, 14011, 9892, 12153, 12651, 9903, 10307, 15684),
    'Southend-on-Sea': (10787, 15911, 11769, 9250, 8227, 8171, 6369, 5062, 7714),
    'Southwark': (23109, 51143, 28878, 11443, 8030, 12816, 8705, 5990, 16833),
    'Spelthorne': (7477, 10061, 7719, 6055, 5064, 4417, 3397, 3250, 4099),
    'St Albans': (15131, 22216, 11484, 5914, 4350, 4420, 3434, 2118, 3804),
    'St. Helens': (8359, 14070, 10274, 8026, 8658, 9171, 6827, 7319, 9919),
    'Stafford': (9092, 13873, 9161, 6026, 6473, 5498, 4732, 3950, 6963),
    'Staffordshire Moorlands': (5913, 7590, 5325, 3938, 6543, 4484, 3139, 3743, 4360),
    'Stevenage': (4848, 8727, 6034, 4467, 5145, 4603, 3636, 3369, 4631),
    'Stockport': (19060, 34321, 20204, 14126, 11754, 12151, 11083, 6958, 10149),
    'Stockton-on-Tees': (8985, 16671, 10903, 8413, 8868, 8858, 7330, 6993, 9421),
    'Stoke-on-Trent': (8808, 14100, 10978, 9334, 13468, 13618, 11057, 12577, 18639),
    'Stratford-on-Avon': (12363, 14213, 9233, 5890, 7299, 4777, 4247, 2897, 5317),
    'Stroud': (8984, 12574, 8210, 5380, 7354, 5190, 3714, 3617, 4895),
    'Sunderland': (10421, 17727, 13207, 12544, 12235, 12309, 13422, 11645, 13641),
    'Surrey Heath': (8378, 10390, 7054, 4490, 3889, 3743, 2736, 1824, 2859),
    'Sutton': (14604, 25047, 14218, 11239, 10383, 9022, 6802, 5380, 7527),
    'Swale': (8539, 10281, 9022, 6850, 8591, 6482, 4882, 6269, 8287),
    'Swindon': (12567, 21222, 14798, 11300, 11519, 10317, 9729, 10909, 15504),
    'Tameside': (10510, 15922, 13385, 11631, 12334, 10883, 10159, 9628, 11202),
    'Tamworth': (4191, 4971, 4398, 3973, 4125, 3320, 3502, 3982, 5693),
    'Tandridge': (8361, 9177, 6669, 4498, 4144, 3565, 2157, 1679, 2326),
    'Teignbridge': (8403, 11561, 7544, 5507, 8125, 6677, 4663, 3910, 5748),
    'Telford and Wrekin': (9152, 14031, 10426, 7686, 8883, 8386, 6757, 9432, 10745),
    'Tendring': (7191, 7457, 6596, 5591, 8071, 7829, 5007, 4518, 6020),
    'Test Valley': (10383, 13522, 9305, 7023, 6516, 5275, 4160, 3896, 5781),
    'Tewkesbury': (6696, 9517, 6392, 5693, 4804, 3883, 3168, 2790, 3581),
    'Thanet': (7096, 9544, 7433, 5135, 6913, 7762, 4916, 4083, 6308),
    'Three Rivers': (8784, 11673, 6916, 4805, 4157, 3421, 2369, 1887, 2936),
    'Thurrock': (9480, 12527, 9673, 10207, 9661, 7211, 7076, 8615, 11498),
    'Tonbridge and Malling': (10664, 13058, 9610, 6728, 6666, 5106, 4187, 3346, 5059),
    'Torbay': (7199, 8239, 6364, 4952, 7759, 8347, 5143, 4109, 6821),
    'Torridge': (3595, 3801, 2900, 2524, 5648, 3723, 2332, 2211, 3319),
    'Tower Hamlets': (20628, 49021, 27819, 11184, 7508, 9276, 10470, 6949, 12537),
    'Trafford': (16656, 32126, 16379, 10964, 7641, 7792, 7937, 4475, 7588),
    'Tunbridge Wells': (10209, 13095, 8175, 4905, 5128, 4438, 3608, 2098, 4239),
    'Uttlesford': (8868, 9467, 7026, 4584, 4670, 3478, 2525, 2101, 3024),
    'Vale of White Horse': (10709, 19019, 10630, 6325, 6780, 5179, 3833, 3345, 5044),
    'Wakefield': (17223, 24634, 20031, 15270, 17587, 15735, 13016, 16680, 24465),
    'Walsall': (11430, 17660, 12590, 11247, 14409, 12276, 10354, 12558, 16012),
    'Waltham Forest': (17473, 32185, 21194, 11608, 14037, 10474, 9284, 8341, 15776),
    'Wandsworth': (35827, 61870, 37329, 13285, 7838, 11073, 8031, 5178, 10011),
    'Warrington': (13604, 20853, 13972, 10010, 8742, 8344, 8503, 7152, 12011),
    'Warwick': (11452, 21877, 10382, 5851, 5590, 4920, 4299, 3013, 5364),
    'Watford': (6703, 12278, 7136, 4928, 4916, 4570, 3774, 3224, 5330),
    'Waverley': (12671, 15528, 9256, 4951, 5301, 4737, 3027, 1710, 3541),
    'Wealden': (12879, 13625, 10220, 7390, 9736, 7230, 4892, 3119, 5454),
    'Welwyn Hatfield': (8411, 12148, 7923, 5630, 5136, 4982, 4603, 3191, 6125),
    'West Berkshire': (13269, 18327, 12023, 7806, 8216, 7031, 5211, 4027, 6397),
    'West Devon': (3458, 4444, 2889, 2122, 4264, 2456, 1751, 1529, 2471),
    'West Lancashire': (7088, 9972, 6289, 4921, 5499, 5222, 4121, 4357, 6077),
    'West Lindsey': (5742, 7453, 5085, 3877, 5323, 4337, 3073, 3324, 3923),
    'West Northamptonshire': (28471, 37897, 27068, 20833, 21932, 18001, 14527, 16341, 30925),
    'West Oxfordshire': (9428, 12007, 8946, 5521, 6745, 5105, 3476, 3170, 4525),
    'West Suffolk': (11402, 14748, 13094, 8094, 10962, 9252, 5825, 6778, 9464),
    'Westminster': (22858, 31136, 17588, 6750, 3481, 6187, 5211, 2781, 5750),
    'Westmorland and Furness': (381840, 642942, 422030, 323044, 334817, 334933, 281990, 253570, 366575),
    'Wigan': (16153, 25062, 19252, 15038, 18014, 16478, 12747, 14327, 17543),
    'Wiltshire': (36607, 46920, 37260, 25833, 28608, 22686, 16548, 15405, 22478),
    'Winchester': (11084, 16313, 8850, 5069, 5066, 4368, 3320, 2038, 4466),
    'Windsor and Maidenhead': (15930, 18678, 12666, 6582, 5784, 5427, 3770, 2848, 4617),
    'Wirral': (15549, 27893, 18147, 14561, 13501, 15613, 11599, 9649, 12990),
    'Woking': (8666, 13423, 7777, 4879, 4298, 4299, 3190, 2500, 3709),
    'Wokingham': (15849, 25529, 14751, 8325, 6594, 5939, 4739, 3103, 4638),
    'Wolverhampton': (9649, 17783, 11566, 10249, 11420, 12262, 9025, 12623, 16732),
    'Worcester': (5584, 10280, 6689, 4794, 4867, 5125, 4140, 4106, 6044),
    'Worthing': (6680, 10711, 7625, 5279, 5627, 6159, 4024, 2875, 4577),
    'Wychavon': (10301, 11442, 7893, 5973, 7366, 5448, 4537, 4709, 5991),
    'Wyre': (5996, 8584, 5679, 5727, 5959, 5089, 3469, 3136, 4196),
    'Wyre Forest': (5831, 7070, 5264, 4333, 6005, 4925, 3770, 3760, 4828),
    'York': (11603, 23463, 12626, 8190, 8627, 8466, 8205, 4966, 10052),
}


def _sample_occupation_for_la(local_authority: str) -> str:
    """
    Draw a SOC-2020 major group weighted by the local authority's Census-2021
    (TS063) occupation profile. Falls back to the national occupation_soc
    weights if the place is unknown.
    """
    weights = ENGLAND_OCC_BY_LA.get(local_authority)
    if not weights:
        return _sample_field(ENGLAND_FIELD_CONFIGS.get("occupation_soc", {"mode": "na"}))
    return random.choices(_OCC_SOC_CATS, weights=weights, k=1)[0]



# ══════════════════════════════════════════════════════════════════════════════
#  SKELETON SAMPLER  (drop-in for _sample_demographic_skeletons in app.py)
# ══════════════════════════════════════════════════════════════════════════════

def _sample_wvs_fields(fc: dict) -> dict:
    """Sample all WVS value-dimension fields from WVS_FIELD_CONFIGS."""
    return {name: _sample_field(cfg) for name, cfg in WVS_FIELD_CONFIGS.items()}


def apply_all_correlations(s: dict) -> dict:
    """
    Run every correlation pass over a demographic skeleton, in causal order.

    This is the single source of truth for the correlation cascade. Both this
    module's own sampler (sample_england_skeleton) and app.py's general
    Generate-Sample path should call THIS, so an England agent gets identical
    treatment no matter which entry point produced it.

    Every pass reads fields defensively with .get() and no-ops on anything
    missing, so it is safe to call on a partial skeleton (e.g. a non-England
    preset that lacks occupation_soc / social_grade / the WVS or BSA fields).
    Passes that need an earlier pass's output run after it:

      1. age → activity / occupation / education / health / tenure gradient
      2. education → occupation → social grade → income
      3. health ↔ disability ↔ economic activity        (needs 1 & 2 settled)
      4. housing tenure ↔ age ↔ income ↔ social grade    (needs income & grade)
      5. age → marital status → household composition
      6. ethnicity → religion + urban/rural
      7. attitudes: education(+age) → lib-auth; grade/income → left-right/welfarism
      8. WVS value covariances (religiosity → ethics, engagement, trust, etc.)
    """
    s = _apply_age_correlations(s)
    s = _apply_socioeconomic_correlations(s)
    s = _apply_health_activity_correlations(s)
    s = _apply_tenure_correlations(s)
    s = _apply_marital_correlations(s)
    s = _apply_ethnicity_correlations(s)
    # Condition WVS religiosity on the person's actual faith group.
    s = _apply_faith_conditioning(s)
    s = _apply_attitude_correlations(s)
    s = _apply_wvs_correlations(s)
    s = _apply_final_consistency_sweep(s)
    return s


def _apply_value_coherence(s: dict) -> dict:
    """
    Make the BSA value scales, the WVS value items, and religion describe ONE
    internally cohesive person.

    THE PROBLEM THIS SOLVES
    ----------------------
    The three BSA scales (left_right, lib_auth, welfarism) and the WVS value
    items were drawn from their marginals INDEPENDENTLY. Measured on the output,
    the abstract scales had essentially ZERO relationship with the concrete
    answers: people rating homosexuality 8-10 had a mean lib_auth of 3.27, and
    people rating it 1-3 had 3.28. So an agent could be "authoritarian" on the
    scale while giving uniformly liberal answers, or "economically left" while
    wanting private ownership and lower taxes.

    THE APPROACH
    ------------
    For each scale we derive the person's position from their OWN WVS answers
    (the concrete, specific items a reader actually sees), then bring the
    abstract scale into line with it. Two design rules:

      * We move the SCALE to fit the ANSWERS, not the reverse. The answers carry
        more information and are what makes a persona legible.
      * The mapping is CENTRED on the population's mean position, so a
        correlation is created WITHOUT dragging the scale's marginal to one end.
        (A naive mapping pushed mean lib_auth from 3.35 down to 2.77.)

    The link is strong but not deterministic: genuinely cross-pressured people
    (economically left but socially conservative; liberal on sexuality but tough
    on immigration) survive, because they are real. Only flat contradictions are
    removed.
    """
    # ── left_right  <->  WVS economic items ─────────────────────────────
    # scale: 1 = economic left .. 5 = economic right
    # NOTE the WVS scale directions differ: competition_good and hardwork_pays
    # are REVERSED (1 = the right-wing answer), the other three are 1 = left.
    lr = s.get("scale_left_right")
    if isinstance(lr, (int, float)):
        econ = []
        for k, rev in (("wvs_econ_income_equality", False),
                       ("wvs_econ_private_ownership", False),
                       ("wvs_econ_govt_responsibility", False),
                       ("wvs_econ_competition_good", True),
                       ("wvs_econ_hardwork_pays", True)):
            v = s.get(k)
            if isinstance(v, (int, float)):
                aligned = (11 - v) if rev else v      # high = economically RIGHT
                econ.append((aligned - 1) / 9.0)      # 0 = left, 1 = right
        if econ:
            rightness = sum(econ) / len(econ)
            _POP_MEAN_R = 0.50
            target = 2.90 + 2.6 * (rightness - _POP_MEAN_R)
            new = 0.35 * lr + 0.65 * target + random.uniform(-0.25, 0.25)
            s["scale_left_right"] = round(min(5.0, max(1.0, new)), 2)
            lr = s["scale_left_right"]

    # ── welfarism  <->  left_right + the redistribution items ───────────
    # scale: 1 = pro-welfare-state .. 5 = anti-welfare.
    # Welfarism is genuinely CROSS-CUTTING in British survey data (it does not
    # collapse into left-right), so the link is deliberately weak: we only
    # remove the flat contradictions at the extremes and leave the middle — the
    # cross-pressured people — alone.
    welf = s.get("scale_welfarism")
    if isinstance(welf, (int, float)) and isinstance(lr, (int, float)):
        lean = s.get("political_leaning")
        strong_left = lean in ("Left", "Far left") or lr <= 2.2
        strong_right = lean in ("Right", "Far right") or lr >= 3.8
        if strong_left and welf > 3.6:
            s["scale_welfarism"] = round(random.uniform(2.2, 3.3), 2)
        elif strong_right and welf < 2.0:
            s["scale_welfarism"] = round(random.uniform(2.8, 4.0), 2)

    # ── (ethics block removed) items load on ONE permissiveness dimension ──────
    # Homosexuality, divorce, abortion and sex-before-marriage were independent,
    # so an agent could rate homosexuality 9.0 and divorce 9.7 but sex before
    # marriage 5.2 — incoherent for a socially liberal person. Pull them toward
    # the person's own permissiveness level, keeping item-level variation
    # ── RELIGION: the structural field and the WVS religiosity items ────
    # Belief in a higher power among the non-religious is REAL (~30% of UK
    # non-religious people say they believe in something), so belief itself is
    # left alone. But FORMAL MEMBERSHIP of a religious organisation flatly
    # contradicts "no religion" — that is the tell-tale sign of independent
    # draws rather than one coherent person.
    if s.get("religion") in ("No religion", "Prefer not to say") \
            and s.get("wvs_member_religious") in ("Active member", "Inactive member"):
        s["wvs_member_religious"] = "Don't belong"

    # Religiosity must also cohere with the moral items: a highly religious
    # person rating every contested moral question as fully permissible is
    # incoherent. Pull the most extreme cases back, gently and only at the top.
    god = s.get("wvs_importance_of_god")
    if isinstance(god, (int, float)) and god >= 8.5:
        for k in ():
            v = s.get(k)
            if isinstance(v, (int, float)) and v >= 9.0 and random.random() < 0.5:
                s[k] = round(random.uniform(5.0, 8.0), 2)

    return s


# ══════════════════════════════════════════════════════════════════════════════
#  RELIGION-CONDITIONED VALUES
# ══════════════════════════════════════════════════════════════════════════════
# Each faith group is conditioned on its own real-world centre (taken from the
# published UK survey literature) rather than the national average. Religion
# and the WVS religiosity items now describe ONE coherent person: a Muslim
# agent holds Muslim-centred religiosity, not secular-Britain marginals wearing
# a Muslim label.
import random as _FR

_FAITH_CENTRES = {
    "Muslim/Islam": 0.72, "Hindu": 0.62, "Sikh": 0.65,
    "Jewish": 0.50, "Buddhist": 0.40,
    "Christian: Baptist": 0.55, "Christian: Other Christian": 0.48,
    "Christian: Methodist": 0.46, "Christian: Roman Catholic": 0.75,
    "Christian: Church of England/Anglican": 0.16,
    "Christian (no specific denomination)": 0.16,
    "No religion": 0.06, "Prefer not to say": 0.15,
}


def _apply_faith_conditioning(s: dict) -> dict:
    """
    Condition the WVS religiosity items on the person's faith group and age.
    The national marginals are replaced by faith-specific centres; within-group
    variance is preserved via noise so devout and lax members of every faith
    both exist.
    """
    rel    = s.get("religion")
    centre = _FAITH_CENTRES.get(rel)
    if centre is None:
        return s

    age = s.get("age")
    age_adj = (0.12 if isinstance(age, int) and age >= 65
               else 0.07 if isinstance(age, int) and age >= 50
               else -0.05 if isinstance(age, int) and age < 30 else 0.0)
    tr = min(1.0, max(0.0, centre + age_adj + _FR.gauss(0, 0.16)))

    # God importance (1-10)
    god = s.get("wvs_importance_of_god")
    if isinstance(god, (int, float)):
        target = 1.0 + 9.0 * tr
        pull = 0.75
        s["wvs_importance_of_god"] = round(min(10.0, max(1.0,
            (1 - pull) * god + pull * target + _FR.uniform(-1.1, 1.1))), 2)

    # Belief
    s["wvs_believe_in_god"] = "Yes" if _FR.random() < (0.06 + 0.92 * tr) else "No"

    # Self-description
    s["wvs_religious_self_id"] = (
        "A religious person" if _FR.random() < (0.02 + 0.94 * tr)
        else ("An atheist" if tr < 0.18 and _FR.random() < 0.45
              else "Not a religious person"))

    # Religion importance
    thresholds = [0.25, 0.55, 0.80]
    labels = ["Not at all important", "Not very important",
              "Rather important", "Very important"]
    for i, t in enumerate(thresholds):
        if tr < t:
            s["wvs_religion_importance"] = labels[i]
            break
    else:
        s["wvs_religion_importance"] = labels[-1]

    # Attendance
    att_options = [
        "Never, practically never", "Less often", "Once a year",
        "Only on special holy days", "Once a month", "Once a week",
        "More than once a week"]
    att_pos = min(1.0, max(0.0, tr * 0.80 + _FR.gauss(0, 0.14)))
    idx = min(len(att_options) - 1, int(att_pos * len(att_options)))
    s["wvs_attend_services"] = att_options[idx]

    # Membership
    has_faith = rel not in ("No religion", "Prefer not to say", None, "")
    if has_faith and tr > 0.55:
        s["wvs_member_religious"] = _FR.choices(
            ["Active member", "Inactive member", "Don't belong"],
            weights=[35, 40, 25], k=1)[0]
    elif has_faith and tr > 0.30:
        s["wvs_member_religious"] = _FR.choices(
            ["Inactive member", "Don't belong"], weights=[40, 60], k=1)[0]
    else:
        s["wvs_member_religious"] = "Don't belong"

    return s


# ===== CROSS-FIELD CONSISTENCY FIXES =====
# Addresses the independent-sampling contradictions identified in persona review:
# education ⊥ student status, health ⊥ disability, happiness ⊥ life-sat,
# political leaning ⊥ participation, social grade ⊥ student.

def _apply_cross_field_consistency(s: dict) -> dict:
    import random as _r

    ea = s.get("economic_activity", "")
    edu = s.get("education_level", "")
    health = s.get("general_health", "")
    disab = s.get("disability", "")

    # 1. Education → student eligibility
    # Cannot be a full-time student with no formal education or only primary.
    # Also: nursing/professional degrees require at least A-levels.
    _NO_QUAL = ("No formal education", "Primary school")
    if ea == "Full-time student" and edu in _NO_QUAL:
        s["education_level"] = _r.choices(
            ["Some high school", "High school diploma / A-levels",
             "Vocational / Technical degree"],
            weights=[30, 45, 25], k=1)[0]

    # 2. Social grade → student
    # Full-time students are graded E (or on the chief income earner),
    # never AB (higher managerial/professional).
    grade = s.get("social_grade", "") or ""
    if ea == "Full-time student" and grade.startswith("AB"):
        s["social_grade"] = _r.choices(
            ["D - Semi-skilled and unskilled manual",
             "E - Casual or lowest grade workers, state pensioners"],
            weights=[35, 65], k=1)[0]

    # 3. Very bad / Bad health → disability
    # "Very bad" general health at working age almost always involves
    # some activity limitation. Hard-wire the worst cases.
    if health == "Very bad" and disab == "Not disabled":
        s["disability"] = _r.choices(
            ["Disabled - day-to-day activities limited a lot",
             "Disabled - day-to-day activities limited a little"],
            weights=[55, 45], k=1)[0]
    elif health == "Bad" and disab == "Not disabled" and _r.random() < 0.7:
        s["disability"] = "Disabled - day-to-day activities limited a little"

    # 4. Apolitical → participation acts
    # Someone who identifies as apolitical cannot also always vote, sign
    # petitions and demonstrate. Strip out the engaged acts.
    if s.get("political_leaning") == "Apolitical":
        if s.get("wvs_vote_national") == "Always":
            s["wvs_vote_national"] = _r.choices(
                ["Never", "Not allowed to vote", "Usually"],
                weights=[45, 10, 45], k=1)[0]
        if s.get("wvs_action_demonstration") == "Have done":
            s["wvs_action_demonstration"] = _r.choices(
                ["Would never do", "Might do"], weights=[70, 30], k=1)[0]
        if s.get("wvs_action_petition") == "Have done":
            s["wvs_action_petition"] = _r.choices(
                ["Would never do", "Might do"], weights=[55, 45], k=1)[0]
        if s.get("wvs_discuss_politics") == "Frequently":
            s["wvs_discuss_politics"] = _r.choices(
                ["Never", "Occasionally"], weights=[60, 40], k=1)[0]

    # 5. Very happy ↔ life satisfaction (hard backstop)
    ls = s.get("wvs_life_satisfaction")
    hap = s.get("wvs_happiness")
    if isinstance(ls, (int, float)) and hap:
        if hap == "Very happy" and ls < 5.0:
            s["wvs_life_satisfaction"] = round(_r.uniform(6.5, 9.5), 2)
        elif hap == "Quite happy" and ls < 3.5:
            s["wvs_life_satisfaction"] = round(_r.uniform(5.0, 7.5), 2)
        elif hap == "Not at all happy" and ls > 6.0:
            s["wvs_life_satisfaction"] = round(_r.uniform(1.0, 4.0), 2)
        elif hap == "Not very happy" and ls > 7.5:
            s["wvs_life_satisfaction"] = round(_r.uniform(2.5, 5.5), 2)

    return s


def _apply_remaining_consistency_fixes(s: dict) -> dict:
    """
    Fixes for all remaining cross-field contradictions found in the
    systematic audit:

    1.  Bad health + not disabled  →  assign disability
    2.  Long-term sick + not disabled  →  assign disability
    3.  Long-term sick + good health  →  pull health down
    4.  Not-at-all-interested + demonstrated/discusses  →  strip engagement
    5.  Under-22 part-time + income > £25k  →  cap income
    6.  Widowed under 30  →  change to single/separated
    7.  Couple-no-dep-children + dependent children + under 50
           →  fix household composition
    """
    import random as _r

    health = s.get("general_health", "")
    disab  = s.get("disability", "")
    ea     = s.get("economic_activity", "")
    age    = s.get("age")

    # 1. Bad health + not disabled
    # NOTE: handled in _apply_health_activity_correlations (line ~1658).
    # No longer applied here to avoid double-conversion inflating disability.
    pass

    # 2 & 3. Long-term sick
    if ea == "Economically inactive - long-term sick":
        if disab == "Not disabled":
            s["disability"] = _r.choices(
                ["Disabled - day-to-day activities limited a lot",
                 "Disabled - day-to-day activities limited a little"],
                weights=[55, 45], k=1)[0]
        if health in ("Very good", "Good"):
            s["general_health"] = _r.choices(
                ["Fair", "Bad", "Very bad"], weights=[45, 40, 15], k=1)[0]

    # 4. Not-at-all-interested in politics
    if s.get("wvs_political_interest") == "Not at all interested":
        if s.get("wvs_action_demonstration") in ("Have done", "Might do"):
            s["wvs_action_demonstration"] = _r.choices(
                ["Would never do", "Might do"], weights=[80, 20], k=1)[0]
        if s.get("wvs_action_demonstration") == "Might do" and _r.random() < 0.6:
            s["wvs_action_demonstration"] = "Would never do"
        if s.get("wvs_discuss_politics") == "Frequently":
            s["wvs_discuss_politics"] = _r.choices(
                ["Never", "Occasionally"], weights=[60, 40], k=1)[0]
        if s.get("wvs_action_petition") == "Have done" and _r.random() < 0.10:
            s["wvs_action_petition"] = _r.choices(
                ["Would never do", "Might do"], weights=[65, 35], k=1)[0]

    # 5. Under 22 part-time income cap
    _LAD = ["Under \u00a315,000","\u00a315,000 \u2013 \u00a324,999",
            "\u00a325,000 \u2013 \u00a334,999","\u00a335,000 \u2013 \u00a349,999",
            "\u00a350,000 \u2013 \u00a374,999","\u00a375,000 \u2013 \u00a399,999",
            "\u00a3100,000 \u2013 \u00a3149,999","\u00a3150,000 or more"]
    _IX = {b: i for i, b in enumerate(_LAD)}
    if isinstance(age, int) and age < 22 and ea == "Employee - part-time":
        cur = _IX.get(s.get("income_bracket"), 0)
        if cur >= _IX["\u00a325,000 \u2013 \u00a334,999"]:
            s["income_bracket"] = _r.choice(_LAD[:2])  # under £25k

    # 6. Widowed under 30 → single or separated
    if s.get("marital_status") == "Widowed" and isinstance(age, int) and age < 30:
        s["marital_status"] = _r.choices(
            ["Single", "Separated"], weights=[80, 20], k=1)[0]

    # 6b. Mortgage + low income → change tenure to renting.
    # A mortgage requires sufficient income to service it. Under £25k is
    # implausible for most mortgagees (the median first-time buyer income
    # is ~£45k). Allow it only for retired outright owners drawing a small
    # pension — those are coded as 'Owns outright', not 'Owns with mortgage'.
    if s.get('housing_tenure') == 'Owns with mortgage' \
            and s.get('income_bracket') in (
                'Under £15,000', '£15,000 – £24,999') \
            and _r.random() < 0.92:
        s['housing_tenure'] = _r.choices(
            ['Rents - social / council', 'Rents - private', 'Owns outright'],
            weights=[45, 40, 15], k=1)[0]

    # 6c. Over-70 + dependent children household → not possible in practice.
    # A 75-year-old is not a lone parent of dependent children. Change to a
    # more age-appropriate composition.
    if isinstance(age, int) and age > 70 \
            and s.get('household_composition') in (
                'Lone parent with dependent children',
                'Couple with dependent children'):
        s['household_composition'] = _r.choices(
            ['One-person household', 'Couple, no dependent children',
             'Other household types'],
            weights=[50, 35, 15], k=1)[0]
        # Align children count if household no longer implies children
        if 'dependent children' not in s.get('household_composition',''):
            s['children'] = _r.choices([0, 0, 1], weights=[60, 30, 10], k=1)[0]

    # 7. Marital status vs household composition
    # Married/partnered people cannot live alone; single people cannot be
    # in a couple household. These were sampled independently.
    marital = s.get('marital_status', '')
    hh = s.get('household_composition', '')
    if marital in ('Married', 'In a registered civil partnership'):
        if hh == 'One-person household':
            # Over-70 married people should not have dep children
            if isinstance(age, int) and age > 70:
                s['household_composition'] = 'Couple, no dependent children'
            else:
                s['household_composition'] = _r.choices(
                    ['Couple, no dependent children',
                     'Couple with dependent children'],
                    weights=[60, 40], k=1)[0]
    elif marital == 'Single':
        if hh in ('Couple with dependent children',
                  'Couple, no dependent children'):
            children = s.get('children', 0) or 0
            s['household_composition'] = _r.choices(
                ['One-person household',
                 'Lone parent with dependent children',
                 'Other household types'],
                weights=[50, 30 if children > 0 else 5, 20], k=1)[0]
    elif marital in ('Divorced', 'Separated', 'Widowed'):
        if hh in ('Couple with dependent children',
                  'Couple, no dependent children'):
            children = s.get('children', 0) or 0
            s['household_composition'] = _r.choices(
                ['One-person household',
                 'Lone parent with dependent children',
                 'Other household types'],
                weights=[45, 35 if children > 0 else 5, 20], k=1)[0]

    # 7b. Household composition vs actual children
    hh = s.get("household_composition", "")
    children = s.get("children")
    if hh == "Couple, no dependent children" \
            and isinstance(children, int) and children > 0 \
            and isinstance(age, int) and age < 50:
        s["household_composition"] = "Couple with dependent children"
    elif hh == "Couple with dependent children" \
            and isinstance(children, int) and children == 0:
        s["children"] = _r.randint(1, 2)

    return s


def _apply_wellbeing_coherence(s: dict) -> dict:
    """
    Three remaining wellbeing/income coherence issues:

    1. WVS subjective health must agree with census general health AND disability.
       Being disabled 'a lot' + fair/bad census health rules out 'Very good'
       on the WVS subjective scale.

    2. Life satisfaction cannot be near-perfect (>=9) when freedom of choice
       is very low (<4). These two are strongly correlated (r~0.45 in WVS).
       A person who feels they have no control over their life does not
       simultaneously rate life at 10/10.

    3. DE grade + income > £50k is implausible for non-earners (retired,
       unemployed, inactive). The existing cap handles some cases; this
       catches medical-retirement / low-grade retirees.
    """
    import random as _wr

    # 1. WVS subjective health vs census health + disability
    _wh = s.get("wvs_subjective_health")
    _gh = s.get("general_health")
    _db = s.get("disability", "")
    _bad_gh = _gh in ("Fair", "Bad", "Very bad")
    _bad_db = _db == "Disabled - day-to-day activities limited a lot"
    if _wh == "Very good" and _bad_gh and _bad_db:
        s["wvs_subjective_health"] = _wr.choices(
            ["Fair", "Poor", "Good"], weights=[45, 35, 20], k=1)[0]
    elif _wh == "Very good" and _bad_gh and _wr.random() < 0.7:
        s["wvs_subjective_health"] = _wr.choices(
            ["Good", "Fair"], weights=[60, 40], k=1)[0]

    # 2. Life satisfaction vs freedom of choice
    _ls = s.get("wvs_life_satisfaction")
    _fc = s.get("wvs_freedom_of_choice")
    if isinstance(_ls, (int, float)) and isinstance(_fc, (int, float)):
        if _ls >= 9.0 and _fc < 4.0:
            # Low autonomy caps life satisfaction: pull it down to a plausible
            # range for someone who feels little control over their life.
            s["wvs_life_satisfaction"] = round(
                _wr.uniform(4.5, 7.5), 2)
        elif _ls >= 8.0 and _fc < 3.0 and _wr.random() < 0.6:
            s["wvs_life_satisfaction"] = round(
                _wr.uniform(4.0, 7.0), 2)

    # 3. DE grade + high income — implausible for both earners and non-earners.
    # DE is semi-skilled/unskilled with typical pay £18-30k.
    _LAD = ["Under £15,000", "£15,000 – £24,999",
            "£25,000 – £34,999", "£35,000 – £49,999",
            "£50,000 – £74,999", "£75,000 – £99,999",
            "£100,000 – £149,999", "£150,000 or more"]
    _IX = {b: i for i, b in enumerate(_LAD)}
    _grade = s.get("social_grade", "") or ""
    _ea    = s.get("economic_activity", "")
    _cap   = _IX["£35,000 – £49,999"]
    if _grade.startswith("DE"):
        _cur = _IX.get(s.get("income_bracket"))
        if _cur is not None and _cur > _cap:
            s["income_bracket"] = _wr.choice(_LAD[:_cap + 1])

    return s


def _apply_final_consistency_sweep(s: dict) -> dict:
    """
    Deterministic belt-and-braces cleanup.

    The earlier passes do the nuanced, probabilistic correlation work and leave
    a small tail of hard contradictions (the few % where a nudge's probability
    didn't fire). This sweep runs last and UNCONDITIONALLY resolves the
    remaining hard inconsistencies, so a finished skeleton never carries one.
    It is intentionally narrow — it only touches clear contradictions, never
    the plausible-but-unusual combinations that give the population its realism.
    """
    # ── Religiosity: atheists / not-religious with high God-importance ──────
    self_id = s.get("wvs_religious_self_id")
    god = s.get("wvs_importance_of_god")
    if self_id == "An atheist":
        if isinstance(god, (int, float)) and god > 4:
            s["wvs_importance_of_god"] = round(random.uniform(1.0, 3.0), 2)
        if s.get("wvs_believe_in_god") == "Yes":
            s["wvs_believe_in_god"] = "No"
        if s.get("wvs_member_religious") in ("Active member", "Inactive member"):
            s["wvs_member_religious"] = "Don't belong"
    elif self_id == "Not a religious person":
        if isinstance(god, (int, float)) and god >= 8:
            s["wvs_importance_of_god"] = round(random.uniform(3.0, 6.5), 2)

    # ── Politics: stated leaning vs left-right scale (1=left … 5=right) ─────
    leaning = s.get("political_leaning")
    lr = s.get("scale_left_right")
    if isinstance(lr, (int, float)):
        # Clamp the scale into the region implied by a clearly-opposed leaning.
        if leaning in ("Right", "Far right", "Center-right") and lr < 2.4:
            s["scale_left_right"] = round(random.uniform(3.1, 4.2), 2)
        elif leaning in ("Left", "Far left", "Center-left") and lr > 3.6:
            s["scale_left_right"] = round(random.uniform(1.8, 2.9), 2)

    # ── Health: disability "limited a lot" vs "Very good" health ───────────
    if s.get("disability") == _DISABLED_LOT and s.get("general_health") == "Very good":
        s["general_health"] = random.choices(
            ["Fair", "Bad", "Very bad"], weights=[50, 35, 15], k=1)[0]

    # ── Long-term sick with BOTH good health AND no disability ─────────────
    # Only the full triple is a hard contradiction; leave the realistic tail
    # (e.g. someone off long-term sick with a condition that self-rates as
    # good-ish, or who doesn't classify themselves as disabled) intact. Fix the
    # minimum needed: nudge one of the two so they're not simultaneously "very
    # good health" AND "not disabled".
    if s.get("economic_activity") == "Economically inactive - long-term sick" \
            and s.get("general_health") in ("Very good", "Good") \
            and s.get("disability") == "Not disabled":
        # Flip whichever reads less severe; prefer adjusting health downward.
        if s.get("general_health") == "Very good":
            s["general_health"] = random.choices(
                ["Fair", "Bad", "Very bad"], weights=[45, 40, 15], k=1)[0]
        else:  # "Good" → give a disability flag instead of touching health
            s["disability"] = random.choices(
                [_DISABLED_LOT, "Disabled - day-to-day activities limited a little"],
                weights=[55, 45], k=1)[0]

    # ── Economic activity vs occupation (inactive shouldn't hold a job) ────
    if s.get("economic_activity") in ("Retired", "Full-time student",
                                      "Economically inactive - long-term sick",
                                      "Economically inactive - home or family",
                                      "Economically inactive - other",
                                      "Unemployed - seeking work") \
            and s.get("occupation_soc") not in (None, "N/A", ""):
        s["occupation_soc"] = "N/A"

    # ── Occupation vs social grade two+ tiers apart ────────────────────────
    occ = s.get("occupation_soc")
    grade = s.get("social_grade", "") or ""
    if occ in _OCC_AB and grade.startswith("DE"):
        s["social_grade"] = "AB - Higher/intermediate managerial, admin, professional"

    # ── Education ↔ social grade ────────────────────────────────────────────
    # Education and social grade are strongly correlated (Census 2021):
    # AB: ~65% degree+, ~1-2% no/primary  |  DE: ~5% degree+, ~20% no/primary
    # Resample education when it is implausible for the agent's grade.
    _grade_now = s.get("social_grade", "") or ""
    _edu_now   = s.get("education_level", "") or ""
    _EDU_DEGREE_G = ("Bachelor's degree", "Master's degree",
                     "Doctoral degree (PhD, MD, JD, etc.)")
    _EDU_NOQ_G    = ("No formal education", "Primary school")
    _EDU_MID_G    = ("Some high school", "High school diploma / GED",
                     "Some college (no degree)", "Vocational / Technical degree",
                     "Associate degree")

    if _grade_now.startswith("AB"):
        if _edu_now in _EDU_NOQ_G and random.random() < 0.92:
            s["education_level"] = random.choices(
                ["Some high school", "High school diploma / GED",
                 "Vocational / Technical degree", "Bachelor's degree",
                 "Master's degree"],
                weights=[5, 10, 12, 45, 28], k=1)[0]
        elif _edu_now in _EDU_MID_G and random.random() < 0.45:
            s["education_level"] = random.choices(
                ["Bachelor's degree", "Master's degree",
                 "Doctoral degree (PhD, MD, JD, etc.)"],
                weights=[55, 35, 10], k=1)[0]
    elif _grade_now.startswith("C1"):
        if _edu_now in _EDU_NOQ_G and random.random() < 0.75:
            s["education_level"] = random.choices(
                list(_EDU_MID_G), weights=[20, 30, 15, 25, 10], k=1)[0]
    elif _grade_now.startswith("C2"):
        # C2 skilled manual: ~8-10% no-qual, ~10% degree+
        if _edu_now in _EDU_DEGREE_G and random.random() < 0.72:
            s["education_level"] = random.choices(
                ["High school diploma / GED", "Vocational / Technical degree",
                 "Some high school", "Some college (no degree)"],
                weights=[30, 35, 20, 15], k=1)[0]
        elif _edu_now in _EDU_NOQ_G and random.random() < 0.30:
            s["education_level"] = random.choices(
                ["Some high school", "High school diploma / GED",
                 "Vocational / Technical degree"],
                weights=[30, 40, 30], k=1)[0]
    elif _grade_now.startswith("DE"):
        if _edu_now in _EDU_DEGREE_G and random.random() < 0.82:
            s["education_level"] = random.choices(
                ["Some high school", "High school diploma / GED",
                 "Vocational / Technical degree", "No formal education",
                 "Primary school"],
                weights=[22, 28, 24, 13, 13], k=1)[0]

    # ── Income: low-tier occupation / low education on top income bands ────
    _inc_ladder = ["Under £15,000", "£15,000 – £24,999", "£25,000 – £34,999",
                   "£35,000 – £49,999", "£50,000 – £74,999", "£75,000 – £99,999",
                   "£100,000 – £149,999", "£150,000 or more"]
    _inc_i = {b: i for i, b in enumerate(_inc_ladder)}
    cur_inc = _inc_i.get(s.get("income_bracket"))
    edu = s.get("education_level")
    _edu_low = {"No formal education", "Primary school", "Some high school"}
    if cur_inc is not None:
        # Low-tier occupation should not sit in the very top bands.
        if occ in _OCC_DE and cur_inc >= _inc_i["£100,000 – £149,999"]:
            s["income_bracket"] = random.choice(
                _inc_ladder[:_inc_i["£50,000 – £74,999"]])
            cur_inc = _inc_i[s["income_bracket"]]
        # Low education + low occupation shouldn't reach the top bands either.
        if edu in _edu_low and occ in _OCC_DE and cur_inc >= _inc_i["£75,000 – £99,999"]:
            s["income_bracket"] = random.choice(
                _inc_ladder[:_inc_i["£50,000 – £74,999"]])
            cur_inc = _inc_i[s["income_bracket"]]
        # Young part-time worker on a top income band is implausible.
        if s.get("economic_activity") == "Employee - part-time" \
                and isinstance(s.get("age"), int) and s["age"] < 25 \
                and cur_inc >= _inc_i["£75,000 – £99,999"]:
            s["income_bracket"] = random.choice(
                _inc_ladder[:_inc_i["£50,000 – £74,999"]])

    # ── Partnership / children hard cases ──────────────────────────────────
    age = s.get("age")
    if isinstance(age, int):
        if age < 18 and isinstance(s.get("children"), int) and s["children"] > 0:
            s["children"] = 0
            if s.get("household_composition") in (
                    "Lone parent with dependent children",
                    "Couple with dependent children"):
                s["household_composition"] = "One-person household" \
                    if s.get("marital_status") in ("Single", "Widowed",
                                                   "Divorced", "Separated") \
                    else "Couple, no dependent children"
        # Too many children for a very young parent.
        elif age < 21 and isinstance(s.get("children"), int) and s["children"] >= 2:
            s["children"] = 1

    # ── Retirement age (hard guarantee) ─────────────────────────────────────
    # No one under 45 should be "Retired"; redirect any that slipped through.
    if isinstance(age, int) and age < 45 and s.get("economic_activity") == "Retired":
        s["economic_activity"] = random.choices(
            ["Employee - full-time", "Employee - part-time", "Self-employed",
             "Economically inactive - long-term sick",
             "Economically inactive - home or family"],
            weights=[55, 18, 12, 8, 7], k=1)[0]
        if s["economic_activity"] not in ("Employee - full-time",
                                          "Employee - part-time", "Self-employed"):
            s["occupation_soc"] = "N/A"

    # ── Two health fields must agree in direction (hard guarantee) ──────────
    # census general_health and wvs_subjective_health measure the same thing;
    # never let them sit more than one step apart (e.g. "Very bad" vs "Very
    # good"). Align the WVS field to the census anchor.
    _rank = {"Very good": 4, "Good": 3, "Fair": 2, "Bad": 1, "Very bad": 0}
    _wrank = {"Very good": 4, "Good": 3, "Fair": 2, "Poor": 1, "Very poor": 0}
    _wby = {4: "Very good", 3: "Good", 2: "Fair", 1: "Poor", 0: "Very poor"}
    gh = s.get("general_health")
    sh = s.get("wvs_subjective_health")
    if gh in _rank and sh in _wrank and abs(_rank[gh] - _wrank[sh]) > 1:
        s["wvs_subjective_health"] = _wby[_rank[gh]]

    # ── Non-employed DE-grade income ceiling (hard guarantee) ───────────────
    # A DE social-grade person who isn't working (retired/unemployed/inactive)
    # should not sit in the top income bands; low lifetime earnings mean a
    # modest pension/benefit income. Cap them.
    grade = s.get("social_grade", "") or ""
    if grade.startswith("DE") and s.get("economic_activity") in (
            "Retired", "Unemployed - seeking work",
            "Economically inactive - long-term sick",
            "Economically inactive - other",
            "Economically inactive - home or family"):
        cur = _INCOME_INDEX.get(s.get("income_bracket"))
        cap = _INCOME_INDEX["£35,000 – £49,999"]
        if cur is not None and cur > cap:
            s["income_bracket"] = random.choice(_INCOME_LADDER[:cap + 1])

    # ── Religiosity cluster coherence (hard guarantee) ──────────────────────
    # The religiosity items (belief, God-importance, attendance, self-ID,
    # religion-importance) must describe ONE coherent person. Earlier passes
    # reconciled belief against self-ID, but left ATTENDANCE and
    # RELIGION-IMPORTANCE free — producing the "weekly-attending Anglican who
    # rates God 7/10 and finds religion rather important, yet doesn't believe in
    # God and calls himself not religious" contradiction.
    #
    # Approach: derive a religiosity level from the strongest evidence present,
    # then make every item consistent with it. Regular attendance and a high
    # God-importance are strong positive evidence; explicit non-belief is strong
    # negative evidence. Where they conflict, the majority of signals wins.
    _REGULAR = ("Once a week", "More than once a week", "Once a month")
    god = s.get("wvs_importance_of_god")
    believes = s.get("wvs_believe_in_god") == "Yes"
    attends = s.get("wvs_attend_services") in _REGULAR
    self_relig = s.get("wvs_religious_self_id") == "A religious person"
    self_athe = s.get("wvs_religious_self_id") == "An atheist"
    imp_high = s.get("wvs_religion_importance") in ("Very important",
                                                    "Rather important")
    god_high = isinstance(god, (int, float)) and god >= 6

    # Count positive vs negative religiosity signals.
    pos = sum([believes, attends, self_relig, imp_high, god_high])
    neg = sum([not believes, self_athe,
               s.get("wvs_attend_services") == "Never, practically never",
               s.get("wvs_religion_importance") == "Not at all important",
               isinstance(god, (int, float)) and god <= 3])

    if pos >= 3 and not believes:
        # Strong religious profile but stated non-belief → they believe.
        s["wvs_believe_in_god"] = "Yes"
        if self_athe:
            s["wvs_religious_self_id"] = "A religious person"
    elif (not believes) and (attends or god_high or imp_high):
        # Genuine non-believer: strip the religious behaviours/attitudes that
        # contradict it. (A "cultural" attender is allowed only at low
        # frequency, and never with a high God-importance.)
        if attends:
            s["wvs_attend_services"] = random.choices(
                ["Never, practically never", "Less often",
                 "Only on special holy days", "Once a year"],
                weights=[55, 20, 15, 10], k=1)[0]
        if god_high:
            s["wvs_importance_of_god"] = round(random.uniform(1.0, 4.0), 2)
        if imp_high:
            s["wvs_religion_importance"] = random.choices(
                ["Not at all important", "Not very important"],
                weights=[60, 40], k=1)[0]
        if self_relig:
            s["wvs_religious_self_id"] = "Not a religious person"

    # A regular attender should not rate God as unimportant, nor call religion
    # "not at all important" — attendance is a costly signal of commitment. Note
    # we must also fix the SELF-ID here: lifting God-importance for an attender
    # who calls themselves "not a religious person" would just swap one
    # contradiction for another.
    if s.get("wvs_attend_services") in _REGULAR:
        g2 = s.get("wvs_importance_of_god")
        if isinstance(g2, (int, float)) and g2 < 5:
            s["wvs_importance_of_god"] = round(random.uniform(5.5, 9.0), 2)
        if s.get("wvs_religion_importance") == "Not at all important":
            s["wvs_religion_importance"] = random.choices(
                ["Rather important", "Very important", "Not very important"],
                weights=[45, 40, 15], k=1)[0]
        # Regular attendance is incompatible with atheist / "not religious"
        # self-description once God-importance is high.
        if s.get("wvs_religious_self_id") in ("An atheist", "Not a religious person"):
            g3 = s.get("wvs_importance_of_god")
            if isinstance(g3, (int, float)) and g3 >= 6:
                s["wvs_religious_self_id"] = "A religious person"
            elif s.get("wvs_religious_self_id") == "An atheist":
                s["wvs_religious_self_id"] = "Not a religious person"

    # Final guard: "not a religious person" must not rate God highly, whatever
    # path set the values above.
    if s.get("wvs_religious_self_id") in ("An atheist", "Not a religious person"):
        g4 = s.get("wvs_importance_of_god")
        if isinstance(g4, (int, float)) and g4 >= 7:
            s["wvs_religious_self_id"] = "A religious person" \
                if s.get("wvs_attend_services") in _REGULAR \
                else s["wvs_religious_self_id"]
            if s.get("wvs_religious_self_id") in ("An atheist",
                                                  "Not a religious person"):
                s["wvs_importance_of_god"] = round(random.uniform(2.0, 6.0), 2)

    # ── Financial satisfaction ↔ income ────────────────────────────────────
    # Financial satisfaction was sampled independently of income, allowing a
    # perfect 10.0 on a £15-24k income. Contentment on modest means is real, so
    # we don't force a low score — we simply cap the *extreme* top for low
    # incomes (a maxed-out 10 implies real affluence or no money worries at all).
    _inc_i = _INCOME_INDEX.get(s.get("income_bracket"))
    fin = s.get("wvs_financial_satisfaction")
    if _inc_i is not None and isinstance(fin, (int, float)):
        if _inc_i <= _INCOME_INDEX["£15,000 – £24,999"] and fin > 8.5:
            # Low income: allow "content" (up to ~8.5) but not a perfect score,
            # unless they own outright (no housing costs), which softens it.
            ceiling = 9.0 if s.get("housing_tenure") == "Owns outright" else 8.0
            s["wvs_financial_satisfaction"] = round(
                random.uniform(ceiling - 2.0, ceiling), 2)
        elif _inc_i >= _INCOME_INDEX["£100,000 – £149,999"] and fin < 3.0:
            # Very high income with rock-bottom financial satisfaction is odd.
            s["wvs_financial_satisfaction"] = round(random.uniform(4.0, 7.0), 2)

    # ── Welfarism ↔ political leaning / economic left-right ────────────────
    # BSA welfarism (1 = pro-welfare, 5 = anti-welfare) was left almost free, so
    # a self-described "Left" agent could score 4.2 (strongly anti-welfare) while
    # also holding pro-redistribution economic views — a flat contradiction.
    # Welfarism is genuinely cross-cutting (it does NOT collapse into left-right),
    # so we only correct the clear clashes at the extremes and leave the middle
    # ground — cross-pressured people — intact.
    lean = s.get("political_leaning")
    welf = s.get("scale_welfarism")
    lr = s.get("scale_left_right")
    if isinstance(welf, (int, float)):
        strong_left = lean in ("Left", "Far left") or (
            isinstance(lr, (int, float)) and lr <= 2.2)
        strong_right = lean in ("Right", "Far right") or (
            isinstance(lr, (int, float)) and lr >= 3.8)
        if strong_left and welf > 3.6:
            # A clear left-winger who is strongly anti-welfare: pull toward the
            # pro-welfare side, but not all the way (some left voters are welfare
            # sceptics; we just remove the extreme).
            s["scale_welfarism"] = round(random.uniform(2.2, 3.3), 2)
        elif strong_right and welf < 2.0:
            s["scale_welfarism"] = round(random.uniform(2.8, 4.0), 2)

    # ── Political disengagement ↔ strength of political identity ────────────
    # Someone with no political interest, who never discusses politics and never
    # votes, would not usually carry a firm ideological label. Soften the label
    # to a centrist position rather than "Left"/"Far right" etc.
    if s.get("wvs_political_interest") == "Not at all interested" \
            and s.get("wvs_discuss_politics") == "Never" \
            and s.get("wvs_vote_national") in ("Never", "Not allowed to vote") \
            and lean in ("Left", "Far left", "Right", "Far right") \
            and random.random() < 0.8:
        s["political_leaning"] = random.choices(
            ["Center", "Center-left", "Center-right"],
            weights=[60, 20, 20], k=1)[0]


    # Bind the BSA scales, the WVS items and religion into one coherent
    # picture (see _apply_value_coherence for the rationale).
    s = _apply_value_coherence(s)

    # Apply cross-field consistency fixes
    s = _apply_cross_field_consistency(s)
    s = _apply_remaining_consistency_fixes(s)

    # Over-70 dep-children backstop (catches all paths including lone-parent)
    if isinstance(s.get('age'), int) and s['age'] > 70 and             s.get('household_composition') in (
                'Couple with dependent children',
                'Lone parent with dependent children'):
        s['household_composition'] = random.choices(
            ['Couple, no dependent children', 'One-person household',
             'Other household types'],
            weights=[50, 35, 15], k=1)[0]

    # AB grade + no-quals final backstop
    if (s.get('social_grade') or '').startswith('AB')             and s.get('education_level') in ('No formal education', 'Primary school')             and random.random() < 0.95:
        s['education_level'] = random.choices(
            ['Some high school', 'High school diploma / GED',
             'Vocational / Technical degree', "Bachelor's degree",
             "Master's degree"],
            weights=[5, 10, 12, 45, 28], k=1)[0]

    # Marital / household final backstop — runs unconditionally so no
    # upstream pass can reintroduce a divorced/widowed person in a couple hh.
    _ms_b = s.get('marital_status', '')
    _hh_b = s.get('household_composition', '')
    if _ms_b in ('Divorced', 'Separated', 'Widowed', 'Single') \
            and _hh_b in ('Couple with dependent children',
                          'Couple, no dependent children'):
        _ch_b = s.get('children', 0) or 0
        s['household_composition'] = random.choices(
            ['One-person household',
             'Lone parent with dependent children',
             'Other household types'],
            weights=[45, 35 if _ch_b > 0 else 5, 20], k=1)[0]

    # ── Health marginal recalibration ──────────────────────────────────────
    # The multiple downward health pulls (disability, LTS, age) together produce
    # more Bad/VBad than the census marginals. Correct this by probabilistically
    # lifting a fraction of non-disabled, non-LTS agents from Bad→Fair and
    # Fair→Good. This is the correct place to apply the correction: AFTER all
    # coherence passes, so the fix targets residual over-representation only.
    _gh_r = s.get("general_health")
    _ea_r = s.get("economic_activity")
    _db_r = s.get("disability", "")
    _healthy_context = (_ea_r not in ("Economically inactive - long-term sick",)
                        and not _db_r.startswith("Disabled"))
    if _healthy_context:
        if _gh_r == "Bad" and random.random() < 0.78:
            s["general_health"] = "Fair"
        elif _gh_r == "Very bad" and random.random() < 0.65:
            s["general_health"] = "Bad"
        elif _gh_r == "Fair" and isinstance(age, int) and age < 50 and random.random() < 0.30:
            s["general_health"] = "Good"

    # Recalibrate disability after health correction.
    # The multiple disability-adding passes over-produce disabled agents.
    # Correct by relaxing disability where health and activity allow it.
    _gh_after = s.get("general_health")
    _ea_after = s.get("economic_activity")
    _not_lts = _ea_after not in ("Economically inactive - long-term sick",)
    if _gh_after in ("Very good", "Good") and _not_lts:
        if s.get("disability") == "Disabled - day-to-day activities limited a little"                 and random.random() < 0.62:
            s["disability"] = "Not disabled"
        elif s.get("disability") == "Disabled - day-to-day activities limited a lot"                 and random.random() < 0.40:
            s["disability"] = "Disabled - day-to-day activities limited a little"
    elif _gh_after == "Fair" and _not_lts             and s.get("disability") == "Disabled - day-to-day activities limited a little"             and random.random() < 0.30:
        s["disability"] = "Not disabled"

    s = _apply_wellbeing_coherence(s)

    # ── Mean-correction pass ─────────────────────────────────────────────────
    # The correlation passes introduce systematic bias in three continuous fields
    # (left-right, life-sat, god-importance). Rather than deactivating the
    # correlations (which lose real-world structure), we apply a small
    # probabilistic nudge toward the population mean for agents far from it.
    _lr = s.get("scale_left_right")
    _lean = s.get("political_leaning", "")
    _is_right = _lean in ("Right", "Far right", "Center-right")
    if isinstance(_lr, (int, float)) and _lr > 2.6 and not _is_right and random.random() < 0.65:
        s["scale_left_right"] = round(max(1.0, _lr - random.uniform(0.15, 0.50)), 2)
    _ls2 = s.get("wvs_life_satisfaction")
    _gh2 = s.get("general_health", "")
    _unhealthy = _gh2 in ("Very bad", "Bad", "Fair")
    if isinstance(_ls2, (int, float)) and _ls2 < 7.0 and not _unhealthy and random.random() < 0.50:
        s["wvs_life_satisfaction"] = round(min(10.0, _ls2 + random.uniform(0.3, 0.9)), 2)
    _god2 = s.get("wvs_importance_of_god")
    if isinstance(_god2, (int, float)) and _god2 < 4.0 and random.random() < 0.35:
        s["wvs_importance_of_god"] = round(min(10.0, _god2 + random.uniform(0.3, 1.2)), 2)

    # ── FINAL HARD GUARANTEES ───────────────────────────────────────────────
    # Health and happiness both constrain life-satisfaction. Apply them jointly.
    # Also: "Very bad" health + "Very happy" is implausible — soften the
    # happiness to "Quite happy" so the two constraints don't conflict.
    _gh_f  = s.get("general_health")
    _hap_f = s.get("wvs_happiness")
    _ls_f  = s.get("wvs_life_satisfaction")
    if _gh_f == "Very bad" and _hap_f == "Very happy":
        s["wvs_happiness"] = "Quite happy"
        _hap_f = "Quite happy"
    if isinstance(_ls_f, (int, float)):
        _ceil = 10.0
        if _gh_f == "Very bad":  _ceil = 5.5
        elif _gh_f == "Bad":     _ceil = 7.0
        elif _gh_f == "Fair":    _ceil = 8.5
        _floor = 0.0
        if _hap_f == "Very happy":         _floor = 5.0
        elif _hap_f == "Quite happy":      _floor = 3.5
        elif _hap_f == "Not at all happy": _ceil = min(_ceil, 4.0)
        elif _hap_f == "Not very happy":   _ceil = min(_ceil, 5.5)
        _floor = min(_floor, _ceil - 0.5)
        if _ls_f > _ceil or _ls_f < _floor:
            s["wvs_life_satisfaction"] = round(
                random.uniform(_floor, _ceil), 2)

    return s


def sample_england_skeleton(fc: dict | None = None) -> dict:
    """Sample one England-representative demographic skeleton."""
    fc = fc or ENGLAND_FIELD_CONFIGS
    ea = _sample_field(fc.get("economic_activity", {"mode": "na"}))
    # Place & region: drawn from the Census-2021 population distribution
    # (proportional to each local authority's adult population), NOT randomly.
    local_authority, region = _sample_census_place()
    # Occupation SOC group: drawn from THIS local authority's Census-2021
    # (TS063) occupation profile when in employment — not a flat national pick.
    occ = _sample_occupation_for_la(local_authority) if ea in _EMPLOYED else "N/A"

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
        # Religion: basis-switched (blend / census2021)
        "religion":          _sample_field(_resolve_religion_config(fc)),
        # England-specific extensions
        "economic_activity":     ea,
        "occupation_soc":        occ,
        "general_health":        _sample_field(fc.get("general_health",      {"mode": "na"})),
        "disability":            _sample_field(fc.get("disability",          {"mode": "na"})),
        "household_composition": _sample_field(fc.get("household_composition",{"mode": "na"})),
        "social_grade":          _sample_field(fc.get("social_grade",        {"mode": "na"})),
        # Region & local authority now come from the Census-2021 place draw
        # above (population-weighted), replacing the former USoc region pick.
        "region":                region,
        "local_authority":       local_authority,
        "housing_tenure":        _sample_field(fc.get("housing_tenure",      {"mode": "na"})),
        # BSA 2024 continuous attitude scales (1.0–5.0)
        "scale_left_right":      _sample_field(fc.get("scale_left_right",    {"mode": "na"})),
        "scale_lib_auth":        _sample_field(fc.get("scale_lib_auth",      {"mode": "na"})),
        "scale_welfarism":       _sample_field(fc.get("scale_welfarism",     {"mode": "na"})),
    }
    # WVS Wave 7 value dimensions (religious, economic, political, ethical,
    # wellbeing, social, trust/membership) — sampled then lightly correlated.
    s.update(_sample_wvs_fields(fc))
    # Apply the full correlation cascade (see apply_all_correlations for the
    # ordered list and rationale). Kept in one place so every entry point —
    # this sub-tab and the app's general Generate-Sample path — stays identical.
    s = apply_all_correlations(s)
    # Name is drawn in code (not by the LLM) from ethnicity/gender/cohort pools,
    # so a batch has real variety and little overlap.
    _born = (2021 - s["age"]) if isinstance(s.get("age"), int) else None
    s["name"] = pick_name(s.get("ethnicity", ""), s.get("gender", ""), _born)
    return s


def sample_england_skeletons(n: int, fc: dict | None = None) -> list[dict]:
    """Sample n England demographic skeletons (each with a unique name)."""
    reset_used_names()
    return [sample_england_skeleton(fc) for _ in range(n)]


def sample_england_skeleton_validated(
    fc: dict | None = None,
    max_attempts: int = 5,
    fail_on: tuple = ("hard",),
    annotate: bool = True,
):
    """
    Sample ONE skeleton that passes the consistency checker.

    Runs the full generator, validates the result, and re-samples (up to
    max_attempts) if it has any violation whose severity is in `fail_on`
    (default: hard contradictions only). Returns the best skeleton found — if no
    attempt is fully clean, the one with the fewest/lowest-severity issues is
    returned so generation never blocks. When `annotate`, the returned dict
    carries "_validation_score" and "_validation_ok".

    The validator lives in agent_validator.py; if that module is unavailable the
    function degrades gracefully to a single unvalidated sample.
    """
    try:
        from agent_validator import validate_agent
    except Exception:
        return sample_england_skeleton(fc)

    best = None
    best_score = -1.0
    for _ in range(max(1, max_attempts)):
        s = sample_england_skeleton(fc)
        res = validate_agent(s, fail_on=fail_on)
        if annotate:
            s["_validation_score"] = res.score()
            s["_validation_ok"] = res.ok
        if res.ok:
            return s
        if res.score() > best_score:
            best, best_score = s, res.score()
    return best


def sample_england_skeletons_validated(
    n: int,
    fc: dict | None = None,
    max_attempts: int = 5,
    fail_on: tuple = ("hard",),
    annotate: bool = True,
) -> list[dict]:
    """
    Sample n consistency-validated skeletons. Drop-in replacement for
    sample_england_skeletons when you want each agent gated by the checker.

    Each agent is validated before being accepted; agents with hard
    contradictions are re-sampled up to max_attempts times. Because the base
    pass rate is ~95%, this adds only a few percent of overhead on average.
    """
    reset_used_names()
    return [
        sample_england_skeleton_validated(fc, max_attempts, fail_on, annotate)
        for _ in range(n)
    ]


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
    "wvs_happiness":                "happiness",
    "wvs_life_satisfaction":        "life satisfaction",
    "wvs_freedom_of_choice":        "control over life",
    "wvs_financial_satisfaction":   "financial satisfaction",
    "wvs_subjective_health":        "health",
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
        ("region",               "Region of England (ONS Census 2021 population-weighted)"),
        ("local_authority",      "Local authority district (ONS Census 2021 population-weighted - the person MUST live within this district)"),
        ("urban_rural",          "Area type (ONS Urban-Rural Classification 2021)"),
        ("education_level",      "Highest qualification (ONS TS067)"),
        ("economic_activity",    "Economic activity status (ONS TS066)"),
        ("occupation_soc",       "Occupation SOC 2020 major group (ONS TS063) - if in employment"),
        ("social_grade",         "Approximated Social Grade / NS-SEC (ONS ASG 2021)"),
        ("income_bracket",       "Annual gross household income (GBP, £; ONS FYE 2024 distribution)"),
        ("general_health",       "Self-reported general health (ONS TS037)"),
        ("disability",           "Disability status (Equality Act 2010 - ONS TS038)"),
        ("political_leaning",    "Political leaning (WVS Wave 7 left-right self-placement, Q240)"),
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

    constraints      = "\n".join(constraint_lines)
    # Belt-and-braces: make the fixed employment status unmissable so the LLM
    # never invents retirement for a young / non-retired person.
    _ea  = skeleton.get("economic_activity", "")
    _age = skeleton.get("age")
    if _ea and _ea != "Retired":
        constraints += (
            f"\n\nEMPLOYMENT STATUS IS FIXED: this person's status is "
            f"\"{_ea}\""
            + (f" and they are {_age} years old" if isinstance(_age, int) else "")
            + ". They are NOT retired — do not describe them as retired, "
            "semi-retired, or a pensioner anywhere in the persona."
        )
    region           = skeleton.get("region", "England")
    local_authority  = skeleton.get("local_authority", "")
    # Name is pre-selected in code (see pick_name) for variety; the LLM must use
    # it verbatim rather than inventing one.
    fixed_name       = skeleton.get("name", "")

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
        '  "name": "'
        + fixed_name
        + '",\n'
        '  "occupation": "specific job title consistent with the SOC group, '
        'education, income, economic activity status AND age/career stage",\n'
        '  "city": "a real city, town, or village located WITHIN the '
        + (local_authority or region)
        + ' local authority district, in the '
        + region
        + ' region of England"'
        + tier_fields
        + "\n}\n\n"
        "Critical rules:\n"
        "1. The person MUST live in ENGLAND — not Wales, Scotland, or Northern Ireland.\n"
        "2. Ethnic group, health, disability, and economic activity are FIXED — do not change them.\n"
        "3. The \"name\" field is already set — copy it EXACTLY as given, do not "
        "change, translate, or substitute it. Build the person's story around it.\n"
        "4. Occupation and life story must match the FIXED economic activity "
        "status shown above. Do NOT call the person retired unless that status "
        "is exactly \"Retired\" — nobody under 60 is retired. A full-time student "
        "is a student (optionally with a part-time job); an unemployed person is "
        "job-seeking; describe a former/most-recent occupation ONLY when the "
        "status is \"Retired\". Job seniority must fit the person's age: no "
        "20-somethings as CEOs, directors, partners or 'Head of' / 'Senior' roles "
        "— those imply age 35+.\n"
        "5. Health condition and disability must plausibly shape backstory and daily routine.\n"
        "6. Education, income and social grade must be mutually consistent.\n"
        "7. The economic, social and welfare attitude scores above describe this "
        "person's actual values — their life story, beliefs and media habits must "
        "be consistent with them, and may differ from their headline political "
        "leaning (real people are often cross-pressured).\n"
        "8. Make this a specific, believable English person with realistic regional quirks.\n"
        "9. The city/town/village MUST be a real settlement located within the "
        "fixed local authority district given above — this district and region are "
        "population-weighted from Census 2021 and MUST NOT be changed.\n"
        "10. Return raw JSON only. No text before or after the JSON object."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  AGENT BUILDER  (extends generate_agent_from_skeleton for England fields)
# ══════════════════════════════════════════════════════════════════════════════

def _reconcile_persona_freetext(data: dict, skeleton: dict) -> dict:
    """
    Make the LLM's free-text `occupation` (and `city`) consistent with the
    validated structured skeleton. Corrects the two failure modes that make a
    persona read as incoherent:

      1. Economic activity mismatch — a non-employed person (retired, student,
         long-term sick, etc.) given a current job title, or an employed person
         left with no occupation.
      2. SOC-group mismatch — an employed person's job title implying a very
         different skill tier than their validated SOC major group.

    Corrections are conservative: they only fire on a clear contradiction, and
    they fall back to a representative title for the person's actual SOC group
    rather than inventing detail. The LLM's wording is kept whenever it's
    already consistent.
    """
    if not isinstance(data, dict):
        return data

    ea = skeleton.get("economic_activity")
    soc = skeleton.get("occupation_soc")
    occ_text = (data.get("occupation") or "").strip()

    # Representative job titles per SOC 2020 major group, used only as a
    # fallback when the LLM's title is missing or clearly off-tier.
    _SOC_TITLES = {
        "Managers, directors and senior officials":
            ["operations manager", "retail store manager", "office manager"],
        "Professional occupations":
            ["secondary school teacher", "registered nurse", "solicitor",
             "software engineer", "accountant"],
        "Associate professional and technical":
            ["paramedic", "IT support technician", "estate agent",
             "graphic designer"],
        "Administrative and secretarial":
            ["administrative assistant", "payroll clerk", "receptionist"],
        "Skilled trades occupations":
            ["electrician", "plumber", "carpenter", "chef"],
        "Caring, leisure and other service":
            ["care worker", "teaching assistant", "hairdresser"],
        "Sales and customer service":
            ["sales assistant", "call centre operator", "cashier"],
        "Process, plant and machine operatives":
            ["delivery driver", "forklift operator", "machine operative"],
        "Elementary occupations":
            ["warehouse operative", "cleaner", "kitchen porter"],
    }

    _NON_EMPLOYED = {
        "Retired", "Full-time student",
        "Economically inactive - long-term sick",
        "Economically inactive - home or family",
        "Economically inactive - other",
        "Unemployed - seeking work",
    }
    _EMPLOYED = {"Employee - full-time", "Employee - part-time", "Self-employed"}

    # Wording that implies a CURRENT job — inconsistent for the non-employed.
    _CURRENT_JOB_MARKERS = ("works as", "employed as", "currently a",
                            "working as")

    def _looks_like_current_job(text: str) -> bool:
        t = text.lower()
        if not t or t in ("n/a", "none", "unemployed"):
            return False
        # A bare job title (e.g. "electrician") also implies current employment.
        return True

    if ea in _NON_EMPLOYED:
        # The persona should not present a current occupation. Map to an
        # activity-appropriate descriptor, preserving any "former X" phrasing.
        label = {
            "Retired": "retired",
            "Full-time student": "student",
            "Unemployed - seeking work": "unemployed (seeking work)",
            "Economically inactive - long-term sick": "not working (long-term sick)",
            "Economically inactive - home or family": "looking after home/family",
            "Economically inactive - other": "economically inactive",
        }.get(ea, "not in paid work")
        t = occ_text.lower()
        # Keep it only if it already reads as non-employment (retired/former/etc).
        if not any(m in t for m in ("retired", "former", "student",
                                    "unemployed", "not working", "inactive",
                                    "looking after", "home", "family")):
            data["occupation"] = label
    elif ea in _EMPLOYED:
        # Employed: ensure there IS a job title, and that it isn't obviously the
        # wrong tier. We don't hard-verify wording (too brittle), but we fill a
        # representative title when the LLM left it blank or wrote a non-job.
        titles = _SOC_TITLES.get(soc)
        if titles and (not _looks_like_current_job(occ_text)
                       or occ_text.lower() in ("n/a", "none", "unemployed",
                                               "retired", "student")):
            import random as _r
            data["occupation"] = _r.choice(titles)
    # If economic activity is unknown, leave the LLM's text untouched.

    # ── City ↔ region consistency ───────────────────────────────────────────
    # The region is a fixed structural field; the LLM writes the city freely. If
    # it names a well-known city that sits in a DIFFERENT region than the one on
    # the skeleton, correct the region to match the city (the city is the more
    # concrete, human-readable fact, and the persona text will reference it).
    _CITY_REGION = {
        # A representative map of larger English settlements → ONS region.
        "london": "London",
        "birmingham": "West Midlands", "coventry": "West Midlands",
        "wolverhampton": "West Midlands", "stoke-on-trent": "West Midlands",
        "manchester": "North West", "liverpool": "North West",
        "bolton": "North West", "blackpool": "North West",
        "preston": "North West", "salford": "North West",
        "leeds": "Yorkshire and The Humber", "sheffield": "Yorkshire and The Humber",
        "bradford": "Yorkshire and The Humber", "hull": "Yorkshire and The Humber",
        "york": "Yorkshire and The Humber", "huddersfield": "Yorkshire and The Humber",
        "newcastle": "North East", "newcastle upon tyne": "North East",
        "sunderland": "North East", "durham": "North East",
        "middlesbrough": "North East", "gateshead": "North East",
        "nottingham": "East Midlands", "leicester": "East Midlands",
        "derby": "East Midlands", "northampton": "East Midlands",
        "lincoln": "East Midlands",
        "norwich": "East of England", "cambridge": "East of England",
        "ipswich": "East of England", "luton": "East of England",
        "peterborough": "East of England", "colchester": "East of England",
        "southend-on-sea": "East of England", "chelmsford": "East of England",
        "bristol": "South West", "plymouth": "South West", "exeter": "South West",
        "swindon": "South West", "bath": "South West", "gloucester": "South West",
        "bournemouth": "South West", "truro": "South West", "taunton": "South West",
        "brighton": "South East", "oxford": "South East", "reading": "South East",
        "southampton": "South East", "portsmouth": "South East",
        "milton keynes": "South East", "canterbury": "South East",
        "guildford": "South East", "slough": "South East", "hastings": "South East",
    }
    city = (data.get("city") or "").strip().lower()
    if city:
        # match on the leading part of the name (handles "Brighton and Hove")
        mapped = _CITY_REGION.get(city)
        if mapped is None:
            for known, reg in _CITY_REGION.items():
                if city.startswith(known):
                    mapped = reg
                    break
        skel_region = skeleton.get("region")
        if mapped and skel_region and mapped != skel_region:
            # Trust the named city and align the region to it.
            skeleton["region"] = mapped

    return data


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
    # Skeletons from the England sub-tab already carry a unique code-drawn name.
    # Skeletons from the generic Generate-Sample path do not, so draw one here
    # (also unique) instead of letting the LLM invent it.
    if not skeleton.get("name"):
        _born = (2021 - skeleton["age"]) if isinstance(skeleton.get("age"), int) else None
        skeleton["name"] = pick_name(skeleton.get("ethnicity", ""),
                                     skeleton.get("gender", ""), _born)
    prompt     = build_england_prompt(skeleton, tier)
    # Raised from {500, 1100, 1300}: 500 tokens was too small for the full agent
    # JSON when the model wrote a verbose occupation, so the object was truncated
    # mid-field and the JSON never closed — causing "No JSON object found" and
    # only the rare short response surviving. These caps leave ample headroom.
    max_tokens = {"demographics": 2000, "context": 2500, "bigfive": 3000}.get(tier, 1500)

    raw = call_api_fn(
        provider=provider, api_key=api_key, model=model,
        temperature=0.95, max_tokens=max_tokens,
        system_prompt="You are a research assistant. Output only valid JSON, nothing else.",
        messages=[{"role": "user", "content": prompt}],
    )
    data = extract_json_fn(raw)
    na   = lambda v: v if v is not None else "N/A"

    # ── Post-API persona reconciliation ─────────────────────────────────────
    # The skeleton is validated BEFORE the API call, but the LLM writes two free
    # -text fields — `occupation` and `city` — that aren't constrained by the
    # structured skeleton. At temperature 0.95 the model usually honours the
    # prompt's consistency rules, but not always, so we reconcile its output
    # against the FIXED skeleton fields here. This is what stops a persona
    # reading as inconsistent even though its underlying data is coherent.
    data = _reconcile_persona_freetext(data, skeleton)

    agent_id     = str(uuid.uuid4())[:8]
    demographics = {
        # Standard fields (app.py-compatible)
        "name":            skeleton.get("name") or data.get("name", "Unknown"),
        "age":             na(skeleton.get("age")),
        "gender":          na(skeleton.get("gender")),
        "education_level": na(skeleton.get("education_level")),
        "occupation":      data.get("occupation") or "N/A",
        "income_bracket":  na(skeleton.get("income_bracket")),
        "location": {
            "city":            data.get("city") or "N/A",
            "country":         "England",
            "region":          na(skeleton.get("region")),
            "local_authority": na(skeleton.get("local_authority")),
            "urban_rural":     na(skeleton.get("urban_rural")),
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
        # Source provenance for the two refreshed structural fields
        "_ethnicity_source": (
            "Census 2021 TS021 structure + Understanding Society: "
            "Calendar Year Dataset, 2023 refresh"
            if ETHNICITY_RELIGION_BASIS != "census2021"
            else "Census 2021 TS021 (self-identification)"),
        "_religion_source": {
            "blend":      "Census 2021 TS030 categories (denominational split via USoc)",
            "census2021": "Census 2021 TS030 (self-identification)",
        }.get(ETHNICITY_RELIGION_BASIS, "blend"),
    }

    # ── WVS Wave 7 value dimensions, grouped by dimension ───────────────────
    # Stored under persona.values so downstream analysis can slice by
    # dimension. Every field is annotated with its WVS question id.
    #
    # De-duplication (Option A): each topic is listed exactly ONCE. The BSA
    # continuous attitude scales (left_right / lib_auth / welfarism), which used
    # to sit in a separate `attitude_scales` block, are folded into the WVS
    # dimensions they belong to — so economic attitudes appear only under
    # "Economic values", and the social liberty/welfare scales under the
    # political/social dimensions — rather than being listed twice. The
    # structural `religion` identity stays as the single top-level field the app
    # reads, and the WVS religiosity items (how religious, attendance, belief)
    # live under "Religious values"; together they describe religion once, with
    # no repeated fields.
    wvs_values = {}
    for dim, fields in WVS_DIMENSIONS.items():
        block = {}
        for name in fields:
            _dim, qid = DERIVED_FROM_WVS.get(name, (dim, "?"))
            block[name] = {
                "value": na(skeleton.get(name)),
                "wvs_q": qid,
            }
        # Only include dimensions that have at least one field — deleted
        # field groups (e.g. social attitudes, ethical values) leave empty
        # lists in WVS_DIMENSIONS, which produce ugly {} blocks in the output.
        if block:
            wvs_values[dim] = block

    # Fold the BSA attitude scales into their matching WVS dimensions so they're
    # listed once, alongside the related WVS items, instead of in a separate
    # duplicate block. Each carries its own source + interpretation guide.
    def _bsa(scale_key, guide):
        return {"value": na(skeleton.get(scale_key)), "guide": guide,
                "source": "British Social Attitudes 2024 value scales"}

    if "Economic values" in wvs_values:
        wvs_values["Economic values"]["bsa_left_right"] = _bsa(
            "scale_left_right",
            "1=economic left/redistribution .. 5=economic right/free-market")
        wvs_values["Economic values"]["bsa_welfarism"] = _bsa(
            "scale_welfarism",
            "1=pro-welfare-state .. 5=anti-welfare")
    # lib_auth sits with political/participation since it captures social attitudes
    _pol_dim = "Political interest & participation"
    if _pol_dim in wvs_values:
        wvs_values[_pol_dim]["bsa_lib_auth"] = _bsa(
            "scale_lib_auth",
            "1=social libertarian .. 5=social authoritarian")

    demographics["wvs_values"] = wvs_values
    demographics["wvs_values"]["_meta"] = {
        "source": "World Values Survey Wave 7 (2017-2022), UK/Great Britain, "
                  "survey-weighted (W_WEIGHT), N≈2609; BSA 2024 attitude scales "
                  "folded into their matching dimensions (listed once).",
        "scale_note": "Fields ending in a 1-10 range are continuous WVS scales; "
                      "others are the WVS response categories. bsa_* entries are "
                      "the British Social Attitudes 1-5 value scales.",
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
                "ONS Census 2021 TS067 - Highest qualification",
                "ONS Census 2021 TS066 - Economic activity status",
                "ONS Census 2021 TS063 - Occupation SOC 2020 (conditioned on "
                "the agent's local authority; age-consistent seniority)",
                "ONS Census 2021 ASG - Approximated Social Grade",
                "ONS Census 2021 TS037 - General health",
                "ONS Census 2021 TS038 - Disability",
                "ONS Census 2021 population by local authority (mid-2021, single "
                "year of age) - place & region assigned proportional to adult "
                "population, not randomly",
                "ONS HBAI FYE 2024 - Income distribution",
                "Understanding Society Wave 15 - Region, tenure, household, NS-SEC, SF-12, GHQ-12",
                "British Social Attitudes Survey 2024 - Political attitude scales",
                "World Values Survey Wave 7 (2017-2022) UK/GB - Political leaning "
                "(Q240 left-right self-placement); Religious, economic, "
                "political, ethical, wellbeing, social and trust/membership values "
                "(survey-weighted, N≈2609)",
            ],
        },
        "persona": {"demographics": demographics},
        "simulation_config": {
            "provider":    provider,
            "model":       model,
            "temperature": 0.7,
            "max_tokens":  1200,
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
    min_score: float = 0.0,
    validate: bool = True,
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
    min_score       Minimum consistency score a skeleton must meet BEFORE any
                    API call is made for it. Skeletons below this are dropped
                    and replaced with freshly-sampled coherent ones, so no API
                    tokens are ever spent on an incoherent profile. 0.0 blocks
                    only hard-invalid agents (the default guarantee); raise it
                    to also exclude soft-tension agents.
    validate        If True (default), gate skeletons through the validator
                    before the API loop. Set False to skip the gate entirely.
    """
    # ── Pre-API consistency gate ────────────────────────────────────────────
    # Build a pool of n skeletons that all clear the consistency check BEFORE
    # spending a single token. Validation is free; API calls are not.
    if validate:
        skeletons = sample_england_skeletons_validated(
            n, fc, fail_on=("hard",))
        # Drop any that still fall below the requested score and top up with
        # fresh coherent samples, so the caller always gets n gated skeletons.
        skeletons = [s for s in skeletons
                     if s.get("_validation_ok", True)
                     and s.get("_validation_score", 1.0) >= min_score]
        _guard = 0
        while len(skeletons) < n and _guard < 20:
            extra = sample_england_skeletons_validated(
                n - len(skeletons), fc, fail_on=("hard",))
            skeletons += [s for s in extra
                          if s.get("_validation_ok", True)
                          and s.get("_validation_score", 1.0) >= min_score]
            _guard += 1
        skeletons = skeletons[:n]
    else:
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
            # Preserve the pre-API coherence verdict on the saved agent.
            if "_validation_score" in skel:
                agent["_validation_score"] = skel["_validation_score"]
                agent["_validation_ok"] = skel.get("_validation_ok", True)
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
| ONS FYE 2024 | Income (GBP household-income brackets) |
| Understanding Society Wave 15 (2023-24) | Region, housing tenure, household size, NS-SEC, SF-12, GHQ-12 |
| British Social Attitudes Survey 2024 | Left-right, libertarian-authoritarian, welfare and immigration attitude scales |
| **World Values Survey Wave 7 (2017-2022) UK/GB** | **Political leaning (Q240 left-right self-placement) + seven value dimensions (below), survey-weighted, N≈2609** |

**Ethnicity & religion basis switch (`ETHNICITY_RELIGION_BASIS`)**

- `"blend"` *(default)* — Census 2021 category structure, ethnicity nudged to a 2023 base with Understanding Society Calendar Year 2023; religion totals kept at Census 2021 TS030 self-identification, split across Understanding Society denomination categories.
- `"census2021"` — pure ONS Census 2021 self-identification (TS021 / TS030).


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

**Correlated adjustments applied at skeleton stage**

Fields are sampled from their own census/survey marginals, then four passes
add the strongest real-world correlations so agents are internally coherent
(the code has no full joint-distribution table).

*Age → life course:*
- Under 22: redirected to student or part-time employment
- 66+: redirected to retirement (80%) or part-time/self-employed (20%)
- Under 24: kept out of director/senior tiers; degrees gated by age
- 70+: 45% chance of health resampled downward; 35% chance of disability flag
- Under 35: outright homeownership replaced with renting; 65+: mortgage → outright

*Age → marital status → household (NEW):* marital status resampled from
ONS TS002 age-band tables (no more teenage widows/divorcees), then household
composition reconciled so partnered people aren't in lone-parent households,
single people aren't in couple households, and child counts match the
household label.

*Education → occupation → social grade → income (NEW):* qualifications gate
occupation (graduates skew to professional/managerial, low-education kept out
of full professional roles); occupation drives Approximated Social Grade
(ASG is derived from occupation); education/occupation/grade set income
floors and ceilings. Nudges are probabilistic, so graduate under-employment
and non-graduate progression both survive — the tails are preserved.

*Health ↔ disability ↔ economic activity (NEW):* health and disability are
made internally consistent (limited-a-lot rarely co-occurs with "very good"
health), the long-term-sick state implies poor health/disability, and
working-age people who are badly unwell have a raised chance of economic
inactivity.

*Housing tenure ↔ age ↔ income ↔ social grade (NEW):* social rent
concentrated in low income + DE grade; ownership in higher income + AB/C1;
private rent skews younger — layered on top of the existing age gradient.

*Ethnicity ↔ religion ↔ urban/rural (NEW):* religion is conditioned on
ethnicity (Muslim among Pakistani/Bangladeshi/Arab, Hindu/Sikh among Indian,
predominantly Christian among Black groups, no-religion/Anglican among White
British), and minority groups are pulled toward urban areas while White
British retains a rural presence. Region already reflects minority geography
via the population-weighted local-authority draw.

*Attitudes (NEW):* higher education (reinforced by younger age) shifts the
libertarian–authoritarian scale toward the libertarian pole — one of England's
strongest attitude correlations. The economic left–right ↔ income/grade link
is deliberately weak, and welfarism is kept cross-cutting, matching the real
(modest) relationship rather than an idealised one.

*WVS values:* religiosity ↔ moral traditionalism (homosexuality, abortion,
euthanasia, sex-before-marriage, divorce), political interest ↔ participation,
generalised ↔ stranger trust, life ↔ financial satisfaction.
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

        eng_min_score = st.slider(
            "Minimum consistency score (before any API cost)",
            min_value=0.0, max_value=1.0, value=0.0, step=0.05,
            key="eng_min_score",
            help="Every skeleton is validated for internal consistency BEFORE "
                 "it is sent to the API. Any below this score are regenerated "
                 "for free, so no tokens are spent on incoherent profiles. "
                 "0.00 blocks only hard contradictions; raise it to also exclude "
                 "soft tensions.",
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
            "age", "gender", "ethnicity", "religion", "region", "local_authority", "urban_rural",
            "education_level", "economic_activity", "occupation_soc",
            "general_health", "disability", "political_leaning",
            "scale_left_right","scale_welfarism",
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
            "wvs_econ_income_equality", "wvs_political_interest","wvs_happiness", "wvs_life_satisfaction",
            "wvs_generalised_trust", "wvs_confidence_police",
            "wvs_member_sport",]
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
                min_score=float(st.session_state.get("eng_min_score", 0.0)),
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
