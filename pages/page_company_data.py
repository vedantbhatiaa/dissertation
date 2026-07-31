"""
pages/page_company_data.py — DSS full KPI template view for any company+year.

"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
import html as _html
_log = logging.getLogger("esg_app")
from formula_engine import (
    TemplateInputs, calculate, validate_submission,
    get_benchmarks, build_template_dataframe, fmt_num,
    yoy_change, ValidationFlag, BenchmarkResult,
)
from ui_components import (
    inject_global_css, kpi_card_html, skeleton_card_html, skeleton_chart_html,
    status_chip_html, section_header_html, empty_state_html, co_card_html,
    apply_chart_animation, chart_layout_defaults, sparkline_html,
    GREEN, AMBER, RED, NAVY, BG, BORDER, TEXT, MUTED,
    CAT_CO2, CAT_ENERGY, CAT_WATER, CAT_WASTE, CAT_RENEW,
)
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


def page_company_data():
    """DSS+ Company Data — full KPI template table for a selected company."""
    companies_in_db = dl.get_companies(state.CONSOLIDATED_DF) or state.COMPANIES
    pre_co     = st.session_state.pop("portfolio_company", None)
    default_co = (pre_co or st.session_state.get("reporting_company") or companies_in_db[0])
    if default_co not in companies_in_db:
        default_co = companies_in_db[0]

    # Need company name for banner — read selectbox default before rendering it
    banner_co = st.session_state.get("codata_company", default_co)
    banner_yr = st.session_state.get("codata_year", state.CURR_YEAR)

    # ── ROW 1: Blue hero banner ───────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{NAVY_DARK} 0%,{NAVY_MID} 100%);
        border-radius:12px;padding:22px 28px;margin-bottom:14px;
        display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;
            color:rgba(255,255,255,.55);margin-bottom:6px">Tire Industry Platform</div>
        <div style="font-size:22px;font-weight:700;color:white;line-height:1.2">{banner_co}</div>
        <div style="font-size:12.5px;color:rgba(255,255,255,.7);margin-top:4px">ESG Company Data</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:10px;color:rgba(255,255,255,.5);text-transform:uppercase;
            letter-spacing:.05em">Reporting Year</div>
        <div style="font-size:30px;font-weight:700;color:white;line-height:1">{banner_yr}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── ROW 2: Company selector · Year selector ───────────────────────────────
    _sp, col_co, col_yr = st.columns([2, 2, 1])
    with col_co:
        sel_co = st.selectbox(
            "Company", options=companies_in_db,
            index=companies_in_db.index(default_co),
            key="codata_company", label_visibility="collapsed",
        )
    with col_yr:
        avail_years = dl.get_years(state.CONSOLIDATED_DF, sel_co) or [state.CURR_YEAR]
        sel_yr = st.selectbox(
            "Year", options=sorted(avail_years, reverse=True),
            key="codata_year", label_visibility="collapsed",
        )

    # ── Load data & set session state ─────────────────────────────────────────
    st.session_state.reporting_company = sel_co
    st.session_state.reporting_year    = sel_yr
    # Suppress the inner blue info box rendered by render_template_table
    st.session_state["hide_template_info_box"] = True
    # Suppress the info banner in qualitative tab and the sub-header in people tab
    st.session_state["hide_qualitative_banner"] = True
    st.session_state["hide_people_subheader"]   = True

    hist      = dl.get_company_hist(state.CONSOLIDATED_DF, sel_co)
    step_data = dl.get_step_data(hist, sel_yr) if hist else {}
    valid_fields = state.VALID_TEMPLATE_FIELDS
    for field, val in step_data.items():
        if field in valid_fields:
            st.session_state[field] = val

    from formula_engine import TemplateInputs as TI, calculate as calc
    valid = {f.name for f in TI.__dataclass_fields__.values()}
    clean = {k: v for k, v in step_data.items() if k in valid}
    inp   = TI(company=sel_co, year=sel_yr, **clean)
    out   = calc(inp)

    st.session_state["_codata_inp"]        = inp
    st.session_state["_codata_out"]        = out
    st.session_state["template_done"]      = True
    st.session_state["company_setup_done"] = True
    st.session_state["step"]               = 6

    # ── ROW 3: Tabs ───────────────────────────────────────────────────────────
    tab_main, tab_elec, tab_waste, tab_people_tpl, tab_qual, tab_conv = st.tabs([
        "Main Data Input", "Electricity by Country", "Waste",
        "People & Governance", "Qualitative Data", "Conversion Tables",
    ])

    with tab_main:
        _mode = _unit_toggle("codata_main")
        _title = (
            "Key Performance Indicators — Corporate Units"
            if _mode == "corporate"
            else "Key Performance Indicators — Common Units"
        )
        _kpi_banner(_title)
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        render_template_table()

    with tab_elec:
        _mode = _unit_toggle_elec("codata_elec")
        _elec_titles = {
            "corporate": "Non-Renewable Electricity Purchased by Country — Corporate Units",
            "common":    "Non-Renewable Electricity Purchased by Country — Common Units",
            "iea":       "CO2 Emissions from IEA",
        }
        _kpi_banner(_elec_titles.get(_mode, ""))
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        render_electricity_tab()

    with tab_waste:
        _mode = _unit_toggle("codata_waste")
        _waste_title = (
            "Waste KPIs — Corporate Units"
            if _mode == "corporate"
            else "Waste KPIs — Common Units"
        )
        _kpi_banner(_waste_title)
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        render_waste_tab()

    with tab_people_tpl:
        _mode = _unit_toggle("codata_people")
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

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    if st.button("← Back to Portfolio", key="codata_back"):
        st.session_state.page = "portfolio"
        st.rerun()