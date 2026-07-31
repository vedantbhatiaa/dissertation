"""
components/render_conversion_tab.py — Conversion tables section.
All globals are read from state.py which app.py keeps up-to-date.
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


def render_conversion_tab():
    import conversion_data as cd
    from formula_engine import EF as _EF

    st.caption("Reference factors used to normalise data to corporate units. Do not edit. "
               "Pulled live from the calculation engine — always matches what's actually used.")

    _subsections = sorted(cd.UNITS_BY_SUBSECTION.keys())
    _sel_sub = st.selectbox(
        "Filter unit conversion factors by field", ["All fields"] + _subsections,
        key="conv_tbl_filter",
    )

    _TBL_HEIGHT = 480

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Energy CO₂ emission factors**")
        st.caption("T.CO₂ per GJ LHV, as used in calculate() for every submission.")
        _ef_rows = [
            {"Energy Type": k, "Unit": "GJ LHV", "CO2 EF (T.CO2/GJ)": v}
            for k, v in _EF.items()
            if k != "Coal Legacy Blended"   # internal-only fallback, not a real fuel type
        ]
        st.dataframe(
            pd.DataFrame(_ef_rows), hide_index=True, use_container_width=True,
            height=_TBL_HEIGHT,
            column_config={
                "CO2 EF (T.CO2/GJ)": st.column_config.NumberColumn(format="%.4f"),
            },
        )

    with col2:
        st.markdown("**Unit conversion factors**")
        st.caption("Corporate unit → common unit multiplier, by KPI field family.")
        # The "to unit" (fixed common unit) for a subsection is whichever
        # unit has factor == 1 — that's how UNIT_CONVERSION_FACTORS encodes
        # the canonical target unit for each field family.
        _common_unit = {}
        for (_sec, _unit), _factor in cd.UNIT_CONVERSION_FACTORS.items():
            if _factor == 1:
                _common_unit[_sec] = _unit

        _rows = [
            {
                "Indicator": sec, "From unit": unit,
                "To unit": _common_unit.get(sec, "—"), "Factor": factor,
            }
            for (sec, unit), factor in cd.UNIT_CONVERSION_FACTORS.items()
            if _sel_sub == "All fields" or sec == _sel_sub
        ]
        _conv_df = pd.DataFrame(_rows).sort_values(["Indicator", "From unit"]).reset_index(drop=True)
        st.dataframe(
            _conv_df, hide_index=True, use_container_width=True,
            height=_TBL_HEIGHT,
            column_config={
                "Factor": st.column_config.NumberColumn(format="%.6f"),
            },
        )
        st.caption(f"{len(_conv_df)} conversion{'s' if len(_conv_df) != 1 else ''} shown"
                   + ("" if _sel_sub == "All fields" else f" for **{_sel_sub}**")
                   + f" · {len(_subsections)} field families total.")

    st.divider()
    st.markdown("**Source:** WBCSD TIP methodology · IEA country factors (Scope 2) · IPCC 2006 Guidelines. "
                "Electricity grid emission factors (Scope 2, by country/year) are used live on the "
                "Electricity by Country → CO2 Emissions from IEA tab rather than duplicated here.")