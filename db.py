"""
db.py — Supabase / PostgreSQL storage layer.

All agents are stored in a single 'agents' table. The full agent dict is kept
in a JSON 'data' column; owner, family_id and has_sampling_metadata are also
stored as their own columns so the database can sort and filter efficiently.

Note on 'tier': agents are demographics-only platform-wide, so this layer no
longer writes a tier value. If your existing 'agents' table still has a 'tier'
column it is simply left at its default (harmless). The column can be dropped
at your discretion with:  alter table agents drop column tier;
New deployments can omit the 'tier' column from the create-table statement.

Reads credentials from .streamlit/secrets.toml:

    [supabase]
    url = "https://YOUR-PROJECT.supabase.co"
    service_key = "sb_secret_..."

Requires the 'agents' table to exist. Create it once in the Supabase SQL
Editor:

    create table agents (
        agent_id text primary key,
        owner text,
        family_id text,
        has_sampling_metadata boolean default false,
        data jsonb,
        created_at timestamptz default now()
    );
    create index idx_agents_owner   on agents (owner);
    create index idx_agents_created on agents (created_at desc);
"""

from __future__ import annotations

import streamlit as st


@st.cache_resource
def _client():
    """Return a cached Supabase client using the secret/service-role key."""
    from supabase import create_client
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["service_key"],
    )


def save_agent(agent: dict, owner: str) -> None:
    """Insert or update an agent. agent_id is the unique conflict key.

    Sets (or re-sets) the owner column, so use update_agent_data() when
    editing existing agents to preserve the original owner.
    """
    row = {
        "agent_id":              agent["agent_id"],
        "owner":                 owner,
        "family_id":             agent.get("family_id"),
        "has_sampling_metadata": "sampling_metadata" in agent,
        "data":                  agent,
    }
    _client().table("agents").upsert(row, on_conflict="agent_id").execute()


def load_all_agents() -> list[dict]:
    """Return every agent, newest first.

    Injects '_owner' and '_family_id' into each dict from the table columns so
    the UI can display, filter, and group by creator.
    """
    res = (
        _client()
        .table("agents")
        .select("data, owner, family_id")
        .order("created_at", desc=True)
        .execute()
    )
    agents: list[dict] = []
    for row in res.data:
        ag = dict(row["data"])
        ag["_owner"]     = row["owner"]
        ag["_family_id"] = row.get("family_id")
        agents.append(ag)
    return agents


def delete_agent(agent_id: str) -> None:
    """Delete one agent by id."""
    _client().table("agents").delete().eq("agent_id", agent_id).execute()


def update_agent_data(agent: dict) -> None:
    """Overwrite the JSON blob of an existing agent without changing its owner."""
    _client().table("agents").update({
        "data":                  agent,
        "has_sampling_metadata": "sampling_metadata" in agent,
    }).eq("agent_id", agent["agent_id"]).execute()
