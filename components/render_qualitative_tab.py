"""
components/render_qualitative_tab.py — Qualitative data section.
All globals are read from state.py which app.py keeps up-to-date.

Client side: fills in free-text answers and can Save — writes a "current"
JSON snapshot (data_storage/reports/TIP/{Company}/{Company}_{Year}_qualitative.json,
overwritten each save) plus appends one line to an audit-trail JSONL file
(data_storage/reports/TIP/{Company}/{Company}_{Year}_qualitative_versions.jsonl,
never overwritten — full history of every save).

Internal (DSS) side: read-only viewer only — no text areas, no Save button.
Shows the current snapshot plus the version history so an analyst can see
exactly what changed and when.

JSON was chosen over CSV/parquet for these logs specifically because the
data is free-text (multi-paragraph answers) rather than numeric — JSON
handles that naturally (no delimiter/escaping issues), is human-readable
without any tooling, and the section/question nesting maps directly.
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime, date

import config as cfg
import data_loader as dl
import state
from utils.helpers import (
    get_hist_outputs, _get_fresh_hist, get_current_outputs,
    _load_company_year_outputs, _compute_industry_scores,
    _compute_kpi_improvement, _chart_key,
    _compute_completeness, _compute_readiness_score,
    _dss_company_selector,
)
from utils.data_utils import (
    _load_supplementary, _save_supplementary, _build_master_row,
    _save_version_parquet, _write_verification_status,
    _save_submission_to_csv, _save_electricity_to_master,
    _sync_consolidate_excel, _sync_company_member_files,
    _elec_col,
)
from utils.comment_utils import (
    load_comments as _load_comments,
    save_change_comment as _save_change_comment,
    update_comment_status as _update_comment_status,
    get_approved_comments as _get_approved_comments,
    get_all_active_comments as _get_all_active_comments,
    update_master_comment_cell as _update_master_comment_cell,
    delete_comment as _delete_comment,
    save_comment_version as _save_comment_version,
)
from ui_components import chart_layout_defaults, apply_chart_animation
import logging
_log = logging.getLogger("esg_app")
from formula_engine import (
    TemplateInputs, calculate, validate_submission,
    get_benchmarks, fmt_num, yoy_change, BenchmarkResult,
)
from ui_components import (
    kpi_card_html, section_header_html, chart_layout_defaults,
    apply_chart_animation, GREEN, AMBER, RED, NAVY, BG, BORDER, TEXT, MUTED,
    CAT_CO2, CAT_ENERGY, CAT_WATER, CAT_WASTE, CAT_RENEW,
)

# ── Question structure — single source of truth ──────────────────────────────
# Used both to render the client's editable form and to know exactly which
# session_state keys to collect when saving, so the two can never drift.
QUAL_SECTIONS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("Energy", [
        ("Program — Management approach", "Explain how your organization manages the energy topic: policies, commitments, ISO 50001 certifications, goals & targets.", "program"),
        ("Impacts", "Include the expected impacts related to the program initiatives. Do you expect efforts to impact the Energy KPI?", "impacts"),
        ("Specific projects completed / underway", "Report specific projects related to energy that you are currently running, implementing or planning.", "projects"),
    ]),
    ("CO2 Emissions", [
        ("Program — Management approach", "Explain how your organization manages CO2: policies, commitments, goals & targets.", "program"),
        ("Impacts", "Do you expect the efforts to positively or negatively impact the CO2 KPI?", "impacts"),
        ("Specific projects completed / underway", "Report specific projects related to CO2 reduction.", "projects"),
    ]),
    ("Water", [
        ("Program — Management approach", "Explain how your organization manages water: policies, commitments, goals & targets.", "program"),
        ("Specific projects completed / underway", "Report specific projects related to water management.", "projects"),
    ]),
    ("Waste", [
        ("Program — Management approach", "Explain how your organization manages waste: policies, commitments, goals & targets.", "program"),
        ("Specific projects completed / underway", "Report the specific projects related to waste that you are currently running.", "projects"),
    ]),
]


def _log_dir(company: str) -> Path:
    return Path("data_storage/reports/TIP") / company.replace(" ", "_")


def _log_paths(company: str, year) -> tuple[Path, Path]:
    base = _log_dir(company)
    safe_co = company.replace(" ", "_")
    current_path  = base / f"{safe_co}_{year}_qualitative.json"
    versions_path = base / f"{safe_co}_{year}_qualitative_versions.jsonl"
    return current_path, versions_path


def _collect_qualitative_answers() -> dict:
    """Read every question's 3 answer fields (public / non-public / other
    comments) out of session_state, plus the Additional Information field,
    keyed by section → question."""
    answers: dict = {}
    for title, questions in QUAL_SECTIONS:
        sec = {}
        for q_label, _hint, q_key in questions:
            sec[q_label] = {
                "public":    st.session_state.get(f"pub_{title}_{q_key}", ""),
                "non_public": st.session_state.get(f"nonpub_{title}_{q_key}", ""),
                "comments":  st.session_state.get(f"cmt_{title}_{q_key}", ""),
            }
        answers[title] = sec
    answers["Additional Information"] = {
        "Other information that may affect the five environmental KPIs": {
            "comments": st.session_state.get("qual_additional", "")
        }
    }
    return answers


def _save_qualitative_log(company: str, year) -> dict:
    """Write the current snapshot (overwritten) and append one line to the
    audit-trail version log (never overwritten). Returns the saved payload."""
    now = datetime.now()
    payload = {
        "company":  company,
        "year":     int(year),
        "saved_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "answers":  _collect_qualitative_answers(),
    }
    base = _log_dir(company)
    base.mkdir(parents=True, exist_ok=True)
    current_path, versions_path = _log_paths(company, year)

    with open(current_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    with open(versions_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return payload


def _load_current_snapshot(company: str, year) -> dict | None:
    current_path, _ = _log_paths(company, year)
    if not current_path.exists():
        return None
    try:
        with open(current_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _log.warning("[qualitative] failed to read %s: %s", current_path, e)
        return None


def _load_version_history(company: str, year) -> list[dict]:
    _, versions_path = _log_paths(company, year)
    if not versions_path.exists():
        return []
    out = []
    try:
        with open(versions_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except Exception as e:
        _log.warning("[qualitative] failed to read %s: %s", versions_path, e)
    return out


def _render_answers_readonly(answers: dict):
    for section, questions in answers.items():
        st.markdown(f"""<div style="background:#0A2240;color:#fff;font-size:13px;font-weight:700;
            padding:9px 16px;border-radius:8px 8px 0 0;margin-top:18px;margin-bottom:0">
          {section}</div>""", unsafe_allow_html=True)
        with st.container(border=True):
            for q_label, fields in questions.items():
                st.markdown(f"**{q_label}**")
                c1, c2, c3 = st.columns(3)
                c1.markdown("*Public information*")
                c1.write(fields.get("public") or "—")
                c2.markdown("*Non-public (confidential)*")
                c2.write(fields.get("non_public") or "—")
                c3.markdown("*Other comments*")
                c3.write(fields.get("comments") or "—")
                st.divider()


def _render_qualitative_viewer(company: str, rep_year):
    """Internal (DSS) read-only view of the client's saved qualitative log."""
    if not company:
        st.info("Select a company to view its qualitative data log.")
        return

    snapshot = _load_current_snapshot(company, rep_year)
    history  = _load_version_history(company, rep_year)

    if not snapshot:
        st.info(f"No qualitative data has been saved yet for **{company}**, **{rep_year}**.")
        return

    st.caption(f"Last saved by client on **{snapshot['saved_at']}** · "
               f"{len(history)} version{'s' if len(history) != 1 else ''} on file.")

    if len(history) > 1:
        _opts = [f"{h['saved_at']} (latest)" if h is history[-1] else h['saved_at']
                 for h in history]
        _sel = st.selectbox("View version", list(reversed(_opts)), key=f"qual_ver_sel_{company}_{rep_year}")
        _idx = _opts.index(_sel)
        snapshot = history[_idx]
        if _idx != len(history) - 1:
            st.warning(f"Viewing a past version saved {snapshot['saved_at']} — not the current one.")

    _render_answers_readonly(snapshot["answers"])


def render_qualitative_tab():
    company  = st.session_state.get("reporting_company") or st.session_state.get("user_company") or ""
    rep_year = st.session_state.get("reporting_year", state.CURR_YEAR)
    is_dss   = st.session_state.get("is_dss", False)

    st.markdown("""
    <div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:14px 18px;margin-bottom:16px;font-size:13px;color:#374151;line-height:1.7">
    This section gathers qualitative data to help gain additional insights for better interpretation of your
    quantitative data. Please report your company's main programs, trends, or actions that are already
    implemented, under implementation or planned.<br>
    <span style="color:#9CA3AF;font-size:12px">Non-public information will be kept confidential and only used at an aggregated level.</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Internal (DSS) side: read-only viewer only ────────────────────────────
    if is_dss:
        _render_qualitative_viewer(company, rep_year)
        return

    # ── Client side: editable form ─────────────────────────────────────────────
    def qual_section(title, questions):
        st.markdown(f"""
        <div style="background:#0A2240;color:#fff;font-size:13px;font-weight:700;
            padding:9px 16px;border-radius:8px 8px 0 0;margin-top:18px;margin-bottom:0">
          {title}
        </div>
        """, unsafe_allow_html=True)
        with st.container(border=True):
            for q_label, q_hint, q_key in questions:
                st.markdown(f"**{q_label}**")
                if q_hint: st.caption(q_hint)
                c1, c2, c3 = st.columns([2,2,1])
                with c1: st.text_area("Public information",   key=f"pub_{title}_{q_key}",   height=90, placeholder="Information for the Global KPIs Report...")
                with c2: st.text_area("Non-public (confidential)", key=f"nonpub_{title}_{q_key}", height=90, placeholder="Used only at aggregated level...")
                with c3: st.text_area("Other comments",       key=f"cmt_{title}_{q_key}",   height=90, placeholder="Any additional remarks...")
                st.divider()

    for title, questions in QUAL_SECTIONS:
        qual_section(title, questions)

    st.markdown("""<div style="background:#0A2240;color:#fff;font-size:13px;font-weight:700;
        padding:9px 16px;border-radius:8px 8px 0 0;margin-top:18px;margin-bottom:0">
      Additional Information</div>""", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("**Other information that may affect the five environmental KPIs**")
        st.text_area("Additional comments", key="qual_additional", height=120,
                     placeholder="e.g. major plant closures, acquisitions, production restructuring...")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("💾 Save Qualitative Responses", type="primary",
                 use_container_width=True, key="qual_save_btn"):
        if not company:
            st.error("No company in session — cannot save.")
        else:
            payload = _save_qualitative_log(company, rep_year)
            st.success(f"Saved for **{company}**, **{rep_year}** at {payload['saved_at']}.")