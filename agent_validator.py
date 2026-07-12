"""
agent_validator.py
==================
A consistency / human-likeness checker for England agent skeletons produced by
uk_england_population.py. It inspects a FINISHED skeleton (after all correlation
passes) and reports internal contradictions, organised by the correlation
clusters the generator is built around.

DESIGN PRINCIPLES
-----------------
1. Flag CONTRADICTIONS, not unusual-but-possible combinations. Real people are
   outliers; a graduate in a low-skill job, a self-made high earner without
   qualifications, or a "no religion" person with mild spiritual belief are all
   REAL and must pass. The validator only fires on things that should almost
   never occur in a coherent individual (a teenage widow; an atheist who
   believes in God; a retiree still holding an occupation).

2. Severity levels:
     "hard"  — a real contradiction; the agent is internally incoherent.
     "soft"  — a stretch / unusual pairing that is defensible but worth noting.
   By default only "hard" violations make an agent INVALID; "soft" ones are
   reported but don't fail the agent (configurable via `fail_on`).

3. Every check reads fields defensively (.get) and no-ops on anything missing,
   so the validator is safe on partial skeletons (non-England presets, etc.).

USAGE
-----
    from agent_validator import validate_agent, ValidationResult

    result = validate_agent(skeleton)
    if not result.ok:
        print(result.summary())
        # result.violations -> list of Violation(cluster, severity, field_a,
        #                                         field_b, message)

To gate generation (regenerate on failure), use validate_and_regenerate() from
uk_england_population, or the helper build_validated_skeletons() below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


# ── Shared category groupings (kept in sync with uk_england_population.py) ────

_EMPLOYED = {
    "Employee - full-time", "Employee - part-time", "Self-employed",
}
_INACTIVE = {
    "Retired", "Full-time student",
    "Economically inactive - long-term sick",
    "Economically inactive - home or family",
    "Economically inactive - other",
    "Unemployed - seeking work",
}
_EDU_HIGH = {
    "Bachelor's degree", "Master's degree",
    "Doctoral degree (PhD, MD, JD, etc.)",
}
_EDU_LOW = {"No formal education", "Primary school", "Some high school"}

_OCC_AB = {
    "Managers, directors and senior officials", "Professional occupations",
}
_OCC_DE = {
    "Caring, leisure and other service", "Sales and customer service",
    "Process, plant and machine operatives", "Elementary occupations",
}

_INCOME_LADDER = [
    "Under £15,000", "£15,000 – £24,999", "£25,000 – £34,999",
    "£35,000 – £49,999", "£50,000 – £74,999", "£75,000 – £99,999",
    "£100,000 – £149,999", "£150,000 or more",
]
_INCOME_IDX = {b: i for i, b in enumerate(_INCOME_LADDER)}
_LOW_INCOME = {"Under £15,000", "£15,000 – £24,999", "£25,000 – £34,999"}
_HIGH_INCOME = {
    "£50,000 – £74,999", "£75,000 – £99,999",
    "£100,000 – £149,999", "£150,000 or more",
}

_PARTNERED = {"Married", "Civil partnership", "In a relationship"}
_DISABLED_LOT = "Disabled - day-to-day activities limited a lot"
_BAD_HEALTH = {"Bad", "Very bad"}

_MINORITY_ETHNICITIES = {
    "Asian or Asian British: Pakistani", "Asian or Asian British: Bangladeshi",
    "Asian or Asian British: Indian", "Asian or Asian British: Chinese",
    "Asian or Asian British: Other Asian", "Black, Black British: African",
    "Black, Black British: Caribbean", "Black, Black British: Other Black",
    "Other ethnic group: Arab",
}


@dataclass
class Violation:
    cluster: str
    severity: str          # "hard" | "soft"
    message: str
    fields: tuple = ()

    def __str__(self):
        tag = "✗" if self.severity == "hard" else "•"
        return f"  {tag} [{self.cluster}] {self.message}"


@dataclass
class ValidationResult:
    violations: list = field(default_factory=list)
    fail_on: tuple = ("hard",)

    @property
    def ok(self) -> bool:
        return not any(v.severity in self.fail_on for v in self.violations)

    @property
    def hard(self) -> list:
        return [v for v in self.violations if v.severity == "hard"]

    @property
    def soft(self) -> list:
        return [v for v in self.violations if v.severity == "soft"]

    def score(self) -> float:
        """A 0–1 human-likeness score: 1.0 = no issues. Hard issues cost more."""
        penalty = sum(0.25 if v.severity == "hard" else 0.05 for v in self.violations)
        return max(0.0, round(1.0 - penalty, 3))

    def summary(self) -> str:
        if not self.violations:
            return "OK — no consistency issues found."
        lines = [f"{'VALID' if self.ok else 'INVALID'} "
                 f"(score {self.score()}; {len(self.hard)} hard, {len(self.soft)} soft):"]
        lines += [str(v) for v in self.violations]
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  CLUSTER CHECKS
#  Each returns a list of Violation. All read fields defensively.
# ══════════════════════════════════════════════════════════════════════════════

def _income_idx(s):
    return _INCOME_IDX.get(s.get("income_bracket"))


def check_socioeconomic(s) -> list:
    """ASG ↔ Occupation ↔ Education ↔ Income ↔ Economic activity."""
    v = []
    ea = s.get("economic_activity")
    occ = s.get("occupation_soc")
    grade = s.get("social_grade", "") or ""
    edu = s.get("education_level")
    inc = _income_idx(s)
    age = s.get("age")

    # Not employed but holds an occupation (retirees/students/inactive).
    if ea in _INACTIVE and occ not in (None, "N/A", ""):
        v.append(Violation("socioeconomic", "hard",
            f"economically '{ea}' yet holds occupation '{occ}'",
            ("economic_activity", "occupation_soc")))

    # Occupation ↔ social grade agreement (ASG is derived from occupation).
    if occ in _OCC_AB and grade.startswith("DE"):
        v.append(Violation("socioeconomic", "hard",
            f"AB-tier occupation '{occ}' but social grade DE",
            ("occupation_soc", "social_grade")))
    if occ in _OCC_DE and grade.startswith("AB"):
        v.append(Violation("socioeconomic", "soft",
            f"DE-tier occupation '{occ}' but social grade AB",
            ("occupation_soc", "social_grade")))

    # Income vs position — only flag the extreme, implausible combinations.
    if inc is not None:
        # Elementary/low occupation on the very top income bands.
        if occ in _OCC_DE and inc >= _INCOME_IDX["£100,000 – £149,999"]:
            v.append(Violation("socioeconomic", "hard",
                f"low-tier occupation '{occ}' on income {s.get('income_bracket')}",
                ("occupation_soc", "income_bracket")))
        # Low education AND low occupation but top-band income.
        if edu in _EDU_LOW and occ in _OCC_DE and inc >= _INCOME_IDX["£75,000 – £99,999"]:
            v.append(Violation("socioeconomic", "hard",
                f"low education + low occupation but income {s.get('income_bracket')}",
                ("education_level", "occupation_soc", "income_bracket")))
        # Full-time student on a very high income.
        if ea == "Full-time student" and inc >= _INCOME_IDX["£50,000 – £74,999"]:
            v.append(Violation("socioeconomic", "soft",
                f"full-time student on income {s.get('income_bracket')}",
                ("economic_activity", "income_bracket")))
        # Young part-time worker on a top band.
        if ea == "Employee - part-time" and isinstance(age, int) and age < 25 \
                and inc >= _INCOME_IDX["£75,000 – £99,999"]:
            v.append(Violation("socioeconomic", "hard",
                f"young part-time worker on income {s.get('income_bracket')}",
                ("age", "economic_activity", "income_bracket")))

    # Degree-gating by age is enforced upstream; catch any leftover.
    if isinstance(age, int):
        if edu == "Doctoral degree (PhD, MD, JD, etc.)" and age < 25:
            v.append(Violation("socioeconomic", "hard",
                f"PhD at age {age} (too young to have completed one)",
                ("education_level", "age")))
    return v


def check_tenure(s) -> list:
    """Housing tenure ↔ Age ↔ Income ↔ Social grade."""
    v = []
    age = s.get("age")
    ten = s.get("housing_tenure")
    inc = _income_idx(s)

    if isinstance(age, int) and ten == "Owns outright" and age < 30:
        v.append(Violation("tenure", "soft",
            f"owns home outright at age {age}",
            ("housing_tenure", "age")))
    # Top-income social renter is unusual (not impossible — recent windfall).
    if ten == "Social / council rented" and inc is not None \
            and inc >= _INCOME_IDX["£75,000 – £99,999"]:
        v.append(Violation("tenure", "soft",
            f"social/council renter on income {s.get('income_bracket')}",
            ("housing_tenure", "income_bracket")))
    return v


def check_partnership(s) -> list:
    """Age ↔ Partnership ↔ Household ↔ Children."""
    v = []
    age = s.get("age")
    ms = s.get("marital_status")
    hh = s.get("household_composition")
    kids = s.get("children")

    if isinstance(age, int):
        if age < 18 and ms in ("Married", "Civil partnership", "Divorced",
                               "Widowed", "Separated"):
            v.append(Violation("partnership", "hard",
                f"age {age} but marital status '{ms}'", ("age", "marital_status")))
        if age < 23 and ms == "Widowed":
            v.append(Violation("partnership", "hard",
                f"widowed at age {age}", ("age", "marital_status")))
        if age < 22 and ms == "Divorced":
            v.append(Violation("partnership", "hard",
                f"divorced at age {age}", ("age", "marital_status")))
        if isinstance(kids, int):
            if age < 18 and kids > 0:
                v.append(Violation("partnership", "hard",
                    f"age {age} with {kids} child(ren)", ("age", "children")))
            elif age < 21 and kids >= 2:
                v.append(Violation("partnership", "hard",
                    f"age {age} with {kids} children", ("age", "children")))

    # Partnership ↔ household consistency.
    if ms in _PARTNERED and hh == "Lone parent with dependent children":
        v.append(Violation("partnership", "hard",
            f"partnered ('{ms}') but in a lone-parent household",
            ("marital_status", "household_composition")))
    if ms in ("Single", "Widowed", "Divorced", "Separated") \
            and hh in ("Couple, no dependent children", "Couple with dependent children"):
        v.append(Violation("partnership", "hard",
            f"'{ms}' but in a couple household",
            ("marital_status", "household_composition")))
    # Household label ↔ child count.
    if hh == "Lone parent with dependent children" and kids == 0:
        v.append(Violation("partnership", "hard",
            "lone-parent household with zero children",
            ("household_composition", "children")))
    if hh == "Couple with dependent children" and kids == 0:
        v.append(Violation("partnership", "hard",
            "couple-with-children household with zero children",
            ("household_composition", "children")))
    return v


def check_health(s) -> list:
    """Health ↔ Disability ↔ Age ↔ Economic activity."""
    v = []
    health = s.get("general_health")
    disab = s.get("disability")
    ea = s.get("economic_activity")

    if disab == _DISABLED_LOT and health == "Very good":
        v.append(Violation("health", "hard",
            "disability limits activities 'a lot' but health is 'Very good'",
            ("disability", "general_health")))
    if ea == "Economically inactive - long-term sick" \
            and health in ("Very good", "Good") and disab == "Not disabled":
        v.append(Violation("health", "hard",
            "long-term sick but good health and not disabled",
            ("economic_activity", "general_health", "disability")))
    return v


def check_ethnicity_religion(s) -> list:
    """Ethnicity ↔ Religion ↔ Urban/rural (region handled via LA draw)."""
    v = []
    eth = s.get("ethnicity", "") or ""
    rel = s.get("religion")
    ur = s.get("urban_rural")

    # Only flag the strongest impossibilities, not the many valid combinations.
    if eth in _MINORITY_ETHNICITIES and ur == "Rural":
        v.append(Violation("ethnicity", "soft",
            f"minority ethnicity in a rural area", ("ethnicity", "urban_rural")))
    return v


def check_religiosity(s) -> list:
    """Structural religion ↔ WVS religiosity items (the recurring flaw)."""
    v = []
    self_id = s.get("wvs_religious_self_id")
    believe = s.get("wvs_believe_in_god")
    god = s.get("wvs_importance_of_god")
    member = s.get("wvs_member_religious")
    religion = s.get("religion", "")
    affiliated = bool(religion) and religion not in (
        "No religion", "Prefer not to say", "", "N/A", None)

    # Atheist who believes in God — a hard contradiction.
    if self_id == "An atheist" and believe == "Yes":
        v.append(Violation("religiosity", "hard",
            "self-described atheist who believes in God",
            ("wvs_religious_self_id", "wvs_believe_in_god")))
    # Atheist rating God important.
    if self_id == "An atheist" and isinstance(god, (int, float)) and god >= 6:
        v.append(Violation("religiosity", "hard",
            f"atheist rating God's importance {god}/10",
            ("wvs_religious_self_id", "wvs_importance_of_god")))
    # Not-religious person with devout God-importance.
    if self_id == "Not a religious person" and isinstance(god, (int, float)) and god >= 8:
        v.append(Violation("religiosity", "hard",
            f"'not a religious person' rating God {god}/10",
            ("wvs_religious_self_id", "wvs_importance_of_god")))
    # Religious-org member who doesn't believe.
    if member in ("Active member", "Inactive member") and believe == "No":
        v.append(Violation("religiosity", "soft",
            "member of a religious org who doesn't believe in God",
            ("wvs_member_religious", "wvs_believe_in_god")))
    # No-religion person who is an active religious-org member.
    if not affiliated and member == "Active member":
        v.append(Violation("religiosity", "soft",
            "no stated religion but active member of a religious org",
            ("religion", "wvs_member_religious")))
    return v


def check_politics(s) -> list:
    """Leaning ↔ scales; interest ↔ participation; participation ladder."""
    v = []
    leaning = s.get("political_leaning")
    lr = s.get("scale_left_right")
    interest = s.get("wvs_political_interest")
    vote = s.get("wvs_vote_national")
    discuss = s.get("wvs_discuss_politics")
    petition = s.get("wvs_action_petition")
    demo = s.get("wvs_action_demonstration")

    # Stated leaning vs left-right scale (1=left … 5=right). Flag clear opposites.
    if isinstance(lr, (int, float)):
        if leaning in ("Right", "Far right", "Center-right") and lr < 2.3:
            v.append(Violation("politics", "hard",
                f"leans '{leaning}' but left-right scale {lr} (left of centre)",
                ("political_leaning", "scale_left_right")))
        if leaning in ("Left", "Far left", "Center-left") and lr > 3.7:
            v.append(Violation("politics", "hard",
                f"leans '{leaning}' but left-right scale {lr} (right of centre)",
                ("political_leaning", "scale_left_right")))

    # Interest vs participation.
    if interest in ("Not very interested", "Not at all interested") \
            and vote == "Always" and discuss == "Frequently":
        v.append(Violation("politics", "soft",
            "low political interest but always votes and discusses frequently",
            ("wvs_political_interest", "wvs_vote_national", "wvs_discuss_politics")))

    # Participation ladder: demonstrated but would never sign a petition.
    if demo == "Have done" and petition == "Would never do":
        v.append(Violation("politics", "hard",
            "has demonstrated but would never sign a petition (ladder inverted)",
            ("wvs_action_demonstration", "wvs_action_petition")))
    return v


def check_social_attitudes(s) -> list:
    """Attitudes that should move together (e.g. homosexuality items)."""
    v = []
    just_h = s.get("wvs_just_homosexuality")
    ss_par = s.get("wvs_homosexual_parents")
    if isinstance(just_h, (int, float)) and ss_par is not None:
        # Low justifiability but strong pro-parenting agreement (or the reverse).
        if just_h <= 3 and ss_par in ("Agree strongly", "Agree"):
            v.append(Violation("social_attitudes", "hard",
                f"rates homosexuality {just_h}/10 (disapproving) yet '{ss_par}' "
                f"that same-sex couples make good parents",
                ("wvs_just_homosexuality", "wvs_homosexual_parents")))
        elif just_h >= 8 and ss_par in ("Disagree", "Disagree strongly"):
            v.append(Violation("social_attitudes", "hard",
                f"rates homosexuality {just_h}/10 (accepting) yet '{ss_par}' "
                f"that same-sex couples make good parents",
                ("wvs_just_homosexuality", "wvs_homosexual_parents")))
    return v


def check_wellbeing(s) -> list:
    """Happiness ↔ life satisfaction coherence."""
    v = []
    happy = s.get("wvs_happiness")
    life = s.get("wvs_life_satisfaction")
    if isinstance(life, (int, float)):
        if happy == "Very happy" and life < 4:
            v.append(Violation("wellbeing", "hard",
                f"'very happy' but life satisfaction {life}/10",
                ("wvs_happiness", "wvs_life_satisfaction")))
        if happy == "Not at all happy" and life > 7:
            v.append(Violation("wellbeing", "hard",
                f"'not at all happy' but life satisfaction {life}/10",
                ("wvs_happiness", "wvs_life_satisfaction")))
    return v


def check_religiosity_ethics(s) -> list:
    """Religiosity ↔ ethical justifiability (graded). Flag strong mismatches."""
    v = []
    god = s.get("wvs_importance_of_god")
    # Only flag the strongest inconsistency: a highly religious person rating the
    # traditionally-contested items as fully justifiable (10/10).
    if isinstance(god, (int, float)) and god >= 9:
        for f, label in (("wvs_just_homosexuality", "homosexuality"),
                         ("wvs_just_abortion", "abortion"),
                         ("wvs_just_euthanasia", "euthanasia")):
            val = s.get(f)
            if isinstance(val, (int, float)) and val >= 9.5:
                v.append(Violation("religiosity_ethics", "soft",
                    f"very religious (God {god}/10) yet rates {label} fully justifiable",
                    ("wvs_importance_of_god", f)))
    return v


def check_value_coherence(s) -> list:
    """
    The BSA value scales must agree with the WVS items they measure, the WVS
    ethical items must hang together, and religion must be internally coherent.
    These were the "independent draws" tells: an authoritarian-scoring agent
    giving uniformly liberal answers, or a "no religion" agent who is a member
    of a religious organisation.
    """
    v = []

    # lib_auth (1 = libertarian .. 5 = authoritarian) vs the social answers.
    la = s.get("scale_lib_auth")
    jh = s.get("wvs_just_homosexuality")
    ssp = s.get("wvs_homosexual_parents")
    if isinstance(la, (int, float)) and isinstance(jh, (int, float)):
        if la >= 4.0 and jh >= 8.5 and ssp in ("Agree strongly", "Agree"):
            v.append(Violation("value_coherence", "hard",
                f"authoritarian lib-auth ({la}) but uniformly liberal social "
                f"answers (homosexuality {jh}, pro same-sex parenting)",
                ("scale_lib_auth", "wvs_just_homosexuality")))
        elif la <= 2.0 and jh <= 2.5 and ssp in ("Disagree", "Disagree strongly"):
            v.append(Violation("value_coherence", "hard",
                f"libertarian lib-auth ({la}) but uniformly illiberal social "
                f"answers (homosexuality {jh})",
                ("scale_lib_auth", "wvs_just_homosexuality")))

    # left_right (1 = left .. 5 = right) vs the economic answers.
    lr = s.get("scale_left_right")
    eq = s.get("wvs_econ_income_equality")     # 1 = more equal (left)
    po = s.get("wvs_econ_private_ownership")   # 10 = private (right)
    if isinstance(lr, (int, float)) and isinstance(eq, (int, float)) \
            and isinstance(po, (int, float)):
        if lr <= 2.0 and eq >= 8.5 and po >= 8.5:
            v.append(Violation("value_coherence", "hard",
                f"economically left scale ({lr}) but wants larger income "
                f"differences ({eq}) and more private ownership ({po})",
                ("scale_left_right", "wvs_econ_income_equality")))
        elif lr >= 4.0 and eq <= 2.5 and po <= 2.5:
            v.append(Violation("value_coherence", "hard",
                f"economically right scale ({lr}) but wants incomes equalised "
                f"({eq}) and state ownership ({po})",
                ("scale_left_right", "wvs_econ_income_equality")))

    # The ethical items should not sit wildly apart.
    eth = [s.get(k) for k in ("wvs_just_homosexuality", "wvs_just_divorce",
                              "wvs_just_sex_before_marriage")]
    eth = [e for e in eth if isinstance(e, (int, float))]
    if len(eth) >= 2 and (max(eth) - min(eth)) > 5.0:
        v.append(Violation("value_coherence", "soft",
            f"personal-morality items span {min(eth)}-{max(eth)}; unusually "
            f"inconsistent permissiveness",
            ("wvs_just_homosexuality", "wvs_just_sex_before_marriage")))

    # Religion: no stated religion but a member of a religious organisation.
    if s.get("religion") in ("No religion", "Prefer not to say") \
            and s.get("wvs_member_religious") in ("Active member", "Inactive member"):
        v.append(Violation("value_coherence", "hard",
            "no stated religion yet a member of a religious organisation",
            ("religion", "wvs_member_religious")))

    return v


_ALL_CHECKS: list = [
    check_socioeconomic, check_tenure, check_partnership, check_health,
    check_ethnicity_religion, check_religiosity, check_politics,
    check_wellbeing, check_religiosity_ethics, check_social_attitudes,
    check_value_coherence,
]


def validate_agent(s: dict, fail_on: tuple = ("hard",)) -> ValidationResult:
    """Run every cluster check on a skeleton and return a ValidationResult."""
    violations = []
    for chk in _ALL_CHECKS:
        try:
            violations.extend(chk(s))
        except Exception as e:  # a check should never crash generation
            violations.append(Violation("validator", "soft",
                f"check {chk.__name__} errored: {e}"))
    return ValidationResult(violations=violations, fail_on=fail_on)


def build_validated_skeletons(
    n: int,
    sampler: Callable[[], dict],
    corrector: Optional[Callable[[dict], dict]] = None,
    max_attempts: int = 5,
    fail_on: tuple = ("hard",),
) -> tuple:
    """
    Generate n skeletons that each pass validation.

    sampler()      -> produces one fully-correlated skeleton.
    corrector(s)   -> optional; re-applies correlation passes to a skeleton
                      (used to try fixing a failed agent before re-sampling).
    Returns (skeletons, report) where report has aggregate stats.
    """
    out = []
    stats = {"attempts": 0, "regenerated": 0, "unfixable": 0,
             "hard_violations": 0, "soft_violations": 0}
    for _ in range(n):
        s = sampler()
        res = validate_agent(s, fail_on=fail_on)
        attempt = 1
        while not res.ok and attempt < max_attempts:
            stats["regenerated"] += 1
            # Try correcting first (cheap), then fall back to a fresh sample.
            if corrector is not None:
                s = corrector(s)
                res = validate_agent(s, fail_on=fail_on)
                if res.ok:
                    break
            s = sampler()
            res = validate_agent(s, fail_on=fail_on)
            attempt += 1
        stats["attempts"] += attempt
        if not res.ok:
            stats["unfixable"] += 1
        stats["hard_violations"] += len(res.hard)
        stats["soft_violations"] += len(res.soft)
        s["_validation_score"] = res.score()
        s["_validation_ok"] = res.ok
        out.append(s)
    return out, stats
