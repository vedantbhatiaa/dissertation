"""
components/render_electricity_tab.py — Electricity by country editor.
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
    _elec_col,                    # column name helper
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
    get_edited_field_years as _get_edited_field_years,
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


def render_electricity_tab():
    """
    Electricity-by-country — read-only display, formatted to match Main Data
    Input / Waste / People & Governance. Values are entered via Submit Data
    (which covers all companies); this tab shows them plus a per-country
    Comments column for change requests, same mechanism as the other tabs.

    Historical fix notes still relevant to the underlying data load below:
    1. VALUES RESET BUG — st.data_editor with a static key causes Streamlit to
       discard edits on the first rerun. Fix: never use a static key when the
       underlying data comes from session_state; give the editor a key that
       is stable only within one company+year session.
    2. PRE-LOAD BUG — elec_data was always initialised to zeros even when the
       master CSV already had non-zero Elec_*_GJ values for this company.
       Fix: on first load (or when company/year changes) read Elec_*_GJ cols
       from state.CONSOLIDATED_DF, convert GJ→MWh, and populate the table.
    """
    # ── Unit mode routing ────────────────────────────────────────────────────
    # Controlled by the toggle buttons in page_my_records / page_company_data.
    #   "corporate" → MWh (company-reported); reads Elec_*_MWh_Corp columns
    #   "common"    → GJ (= MWh × 3.6);       reads Elec_*_GJ columns
    #   "iea"       → tCO₂ from template;     reads IEA_CO2_*_tCO2 columns
    unit_mode = st.session_state.get("unit_mode", "corporate")

    company  = st.session_state.get("reporting_company") or st.session_state.get("user_company", "")
    rep_year = st.session_state.get("reporting_year", state.CURR_YEAR)
    _co_yrs  = []
    if not state.CONSOLIDATED_DF.empty and company:
        _co_yrs = dl.get_years(state.CONSOLIDATED_DF, company) or []
    _max_yr = max([rep_year] + (_co_yrs or [2023]))
    YEARS   = list(range(2009, _max_yr + 1))
    mdf     = state.CONSOLIDATED_DF

    if unit_mode in ("common", "iea"):
        COUNTRY_COL_GJ = state.ELEC_COUNTRY_COLS    # {country: "Elec_<Country>_GJ"} — full ~150 schema
        ALL_COUNTRIES  = state.ELEC_ALL_COUNTRIES

        # Build ONE GJ pivot covering EVERY country in the schema — not just
        # whichever Elec_*_GJ columns happen to already exist in the master
        # CSV. A country with data in only one year (or none at all yet)
        # still gets its own row, at 0, instead of being silently absent
        # until the platform decides some other row is "non-zero enough" to
        # bother showing. This is the same exhaustive list Corporate Units
        # already shows, so all three sub-tabs always agree on which rows
        # exist — adding data for a country never requires "creating a row"
        # anywhere; the row was always there.
        gj_pivot = pd.DataFrame()
        if not mdf.empty and company:
            co_df = mdf[mdf["Company"] == company].set_index("Year")
            if not co_df.empty:
                gj_rows = {}
                for country in ALL_COUNTRIES:
                    col = COUNTRY_COL_GJ.get(country)
                    if col and col in co_df.columns:
                        s = pd.to_numeric(co_df[col], errors="coerce")
                        gj_rows[country] = s.reindex(YEARS).fillna(0.0)
                    else:
                        gj_rows[country] = pd.Series(0.0, index=YEARS)
                gj_pivot = pd.DataFrame(gj_rows, index=YEARS).T   # rows=country, cols=year (int)

        if unit_mode == "common":
            st.caption("MWh × 3.6. Normalised values used in all analytics and benchmarking.")
            if not gj_pivot.empty:
                _disp = gj_pivot.rename(columns={y: str(y) for y in gj_pivot.columns})
                _disp.insert(0, "Unit", "GJ")
                _disp.index.name = "Country"
                _curr = str(rep_year)
                def _style_common(row):
                    return ["background-color:#DBEAFE;color:#1D4ED8;font-weight:800" if col == _curr
                            else "" for col in row.index]
                _styled_common = _disp.style.apply(_style_common, axis=1)
                st.dataframe(
                    _styled_common, use_container_width=True, hide_index=False,
                    height=min(900, max(220, len(_disp) * 38 + 60)),
                    column_config={
                        "_index": st.column_config.Column("Country", width=230),
                        "Unit":   st.column_config.Column("Unit", width=70),
                        **{str(y): st.column_config.NumberColumn(str(y), format="%.2f", width=100) for y in gj_pivot.columns},
                    },
                )
                total_gj = gj_pivot[rep_year].sum() if rep_year in gj_pivot.columns else 0
                st.metric(f"Total ({rep_year})", f"{total_gj:,.0f} GJ  ≈ {total_gj/3.6:,.0f} MWh")
                return
            st.info("No country electricity data yet.")
            return

        # unit_mode == "iea" — computed LIVE from the GJ pivot above using
        # the grid emission factors in conversion_data.py, rather than from
        # a separately-persisted IEA_CO2_*_tCO2 column. That column only
        # ever gets written by the save paths that know to compute it —
        # any data saved before that existed (or by a path that doesn't call
        # it) leaves the IEA tab empty even though the GJ data it needs is
        # right there. Computing it on the fly means this tab is correct
        # for every existing record immediately, no backfill required.
        import conversion_data as cd
        st.caption("tCO₂ per country, as computed in the TIP template: MWh × IEA grid EF.")
        if not gj_pivot.empty:
            iea_rows = {}
            for country in gj_pivot.index:
                row = []
                for yr in gj_pivot.columns:
                    ef = cd.get_grid_ef(country, int(yr))
                    gj = gj_pivot.loc[country, yr]
                    row.append(round((gj / 3.6) * ef / 1000.0, 4) if ef is not None else 0.0)
                iea_rows[country] = row
            iea_pivot = pd.DataFrame(iea_rows, index=list(gj_pivot.columns)).T
            _disp = iea_pivot.rename(columns={y: str(y) for y in iea_pivot.columns})
            _disp.insert(0, "Unit", "tCO₂")
            _disp.index.name = "Country"
            _curr = str(rep_year)
            def _style_iea(row):
                return ["background-color:#DBEAFE;color:#1D4ED8;font-weight:800" if col == _curr
                        else "" for col in row.index]
            _styled_iea = _disp.style.apply(_style_iea, axis=1)
            st.dataframe(
                _styled_iea, use_container_width=True, hide_index=False,
                height=min(900, max(220, len(_disp) * 38 + 60)),
                column_config={
                    "_index": st.column_config.Column("Country", width=230),
                    "Unit":   st.column_config.Column("Unit", width=70),
                    **{str(y): st.column_config.NumberColumn(str(y), format="%.2f", width=100) for y in iea_pivot.columns},
                },
            )
            total_iea = iea_pivot[rep_year].sum() if rep_year in iea_pivot.columns else 0
            st.metric(f"Total CO₂ from electricity ({rep_year})", f"{total_iea:,.0f} tCO₂")
            return
        st.info("No IEA CO₂ data yet — submit country electricity data first.")
        return

    # ── Corporate Units (MWh) editable grid — fall through ───────────────────

    # Countries shown in the UI — full IEA taxonomy (~150 entries across 8
    # macro-regions), grouped via state.ELEC_COUNTRY_REGIONS. Display-only for
    # countries not in the master schema until they have data.
    ELEC_COUNTRIES = state.ELEC_ALL_COUNTRIES
    COUNTRY_COL_GJ = state.ELEC_COUNTRY_COLS
    GJ_TO_MWH = 1.0 / 3.6



    # ── Key that tracks which company+year the editor was last initialised for ──
    # When this changes we rebuild elec_data from the master so the editor
    # always shows what is actually stored in the DB.
    load_key = f"{company}|{rep_year}"
    needs_reload = st.session_state.get("_elec_load_key") != load_key

    if needs_reload:
        # Build base DataFrame of zeros
        rows = [{"Country": c, "Unit": "MWh", **{str(yr): 0.0 for yr in YEARS}}
                for c in ELEC_COUNTRIES]
        df = pd.DataFrame(rows)

        # Pre-populate from master CSV for countries that are stored — fully
        # vectorized (one company filter, one pivot, one assign) instead of
        # the old per-country `.iterrows()` + linear `df.index[...]` scan,
        # which was O(countries × years) and the main load-time cost here.
        if not state.CONSOLIDATED_DF.empty and company:
            co_df = state.CONSOLIDATED_DF[state.CONSOLIDATED_DF["Company"] == company]
            if not co_df.empty and "Year" in co_df.columns:
                co_df = co_df.dropna(subset=["Year"]).copy()
                co_df["Year"] = co_df["Year"].astype(int)
                co_df = co_df[co_df["Year"] >= 2009].set_index("Year")

                # Extend YEARS for any year present in the master not yet covered
                _new_years = sorted(y for y in co_df.index.unique() if y not in YEARS)
                for yr in _new_years:
                    YEARS.append(yr)
                    df[str(yr)] = 0.0
                YEARS.sort()

                gj_to_country   = {v: k for k, v in COUNTRY_COL_GJ.items()}
                gj_cols_present = [c for c in COUNTRY_COL_GJ.values() if c in co_df.columns]
                if gj_cols_present:
                    # rows=Year, cols=country (renamed from Elec_*_GJ), in MWh
                    sub = (co_df[gj_cols_present].apply(pd.to_numeric, errors="coerce")
                           .fillna(0.0) * GJ_TO_MWH).round(2)
                    sub = sub.rename(columns=gj_to_country)
                    sub_t = sub.T
                    sub_t.columns = [str(c) for c in sub_t.columns]

                    df = df.set_index("Country")
                    common_idx = df.index.intersection(sub_t.index)
                    common_cols = df.columns.intersection(sub_t.columns)
                    df.loc[common_idx, common_cols] = sub_t.loc[common_idx, common_cols]
                    df = df.reset_index()

        # Ensure all year columns are numeric (avoid object dtype after assignment)
        for yr in YEARS:
            df[str(yr)] = pd.to_numeric(df[str(yr)], errors="coerce").fillna(0.0)

        # Comments column — ONE comment per country, scoped to the currently
        # selected reporting year (rep_year). Keys are namespaced "elec:<country>"
        # so they never collide with identically-named fields on other tabs.
        # Re-applied below on every render (not just on reload) so status
        # changes from Verification show up immediately.
        df["Comments"] = ""

        st.session_state.elec_data     = df
        st.session_state._elec_load_key = load_key
        # Drop the old widget key so Streamlit re-renders a fresh editor
        if "_elec_editor_key_idx" not in st.session_state:
            st.session_state._elec_editor_key_idx = 0
        st.session_state._elec_editor_key_idx += 1

    # Always refresh the Comments column from the live comment store for the
    # currently selected reporting year, so Accept/Seen/Reject from the
    # Verification Queue is reflected immediately without a full reload.
    _all_cmts_elec = _get_all_active_comments(company, rep_year)
    if "Comments" not in st.session_state.elec_data.columns:
        st.session_state.elec_data["Comments"] = ""
    for idx, c_name in st.session_state.elec_data["Country"].items():
        _e = _all_cmts_elec.get(f"elec:{c_name}")
        st.session_state.elec_data.loc[idx, "Comments"] = _e[1] if _e else ""

    st.caption(f"Values are entered via **Submit Data** and shown here read-only. "
               f"Comments below apply to reporting year **{rep_year}** and follow the dropdown.")

    # ── Region filter — ~150 countries is too long to scroll as one table. ────
    region_options = ["All regions"] + list(state.ELEC_COUNTRY_REGIONS.keys())
    sel_region = st.selectbox(
        "Show region", region_options, key=f"elec_region_filter_{company}_{rep_year}",
        help="Filters which countries are shown below. Your data for "
             "every region is still saved regardless of which one is selected.",
    )
    full_df = st.session_state.elec_data
    if sel_region == "All regions":
        view_df = full_df
    else:
        region_countries = set(state.ELEC_COUNTRY_REGIONS[sel_region])
        view_df = full_df[full_df["Country"].isin(region_countries)]

    # ── Editor key: unique per company+year+region so Streamlit does not reuse ─
    # the old internal widget state. Also bump on comment-store changes so
    # Accept/Seen/Reject is picked up immediately.
    editor_key = (f"elec_editor_{st.session_state.get('_elec_editor_key_idx', 0)}"
                  f"_v{len(_all_cmts_elec)}_{sel_region.replace(' ', '_')}")

    # Permanent "corrected value" marker — once a country's electricity
    # figure has ever had a change comment submitted for a given year (via
    # Submit Data or a direct comment here), that cell stays red/bold
    # forever, independent of the comment's later Seen/Rejected/Accepted
    # status — same mechanism as Main Data Input, Waste, and People & Governance.
    _edited_pairs_elec = _get_edited_field_years(company)
    curr_col = str(rep_year)

    # Build a display copy with year values formatted as text (matching the
    # other three tabs, which are all disabled/display TextColumns) — the
    # raw numeric data stays in st.session_state.elec_data for the totals
    # below, this copy is purely for rendering.
    _display_df = view_df.copy()
    for _yr in YEARS:
        _yc = str(_yr)
        if _yc in _display_df.columns:
            _display_df[_yc] = _display_df[_yc].map(lambda v: f"{float(v):,.2f}")

    # Country → original row position in the full 152-row frame, captured
    # before we reindex by Country for display (needed to freeze that column).
    _country_to_pos = dict(zip(view_df["Country"], view_df.index))

    # Snapshot of pre-edit comments for the VISIBLE rows only, keyed by row
    # position, so we can detect what actually changed after the editor returns.
    _comments_before = view_df["Comments"].copy()

    def _style_elec_row(row):
        country = row.name
        edited_key = f"elec:{country}"
        cmt = str(row.get("Comments", ""))
        styles = []
        for col in row.index:
            if col == "Comments":
                if cmt and not cmt.startswith("⏳") and not cmt.startswith("⚠"):
                    styles.append("color:#B91C1C;font-weight:800;font-size:11px;background:#FEF2F2")
                elif cmt.startswith("⏳"):
                    styles.append("color:#92400E;font-weight:600;font-size:11px;background:#FFFBEB")
                elif cmt.startswith("⚠"):
                    styles.append("color:#C2410C;font-weight:600;font-size:11px;background:#FFF7ED")
                else:
                    styles.append("color:#9CA3AF;font-size:11px")
                continue
            if col != "Unit" and (col, edited_key) in _edited_pairs_elec:
                styles.append("color:#B91C1C;font-weight:800")
            elif col == curr_col:
                styles.append("background-color:#DBEAFE;color:#1D4ED8;font-weight:800")
            elif col == "Unit":
                styles.append("")
            else:
                styles.append("background-color:#F0F9FF")
        return styles

    _styled_elec = _display_df.set_index("Country").style.apply(_style_elec_row, axis=1)

    col_cfg = {
        "Unit": st.column_config.TextColumn("Unit", disabled=True, width=70),
    }
    for yr in YEARS:
        col_cfg[str(yr)] = st.column_config.TextColumn(str(yr), disabled=True, width=100)
    col_cfg["Comments"] = st.column_config.TextColumn(
        "Comments ✏", width=160,
        help=f"One comment per country for {rep_year}. Type reason and press Enter → "
             "Pending (DSS will review). Clear cell and press Enter → deletes comment.",
    )
    col_cfg["_index"] = st.column_config.Column("Country", width=230, disabled=True)

    # Values are read-only (Submit Data is the single entry point) — only
    # the Comments column is editable here, same as the other three tabs.
    edited_view = st.data_editor(
        _styled_elec,
        column_config=col_cfg,
        hide_index=False,
        use_container_width=True,
        height=min(900, max(220, len(view_df) * 38 + 60)),
        key=editor_key,
        num_rows="fixed",
    )
    edited = edited_view.reset_index()
    edited.index = edited["Country"].map(_country_to_pos)

    # ── Persist any per-country comment changes for this reporting year ──────
    if "Comments" in edited.columns:
        actor = st.session_state.get("username", "Client")
        for idx, row_e in edited.iterrows():
            country  = row_e.get("Country", "")
            if not country:
                continue
            fk       = f"elec:{country}"
            new_cmt  = str(row_e.get("Comments", "")).strip()
            old_raw  = str(_comments_before.get(idx, "") or "")
            for _pfx in ("⏳ ", "⚠ "): old_raw = old_raw.replace(_pfx, "")
            old_raw  = old_raw.strip()
            if new_cmt == "" and old_raw:
                _delete_comment(company, rep_year, fk)
                _save_comment_version(company, rep_year, fk, old_raw, "Deleted", actor)
            elif new_cmt and new_cmt != old_raw:
                _save_change_comment(company, rep_year, fk,
                                     f"Electricity by Country — {country}",
                                     old_val="", new_val="", reason=new_cmt)

    st.markdown(f"""<div class="tbl-legend">
      <div class="tl"><div class="tl-sw" style="background:#F0F9FF;border-color:#BAE6FD"></div>Company input (historical)</div>
      <div class="tl"><div class="tl" style="color:#1D4ED8;font-weight:800;padding:0 6px">{rep_year}</div>Selected reporting year — bold blue text, whole column</div>
      <div class="tl"><div class="tl-sw" style="background:#FEF2F2;border-color:#FCA5A5"></div>Change comment (Pending/⏳Seen/⚠Rejected)</div>
    </div>""", unsafe_allow_html=True)

    # ── Summary metrics — always computed from the FULL 152-country frame, ────
    # not just whichever region is currently filtered/visible.
    rep_yr_str = str(rep_year)
    full_df    = st.session_state.elec_data
    total_rep  = full_df[rep_yr_str].sum() if rep_yr_str in full_df.columns else 0
    total_all  = sum(full_df[str(yr)].sum() for yr in YEARS if str(yr) in full_df.columns)
    c1, c2 = st.columns(2)
    c1.metric(f"Total — {rep_yr_str} (all countries)", f"{total_rep:,.0f} MWh")
    c2.metric("Grand total all years", f"{total_all:,.0f} MWh")