"""
components/render_waste_tab.py — Waste data section.
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


def render_waste_tab():
    inp, out = get_current_outputs()
    hist     = get_hist_outputs()
    rep_year = st.session_state.get("reporting_year", state.CURR_YEAR)
    company  = st.session_state.get("reporting_company") or st.session_state.get("user_company") or ""
    _mode    = st.session_state.get("unit_mode", "corporate")
    st.caption("Total waste must equal Recovery + Elimination. The consistency check validates this. "
               "Waste is reported in metric T either way — there's no unit conversion for this section.")

    WASTE_ROWS = [
        ("section","Global Information",None,None,None),
        ("input","Total no. of sites","no.","total_sites",None),
        ("input","Production","metric t","production",None),
        ("section","Waste",None,None,None),
        ("input","Total amount of waste","metric t","waste_total",None),
        ("input","Amount of waste sent to recovery","metric t","waste_recovery",None),
        ("calc","Amount of waste sent to elimination","metric t",None,lambda i,o:f"{o.waste_elimination:,.0f}"),
        ("calc","Consistency check","—",None,lambda i,o:"OK" if o.check_waste else "Error"),
        ("calc","Recovery rate","%",None,lambda i,o:f"{o.waste_recovery_pct*100:.1f}%"),
        ("calc","Waste intensity","kg/T prod",None,lambda i,o:f"{i.waste_total/i.production*1000:.2f}" if i.production else "—"),
    ]

    # Comments are only ever attached to the actual input field that was
    # changed (e.g. "Total amount of waste") — never to the calc rows that
    # are derived from it (e.g. "Amount of waste sent to elimination",
    # "Recovery rate"), since editing the input is the real event and the
    # calc rows just reflect the formula. Keys are namespaced "waste:<key>"
    # so they never collide with the same field name used on other tabs.
    _all_cmts = _get_all_active_comments(company, rep_year)

    data = []
    for rtype, label, unit, key, fn in WASTE_ROWS:
        if rtype == "section":
            row = {"Indicator": f"▸ {label.upper()}", "Unit": ""}
            for yr, hi, ho in hist: row[str(yr)] = ""
            row[str(rep_year)] = ""; row["YoY %"] = ""; row["Comments"] = ""
            data.append({"_type":"section","_row":row,"_key":""}); continue
        row = {"Indicator": label, "Unit": unit or ""}
        hist_nums  = []
        hist_by_yr = {}
        for yr, hi, ho in hist:
            v = getattr(hi, key, None) if key else None
            if v is None and fn: v = fn(hi, ho)
            try:
                row[str(yr)] = f"{int(round(float(v))):,}" if isinstance(v,(int,float)) else (str(v) if v else "—")
            except (TypeError, ValueError):
                row[str(yr)] = str(v) if v is not None else "—"
            try:
                numv = float(str(v).replace(",","").replace("%","").replace("—","0"))
            except:
                numv = 0
            hist_nums.append(numv)
            hist_by_yr[yr] = numv
        cv = getattr(inp, key, None) if key else None
        if cv is None and fn: cv = fn(inp, out)
        row[str(rep_year)] = str(cv) if cv is not None else "—"
        try:
            cn = float(str(cv).replace(",","").replace("%",""))
            # Look up rep_year-1 explicitly — using hist_nums[-1] (last item)
            # breaks once padding years with no data sit after it in the list.
            pn = hist_by_yr.get(rep_year - 1, 0)
            row["YoY %"] = f"{(cn-pn)/abs(pn)*100:+.1f}%" if pn else "—"
        except: row["YoY %"] = "—"

        fk = f"waste:{key}" if (rtype == "input" and key) else ""
        if fk:
            _e = _all_cmts.get(fk)
            row["Comments"] = _e[1] if _e else ""
        else:
            row["Comments"] = ""  # calc rows: no comment field, not editable
        data.append({"_type":rtype,"_row":row,"_key":fk})

    all_rows  = [d["_row"]  for d in data]
    all_types = [d["_type"] for d in data]
    all_keys  = [d["_key"]  for d in data]
    df_w = pd.DataFrame(all_rows)
    curr_col = str(rep_year)
    disp_cols = [c for c in df_w.columns if c != "Indicator"]
    _label_to_pos = {lbl: i for i, lbl in enumerate(df_w["Indicator"])}

    _edited_pairs = _get_edited_field_years(company)

    def _style_waste(row, idx):
        rt  = all_types[idx]
        cmt = str(row.get("Comments", ""))
        edited_key = all_keys[idx] if idx < len(all_keys) else ""
        styles = []
        for col in disp_cols:
            if (edited_key and rt == "input"
                    and col not in ("Unit", "YoY %", "Comments")
                    and (col, edited_key) in _edited_pairs):
                styles.append("color:#B91C1C;font-weight:800")
                continue
            if col == curr_col:
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
                elif rt == "calc":
                    styles.append("background:#F8FAFC;color:#D1D5DB")  # not editable
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

    def _index_style_waste(idx):
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

    _cmt_ver = len(_all_cmts)
    df_w_idx = df_w.set_index("Indicator")
    _styled_w = df_w_idx.style.apply(
        lambda row: _style_waste(row, _label_to_pos.get(row.name, 0)), axis=1)
    _styled_w = _styled_w.apply_index(_index_style_waste, axis=0)
    edited_w = st.data_editor(
        _styled_w,
        hide_index=False, use_container_width=True, height=min(560, max(400, len(all_rows)*38+60)),
        column_config={
            "_index":    st.column_config.Column("Indicator", width=230, disabled=True),
            "Unit":      st.column_config.TextColumn(disabled=True, width=70),
            "YoY %":     st.column_config.TextColumn(disabled=True, width=70),
            **{str(yr): st.column_config.TextColumn(disabled=True, width=100) for yr, *_ in hist},
            "Comments":  st.column_config.TextColumn(
                "Comments ✏", width=160,
                help="Type reason and press Enter → Pending (DSS will review). "
                     "Only enabled on input rows — calc rows (e.g. Recovery rate) "
                     "inherit their value from the input you comment on.",
            ),
        },
        key=f"waste_tbl_editor_{company}_{rep_year}_v{_cmt_ver}",
    )

    if edited_w is not None and "Comments" in edited_w.columns:
        actor = st.session_state.get("username", "Client")
        for idx_r, row_e in edited_w.iterrows():
            pos = _label_to_pos.get(idx_r)
            if pos is None:
                continue
            fk_r = all_keys[pos] if pos < len(all_keys) else ""
            if not fk_r:
                continue  # section/calc row — not commentable
            new_cmt = str(row_e.get("Comments", "")).strip()
            lbl_r   = "Waste — " + str(idx_r).strip()
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

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Waste", f"{inp.waste_total:,.0f} T")
    c2.metric("Recovery Rate", f"{out.waste_recovery_pct*100:.1f}%")
    c3.metric("Consistency", "OK" if out.check_waste else "Error")