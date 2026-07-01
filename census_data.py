"""
census_data.py
================
Provides COUNTRY_PRESETS for the "Preset country (census-approximate)" mode
in Generate Sample > Configure & Generate.

This build contains a single preset — United Kingdom (England) — and is now a
FULL-PARITY preset. Every field the dedicated England generator
(uk_england_population.py) samples is exposed here, drawn from the single
source of truth ENGLAND_FIELD_CONFIGS / WVS_FIELD_CONFIGS, so the preset
route and the "England — 30k" sub-tab produce demographically identical
agents.

────────────────────────────────────────────────────────────────────────────
WHY THIS FILE CHANGED
────────────────────────────────────────────────────────────────────────────
Previously this preset carried only the 11 fields that app.py's base sampler
(_sample_demographic_skeletons) reads by name:
    country, age, gender, education_level, income_bracket, urban_rural,
    political_leaning, marital_status, children, ethnicity, religion
and it set ethnicity=True / religion=True, meaning those two were invented by
the persona-generation LLM rather than sampled from real ONS categories.

That left preset agents much thinner than England-generator agents, and made
ethnicity/religion statistically unanchored. This version fixes both:

  1. ethnicity & religion are now sampled from the real ONS-derived weighted
     category lists (ENGLAND_FIELD_CONFIGS["ethnicity_detailed"] and the
     basis-switched religion config), NOT LLM-guessed.

  2. All the richer England fields — household composition, region, housing
     tenure, social grade, economic activity, occupation, general health,
     disability, the three BSA attitude scales, and the 46 World Values
     Survey Wave 7 value fields — are now produced for preset agents too.

────────────────────────────────────────────────────────────────────────────
HOW THE TWO SHAPES COEXIST  (important integration note)
────────────────────────────────────────────────────────────────────────────
app.py's base sampler only READS the 11 named slots and ignores unknown keys.
So full parity cannot come from config dicts alone — something has to sample
the extra fields. This file does it directly:

  • COUNTRY_PRESETS["United Kingdom"] still provides the 11 base-sampler slots
    as {"mode": ...} distribution dicts, so the existing app.py path keeps
    working unchanged and now yields REAL ONS ethnicity/religion because the
    two booleans became weighted categorical configs.

  • sample_uk_preset_skeleton() / build_uk_preset_skeletons() produce the FULL
    agent skeleton (all 21 demographic fields + BSA scales + WVS values) by
    delegating to uk_england_population.sample_england_skeleton(). Point your
    preset generation call at these to get parity with the England sub-tab.

If your app.py base sampler can be patched to merge any extra keys a preset
supplies, you can instead expose the full config via
UK_PRESET_FULL_CONFIG below. Both routes draw from the same source of truth,
so they cannot drift.
"""

from __future__ import annotations

from uk_england_population import (
    ENGLAND_FIELD_CONFIGS,
    WVS_FIELD_CONFIGS,
    _resolve_religion_config,
    sample_england_skeleton,
    sample_england_skeletons,
)


# ══════════════════════════════════════════════════════════════════════════════
#  BASE-SAMPLER PRESET  (the 11 fields app.py reads by name)
#  Unchanged shape, but ethnicity & religion are now REAL weighted categorical
#  configs instead of the True/True "let the LLM invent it" flags.
# ══════════════════════════════════════════════════════════════════════════════

_UK_PRESET: dict = {
    "country": "United Kingdom",

    "age":               ENGLAND_FIELD_CONFIGS["age"],
    "gender":            ENGLAND_FIELD_CONFIGS["gender"],
    "education_level":   ENGLAND_FIELD_CONFIGS["education_level"],
    "income_bracket":    ENGLAND_FIELD_CONFIGS["income_bracket"],
    "urban_rural":       ENGLAND_FIELD_CONFIGS["urban_rural"],
    "political_leaning": ENGLAND_FIELD_CONFIGS["political_leaning"],
    "marital_status":    ENGLAND_FIELD_CONFIGS["marital_status"],
    "children":          ENGLAND_FIELD_CONFIGS["children"],

    # NOW sampled from real ONS categories (was ethnicity=True / religion=True).
    # ENGLAND_FIELD_CONFIGS keys them "ethnicity_detailed" and (basis-switched)
    # "religion"; app.py's base sampler expects the slots to be named
    # "ethnicity" and "religion", so we map them here.
    "ethnicity": ENGLAND_FIELD_CONFIGS["ethnicity_detailed"],
    "religion":  _resolve_religion_config(ENGLAND_FIELD_CONFIGS),
}


# ══════════════════════════════════════════════════════════════════════════════
#  ENGLAND EXTENSION FIELDS  (the fields BEYOND the base 11)
#  app.py's _sample_demographic_skeletons imports this tuple and, for each name
#  present in the loaded preset, samples it and carries it onto the skeleton.
#  Exposing it here is what lets the PRESET route reach full parity with the
#  dedicated "England — 30k" sub-tab WITHOUT any change to app.py — the base
#  sampler already loops over these; it just needed the list + the configs.
#
#  Order groups demographic/scale fields first, then the 45 WVS value fields.
# ══════════════════════════════════════════════════════════════════════════════

_ENGLAND_EXTENSION_DEMOGRAPHIC: tuple = (
    "household_composition",
    "economic_activity",
    "occupation_soc",
    "social_grade",
    "general_health",
    "disability",
    "region",
    "housing_tenure",
    "scale_left_right",
    "scale_lib_auth",
    "scale_welfarism",
)

# The 45 WVS value fields (religious, economic, political, ethical, wellbeing,
# social, trust/membership), taken live from the single source of truth.
_ENGLAND_EXTENSION_WVS: tuple = tuple(WVS_FIELD_CONFIGS.keys())

ENGLAND_EXTENSION_FIELDS: tuple = (
    _ENGLAND_EXTENSION_DEMOGRAPHIC + _ENGLAND_EXTENSION_WVS
)

# Add every extension field's distribution config to the base preset so the
# base sampler (which reads config dicts) can draw them. The 11 base slots
# above are untouched; these are additive.
for _f in _ENGLAND_EXTENSION_DEMOGRAPHIC:
    # occupation_soc / scales use their ENGLAND_FIELD_CONFIGS entry directly
    _UK_PRESET[_f] = ENGLAND_FIELD_CONFIGS[_f]
for _f in _ENGLAND_EXTENSION_WVS:
    _UK_PRESET[_f] = WVS_FIELD_CONFIGS[_f]

# CAVEAT — base-sampler route vs. full-parity samplers:
# app.py's base sampler draws each field INDEPENDENTLY and does not run the
# age / economic-activity / religiosity correlation passes that
# sample_england_skeleton() applies. So preset-route agents are demographically
# representative on every marginal, but slightly less internally correlated
# (e.g. a retired agent may still receive an occupation_soc; a highly religious
# agent's belief items won't be nudged together). For maximum coherence, drive
# preset generation through build_uk_preset_skeletons() / PRESET_FULL_SAMPLERS
# below, which delegate to the England generator and apply the correlations.


# ══════════════════════════════════════════════════════════════════════════════
#  FULL-PARITY CONFIG  (every field, for a base sampler that can merge extras)
#  Use this if/when app.py's _sample_demographic_skeletons is patched to loop
#  over all provided fields rather than the fixed 11.
# ══════════════════════════════════════════════════════════════════════════════

# Demographic + BSA-scale fields, renamed to the flat skeleton keys that
# uk_england_population.sample_england_skeleton() emits.
_FULL_DEMOGRAPHIC_KEYS: dict = {
    "age":                   ENGLAND_FIELD_CONFIGS["age"],
    "gender":                ENGLAND_FIELD_CONFIGS["gender"],
    "marital_status":        ENGLAND_FIELD_CONFIGS["marital_status"],
    "household_composition": ENGLAND_FIELD_CONFIGS["household_composition"],
    "urban_rural":           ENGLAND_FIELD_CONFIGS["urban_rural"],
    "ethnicity":             ENGLAND_FIELD_CONFIGS["ethnicity_detailed"],
    "religion":              _resolve_religion_config(ENGLAND_FIELD_CONFIGS),
    "education_level":       ENGLAND_FIELD_CONFIGS["education_level"],
    "economic_activity":     ENGLAND_FIELD_CONFIGS["economic_activity"],
    "occupation_soc":        ENGLAND_FIELD_CONFIGS["occupation_soc"],
    "social_grade":          ENGLAND_FIELD_CONFIGS["social_grade"],
    "income_bracket":        ENGLAND_FIELD_CONFIGS["income_bracket"],
    "political_leaning":     ENGLAND_FIELD_CONFIGS["political_leaning"],
    "scale_left_right":      ENGLAND_FIELD_CONFIGS["scale_left_right"],
    "scale_lib_auth":        ENGLAND_FIELD_CONFIGS["scale_lib_auth"],
    "scale_welfarism":       ENGLAND_FIELD_CONFIGS["scale_welfarism"],
    "general_health":        ENGLAND_FIELD_CONFIGS["general_health"],
    "disability":            ENGLAND_FIELD_CONFIGS["disability"],
    "children":              ENGLAND_FIELD_CONFIGS["children"],
    "region":                ENGLAND_FIELD_CONFIGS["region"],
    "housing_tenure":        ENGLAND_FIELD_CONFIGS["housing_tenure"],
}

# Everything, including the 46 WVS value fields, in one config dict.
UK_PRESET_FULL_CONFIG: dict = {
    "country": "United Kingdom",
    **_FULL_DEMOGRAPHIC_KEYS,
    **WVS_FIELD_CONFIGS,
}


# ══════════════════════════════════════════════════════════════════════════════
#  FULL-PARITY SAMPLERS
#  Delegate to the England generator so the preset route and the dedicated
#  "England — 30k" sub-tab are guaranteed to produce identical agents.
#  These return a complete skeleton: all 21 demographic fields, the 3 BSA
#  scales, and all 46 WVS value fields, with age/economic-activity/religiosity
#  correlations already applied.
# ══════════════════════════════════════════════════════════════════════════════

def sample_uk_preset_skeleton() -> dict:
    """One full England-parity skeleton, labelled as the UK preset."""
    s = sample_england_skeleton(ENGLAND_FIELD_CONFIGS)
    s["country"] = "United Kingdom"
    s["preset"] = "United Kingdom (England, census-approximate)"
    return s


def build_uk_preset_skeletons(n: int) -> list[dict]:
    """n full England-parity skeletons for the UK preset."""
    out = sample_england_skeletons(n, ENGLAND_FIELD_CONFIGS)
    for s in out:
        s["country"] = "United Kingdom"
        s["preset"] = "United Kingdom (England, census-approximate)"
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

COUNTRY_PRESETS: dict = {
    "United Kingdom": _UK_PRESET,
}

# Optional richer registry for a full-parity-aware caller.
COUNTRY_PRESETS_FULL: dict = {
    "United Kingdom": UK_PRESET_FULL_CONFIG,
}

# Sampler lookup so a preset-aware generator can pick the full sampler by name.
PRESET_FULL_SAMPLERS: dict = {
    "United Kingdom": build_uk_preset_skeletons,
}
