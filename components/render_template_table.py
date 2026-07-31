"""
components/render_template_table.py — KPI template table with Comments column.
Used by both page_my_records (client) and page_company_data (DSS).
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
import field_registry as fr
import conversion_data as cd
from utils.helpers import (
    get_hist_outputs, _get_fresh_hist, get_current_outputs,
    _load_company_year_outputs, _compute_industry_scores,
    _compute_kpi_improvement, _chart_key,
    _compute_completeness, _compute_readiness_score,
    _dss_company_selector,
)
from utils.data_utils import _load_supplementary
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
import html as _html
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


def render_template_table():
    company  = st.session_state.get("reporting_company") or st.session_state.get("user_company") or "TIP Member Company"
    if company == "All Companies": company = "TIP Member Company"
    rep_year = st.session_state.get("reporting_year", state.CURR_YEAR)
    # "corporate" → show each year's value in whatever unit the company actually
    # entered it in (can differ year to year); "common" → show the normalised
    # GJ/common-unit value everything is converted to for calculations.
    unit_mode = st.session_state.get("unit_mode", "corporate")
    # Always reload from state.CONSOLIDATED_DF so updates to any year are visible
    _hist    = _get_fresh_hist(company)

    def _corp_value_and_unit(yr, key):
        """Look up a registered unit-bearing field's corporate (as-entered)
        value + unit for a specific year, straight from the master CSV —
        same columns page_entry.py's Submit Data form writes to. Returns
        (None, None) if this field isn't unit-bearing, or that year predates
        the unit system (no corp/unit columns recorded yet)."""
        uf = fr.BY_FIELD.get(key)
        if uf is None or state.CONSOLIDATED_DF.empty:
            return None, None
        df = state.CONSOLIDATED_DF
        corp_col, unit_col = fr.corporate_col(uf), fr.unit_col(uf)
        if corp_col not in df.columns or unit_col not in df.columns or "Company" not in df.columns:
            return None, None
        rowm = df[(df["Company"] == company) & (df["Year"] == yr)]
        if rowm.empty:
            return None, None
        cv, un = rowm.iloc[0].get(corp_col), rowm.iloc[0].get(unit_col)
        if pd.isna(cv) or pd.isna(un) or not un:
            return None, None
        try:
            return float(cv), str(un)
        except (TypeError, ValueError):
            return None, None

    if unit_mode == "corporate":
        st.info("Showing each year's value in the unit the company actually entered it in "
                 "(shown inline per cell, since it can change year to year). "
                 "Blue cells = company input, grey italic = auto-calculated formula.")
    else:
        st.info("Showing values normalised to common units (GJ for energy) — what's used in "
                 "all calculations and benchmarking. Blue cells = company input, grey italic = auto-calculated formula.")

    # ── Data sources — all from state.CONSOLIDATED_DF so saves are immediately visible ──
    hist = get_hist_outputs()   # ALL years including current year

    # For the current reporting year prefer _codata_inp (freshest — set right after save)
    if (st.session_state.get("_codata_inp") is not None and
            getattr(st.session_state["_codata_inp"], "year", None) == rep_year):
        inp = st.session_state["_codata_inp"]
        out = st.session_state["_codata_out"]
    else:
        inp, out = _load_company_year_outputs(company, rep_year)

    # Always ensure current year is in hist with the freshest values
    hist = sorted(
        [(yr, hi, ho) for yr, hi, ho in hist if yr != rep_year] + [(rep_year, inp, out)],
        key=lambda t: t[0],
    )
    # Year-keyed lookup — used below to find rep_year-1 reliably even when
    # padding years (no data yet) sit after it in the chronological list.
    hist_by_yr = {yr: (hi, ho) for yr, hi, ho in hist}

    ROWS = [
        ("section","ISO 14001",None,None,None),
        ("input","Total no. of sites","no.","total_sites",None),
        ("input","ISO 14001 certified sites","no.","iso_sites",None),
        ("calc","% certified sites","%",None,lambda i,o:f"{o.pct_certified*100:.1f}%"),
        ("section","Production",None,None,None),
        ("input","Production","metric t","production",None),
        ("section","Water",None,None,None),
        ("input","Water withdrawals","m³","water_withdrawals",None),
        ("supp","Stress water withdrawal","m³","stress_water_withdrawal",None),
        ("supp","Non-stress water withdrawal","m³","non_stress_water_withdrawal",None),
        ("calc","Water intensity KPI","m³/t",None,lambda i,o:f"{o.water_kpi:.2f}"),
        ("section","Energy",None,None,None),
        ("calc","Total Electricity","GJ",None,lambda i,o:f"{o.total_electricity:,.0f}"),
        ("input","— Renewable electricity purchased","GJ","renew_elec_purchased",None),
        ("input","— Non-renewable electricity purchased","GJ","nonrenew_elec_purchased",None),
        ("input","— Self-generated renewable on-site","GJ","self_gen_elec",None),
        ("input","Purchased Steam","GJ","purchased_steam",None),
        ("input","Sold Electricity","GJ","sold_electricity",None),
        ("input","Sold Steam","GJ","sold_steam",None),
        ("input","Natural Gas","GJ LHV","nat_gas",None),
        ("input","Coal (all types)","GJ LHV","coal_sub",None),
        ("supp","— Sub-bituminous coal","GJ LHV","coal_sub_bituminous",None),
        ("supp","— Brown coal briquettes","GJ LHV","coal_brown_briquettes",None),
        ("supp","— Other bituminous coal","GJ LHV","coal_other_bituminous",None),
        ("input","Propane","GJ LHV","propane",None),
        ("input","Fuel Oil","GJ LHV","fuel_oil_heavy_a",None),
        ("input","Diesel","GJ LHV","diesel",None),
        ("input","Petrol","GJ LHV","petrol",None),
        ("input","Biomass","GJ LHV","biomass",None),
        ("input","Waste tires","metric t","waste_tires_mt",None),
        ("input","LPG","GJ LHV","lpg",None),
        ("input","Other fuels","GJ LHV","other_fuels",None),
        ("calc","TOTAL ENERGY","GJ",None,lambda i,o:f"{o.total_energy:,.0f}"),
        ("calc","Energy intensity KPI","GJ/t",None,lambda i,o:f"{o.energy_kpi:.2f}"),
        ("section","CO2 Emissions",None,None,None),
        ("input","Scope 2 — Steam","T.CO2","co2_scope2_steam",None),
        ("calc","CO2 — Natural Gas","T.CO2",None,lambda i,o:f"{o.co2_nat_gas:,.0f}"),
        ("calc","CO2 — Coal","T.CO2",None,lambda i,o:f"{o.co2_coal:,.0f}"),
        ("calc","CO2 — Propane","T.CO2",None,lambda i,o:f"{o.co2_propane:,.0f}"),
        ("calc","CO2 — Fuel Oil","T.CO2",None,lambda i,o:f"{o.co2_fuel_oil:,.0f}"),
        ("calc","CO2 — Diesel","T.CO2",None,lambda i,o:f"{o.co2_diesel:,.0f}"),
        ("calc","CO2 — Petrol","T.CO2",None,lambda i,o:f"{o.co2_petrol:,.0f}"),
        ("calc","CO2 — LPG","T.CO2",None,lambda i,o:f"{o.co2_lpg:,.0f}"),
        ("calc","TOTAL CO2 Scope 1","T.CO2",None,lambda i,o:f"{o.total_co2_scope1:,.0f}"),
        ("calc","TOTAL CO2 Scope 2","T.CO2",None,lambda i,o:f"{o.total_co2_scope2:,.0f}"),
        ("calc","TOTAL CO2 (S1+S2)","T.CO2",None,lambda i,o:f"{o.total_co2:,.0f}"),
        ("calc","CO2 intensity KPI","T.CO2/T",None,lambda i,o:f"{o.co2_kpi:.3f}"),
        ("section","Waste",None,None,None),
        ("input","Total waste generated","metric t","waste_total",None),
        ("input","Waste sent to recovery","metric t","waste_recovery",None),
        ("calc","Waste sent to elimination","metric t",None,lambda i,o:f"{o.waste_elimination:,.0f}"),
        ("calc","Recovery rate","%",None,lambda i,o:f"{o.waste_recovery_pct*100:.1f}%"),
        ("calc","Waste intensity KPI","kg/T",None,lambda i,o:f"{i.waste_total/i.production*1000:.1f}" if i.production else "—"),
    ]

    _all_cmts = _get_all_active_comments(company, rep_year)

    data = []
    for rdef in ROWS:
        rtype, label, unit, key, fn = rdef
        if rtype == "section":
            row = {"Indicator": f"▸ {label.upper()}", "Unit": ""}
            for yr, hi, ho in hist: row[str(yr)] = ""
            row["YoY %"] = ""
            row["Comments"] = ""
            data.append({"_type": "section", "_row": row, "_key": "", "_label": label})
            continue

        row = {"Indicator": label, "Unit": unit or ""}
        _is_unit_bearing = bool(key and fr.BY_FIELD.get(key) is not None)
        _row_corp_units = {}  # yr -> unit actually used that year (corporate mode only)
        if unit_mode == "corporate" and _is_unit_bearing:
            # The unit can change year to year, so first scan history to find
            # what was actually used. We show ONE unit in the Unit column —
            # preferring the reporting year's unit, then the most recent year
            # that has one, then falling back to the canonical common unit
            # for companies that have never touched the unit dropdown.
            for yr, _, _ in hist:
                _, cu = _corp_value_and_unit(yr, key)
                if cu:
                    _row_corp_units[yr] = cu
            if rep_year in _row_corp_units:
                row["Unit"] = _row_corp_units[rep_year]
            elif _row_corp_units:
                row["Unit"] = _row_corp_units[max(_row_corp_units)]
            # else: leave the canonical unit already set above as the fallback

        prev_num = None
        for yr, hi, ho in hist:
            if unit_mode == "corporate" and _is_unit_bearing:
                cv, cu = _corp_value_and_unit(yr, key)
                if cv is not None:
                    row[str(yr)] = f"{cv:,.0f}"
                    prev_num = cv
                    continue
                # No corp/unit history yet for this year (predates the unit
                # system) — fall back to the common-unit value, same
                # "assume it was already common-unit" rule page_entry.py uses.
                v_fallback = getattr(hi, key, None)
                if v_fallback is not None:
                    try:
                        row[str(yr)] = f"{float(v_fallback):,.0f}"
                        prev_num = float(v_fallback)
                        continue
                    except (TypeError, ValueError):
                        pass

            # supp rows read from master CSV supplementary columns
            if rtype == "supp" and key:
                yr_supp = _load_supplementary(company, yr)
                v = yr_supp.get(key, None)
                # also check master CSV columns (after migration)
                if v is None:
                    _mrow = state.CONSOLIDATED_DF[
                        (state.CONSOLIDATED_DF.get("Company","") == company) &
                        (state.CONSOLIDATED_DF.get("Year","") == yr)
                    ] if not state.CONSOLIDATED_DF.empty and "Company" in state.CONSOLIDATED_DF.columns else None
                    if _mrow is not None and not _mrow.empty:
                        _col_map = {
                            "stress_water_withdrawal":   "Stress Water Withdrawal",
                            "non_stress_water_withdrawal":"Non-Stress Water Withdrawal",
                            "coal_sub_bituminous":       "Coal Sub-Bituminous",
                            "coal_brown_briquettes":     "Coal Brown Briquettes",
                            "coal_other_bituminous":     "Coal Other Bituminous",
                            "hs_external_audit":         "HS External Audit Sites",
                            "hs_internal_audit":         "HS Internal Audit Sites",
                            "total_employees":           "Total Employees",
                            "female_employees":          "Female Employees",
                            "board_total":               "Board Total",
                            "female_board":              "Female Board",
                            "sbt_total":                 "SBT Total",
                            "sbt_validated":             "SBT Validated",
                            "sbt_committed":             "SBT Committed",
                            "sbt_non_committed":         "SBT Non-Committed",
                        }
                        mc = _col_map.get(key)
                        if mc and mc in _mrow.columns:
                            v = _mrow[mc].values[0]
            else:
                v = getattr(hi, key, None) if key else None
            if v is None and fn:
                v = fn(hi, ho)
            try:
                row[str(yr)] = f"{int(round(float(v))):,}"
            except (TypeError, ValueError):
                row[str(yr)] = str(v) if v else "—"
            try:
                prev_num = float(str(v).replace(",", "").replace("%", "").replace("—", "0"))
            except:
                pass

        # YoY %: compare raw floats — avoids string formatting artifacts
        def _rv(hi, ho, k, f):
            if k:
                v = getattr(hi, k, None)
                if v is not None:
                    try: return float(v)
                    except: pass
            if f:
                raw = f(hi, ho)
                try: return float(str(raw).replace(",","").replace("%","")
                                          .replace("—","0") or "0")
                except: pass
            return None
        curr_num = _rv(inp, out, key, fn)
        prev_num = None
        prev_entry = hist_by_yr.get(rep_year - 1)
        if prev_entry is not None:
            ph, po = prev_entry
            prev_num = _rv(ph, po, key, fn)
        try:
            if curr_num is not None and prev_num is not None and prev_num != 0:
                row["YoY %"] = f"{(curr_num-prev_num)/abs(prev_num)*100:+.1f}%"
            else:
                row["YoY %"] = "—"
        except:
            row["YoY %"] = "—"

        fk = key or label
        _e = _all_cmts.get(fk)
        row["Comments"] = _e[1] if _e else ""
        data.append({"_type": rtype, "_row": row, "_key": key or "", "_label": label})

    all_rows       = [d["_row"]  for d in data]
    all_types      = [d["_type"] for d in data]
    _all_keys_list = [d["_key"]  for d in data]
    df_tbl         = pd.DataFrame(all_rows)
    curr_col       = str(rep_year)
    # Columns actually rendered as data columns once Indicator becomes the
    # (frozen) index — used by style_row below instead of df_tbl.columns,
    # since df_tbl itself gets reindexed further down.
    disp_cols      = [c for c in df_tbl.columns if c != "Indicator"]
    # Indicator labels are unique across ROWS, so this safely recovers each
    # row's original position after the DataFrame is reindexed by label.
    _label_to_pos  = {lbl: i for i, lbl in enumerate(df_tbl["Indicator"])}

    _edited_pairs = _get_edited_field_years(company)

    def style_row(row, idx):
        rt  = all_types[idx]
        cmt = str(row.get("Comments", ""))
        edited_key = _all_keys_list[idx] if idx < len(_all_keys_list) else ""
        styles = []
        for col in disp_cols:
            # Permanent "corrected value" marker — once a field has ever had
            # a change comment submitted for it, that specific year's cell
            # stays red/bold forever, independent of whether the comment
            # itself is later Seen / Rejected / Accepted.
            if (edited_key and rt in ("input", "supp")
                    and col not in ("Unit", "YoY %", "Comments")
                    and (col, edited_key) in _edited_pairs):
                styles.append("color:#B91C1C;font-weight:800")
                continue
            if col == curr_col:
                # Selected reporting-year column: highlighted background +
                # bold blue text, all the way down — including section rows —
                # and follows whichever year is picked in the dropdown
                # (curr_col = str(rep_year)).
                cell = "background-color:#DBEAFE;color:#1D4ED8;font-weight:800"
                if rt == "section":
                    cell += ";font-size:13px;letter-spacing:.3px;text-transform:uppercase"
                elif rt == "calc":
                    cell += ";font-style:italic"
                styles.append(cell)
            elif col == "Comments":
                if rt == "section":
                    styles.append("background-color:#E8F5F0;color:#065F46;font-weight:800;font-size:13px;"
                                   "border-top:2px solid #6EE7B7;padding-top:8px;padding-bottom:8px;"
                                   "letter-spacing:.3px;text-transform:uppercase")
                elif cmt and not cmt.startswith("⏳") and not cmt.startswith("⚠"):
                    styles.append("color:#B91C1C;font-weight:800;font-size:11px;background:#FEF2F2")
                elif cmt.startswith("⏳"):
                    styles.append("color:#92400E;font-weight:600;font-size:11px;background:#FFFBEB")
                elif cmt.startswith("⚠"):
                    styles.append("color:#C2410C;font-weight:600;font-size:11px;background:#FFF7ED")
                else:
                    styles.append("color:#9CA3AF;font-size:11px")
            elif rt == "section":
                styles.append("background-color:#E8F5F0;color:#065F46;font-weight:800;font-size:13px;"
                               "border-top:2px solid #6EE7B7;padding-top:8px;padding-bottom:8px;"
                               "letter-spacing:.3px;text-transform:uppercase")
            elif rt == "calc":
                styles.append("background-color:#F8FAFC;color:#6B7280;font-style:italic")
            else:
                styles.append("background-color:#F0F9FF;")
        return styles

    def _index_style(idx):
        """Style the frozen Indicator column itself — Styler.apply() only
        covers data columns, not the index, so without this the section
        subheadings (ISO 14001, Production, Water, Energy...) lost their
        bold/highlighted look on the label text when that column became
        the frozen index."""
        styles = []
        for lbl in idx:
            pos = _label_to_pos.get(lbl)
            if pos is not None and all_types[pos] == "section":
                styles.append("font-weight:800;background-color:#E8F5F0;color:#065F46;"
                              "font-size:13px;text-transform:uppercase;letter-spacing:.3px;"
                              "border-top:2px solid #6EE7B7")
            else:
                styles.append("")
        return styles

    df_tbl_idx = df_tbl.set_index("Indicator")
    styled     = df_tbl_idx.style.apply(
        lambda row: style_row(row, _label_to_pos.get(row.name, 0)), axis=1)
    styled     = styled.apply_index(_index_style, axis=0)
    tbl_height = min(900, max(400, len(all_rows)*36+60))
    _cmt_ver   = len(_all_cmts)

    edited_df = st.data_editor(
        styled, hide_index=False, height=tbl_height, use_container_width=True,
        column_config={
            # "_index" configures the frozen Indicator column — index columns
            # stick to the left on horizontal scroll by default in this grid,
            # which is what gives us the "freeze first column" behaviour.
            "_index":    st.column_config.Column("Indicator", width=230, disabled=True),
            "Unit":      st.column_config.TextColumn(disabled=True, width=70),
            "YoY %":     st.column_config.TextColumn(disabled=True, width=70),
            **{str(yr): st.column_config.TextColumn(disabled=True, width=100) for yr, *_ in hist},
            "Comments":  st.column_config.TextColumn(
                "Comments ✏", width=160,
                help="Type reason and press Enter → Pending. "
                     "Clear cell and press Enter → deletes comment.",
            ),
        },
        key=f"tbl_editor_{company}_{rep_year}_v{_cmt_ver}",
    )

    if edited_df is not None and "Comments" in edited_df.columns:
        actor = st.session_state.get("username", "Client")
        for idx_r, row_e in edited_df.iterrows():
            pos     = _label_to_pos.get(idx_r)
            if pos is None:
                continue
            new_cmt = str(row_e.get("Comments", "")).strip()
            fk_r    = _all_keys_list[pos] if pos < len(_all_keys_list) else ""
            lbl_r   = str(idx_r)
            old_raw = (all_rows[pos].get("Comments", "") or "")
            for _pfx in ("⏳ ", "⚠ "): old_raw = old_raw.replace(_pfx, "")
            old_raw = old_raw.strip()
            if new_cmt == "" and old_raw:
                _delete_comment(company, rep_year, fk_r)
                _save_comment_version(company, rep_year, fk_r, old_raw, "Deleted", actor)
            elif new_cmt and new_cmt != old_raw:
                _save_change_comment(company, rep_year, fk_r, lbl_r,
                                     old_val="", new_val="", reason=new_cmt)

    st.markdown(f"""<div class="tbl-legend">
      <div class="tl"><div class="tl-sw" style="background:#F0F9FF;border-color:#BAE6FD"></div>Company input (historical)</div>
      <div class="tl"><div class="tl" style="color:#1D4ED8;font-weight:800;padding:0 6px">{rep_year}</div>Selected reporting year — bold blue text, whole column</div>
      <div class="tl"><div class="tl-sw" style="background:#F8FAFC;border-color:#E5E7EB"></div>Auto-calculated (historical)</div>
      <div class="tl"><div class="tl-sw" style="background:#FEF2F2;border-color:#FCA5A5"></div>Change comment (Pending/⏳Seen/⚠Rejected)</div>
    </div>""", unsafe_allow_html=True)