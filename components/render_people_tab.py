"""
components/render_people_tab.py — People & Governance section (H&S, Diversity, SBT).
All globals are read from state.py which app.py keeps up-to-date.
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import logging

import state
from utils.helpers import get_hist_outputs
from utils.data_utils import _load_supplementary          # now master-backed
from utils.comment_utils import (
    save_change_comment as _save_change_comment,
    get_all_active_comments as _get_all_active_comments,
    delete_comment as _delete_comment,
    save_comment_version as _save_comment_version,
    get_edited_field_years as _get_edited_field_years,
)

_log = logging.getLogger("esg_app")


def _render_people_governance_tab():
    """
    People & Governance tab shown in My Records and Company Data.
    Reads live data from master CSV (promoted from supplementary) and displays
    as a structured table with all H&S, Diversity, and SBT fields across all years.
    """
    company  = st.session_state.get("reporting_company") or st.session_state.get("user_company") or ""
    rep_year = st.session_state.get("reporting_year", state.CURR_YEAR)
    hist     = get_hist_outputs()

    st.caption("Data entered via Submit Data → Sections 7–9. Submit new year to update.")

    # Row definitions: (label, unit, supp_key, master_col, is_section)
    PG_ROWS = [
        # H&S
        (True,  "Health & Safety",                  None,    None,       None),
        (False, "Total sites (H&S)",                "no.",   "hs_total_sites", None),
        (False, "Externally audited H&S sites",     "no.",   "hs_external_audit", "HS External Audit Sites"),
        (False, "— External audit coverage",        "%",     "hs_ext_pct",        "HS External Audit %"),
        (False, "Internally audited H&S sites",     "no.",   "hs_internal_audit", "HS Internal Audit Sites"),
        (False, "— Internal audit coverage",        "%",     "hs_int_pct",        "HS Internal Audit %"),
        # Diversity
        (True,  "Diversity & Inclusion",            None,    None,       None),
        (False, "Total employees",                  "no.",   "total_employees",   "Total Employees"),
        (False, "Female employees",                 "no.",   "female_employees",  "Female Employees"),
        (False, "— % Female employees",             "%",     "fem_emp_pct",       "Female Employees %"),
        (False, "Board of Directors (total)",       "no.",   "board_total",       "Board Total"),
        (False, "Female Board members",             "no.",   "female_board",      "Female Board"),
        (False, "— % Female Board",                 "%",     "fem_bod_pct",       "Female Board %"),
        # SBT
        (True,  "Science-Based Targets",            None,    None,       None),
        (False, "Total with SBT",                   "no.",   "sbt_total",         "SBT Total"),
        (False, "Validated",                        "no.",   "sbt_validated",     "SBT Validated"),
        (False, "Committed",                        "no.",   "sbt_committed",     "SBT Committed"),
        (False, "Non-committed",                    "no.",   "sbt_non_committed", "SBT Non-Committed"),
    ]

    # Pre-slice company rows once for the whole tab render
    _pg_df = None
    if not state.CONSOLIDATED_DF.empty and "Company" in state.CONSOLIDATED_DF.columns:
        _pg_df = (state.CONSOLIDATED_DF[state.CONSOLIDATED_DF["Company"] == company]
                  .set_index("Year"))

    def _get_supp_val(yr, master_col):
        """Read a P&G value from the master wide CSV (supplementary retired)."""
        if not master_col or _pg_df is None or _pg_df.empty:
            return 0.0
        if master_col not in _pg_df.columns or yr not in _pg_df.index:
            return 0.0
        v = _pg_df.at[yr, master_col]
        if pd.notna(v):
            try: return float(v)
            except (TypeError, ValueError): return 0.0
        return 0.0

    table_data = []
    yr_cols    = [str(yr) for yr, *_ in hist]

    for is_sec, label, unit, supp_key, master_col in PG_ROWS:
        row = {"Indicator": f"▸ {label.upper()}" if is_sec else ("  " + label), "Unit": unit or ""}
        if is_sec:
            for yc in yr_cols: row[yc] = ""
            row["YoY %"] = ""
            table_data.append(row); continue

        vals_num = []
        for yr, hi, ho in hist:
            # H&S coverage denominator = the H&S total-sites the company entered
            # (falls back to the company-wide site count when not recorded).
            hs_tot = _get_supp_val(yr, "HS Total Sites") or (int(hi.total_sites) or 1)

            if supp_key == "hs_total_sites":
                v = hs_tot
            elif supp_key == "hs_ext_pct":
                ext = _get_supp_val(yr, "HS External Audit Sites")
                v = round(ext / max(hs_tot, 1) * 100, 1)
            elif supp_key == "hs_int_pct":
                intr = _get_supp_val(yr, "HS Internal Audit Sites")
                v = round(intr / max(hs_tot, 1) * 100, 1)
            elif supp_key == "fem_emp_pct":
                emp = _get_supp_val(yr, "Total Employees")
                fem = _get_supp_val(yr, "Female Employees")
                v = round(fem / max(emp, 1) * 100, 1)
            elif supp_key == "fem_bod_pct":
                bod = _get_supp_val(yr, "Board Total")
                fem = _get_supp_val(yr, "Female Board")
                v = round(fem / max(bod, 1) * 100, 1)
            else:
                v = _get_supp_val(yr, master_col)

            try:
                fv = float(v)
                if unit == "%":
                    row[str(yr)] = f"{fv:.1f}%"
                elif fv == int(fv):
                    row[str(yr)] = f"{int(fv):,}" if fv else "—"
                else:
                    row[str(yr)] = f"{fv:,.1f}"
                if fv: vals_num.append(fv)
            except:
                row[str(yr)] = "—"

        row["YoY %"] = "—"
        if len(vals_num) >= 2:
            pv, lv = vals_num[-2], vals_num[-1]
            if pv:
                row["YoY %"] = f"{(lv-pv)/abs(pv)*100:+.1f}%"

        table_data.append(row)

    if table_data:
        df_pg = pd.DataFrame(table_data)
        cols  = ["Indicator","Unit"] + yr_cols + ["YoY %"]
        df_pg = df_pg.reindex(columns=[c for c in cols if c in df_pg.columns])

        # Full Pending/Seen/Rejected/Approved comment workflow — same mechanism
        # as the main KPI template and Waste tab. Keys are namespaced "pg:<key>"
        # so they never collide with identically-named fields on other tabs.
        _all_cmts = _get_all_active_comments(company, rep_year)
        df_pg["Comments"] = ""
        for r_idx, (is_sec, label, unit, supp_key, master_col) in enumerate(PG_ROWS):
            if is_sec or not supp_key:
                continue
            fk = f"pg:{supp_key}"
            _e = _all_cmts.get(fk)
            if _e:
                df_pg.loc[r_idx, "Comments"] = _e[1]

        all_types_pg = ["section" if r[0] else "input" for r in PG_ROWS]
        all_keys_pg  = [f"pg:{r[3]}" if (not r[0] and r[3]) else "" for r in PG_ROWS]

        disp_cols_pg  = [c for c in df_pg.columns if c != "Indicator"]
        _label_to_pos_pg = {lbl: i for i, lbl in enumerate(df_pg["Indicator"])}

        _edited_pairs_pg = _get_edited_field_years(company)

        def _style_pg(row, idx):
            rt  = all_types_pg[idx] if idx < len(all_types_pg) else "input"
            cmt = str(row.get("Comments", ""))
            edited_key = all_keys_pg[idx] if idx < len(all_keys_pg) else ""
            styles = []
            for col in disp_cols_pg:
                if (edited_key and rt == "input"
                        and col not in ("Unit", "YoY %", "Comments")
                        and (col, edited_key) in _edited_pairs_pg):
                    styles.append("color:#B91C1C;font-weight:800")
                    continue
                if col == str(rep_year):
                    cell = "background-color:#DBEAFE;color:#1D4ED8;font-weight:800"
                    if rt == "section":
                        cell += ";font-size:13px;letter-spacing:.3px;text-transform:uppercase"
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
                else:
                    styles.append("background-color:#F0F9FF;")
            return styles

        def _index_style_pg(idx):
            styles = []
            for lbl in idx:
                pos = _label_to_pos_pg.get(lbl)
                if pos is not None and all_types_pg[pos] == "section":
                    styles.append("font-weight:800;background-color:#E8F5F0;color:#065F46;"
                                  "font-size:13px;text-transform:uppercase;letter-spacing:.3px;"
                                  "border-top:2px solid #6EE7B7")
                else:
                    styles.append("")
            return styles

        _cmt_ver_pg = len(_all_cmts)
        df_pg_idx = df_pg.set_index("Indicator")
        _styled_pg = df_pg_idx.style.apply(
            lambda row: _style_pg(row, _label_to_pos_pg.get(row.name, 0)), axis=1)
        _styled_pg = _styled_pg.apply_index(_index_style_pg, axis=0)
        edited_pg = st.data_editor(
            _styled_pg,
            use_container_width=True, hide_index=False,
            column_config={
                "_index":    st.column_config.Column("Indicator", width=230, disabled=True),
                "Unit":      st.column_config.TextColumn("Unit", width=70, disabled=True),
                **{yc: st.column_config.TextColumn(disabled=True, width=100) for yc in yr_cols},
                "YoY %":     st.column_config.TextColumn("YoY %", width=70, disabled=True),
                "Comments":  st.column_config.TextColumn(
                    "Comments ✏", width=160,
                    help="Type reason and press Enter → Pending (DSS will review). "
                         "Clear cell and press Enter → deletes comment.",
                ),
            },
            height=min(38 + len(table_data) * 35, 740),
            key=f"pg_tbl_editor_{company}_{rep_year}_v{_cmt_ver_pg}",
        )

        if edited_pg is not None and "Comments" in edited_pg.columns:
            actor = st.session_state.get("username", "Client")
            for idx_r, row_e in edited_pg.iterrows():
                pos = _label_to_pos_pg.get(idx_r)
                if pos is None:
                    continue
                fk_r = all_keys_pg[pos] if pos < len(all_keys_pg) else ""
                if not fk_r:
                    continue
                new_cmt = str(row_e.get("Comments", "")).strip()
                lbl_r   = "People & Governance — " + str(idx_r).strip()
                old_raw = str(df_pg.loc[pos, "Comments"] or "")
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
          <div class="tl"><div class="tl-sw" style="background:#FEF2F2;border-color:#FCA5A5"></div>Change comment (Pending/⏳Seen/⚠Rejected)</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.info("No People & Governance data available. Submit data via Sections 7–9 in Submit Data.")