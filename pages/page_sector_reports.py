"""
pages/page_sector_reports.py — TIP sector progress report viewer.
Globals are read from state.py (populated by app.py at startup).
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


def page_sector_reports():
    from scripts.tip_progress_report import render_tip_progress_report

    # ── Hero card (matches My Dashboard / Benchmarking / Analysis style) ─────
    NAVY_DARK = "#0F2540"
    NAVY_MID  = "#1A3A5C"
    st.markdown(f"""
    <style>
    .sector-hero {{
        background: linear-gradient(135deg, {NAVY_DARK} 0%, {NAVY_MID} 100%);
        border-radius: 12px; padding: 22px 28px; margin-bottom: 18px;
        display: flex; justify-content: space-between; align-items: flex-start;
    }}
    .sector-hero-eyebrow {{ font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
                           color: rgba(255,255,255,.55); margin-bottom: 6px; }}
    .sector-hero-title {{ font-size: 30px; font-weight: 800; color: white; line-height: 1.2; }}
    .sector-hero-sub {{ font-size: 12.5px; color: rgba(255,255,255,.7); margin-top: 4px; }}
    .sector-hero-year-label {{ font-size: 10px; color: rgba(255,255,255,.5); text-align: right;
                              text-transform: uppercase; letter-spacing: .05em; }}
    .sector-hero-year {{ font-size: 30px; font-weight: 700; color: white; text-align: right; line-height: 1; }}
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f'''<div class="sector-hero">
        <div>
            <div class="sector-hero-eyebrow">Tire Industry Platform</div>
            <div class="sector-hero-title">All TIP Member Companies</div>
            <div class="sector-hero-sub">Sector Progress Report — Pathways 3, 4, 5</div>
        </div>
        <div>
            <div class="sector-hero-year-label">Reporting Year</div>
            <div class="sector-hero-year">{state.CURR_YEAR}</div>
        </div>
    </div>''', unsafe_allow_html=True)

    render_tip_progress_report(state.SECTOR_DF, state.CONSOLIDATED_DF)