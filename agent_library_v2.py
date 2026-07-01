"""
agent_library_v2.py  —  Drop-in replacement for ui_my_agents() in app.py
=========================================================================
Two-layer clustering system for the Agent Library tab.

Layer 1  —  Usage clusters
    Survey  |  Unassigned
    Assign/remove agents to a cluster from within the library.
    Tags stored in the agent dict under agent["clusters"] = ["survey", ...]

Layer 2  —  Demographic sub-clusters  (Survey cluster only)
    Auto-computed grid:  Age Band  ×  SES tier  ×  Geography type
    Each cell shows agent count and expands to show agent cards.

Integration (2 lines in app.py):
    from agent_library_v2 import ui_agent_library_v2
    with tab2: ui_agent_library_v2()
"""

from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

# ── These are imported from the outer app namespace ────────────────────────────
# from app import (
#     load_agents, save_agent, delete_agent, update_agent_data,
#     generate_system_prompt, owner_badge_html, current_user,
#     DISPLAY_NAMES, TIER_LABELS,
# )

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

USAGE_CLUSTERS = {
    "survey":      {"label": "Survey",      "icon": "📊", "color": "#1D9E75"},
    "unassigned":  {"label": "Unassigned",  "icon": "📂", "color": "#888780"},
}

# ── Demographic cluster definitions ───────────────────────────────────────────

AGE_BANDS = [
    ("18–24", 18, 24),
    ("25–34", 25, 34),
    ("35–44", 35, 44),
    ("45–54", 45, 54),
    ("55–64", 55, 64),
    ("65+",   65, 120),
]

_EDU_SES_SCORE = {
    "No formal education":               1,
    "Primary school":                    1,
    "Some high school":                  2,
    "High school diploma / GED":         3,
    "Some college (no degree)":          3,
    "Vocational / Technical degree":     4,
    "Associate degree":                  4,
    "Bachelor's degree":                 5,
    "Master's degree":                   6,
    "Doctoral degree (PhD, MD, JD, etc.)": 7,
}

_INC_SES_SCORE = {
    "Under $15,000":        1,
    "$15,000 - $29,999":    2,
    "$30,000 - $49,999":    3,
    "$50,000 - $74,999":    4,
    "$75,000 - $99,999":    5,
    "$100,000 - $149,999":  6,
    "$150,000 - $199,999":  7,
    "$200,000 or more":     8,
}

SES_TIERS = [
    ("Low SES",    1, 3),
    ("Mid SES",    3, 5),
    ("High SES",   5, 9),
]

GEO_TYPES = ["Urban", "Suburban", "Rural", "Unknown"]


# ─────────────────────────────────────────────────────────────────────────────
# CLUSTER TAG HELPERS  (write into agent dict, persist via update_agent_data)
# ─────────────────────────────────────────────────────────────────────────────

def _get_clusters(agent: dict) -> list[str]:
    return agent.get("clusters", [])


def _set_clusters(agent: dict, clusters: list[str], update_fn) -> None:
    """Persist cluster tags on the agent. update_fn = update_agent_data from db."""
    agent["clusters"] = clusters
    ag_copy = {k: v for k, v in agent.items() if k != "_owner"}
    update_fn(ag_copy)


def _add_cluster(agent: dict, cluster_key: str, update_fn) -> None:
    current = _get_clusters(agent)
    if cluster_key not in current:
        _set_clusters(agent, current + [cluster_key], update_fn)


def _remove_cluster(agent: dict, cluster_key: str, update_fn) -> None:
    current = _get_clusters(agent)
    _set_clusters(agent, [c for c in current if c != cluster_key], update_fn)


# ─────────────────────────────────────────────────────────────────────────────
# DEMOGRAPHIC CLUSTERING LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def _safe_age(agent: dict) -> int | None:
    age = agent.get("persona", {}).get("demographics", {}).get("age")
    if age is None or str(age) in ("N/A", "n/a", ""):
        return None
    try:
        return int(age)
    except (ValueError, TypeError):
        return None


def _ses_score(agent: dict) -> float:
    d = agent.get("persona", {}).get("demographics", {})
    edu_s = _EDU_SES_SCORE.get(d.get("education_level", ""), 0)
    inc_s = _INC_SES_SCORE.get(d.get("income_bracket", ""), 0)
    if edu_s and inc_s:
        return (edu_s + inc_s) / 2
    return edu_s or inc_s or 0


def _age_band(agent: dict) -> str:
    age = _safe_age(agent)
    if age is None:
        return "Unknown"
    for label, lo, hi in AGE_BANDS:
        if lo <= age <= hi:
            return label
    return "Unknown"


def _ses_tier(agent: dict) -> str:
    score = _ses_score(agent)
    if score == 0:
        return "Unknown"
    for label, lo, hi in SES_TIERS:
        if lo <= score < hi:
            return label
    return "High SES"


def _geo_type(agent: dict) -> str:
    ur = agent.get("persona", {}).get("demographics", {}).get("location", {}).get("urban_rural", "")
    return ur if ur in ("Urban", "Suburban", "Rural") else "Unknown"


def _build_demo_clusters(agents: list[dict]) -> dict:
    """
    Returns a nested dict:
        result[age_band][ses_tier][geo_type] = [agent, ...]
    Only populated cells are included.
    """
    result: dict = {}
    for ag in agents:
        ab  = _age_band(ag)
        ses = _ses_tier(ag)
        geo = _geo_type(ag)
        result.setdefault(ab, {}).setdefault(ses, {}).setdefault(geo, []).append(ag)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# SHARED AGENT CARD RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def _render_agent_card(
    ag: dict,
    update_fn,
    delete_fn,
    generate_prompt_fn,
    owner_badge_fn,
    DISPLAY_NAMES: dict,
    TIER_LABELS: dict | None = None,   # deprecated: tiers removed; kept for call compatibility
    card_key_suffix: str = "",
):
    """Render a single agent expander card with assign/remove/edit/delete controls."""
    d    = ag.get("persona", {}).get("demographics", {})
    name = d.get("name", "Unnamed")
    age  = d.get("age", "?")
    occ  = d.get("occupation", "") or ""
    loc  = d.get("location", {})
    place = ", ".join(filter(None, [loc.get("city"), loc.get("country")]))
    owner = ag.get("_owner", "")
    current_clusters = _get_clusters(ag)

    cluster_badges = " ".join(
        f"`{USAGE_CLUSTERS[c]['icon']} {USAGE_CLUSTERS[c]['label']}`"
        for c in current_clusters
        if c in USAGE_CLUSTERS
    ) or "`📂 Unassigned`"

    header = (
        f"**{name}** — {age} y.o."
        + (f" — {occ}" if occ and occ != "N/A" else "")
        + (f" — {place}" if place else "")
    )

    aid = ag["agent_id"]
    suffix = f"_{card_key_suffix}" if card_key_suffix else ""

    with st.expander(header, expanded=False):
        # ── Meta row ─────────────────────────────────────────────────────────
        st.markdown(
            f"Created by: {owner_badge_fn(owner)} &nbsp;|&nbsp; {cluster_badges}",
            unsafe_allow_html=True,
        )

        # ── Cluster assignment ────────────────────────────────────────────────
        with st.container():
            st.caption("Assign to usage clusters:")
            cluster_cols = st.columns(4)
            for ci, (ckey, cinfo) in enumerate(USAGE_CLUSTERS.items()):
                if ckey == "unassigned":
                    continue
                with cluster_cols[ci]:
                    already = ckey in current_clusters
                    btn_label = f"{'✓ ' if already else '+ '}{cinfo['icon']} {cinfo['label']}"
                    if st.button(
                        btn_label,
                        key=f"cl_{ckey}_{aid}{suffix}",
                        use_container_width=True,
                        type="secondary",
                    ):
                        if already:
                            _remove_cluster(ag, ckey, update_fn)
                        else:
                            _add_cluster(ag, ckey, update_fn)
                        st.rerun()

        st.divider()

        # ── Action buttons ────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.download_button(
                "Download JSON",
                data=json.dumps(ag, indent=2, ensure_ascii=False),
                file_name=f"agent_{aid}.json",
                mime="application/json",
                key=f"dl_{aid}{suffix}",
            )
        with c2:
            if st.button("System prompt", key=f"sp_{aid}{suffix}"):
                k = f"show_sp_{aid}{suffix}"
                st.session_state[k] = not st.session_state.get(k, False)
        with c3:
            if st.button("Edit JSON", key=f"edit_btn_{aid}{suffix}"):
                k = f"show_edit_{aid}{suffix}"
                st.session_state[k] = not st.session_state.get(k, False)
        with c4:
            if st.button("Delete", key=f"rm_{aid}{suffix}", type="secondary"):
                delete_fn(aid)
                st.rerun()

        if st.session_state.get(f"show_sp_{aid}{suffix}"):
            st.code(generate_prompt_fn(ag), language="markdown")

        if st.session_state.get(f"show_edit_{aid}{suffix}"):
            edited = st.text_area(
                "Edit JSON — click Save to apply",
                value=json.dumps(ag, indent=2, ensure_ascii=False),
                height=320,
                key=f"edit_json_{aid}{suffix}",
            )
            if st.button("Save Changes", key=f"edit_save_{aid}{suffix}"):
                try:
                    new_ag = json.loads(edited)
                    new_ag.pop("_owner", None)
                    update_fn(new_ag)
                    st.success("Saved.")
                    st.rerun()
                except json.JSONDecodeError as exc:
                    st.error(f"Invalid JSON — not saved: {exc}")

        cfg = ag.get("simulation_config", {})
        st.caption(
            f"ID: `{aid}` | "
            f"Temp: {cfg.get('temperature','?')} | Max tokens: {cfg.get('max_tokens','?')}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# DEMOGRAPHIC CLUSTER VIEW  (inside Survey tab)
# ─────────────────────────────────────────────────────────────────────────────

def _render_demo_cluster_grid(
    survey_agents: list[dict],
    update_fn,
    delete_fn,
    generate_prompt_fn,
    owner_badge_fn,
    DISPLAY_NAMES: dict,
    TIER_LABELS: dict | None = None,   # deprecated: tiers removed
):
    """Render the Layer-2 demographic cluster grid for Survey agents."""
    if not survey_agents:
        st.info("No agents in the Survey cluster yet.")
        return

    clusters = _build_demo_clusters(survey_agents)
    total = len(survey_agents)

    # ── Cluster mode selector ─────────────────────────────────────────────────
    cluster_mode = st.radio(
        "Group by",
        ["Age band", "SES tier", "Geography", "Age × SES", "Age × Geography"],
        horizontal=True,
        key="demo_cluster_mode",
    )

    st.caption(f"{total} survey agent(s) across all demographic clusters")
    st.divider()

    # ── Single-dimension groupings ────────────────────────────────────────────
    if cluster_mode == "Age band":
        for ab_label, ab_lo, ab_hi in AGE_BANDS + [("Unknown", -1, -1)]:
            agents_in_band: list[dict] = []
            for ses_data in clusters.get(ab_label, {}).values():
                for geo_list in ses_data.values():
                    agents_in_band.extend(geo_list)
            if not agents_in_band:
                continue

            pct = len(agents_in_band) / total * 100
            with st.expander(
                f"**{ab_label}** — {len(agents_in_band)} agent(s) &nbsp;·&nbsp; {pct:.0f}% of survey pool",
                expanded=False,
            ):
                _render_mini_demo_breakdown(agents_in_band)
                for i, ag in enumerate(agents_in_band):
                    _render_agent_card(
                        ag, update_fn, delete_fn, generate_prompt_fn,
                        owner_badge_fn, DISPLAY_NAMES, TIER_LABELS,
                        card_key_suffix=f"ab_{ab_label}_{i}",
                    )

    elif cluster_mode == "SES tier":
        for ses_label, _, _ in SES_TIERS + [("Unknown", 0, 0)]:
            agents_in_ses: list[dict] = []
            for ab_data in clusters.values():
                for geo_list in ab_data.get(ses_label, {}).values():
                    agents_in_ses.extend(geo_list)
            if not agents_in_ses:
                continue

            pct = len(agents_in_ses) / total * 100
            with st.expander(
                f"**{ses_label}** — {len(agents_in_ses)} agent(s) &nbsp;·&nbsp; {pct:.0f}% of survey pool",
                expanded=False,
            ):
                _render_mini_demo_breakdown(agents_in_ses)
                for i, ag in enumerate(agents_in_ses):
                    _render_agent_card(
                        ag, update_fn, delete_fn, generate_prompt_fn,
                        owner_badge_fn, DISPLAY_NAMES, TIER_LABELS,
                        card_key_suffix=f"ses_{ses_label}_{i}",
                    )

    elif cluster_mode == "Geography":
        for geo in GEO_TYPES:
            agents_in_geo: list[dict] = []
            for ab_data in clusters.values():
                for ses_data in ab_data.values():
                    agents_in_geo.extend(ses_data.get(geo, []))
            if not agents_in_geo:
                continue

            pct = len(agents_in_geo) / total * 100
            geo_icon = {"Urban": "🏙️", "Suburban": "🏘️", "Rural": "🌾", "Unknown": "📍"}.get(geo, "📍")
            with st.expander(
                f"{geo_icon} **{geo}** — {len(agents_in_geo)} agent(s) &nbsp;·&nbsp; {pct:.0f}% of survey pool",
                expanded=False,
            ):
                _render_mini_demo_breakdown(agents_in_geo)
                for i, ag in enumerate(agents_in_geo):
                    _render_agent_card(
                        ag, update_fn, delete_fn, generate_prompt_fn,
                        owner_badge_fn, DISPLAY_NAMES, TIER_LABELS,
                        card_key_suffix=f"geo_{geo}_{i}",
                    )

    # ── Two-dimension cross-tab ───────────────────────────────────────────────
    elif cluster_mode == "Age × SES":
        all_age_bands  = [ab[0] for ab in AGE_BANDS] + ["Unknown"]
        all_ses_tiers  = [s[0] for s in SES_TIERS]   + ["Unknown"]

        # Summary cross-tab table
        rows = []
        for ab in all_age_bands:
            row_dict = {"Age band": ab}
            for ses in all_ses_tiers:
                count = len(clusters.get(ab, {}).get(ses, {}).get("Urban", []) +
                            clusters.get(ab, {}).get(ses, {}).get("Suburban", []) +
                            clusters.get(ab, {}).get(ses, {}).get("Rural", []) +
                            clusters.get(ab, {}).get(ses, {}).get("Unknown", []))
                # sum across all geo types
                n = sum(
                    len(clusters.get(ab, {}).get(ses, {}).get(g, []))
                    for g in GEO_TYPES
                )
                row_dict[ses] = n if n > 0 else "—"
            rows.append(row_dict)

        import pandas as pd
        df = pd.DataFrame(rows).set_index("Age band")
        st.dataframe(df, use_container_width=True)
        st.caption("Numbers = agent count per cell. Click a cluster below to view agents.")
        st.divider()

        # Expandable cells
        for ab in all_age_bands:
            for ses in all_ses_tiers:
                cell_agents = []
                for g in GEO_TYPES:
                    cell_agents.extend(clusters.get(ab, {}).get(ses, {}).get(g, []))
                if not cell_agents:
                    continue
                with st.expander(
                    f"**{ab}** × **{ses}** — {len(cell_agents)} agent(s)",
                    expanded=False,
                ):
                    for i, ag in enumerate(cell_agents):
                        _render_agent_card(
                            ag, update_fn, delete_fn, generate_prompt_fn,
                            owner_badge_fn, DISPLAY_NAMES, TIER_LABELS,
                            card_key_suffix=f"axs_{ab}_{ses}_{i}",
                        )

    elif cluster_mode == "Age × Geography":
        all_age_bands = [ab[0] for ab in AGE_BANDS] + ["Unknown"]

        import pandas as pd
        rows = []
        for ab in all_age_bands:
            row_dict = {"Age band": ab}
            for geo in GEO_TYPES:
                n = sum(
                    len(clusters.get(ab, {}).get(ses, {}).get(geo, []))
                    for ses in ([s[0] for s in SES_TIERS] + ["Unknown"])
                )
                row_dict[geo] = n if n > 0 else "—"
            rows.append(row_dict)

        df = pd.DataFrame(rows).set_index("Age band")
        st.dataframe(df, use_container_width=True)
        st.caption("Numbers = agent count per cell.")
        st.divider()

        for ab in all_age_bands:
            for geo in GEO_TYPES:
                cell_agents = []
                for ses in ([s[0] for s in SES_TIERS] + ["Unknown"]):
                    cell_agents.extend(clusters.get(ab, {}).get(ses, {}).get(geo, []))
                if not cell_agents:
                    continue
                geo_icon = {"Urban": "🏙️", "Suburban": "🏘️", "Rural": "🌾", "Unknown": "📍"}.get(geo, "📍")
                with st.expander(
                    f"**{ab}** × {geo_icon} **{geo}** — {len(cell_agents)} agent(s)",
                    expanded=False,
                ):
                    for i, ag in enumerate(cell_agents):
                        _render_agent_card(
                            ag, update_fn, delete_fn, generate_prompt_fn,
                            owner_badge_fn, DISPLAY_NAMES, TIER_LABELS,
                            card_key_suffix=f"axg_{ab}_{geo}_{i}",
                        )


def _render_mini_demo_breakdown(agents: list[dict]):
    """Show a compact demographic breakdown bar within an expander."""
    if not agents:
        return
    total = len(agents)

    # Gender split
    gender_counts: dict[str, int] = {}
    for ag in agents:
        g = ag.get("persona", {}).get("demographics", {}).get("gender", "Unknown") or "Unknown"
        gender_counts[g] = gender_counts.get(g, 0) + 1

    # Country split (top 3)
    country_counts: dict[str, int] = {}
    for ag in agents:
        c = ag.get("persona", {}).get("demographics", {}).get("location", {}).get("country", "Unknown") or "Unknown"
        country_counts[c] = country_counts.get(c, 0) + 1
    top_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    mc1, mc2 = st.columns(2)
    with mc1:
        gender_str = "  ·  ".join(
            f"**{k}** {v} ({v/total*100:.0f}%)"
            for k, v in sorted(gender_counts.items(), key=lambda x: x[1], reverse=True)
        )
        st.caption(f"Gender: {gender_str}")
    with mc2:
        country_str = "  ·  ".join(f"**{c}** {n}" for c, n in top_countries)
        if len(country_counts) > 3:
            country_str += f"  · +{len(country_counts) - 3} more"
        st.caption(f"Countries: {country_str}")

    st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# BULK ASSIGNMENT HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _render_bulk_assign(
    agents: list[dict],
    update_fn,
    filtered_agents: list[dict],
):
    """Render a bulk-assign panel above the agent list."""
    with st.expander("⚡ Bulk assign clusters", expanded=False):
        st.caption(
            f"Assign all **{len(filtered_agents)}** visible agents to a usage cluster at once."
        )
        ba_cols = st.columns(3)
        with ba_cols[0]:
            target_cluster = st.selectbox(
                "Target cluster",
                [k for k in USAGE_CLUSTERS if k != "unassigned"],
                format_func=lambda k: f"{USAGE_CLUSTERS[k]['icon']} {USAGE_CLUSTERS[k]['label']}",
                key="bulk_assign_target",
                label_visibility="collapsed",
            )
        with ba_cols[1]:
            bulk_mode = st.radio(
                "Mode",
                ["Add", "Replace all", "Remove"],
                horizontal=True,
                key="bulk_assign_mode",
                label_visibility="collapsed",
            )
        with ba_cols[2]:
            if st.button(
                f"Apply to {len(filtered_agents)} agent(s)",
                key="bulk_assign_go",
                type="primary",
                use_container_width=True,
            ):
                for ag in filtered_agents:
                    current = _get_clusters(ag)
                    if bulk_mode == "Add":
                        if target_cluster not in current:
                            _set_clusters(ag, current + [target_cluster], update_fn)
                    elif bulk_mode == "Replace all":
                        _set_clusters(ag, [target_cluster], update_fn)
                    elif bulk_mode == "Remove":
                        _set_clusters(ag, [c for c in current if c != target_cluster], update_fn)
                st.success(f"Done. Refreshing…")
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN UI  — replacement for ui_my_agents()
# ─────────────────────────────────────────────────────────────────────────────

def ui_agent_library_v2(
    load_agents_fn,
    update_agent_data_fn,
    delete_agent_fn,
    generate_system_prompt_fn,
    owner_badge_html_fn,
    current_user_fn,
    DISPLAY_NAMES: dict,
    TIER_LABELS: dict | None = None,   # deprecated: tiers removed platform-wide
):
    """
    Full replacement for ui_my_agents().
    Call from app.py:

        from agent_library_v2 import ui_agent_library_v2
        with tab2:
            ui_agent_library_v2(
                load_agents, update_agent_data, delete_agent,
                generate_system_prompt, owner_badge_html, current_user,
                DISPLAY_NAMES,
            )
    """
    st.header("Agent Library")
    st.caption(
        "Organise agents by how they're used, then drill into survey agents "
        "by demographic profile."
    )

    all_agents = load_agents_fn()
    if not all_agents:
        st.info("No agents yet. Go to **Build Agent** or **Generate Sample** to create your first one.")
        return

    # ── Top toolbar ───────────────────────────────────────────────────────────
    toolbar_l, toolbar_m, toolbar_r = st.columns([2, 3, 2])
    with toolbar_l:
        st.caption(f"**{len(all_agents)}** agent(s) in the shared library")
    with toolbar_m:
        mine_only = st.toggle("My agents only", key="al2_mine_only")
    with toolbar_r:
        st.download_button(
            "Export all (JSON)",
            data=json.dumps(all_agents, indent=2, ensure_ascii=False),
            file_name=f"agent_library_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True,
        )

    base_agents = (
        [a for a in all_agents if a.get("_owner") == current_user_fn()]
        if mine_only else all_agents
    )

    if not base_agents:
        st.info("No agents match the current filter.")
        return

    # ── Layer 1: Usage cluster tabs ───────────────────────────────────────────
    # Partition agents by cluster membership
    def _agents_in_cluster(cluster_key: str) -> list[dict]:
        if cluster_key == "unassigned":
            return [a for a in base_agents if not _get_clusters(a)]
        return [a for a in base_agents if cluster_key in _get_clusters(a)]

    cluster_counts = {k: len(_agents_in_cluster(k)) for k in USAGE_CLUSTERS}

    tab_labels = [
        f"{info['icon']} {info['label']} ({cluster_counts[k]})"
        for k, info in USAGE_CLUSTERS.items()
    ]
    tabs = st.tabs(tab_labels)

    for ti, (cluster_key, cluster_info) in enumerate(USAGE_CLUSTERS.items()):
        with tabs[ti]:
            cluster_agents = _agents_in_cluster(cluster_key)

            if not cluster_agents:
                st.info(
                    f"No agents in the **{cluster_info['label']}** cluster yet. "
                    f"Use the assign buttons on any agent card, or the bulk-assign panel."
                )
                if cluster_key != "unassigned":
                    st.caption(
                        "**Tip:** Switch to the Unassigned tab to tag agents in bulk."
                    )
                continue

            # ── Bulk assign ───────────────────────────────────────────────────
            _render_bulk_assign(all_agents, update_agent_data_fn, cluster_agents)

            # ── Survey: Layer-2 demographic clustering ────────────────────────
            if cluster_key == "survey":
                view_mode = st.radio(
                    "View as",
                    ["📋  List view", "🗂️  Demographic clusters"],
                    horizontal=True,
                    key="survey_view_mode",
                )

                if "Demographic" in view_mode:
                    _render_demo_cluster_grid(
                        cluster_agents,
                        update_agent_data_fn,
                        delete_agent_fn,
                        generate_system_prompt_fn,
                        owner_badge_html_fn,
                        DISPLAY_NAMES,
                        TIER_LABELS,
                    )
                    return  # skip list rendering below

            # ── Standard list view (all clusters, or Survey in list mode) ─────
            st.caption(
                f"{len(cluster_agents)} agent(s) in this cluster"
                + (" — sorted by name" if cluster_agents else "")
            )

            for i, ag in enumerate(
                sorted(cluster_agents,
                       key=lambda a: a.get("persona", {}).get("demographics", {}).get("name", "").lower())
            ):
                _render_agent_card(
                    ag,
                    update_agent_data_fn,
                    delete_agent_fn,
                    generate_system_prompt_fn,
                    owner_badge_html_fn,
                    DISPLAY_NAMES,
                    TIER_LABELS,
                    card_key_suffix=f"{cluster_key}_{i}",
                )
