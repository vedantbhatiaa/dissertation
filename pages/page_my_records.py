"""
pages/page_my_records.py — My Records: full template table with Submit & Save.

"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

import config as cfg
import data_loader as dl
import state
# helpers: none needed directly in this page
from utils.data_utils import _save_submission_to_csv, _load_supplementary
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
import logging
import html as _html
_log = logging.getLogger("esg_app")
from formula_engine import TemplateInputs, calculate
from ui_components import GREEN, AMBER, RED, NAVY, BG, BORDER, TEXT, MUTED
from components.render_template_table import render_template_table
from components.render_electricity_tab import render_electricity_tab
from components.render_waste_tab import render_waste_tab
from components.render_people_tab import _render_people_governance_tab
from components.render_qualitative_tab import render_qualitative_tab
from components.render_conversion_tab import render_conversion_tab

NAVY_DARK = "#0F2540"
NAVY_MID  = "#1B4060"


def _kpi_banner(title_line1: str):
    """Unified section title used across all four data tabs (Main Data Input,
    Electricity by Country, Waste, People & Governance) — just the title in
    bold green, no company name repeat (already in the hero banner above)
    and no subtitle."""
    st.markdown(f"""
    <div style="margin-bottom:14px;font-size:26px;font-weight:800;color:#00916E;letter-spacing:-.4px">
      {title_line1}
    </div>
    """, unsafe_allow_html=True)


def _unit_toggle(key_prefix: str):
    """Corporate Units / Common Units pill toggle. Returns active mode."""
    mode_key = f"{key_prefix}_unit_mode"
    if mode_key not in st.session_state:
        st.session_state[mode_key] = "corporate"
    b1, b2, _sp = st.columns([1, 1, 6])
    with b1:
        if st.button(
            "Corporate Units",
            key=f"{key_prefix}_corp_btn",
            type="primary" if st.session_state[mode_key] == "corporate" else "secondary",
            use_container_width=True,
        ):
            st.session_state[mode_key] = "corporate"
            st.rerun()
    with b2:
        if st.button(
            "Common Units",
            key=f"{key_prefix}_common_btn",
            type="primary" if st.session_state[mode_key] == "common" else "secondary",
            use_container_width=True,
        ):
            st.session_state[mode_key] = "common"
            st.rerun()
    st.session_state["unit_mode"] = st.session_state[mode_key]
    return st.session_state[mode_key]


def _unit_toggle_elec(key_prefix: str):
    """Corporate Units / Common Units / CO2 Emissions from IEA toggle for Electricity tab."""
    mode_key = f"{key_prefix}_unit_mode"
    if mode_key not in st.session_state:
        st.session_state[mode_key] = "corporate"
    b1, b2, b3, _sp = st.columns([1.2, 1.2, 1.6, 4])
    with b1:
        if st.button(
            "Corporate Units",
            key=f"{key_prefix}_corp_btn",
            type="primary" if st.session_state[mode_key] == "corporate" else "secondary",
            use_container_width=True,
        ):
            st.session_state[mode_key] = "corporate"
            st.rerun()
    with b2:
        if st.button(
            "Common Units",
            key=f"{key_prefix}_common_btn",
            type="primary" if st.session_state[mode_key] == "common" else "secondary",
            use_container_width=True,
        ):
            st.session_state[mode_key] = "common"
            st.rerun()
    with b3:
        if st.button(
            "CO2 Emissions from IEA",
            key=f"{key_prefix}_iea_btn",
            type="primary" if st.session_state[mode_key] == "iea" else "secondary",
            use_container_width=True,
        ):
            st.session_state[mode_key] = "iea"
            st.rerun()
    st.session_state["unit_mode"] = st.session_state[mode_key]
    return st.session_state[mode_key]


def page_my_records():
    """My Records — view and save all historical KPI data. CLIENT SIDE ONLY."""
    company   = st.session_state.user_company
    comp_hist = dl.get_company_hist(state.CONSOLIDATED_DF, company)
    co_years  = sorted(dl.get_years(state.CONSOLIDATED_DF, company) or [])
    _lo       = co_years[0] if co_years else state.CURR_YEAR
    all_yrs   = sorted(set(co_years) | set(range(_lo, state.CURR_YEAR + 2)), reverse=True)

    # ── ROW 1: Blue hero banner ───────────────────────────────────────────────
    sel_yr_preview = st.session_state.get("myrec_year", all_yrs[0] if all_yrs else state.CURR_YEAR)
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{NAVY_DARK} 0%,{NAVY_MID} 100%);
        border-radius:12px;padding:22px 28px;margin-bottom:14px;
        display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;
            color:rgba(255,255,255,.55);margin-bottom:6px">Tire Industry Platform</div>
        <div style="font-size:22px;font-weight:700;color:white;line-height:1.2">{company}</div>
        <div style="font-size:12.5px;color:rgba(255,255,255,.7);margin-top:4px">ESG My Records</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:10px;color:rgba(255,255,255,.5);text-transform:uppercase;
            letter-spacing:.05em">Reporting Year</div>
        <div style="font-size:30px;font-weight:700;color:white;line-height:1">{sel_yr_preview}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── ROW 2: Year dropdown · Submit & Save ──────────────────────────────────
    _sp, h_yr, h_btn = st.columns([3, 1, 1])
    with h_yr:
        _def_yr  = st.session_state.get("reporting_year", all_yrs[0] if all_yrs else state.CURR_YEAR)
        _def_idx = all_yrs.index(_def_yr) if _def_yr in all_yrs else 0
        sel_yr   = st.selectbox("Year", all_yrs, index=_def_idx,
                                key="myrec_year", label_visibility="collapsed")
    with h_btn:
        save_clicked = st.button("💾  Submit & Save", type="primary",
                                 use_container_width=True, key="myrec_save_btn")

    if "_last_save_msg" in st.session_state:
        st.success(f"✅ {st.session_state.pop('_last_save_msg')}")

    # ── Load data ─────────────────────────────────────────────────────────────
    st.session_state.reporting_company  = company
    st.session_state.reporting_year     = sel_yr
    # Suppress the inner blue info box rendered by render_template_table
    st.session_state["hide_template_info_box"] = True
    # Suppress the info banner in qualitative tab and the sub-header in people tab
    st.session_state["hide_qualitative_banner"] = True
    st.session_state["hide_people_subheader"]   = True

    fresh_hist = dl.get_company_hist(state.CONSOLIDATED_DF, company)
    step_data  = dl.get_step_data(fresh_hist, sel_yr) if fresh_hist else {}
    valid_flds = {f.name for f in TemplateInputs.__dataclass_fields__.values()}
    clean      = {k: v for k, v in step_data.items() if k in valid_flds}

    if clean:
        for k, v in clean.items():
            st.session_state[k] = v
        inp = TemplateInputs(company=company, year=sel_yr, **clean)
        out = calculate(inp)
    else:
        inp = TemplateInputs(company=company, year=sel_yr)
        out = calculate(inp)

    st.session_state.step_data          = {fld: getattr(inp, fld) for fld in state.VALID_TEMPLATE_FIELDS}
    st.session_state["_codata_inp"]     = inp
    st.session_state["_codata_out"]     = out
    st.session_state.template_done      = True
    st.session_state.company_setup_done = True
    st.session_state.step               = 6

    if save_clicked:
        _supp = _load_supplementary(company, sel_yr)
        msg = _save_submission_to_csv(inp, out, supp=_supp)
        st.success(f"✅ {msg}")
        st.rerun()

    # ── ROW 3: Tabs ──────────────────────────────────────────────────────────
    tab_main, tab_elec, tab_waste, tab_people_tpl, tab_qual, tab_conv = st.tabs([
        "Main Data Input", "Electricity by Country", "Waste",
        "People & Governance", "Qualitative Data", "Conversion Tables",
    ])

    with tab_main:
        _mode = _unit_toggle("myrec_main")
        _title = (
            "Key Performance Indicators — Corporate Units"
            if _mode == "corporate"
            else "Key Performance Indicators — Common Units"
        )
        _kpi_banner(_title)
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        render_template_table()

    with tab_elec:
        _mode = _unit_toggle_elec("myrec_elec")
        _elec_titles = {
            "corporate": "Non-Renewable Electricity Purchased by Country — Corporate Units",
            "common":    "Non-Renewable Electricity Purchased by Country — Common Units",
            "iea":       "CO2 Emissions from IEA",
        }
        _kpi_banner(_elec_titles.get(_mode, ""))
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        render_electricity_tab()

    with tab_waste:
        _mode = _unit_toggle("myrec_waste")
        _waste_title = (
            "Waste KPIs — Corporate Units"
            if _mode == "corporate"
            else "Waste KPIs — Common Units"
        )
        _kpi_banner(_waste_title)
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        render_waste_tab()

    with tab_people_tpl:
        _mode = _unit_toggle("myrec_people")
        _people_title = (
            "People & Governance — Corporate Units"
            if _mode == "corporate"
            else "People & Governance — Common Units"
        )
        _kpi_banner(_people_title)
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        _render_people_governance_tab()

    with tab_qual:
        _kpi_banner("Qualitative Data")
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        render_qualitative_tab()

    with tab_conv:
        _kpi_banner("Conversion Tables")
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        render_conversion_tab()