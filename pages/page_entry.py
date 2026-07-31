"""
pages/page_entry.py — Submit Data form (live KPI entry, all sections).
Globals are read from state.py (populated by app.py at startup).
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, date

import html as _html
import config as cfg
import data_loader as dl
import state
import field_registry as fr
import conversion_data as cd
# helpers: none needed directly in page_entry
from utils.data_utils import (
    _load_supplementary,             # prefill P&G fields from master
    _save_supplementary,             # no-op shim (supplementary CSV retired)
    _save_submission_to_csv,         # writes wide + long master + parquet version
    _save_country_electricity_values,# writes Elec_*_GJ cols to master
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
import logging
_log = logging.getLogger("esg_app")
from formula_engine import TemplateInputs, calculate
from ui_components import (
    GREEN, AMBER, RED, NAVY, BG, BORDER, TEXT, MUTED,
    CAT_CO2, CAT_ENERGY, CAT_WATER, CAT_WASTE, CAT_RENEW,
)


def page_entry():
    """
    Submit Data — full comprehensive form covering all TIP KPI fields.
    Sections: Global Info · Water · Energy (Electricity + Fuels) · CO₂ ·
              Waste · Health & Safety · Diversity · Science-Based Targets
    Auto-calculates KPIs live. On submit → saves to master CSV + supplementary
    CSV. When editing a previous year, requires a change reason which goes
    to the Verification Queue for DSS approval before becoming visible.
    """
    from pathlib import Path as _P
    from formula_engine import EF as _EF, GJ_TO_MWH as _G2M, _DEFAULT_SCOPE2_ELEC_EF as _S2EF

    company   = st.session_state.user_company
    comp_hist = dl.get_company_hist(state.CONSOLIDATED_DF, company)
    all_yrs   = sorted(dl.get_years(state.CONSOLIDATED_DF, company) or [])

    # ── Header ────────────────────────────────────────────────────────────────
    h1, _sp, h2 = st.columns([2, 2, 1])
    with h1:
        st.markdown(f"""<div style="font-size:22px;font-weight:800;color:{TEXT};margin-top:4px">
          {_html.escape(company)}</div>
          <div style="font-size:12px;color:{MUTED}">ESG KPI Data Entry — All TIP Fields</div>
        """, unsafe_allow_html=True)
    with h2:
        # Always offer every year from the company's first reported year (or
        # the platform current year, if they have none yet) through
        # state.CURR_YEAR + 1. CURR_YEAR is the platform-wide most recent
        # year ANY company has data for (recalculated on every save via
        # cfg.refresh_year_bounds) — so the +1 means the moment any company
        # submits e.g. 2025, every company's dropdown immediately offers 2026
        # too, without needing to touch this file again. This also fixes the
        # old bug where a company that stopped at 2023 while the platform had
        # moved on to 2025 would see "2025, 2023, 2022..." with 2024 missing
        # entirely — the old code only unioned all_yrs with the single value
        # state.CURR_YEAR, never filling the gap between them.
        lo = all_yrs[0] if all_yrs else state.CURR_YEAR
        yr_options = sorted(set(all_yrs) | set(range(lo, state.CURR_YEAR + 2)), reverse=True)
        sel_yr = st.selectbox("Year", yr_options, key="entry_year_sel",
                              label_visibility="collapsed")

    is_new = sel_yr not in all_yrs
    is_editing_prior = (not is_new) and (sel_yr < max(all_yrs + [sel_yr]))
    if is_new:
        st.info(f"Entering **new data** for **{sel_yr}** — fields pre-filled from last year's projection")
    elif is_editing_prior:
        st.warning(f"Editing **existing data** for **{sel_yr}** — any changes will require a reason and DSS approval")
    else:
        st.info(f"Editing data for **{sel_yr}** (pre-filled from database)")

    # ── Pre-fill: from DB or projected ────────────────────────────────────────
    existing = dl.get_step_data(comp_hist, sel_yr) if (comp_hist and not is_new) else {}
    supp     = _load_supplementary(company, sel_yr)

    if is_new and comp_hist:
        prior_yr   = max(all_yrs) if all_yrs else sel_yr - 1
        prior_data = dl.get_step_data(comp_hist, prior_yr)
        def _num(key, default=0.0, supp_key=None):
            if supp_key:
                return float(_load_supplementary(company, prior_yr).get(supp_key, default) or default)
            return float(prior_data.get(key, default) or default)
    else:
        def _num(key, default=0.0, supp_key=None):
            if supp_key:
                return float(supp.get(supp_key, default) or default)
            return float(existing.get(key, default) or default)

    _yk = f"_{sel_yr}"     # key suffix per year avoids stale state

    # Source year for pre-filling "Electricity by Country" below — mirrors
    # the _num() helper's own logic: brand-new year pre-fills from the most
    # recent prior year, otherwise reads the year actually being edited.
    _elec_src_yr = (max(all_yrs) if all_yrs else sel_yr - 1) if (is_new and comp_hist) else sel_yr

    # ── Unit-aware field helper (value + unit dropdown, independent per field) ──
    units_selected:       dict[str, str]   = {}  # field -> chosen unit
    corp_values_selected: dict[str, float] = {}  # field -> raw value as typed   # field -> chosen unit, for the save step

    def _prior_unit_and_corp_value(field_key, source_year):
        """Read this field's previously-used corporate value + unit directly
        from the master CSV, independent of the existing/prior_data dicts
        (which don't carry the new corporate/unit columns). Returns
        (None, None) if this field has never used the unit system yet."""
        uf = fr.BY_FIELD.get(field_key)
        if uf is None or state.CONSOLIDATED_DF.empty:
            return None, None
        df = state.CONSOLIDATED_DF
        corp_col, unit_col = fr.corporate_col(uf), fr.unit_col(uf)
        if corp_col not in df.columns or unit_col not in df.columns or "Company" not in df.columns:
            return None, None
        row = df[(df["Company"] == company) & (df["Year"] == source_year)]
        if row.empty:
            return None, None
        cv, un = row.iloc[0].get(corp_col), row.iloc[0].get(unit_col)
        if pd.isna(cv) or pd.isna(un) or not un:
            return None, None
        try:
            return float(cv), str(un)
        except (TypeError, ValueError):
            return None, None

    def _ni(container, label, key, value, **kwargs):
        """number_input wrapper that avoids Streamlit's "widget was created
        with a default value but also had its value set via the Session
        State API" warning. Once a widget's key already holds a
        session_state entry — e.g. because _rescale_unit_change just wrote
        one this run, or because Streamlit is persisting it from the user's
        last edit — passing `value=` again conflicts with that and triggers
        the warning. So: pass `value=` only on first creation; afterwards
        let the widget read straight from session_state."""
        if key in st.session_state:
            return container.number_input(label, key=key, **kwargs)
        return container.number_input(label, value=value, key=key, **kwargs)

    def _unit_field(field_key, label, container, default_common_value=0.0, step=100.0,
                     fmt="%.0f", min_value=0.0, help=None, shared_unit=None):
        """Render a value field for one of the 23 registered unit-bearing
        fields. Returns the value CONVERTED TO COMMON UNITS (GJ/metric T/etc
        — whatever formula_engine expects), and records the chosen unit into
        units_selected for the save step.

        If `shared_unit` is given, this field has NO unit dropdown of its own
        — it's driven by a section-level dropdown (see `_section_unit_default`
        below) and just renders the number_input, converting the stored
        common-unit value into whatever unit the section dropdown currently
        has selected. This is the case for Section 3 (Electricity) and all
        of Section 4 (Fuels).

        If `shared_unit` is None, falls back to the original behaviour: an
        independent per-field (value, unit) pair, pre-filled from whatever
        this company last used for this specific field."""
        uf = fr.BY_FIELD[field_key]
        options = cd.UNITS_BY_SUBSECTION.get(uf.subsection, [])
        wkey = f"e_{field_key}{_yk}"
        if not options:
            v = _ni(container, label, wkey, default_common_value,
                     min_value=min_value, step=step, format=fmt, help=help)
            units_selected[field_key] = None
            return v

        if shared_unit is not None:
            # Section-level dropdown controls the unit — just convert the
            # common-unit default into that unit for display/pre-fill.
            cf_default  = cd.get_unit_conversion_factor(uf.subsection, shared_unit)
            default_raw = default_common_value / cf_default if cf_default else default_common_value
            raw_val = _ni(container, label, wkey, float(default_raw),
                          min_value=min_value, step=step, format=fmt, help=help)
            units_selected[field_key]       = shared_unit
            corp_values_selected[field_key] = raw_val
            return raw_val * cf_default if cf_default else raw_val

        prior_corp_val, prior_unit = _prior_unit_and_corp_value(field_key, _elec_src_yr)
        if prior_unit and prior_unit in options:
            default_unit = prior_unit
            default_raw  = prior_corp_val if prior_corp_val is not None else default_common_value
        else:
            # No corporate-unit history yet for this field — the agreed
            # backfill default is "assume the existing value was already in
            # the field's common unit" (CF=1 unit, where one exists).
            default_unit = next((u for u in options
                                  if cd.get_unit_conversion_factor(uf.subsection, u) == 1), options[0])
            default_raw  = default_common_value

        sub1, sub2 = container.columns([2, 1])
        raw_val = _ni(sub1, label, wkey, float(default_raw),
                      min_value=min_value, step=step, format=fmt, help=help)
        unit = sub2.selectbox("Unit", options,
                              index=options.index(default_unit), key=f"e_{field_key}_unit{_yk}",
                              label_visibility="visible" if container is st else "collapsed")
        units_selected[field_key]       = unit
        corp_values_selected[field_key] = raw_val   # preserve as-typed for save
        cf = cd.get_unit_conversion_factor(uf.subsection, unit)
        return raw_val * cf if cf is not None else raw_val

    def _section_unit_default(*field_keys):
        """Pick the options list + default selection for a section-level unit
        dropdown. Uses the first field's subsection to get the options list
        (all fields passed in must share the same unit family), then checks
        each field in order for prior per-field unit history — the first
        match wins. Falls back to the canonical CF=1 unit if no field in the
        section has unit history yet."""
        uf = fr.BY_FIELD[field_keys[0]]
        options = cd.UNITS_BY_SUBSECTION.get(uf.subsection, [])
        if not options:
            return options, None
        for fk in field_keys:
            _, prior_unit = _prior_unit_and_corp_value(fk, _elec_src_yr)
            if prior_unit and prior_unit in options:
                return options, prior_unit
        default_unit = next((u for u in options
                              if cd.get_unit_conversion_factor(uf.subsection, u) == 1), options[0])
        return options, default_unit

    def _rescale_unit_change(sel_key, prev_key, field_widget_keys, subsection):
        """Streamlit keeps a widget's session_state value across reruns and
        ignores any new `value=` we pass in, so simply changing a section
        dropdown does NOT update the digits already sitting in each field's
        number_input — yet the conversion factor used downstream DOES change,
        which silently multiplies stale digits by the new factor and produces
        a wrong total. This fixes that: if `sel_key` (the dropdown) changed
        since the last run, rewrite each field's session_state value in
        `field_widget_keys` so the SAME physical quantity is re-expressed in
        the new unit. Must be called right after the dropdown renders and
        before any of the affected number_input widgets render."""
        new_unit = st.session_state.get(sel_key)
        old_unit = st.session_state.get(prev_key, new_unit)
        if new_unit and old_unit and new_unit != old_unit:
            old_cf = cd.get_unit_conversion_factor(subsection, old_unit) or 1.0
            new_cf = cd.get_unit_conversion_factor(subsection, new_unit) or 1.0
            for wkey in field_widget_keys:
                if wkey in st.session_state:
                    try:
                        st.session_state[wkey] = float(st.session_state[wkey]) * old_cf / new_cf
                    except (TypeError, ValueError):
                        pass
        st.session_state[prev_key] = new_unit

    # ══════════════════════════════════════════════════════════════════════════
    # SUBMIT DATA — grouped into two tabs so related fields stay together and
    # the form doesn't read as one very long undifferentiated list.
    # ══════════════════════════════════════════════════════════════════════════
    tab_energy, tab_co2waste, tab_hns = st.tabs(["Energy", "CO₂ & Waste", "Health & Safety"])

    with tab_energy:
        # ══════════════════════════════════════════════════════════════════════════
        # SECTION 1 — Global Information
        # ══════════════════════════════════════════════════════════════════════════
        st.markdown(f"""<div style="border-left:4px solid {GREEN};padding:4px 12px;margin:16px 0 8px">
          <b style="font-size:15px;color:{TEXT}">1. Global Information</b>
          <div style="font-size:11px;color:{MUTED}">Sites, ISO 14001 certification, production volume</div>
        </div>""", unsafe_allow_html=True)

        g1, g2, g3 = st.columns(3)
        total_sites = g1.number_input("Total number of sites", min_value=0,
            value=int(_num("total_sites")), step=1, key=f"e_sites{_yk}")
        iso_sites = g2.number_input("ISO 14001 certified sites", min_value=0,
            value=int(_num("iso_sites")), step=1, key=f"e_iso{_yk}")
        iso_pct = round(iso_sites / max(total_sites, 1) * 100, 1)
        g3.metric("ISO 14001 % (auto)", f"{iso_pct:.1f}%")

        production = st.number_input(
            "Total Production (metric T)", min_value=0.0,
            value=float(_num("production")), step=1000.0, format="%.0f",
            key=f"e_production{_yk}")
        units_selected["production"]       = "metric T"
        corp_values_selected["production"] = production
        st.divider()

        # ══════════════════════════════════════════════════════════════════════════
        # SECTION 3 — Energy: Electricity
        # ══════════════════════════════════════════════════════════════════════════
        sec3_l, sec3_r = st.columns([3, 1])
        with sec3_l:
            st.markdown(f"""<div style="border-left:4px solid {CAT_ENERGY};padding:4px 12px;margin:16px 0 8px">
              <b style="font-size:15px;color:{TEXT}">3. Energy — Electricity</b>
            </div>""", unsafe_allow_html=True)
        with sec3_r:
            elec_unit_options, elec_unit_default = _section_unit_default(
                "renew_elec_purchased", "nonrenew_elec_purchased", "self_gen_elec",
                "purchased_steam", "sold_steam", "sold_electricity")
            _elec_sec_keys = ["renew_elec_purchased", "nonrenew_elec_purchased", "self_gen_elec",
                              "purchased_steam", "sold_steam", "sold_electricity"]
            elec_sel_key = f"e_elec_section_unit{_yk}"
            elec_section_unit = st.selectbox(
                "Unit", elec_unit_options, index=elec_unit_options.index(elec_unit_default),
                key=elec_sel_key, label_visibility="collapsed")
            _rescale_unit_change(
                elec_sel_key, f"_prev_elec_section_unit{_yk}",
                [f"e_{fk}{_yk}" for fk in _elec_sec_keys],
                fr.BY_FIELD["renew_elec_purchased"].subsection)

        ec1, ec2, ec3 = st.columns(3)
        renew_elec    = _unit_field("renew_elec_purchased", "Renewable electricity purchased", ec1,
                                     default_common_value=_num("renew_elec_purchased"),
                                     shared_unit=elec_section_unit)
        nonrenew_elec = _unit_field("nonrenew_elec_purchased", "Non-renewable electricity purchased", ec2,
                                     default_common_value=_num("nonrenew_elec_purchased"),
                                     shared_unit=elec_section_unit)
        self_gen      = _unit_field("self_gen_elec", "Self-generated electricity", ec3,
                                     default_common_value=_num("self_gen_elec"),
                                     shared_unit=elec_section_unit)

        ec4, ec5, ec6 = st.columns(3)
        purchased_steam = _unit_field("purchased_steam", "Purchased steam", ec4,
                                       default_common_value=_num("purchased_steam"),
                                       shared_unit=elec_section_unit)
        sold_steam      = _unit_field("sold_steam", "Sold steam", ec5,
                                       default_common_value=_num("sold_steam"),
                                       help="Energy sold as steam — deducted from total",
                                       shared_unit=elec_section_unit)
        sold_electricity = _unit_field("sold_electricity", "Sold electricity", ec6,
                                        default_common_value=_num("sold_electricity"),
                                        shared_unit=elec_section_unit)

        total_elec = renew_elec + nonrenew_elec + self_gen
        _elec_total_cf = cd.get_unit_conversion_factor(
            fr.BY_FIELD["renew_elec_purchased"].subsection, elec_section_unit) or 1.0
        if elec_section_unit == "GJ":
            st.metric("Total Electricity (auto)", f"{total_elec:,.0f} GJ")
        else:
            st.metric("Total Electricity (auto)",
                      f"{total_elec / _elec_total_cf:,.0f} {elec_section_unit}",
                      help=f"= {total_elec:,.0f} GJ")
        st.divider()

        # ══════════════════════════════════════════════════════════════════════════
        # SECTION 3b — Electricity by Country
        # ══════════════════════════════════════════════════════════════════════════
        _ELEC_REGIONS = list(state.ELEC_COUNTRY_REGIONS.items())

        sec3b_l, sec3b_r = st.columns([3, 1])
        with sec3b_l:
            st.markdown(f"""<div style="border-left:4px solid {CAT_ENERGY};padding:4px 12px;margin:16px 0 8px">
              <b style="font-size:15px;color:{TEXT}">3b. Electricity by Country</b>
              <div style="font-size:11px;color:{MUTED}">Country-level breakdown of electricity purchased — optional detail, grouped by region</div>
            </div>""", unsafe_allow_html=True)
        with sec3b_r:
            # ONE shared unit for the whole by-country breakdown — matches the
            # real template, which has a single "Unit" column covering every
            # country row rather than a per-country choice.
            _elec_options = cd.UNITS_BY_SUBSECTION.get("Non-Renewable Electricity Purchased", ["GJ"])
            _prior_elec_unit = supp.get("elec_by_country_unit") if not is_new else \
                                _load_supplementary(company, _elec_src_yr).get("elec_by_country_unit")
            _elec_default_unit = _prior_elec_unit if _prior_elec_unit in _elec_options else "GJ"
            elec_unit_sel_key = f"e_elec_unit{_yk}"
            elec_by_country_unit = st.selectbox(
                "Unit", _elec_options, index=_elec_options.index(_elec_default_unit),
                key=elec_unit_sel_key, label_visibility="collapsed",
                help="One unit applies to the whole country breakdown, matching how this is "
                     "reported in the source KPI Collection Tool.",
            )
            _rescale_unit_change(
                elec_unit_sel_key, f"_prev_elec_unit{_yk}",
                [f"e_elec_{c.replace(' ', '_')}{_yk}" for _, _countries in _ELEC_REGIONS for c in _countries],
                "Non-Renewable Electricity Purchased")

        def _elec_existing_gj(country: str) -> float:
            """Read this country's current GJ value for `_elec_src_yr` from the
            consolidated master data, so the field pre-fills like every other
            field on this form (existing value, or prior year's for a new entry)."""
            col = state.ELEC_COUNTRY_COLS.get(country)
            if not col or state.CONSOLIDATED_DF.empty or col not in state.CONSOLIDATED_DF.columns:
                return 0.0
            df = state.CONSOLIDATED_DF
            if "Company" not in df.columns or "Year" not in df.columns:
                return 0.0
            row = df[(df["Company"] == company) & (df["Year"] == _elec_src_yr)]
            if row.empty:
                return 0.0
            v = row[col].values[0]
            try:
                return float(v) if pd.notna(v) else 0.0
            except (TypeError, ValueError):
                return 0.0

        _elec_cf = cd.get_unit_conversion_factor("Non-Renewable Electricity Purchased", elec_by_country_unit) or 1.0

        elec_country_values = {}
        for region_name, countries in _ELEC_REGIONS:
            region_total_existing = sum(_elec_existing_gj(c) for c in countries)
            with st.expander(f"{region_name} ({len(countries)} countries)",
                              expanded=region_total_existing > 0):
                cols = st.columns(3)
                for i, country in enumerate(countries):
                    key_safe = country.replace(" ", "_")
                    ckey = f"e_elec_{key_safe}{_yk}"
                    # Pre-fill in the CHOSEN unit, converting back from the
                    # stored common-unit (GJ) value.
                    default_raw = _elec_existing_gj(country) / _elec_cf if _elec_cf else 0.0
                    val = _ni(cols[i % 3], f"{country} ({elec_by_country_unit})", ckey, default_raw,
                              min_value=0.0, step=100.0, format="%.0f")
                    elec_country_values[country] = val * _elec_cf   # always stored as GJ

        elec_country_total = sum(elec_country_values.values())
        st.caption(
            f"Country breakdown total: **{elec_country_total:,.0f} GJ** — for reference against "
            f"Total Electricity above ({total_elec:,.0f} GJ). These don't have to match exactly "
            f"if some electricity isn't attributed to a specific country."
        )
        st.divider()

        # ══════════════════════════════════════════════════════════════════════════
        # SECTION 4 — Energy: Fuels
        # ══════════════════════════════════════════════════════════════════════════
        sec4_l, sec4_r = st.columns([3, 1])
        with sec4_l:
            st.markdown(f"""<div style="border-left:4px solid {CAT_ENERGY};padding:4px 12px;margin:16px 0 8px">
              <b style="font-size:15px;color:{TEXT}">4. Energy — Fuels (LHV)</b>
            </div>""", unsafe_allow_html=True)
        with sec4_r:
            _fuel_sec_keys = ["nat_gas", "propane", "diesel", "petrol", "biomass", "waste_tires_mt",
                              "lpg", "other_fuels", "fuel_oil_heavy_a", "fuel_oil_heavy_c",
                              "coal_sub_bituminous", "coal_brown_briquettes", "coal_other_bituminous"]
            fuel_unit_options, fuel_unit_default = _section_unit_default(*_fuel_sec_keys)
            fuel_sel_key = f"e_fuel_section_unit{_yk}"
            fuel_section_unit = st.selectbox(
                "Unit", fuel_unit_options, index=fuel_unit_options.index(fuel_unit_default),
                key=fuel_sel_key, label_visibility="collapsed")
            _rescale_unit_change(
                fuel_sel_key, f"_prev_fuel_section_unit{_yk}",
                [f"e_{fk}{_yk}" for fk in _fuel_sec_keys] + [f"e_fo_total{_yk}", f"e_coal_total_direct{_yk}"],
                fr.BY_FIELD["nat_gas"].subsection)

        fc1, fc2, fc3 = st.columns(3)
        nat_gas  = _unit_field("nat_gas", "Natural gas", fc1, default_common_value=_num("nat_gas"),
                                shared_unit=fuel_section_unit)
        propane  = _unit_field("propane", "Propane", fc2, default_common_value=_num("propane"),
                                shared_unit=fuel_section_unit)

        fc4, fc5, fc6 = st.columns(3)
        diesel  = _unit_field("diesel", "Diesel", fc4, default_common_value=_num("diesel"),
                               shared_unit=fuel_section_unit)
        petrol  = _unit_field("petrol", "Petrol", fc5, default_common_value=_num("petrol"),
                               shared_unit=fuel_section_unit)
        biomass = _unit_field("biomass", "Biomass", fc6, default_common_value=_num("biomass"),
                               shared_unit=fuel_section_unit)

        fc7, fc8, fc9 = st.columns(3)
        waste_tires = _unit_field("waste_tires_mt", "Waste tires", fc7,
            default_common_value=_num("waste_tires_mt"), step=1.0,
            shared_unit=fuel_section_unit)
        lpg         = _unit_field("lpg", "LPG", fc8, default_common_value=_num("lpg"),
                                   shared_unit=fuel_section_unit)
        other_fuels = _unit_field("other_fuels", "Other fuels", fc9, default_common_value=_num("other_fuels"),
                                   shared_unit=fuel_section_unit)

        # ── Fuel Oil ─────────────────────────────────────────────────────────────
        # Companies can report either: (a) Heavy A + Heavy C separately, OR
        # (b) a single Total Fuel Oil figure. Both paths are supported.
        # If either sub-type is entered the granular path takes precedence;
        # the "Total (if not reporting separately)" field is used only when
        # both sub-types are zero, feeding the formula engine's legacy coal_sub.
        st.markdown(f"<div style='font-size:13px;font-weight:600;color:{TEXT};margin:8px 0 4px'>Fuel Oil breakdown</div>", unsafe_allow_html=True)
        st.caption("Enter Heavy A + Heavy C separately, OR enter the Total below — whichever your reporting supports.")
        fo1, fo2, fo3 = st.columns(3)
        fuel_oil_a = _unit_field("fuel_oil_heavy_a", "Fuel Oil Heavy A", fo1,
                                  default_common_value=_num("fuel_oil_heavy_a"),
                                  shared_unit=fuel_section_unit)
        fuel_oil_c = _unit_field("fuel_oil_heavy_c", "Fuel Oil Heavy C", fo2,
                                  default_common_value=_num("", 0.0, "fuel_oil_heavy_c"),
                                  shared_unit=fuel_section_unit)
        # Total direct entry — used when company doesn't split A/C. Now
        # driven by the same fuel_section_unit dropdown as everything else
        # in this section (converted for display, rescaled on unit change).
        _fo_cf = cd.get_unit_conversion_factor(fr.BY_FIELD["fuel_oil_heavy_a"].subsection, fuel_section_unit) or 1.0
        _fo_total_default_gj  = _num("fuel_oil_heavy_a") if (_num("fuel_oil_heavy_a") + _num("", 0.0, "fuel_oil_heavy_c")) > 0 else 0.0
        _fo_total_default_raw = _fo_total_default_gj / _fo_cf if _fo_cf else _fo_total_default_gj
        fuel_oil_direct_raw = _ni(fo3, f"Total Fuel Oil ({fuel_section_unit}, if not split above)",
            f"e_fo_total{_yk}", float(_fo_total_default_raw), min_value=0.0, step=100.0, format="%.0f",
            help="Fill this ONLY if not reporting Heavy A / Heavy C separately. "
                 "This is ignored when Heavy A or Heavy C has a value.")
        fuel_oil_direct = fuel_oil_direct_raw * _fo_cf if _fo_cf else fuel_oil_direct_raw
        # Prefer granular sub-types; fall back to direct total
        fuel_oil_total = (fuel_oil_a + fuel_oil_c) if (fuel_oil_a + fuel_oil_c) > 0 else fuel_oil_direct
        st.caption(f"Total Fuel Oil (auto): **{fuel_oil_total / _fo_cf:,.0f} {fuel_section_unit}** "
                   f"({fuel_oil_total:,.0f} GJ)")

        # ── Coal breakdown ────────────────────────────────────────────────────────
        # Same pattern: 3 sub-types OR a single blended total.
        # formula_engine uses granular when any sub-type > 0, else coal_sub total.
        st.markdown(f"<div style='font-size:13px;font-weight:600;color:{TEXT};margin:8px 0 4px'>Coal breakdown</div>", unsafe_allow_html=True)
        st.caption("Enter sub-types separately, OR enter the Total Coal below — whichever your reporting supports.")
        cc1, cc2, cc3 = st.columns(3)
        coal_sub_bit = _unit_field("coal_sub_bituminous",   "Sub-bituminous coal",   cc1,
                                    default_common_value=_num("", 0.0, "coal_sub_bituminous"),
                                    shared_unit=fuel_section_unit)
        coal_brown   = _unit_field("coal_brown_briquettes", "Brown coal briquettes", cc2,
                                    default_common_value=_num("", 0.0, "coal_brown_briquettes"),
                                    shared_unit=fuel_section_unit)
        coal_other   = _unit_field("coal_other_bituminous", "Other bituminous coal", cc3,
                                    default_common_value=_num("", 0.0, "coal_other_bituminous"),
                                    shared_unit=fuel_section_unit)
        # Total Coal direct entry — used when company doesn't report sub-types.
        # Driven by fuel_section_unit, same as the rest of Section 4.
        _coal_cf = cd.get_unit_conversion_factor(fr.BY_FIELD["coal_sub_bituminous"].subsection, fuel_section_unit) or 1.0
        _coal_sub_legacy_default_gj  = _num("coal_sub", 0.0)
        _coal_sub_legacy_default_raw = _coal_sub_legacy_default_gj / _coal_cf if _coal_cf else _coal_sub_legacy_default_gj
        coal_sub_direct_raw = _ni(st, f"Total Coal ({fuel_section_unit}, if not reporting sub-types)",
            f"e_coal_total_direct{_yk}", float(_coal_sub_legacy_default_raw), min_value=0.0, step=100.0, format="%.0f",
            help="Fill this ONLY if you are not reporting sub-types above. "
                 "Ignored when any sub-type has a value. Uses blended CO₂ factor.")
        coal_sub_direct = coal_sub_direct_raw * _coal_cf if _coal_cf else coal_sub_direct_raw
        coal_granular_total = coal_sub_bit + coal_brown + coal_other
        coal_total = coal_granular_total if coal_granular_total > 0 else coal_sub_direct
        st.caption(f"Total Coal (auto): **{coal_total / _coal_cf:,.0f} {fuel_section_unit}** "
                   f"({coal_total:,.0f} GJ)")

        # Live energy totals — waste_tires is already common-unit GJ by this
        # point (the unit dropdown did the mass->energy conversion), so no
        # separate *28.0 (or *36.226) step here — that used to be a SEPARATE,
        # WRONG constant from the one actually used at save time.
        total_energy_live = (total_elec + purchased_steam + nat_gas + coal_total + propane +
                             fuel_oil_total + diesel + petrol + biomass + waste_tires + lpg +
                             other_fuels - sold_steam - sold_electricity)
        energy_kpi_live  = round(total_energy_live / max(production, 1), 4)
        renew_share_live = round((renew_elec + self_gen) / max(total_elec, 1) * 100, 1)

        # These are still just energy totals at heart (electricity and fuels
        # are both energy), so re-expressing them in whichever unit is
        # currently selected is just a unit relabeling, not a mismatch.
        # Total Electricity follows the Electricity dropdown; Total Energy +
        # Energy KPI (which is Total Energy ÷ production) follow the Fuels
        # dropdown, since that's the broader combined total and sits directly
        # under it.
        _elec_disp_cf  = cd.get_unit_conversion_factor(fr.BY_FIELD["renew_elec_purchased"].subsection, elec_section_unit) or 1.0
        _energy_disp_cf = cd.get_unit_conversion_factor(fr.BY_FIELD["nat_gas"].subsection, fuel_section_unit) or 1.0

        em1, em2, em3, em4 = st.columns(4)
        em1.metric(f"Total Electricity ({elec_section_unit})",
                   f"{total_elec / _elec_disp_cf:,.0f}", help=f"= {total_elec:,.0f} GJ")
        em2.metric(f"Total Energy ({fuel_section_unit})",
                   f"{total_energy_live / _energy_disp_cf:,.0f}", help=f"= {total_energy_live:,.0f} GJ")
        em3.metric(f"Energy KPI ({fuel_section_unit}/t)",
                   f"{energy_kpi_live / _energy_disp_cf:.4f}", help=f"= {energy_kpi_live:.4f} GJ/t")
        em4.metric("Renewable Share", f"{renew_share_live:.1f}%")
        st.divider()

        # ══════════════════════════════════════════════════════════════════════════

    with tab_co2waste:

        # SECTION 2 — Water
        # ══════════════════════════════════════════════════════════════════════════
        st.markdown(f"""<div style="border-left:4px solid {CAT_WATER};padding:4px 12px;margin:16px 0 8px">
          <b style="font-size:15px;color:{TEXT}">2. Water</b>
          <div style="font-size:11px;color:{MUTED}">All figures in m³</div>
        </div>""", unsafe_allow_html=True)

        w1, w2 = st.columns(2)
        water_intake = w1.number_input(
            "Water intake (m³)", min_value=0.0,
            value=float(_num("water_withdrawals")), step=1000.0, format="%.0f",
            key=f"e_water_withdrawals{_yk}", help="Total water taken from all sources")
        units_selected["water_withdrawals"]       = "m3"
        corp_values_selected["water_withdrawals"] = water_intake
        water_withdrawal = w2.number_input("Water withdrawal (m³)", min_value=0.0,
            value=_num("water_withdrawals"), step=1000.0, format="%.0f", key=f"e_wdraw{_yk}",
            help="Total water withdrawn (may equal intake) — tracked separately, common unit only")

        ws1, ws2 = st.columns(2)
        stress_wd = ws1.number_input("Stress water withdrawal (m³)", min_value=0.0,
            value=_num("", 0.0, "stress_water_withdrawal"), step=1000.0, format="%.0f", key=f"e_stress{_yk}",
            help="Withdrawals from water-stressed areas")
        non_stress_wd = round(max(water_withdrawal - stress_wd, 0), 0)
        ws2.metric("Non-stress withdrawal (auto)", f"{non_stress_wd:,.0f} m³")

        water_kpi_live = round(water_intake / max(production, 1), 4)
        st.metric("Water Intake KPI (m³/t)", f"{water_kpi_live:.4f}",
                  help="Auto-calculated: Water intake ÷ Production")
        st.divider()

        # ══════════════════════════════════════════════════════════════════════════
        # SECTION 5 — CO₂ Emissions (all fields manual input)
        # ══════════════════════════════════════════════════════════════════════════
        st.markdown(f"""<div style="border-left:4px solid {RED};padding:4px 12px;margin:16px 0 8px">
          <b style="font-size:15px;color:{TEXT}">5. CO₂ Emissions (tCO₂)</b>
          <div style="font-size:11px;color:{MUTED}">Enter CO₂ values per fuel source. Total Scope 1 auto-sums. CO₂ KPI auto-calculated.</div>
        </div>""", unsafe_allow_html=True)

        # ── CO₂ Scope 1 — manual input per fuel ──────────────────────────────────
        ca1,ca2,ca3 = st.columns(3)
        co2_nat_gas  = ca1.number_input("Natural Gas (tCO₂)", min_value=0.0,
            value=_num("", nat_gas*_EF.get("Natural Gas",0.0561), "co2_nat_gas"),
            step=10.0, format="%.1f", key=f"e_c_ng{_yk}")
        co2_coal_inp = ca2.number_input("Coal (tCO₂)", min_value=0.0,
            value=_num("", coal_total*_EF.get("Coal",0.0946), "co2_coal"),
            step=10.0, format="%.1f", key=f"e_c_coal{_yk}")
        co2_propane  = ca3.number_input("Propane (tCO₂)", min_value=0.0,
            value=_num("", propane*_EF.get("Propane",0.0631), "co2_propane"),
            step=10.0, format="%.1f", key=f"e_c_prop{_yk}")

        cb1,cb2,cb3 = st.columns(3)
        co2_fuel_oil = cb1.number_input("Fuel Oil (tCO₂)", min_value=0.0,
            value=_num("", fuel_oil_total*_EF.get("Fuel Oil",0.0745), "co2_fuel_oil"),
            step=10.0, format="%.1f", key=f"e_c_foil{_yk}")
        co2_diesel   = cb2.number_input("Diesel (tCO₂)", min_value=0.0,
            value=_num("", diesel*_EF.get("Diesel",0.0741), "co2_diesel"),
            step=10.0, format="%.1f", key=f"e_c_dies{_yk}")
        co2_petrol   = cb3.number_input("Petrol (tCO₂)", min_value=0.0,
            value=_num("", petrol*_EF.get("Petrol",0.0693), "co2_petrol"),
            step=10.0, format="%.1f", key=f"e_c_pet{_yk}")

        cc1,cc2,cc3 = st.columns(3)
        co2_waste_tires = cc1.number_input("Waste Tires (tCO₂)", min_value=0.0,
            value=_num("", waste_tires*_EF.get("Waste Tires",0.085), "co2_waste_tires"),
            step=10.0, format="%.1f", key=f"e_c_wt{_yk}")
        co2_lpg      = cc2.number_input("LPG (tCO₂)", min_value=0.0,
            value=_num("", lpg*_EF.get("LPG",0.0639), "co2_lpg"),
            step=10.0, format="%.1f", key=f"e_c_lpg{_yk}")
        co2_other    = cc3.number_input("Other (tCO₂)", min_value=0.0,
            value=_num("", other_fuels*_EF.get("Other",0.075), "co2_other"),
            step=10.0, format="%.1f", key=f"e_c_oth{_yk}")

        # ── Scope 2 (keep steam for formula engine compatibility) ─────────────────
        co2_scope2_steam = 0.0   # removed from UI — set to 0
        scope1_total = (co2_nat_gas + co2_coal_inp + co2_propane + co2_fuel_oil +
                        co2_diesel + co2_petrol + co2_waste_tires + co2_lpg + co2_other)
        scope2_elec_auto = (nonrenew_elec * _G2M) * _S2EF
        scope2_total     = scope2_elec_auto        # only electricity scope 2 remains
        co2_total        = scope1_total + scope2_total
        co2_kpi_live     = round(co2_total / max(production, 1), 4)

        cd1,cd2,cd3,cd4 = st.columns(4)
        cd1.metric("Total CO₂ Scope 1 (tCO₂)",   f"{scope1_total:,.1f}")
        cd2.metric("Total CO₂ Scope 2 (tCO₂)",   f"{scope2_total:,.1f}")
        cd3.metric("Total CO₂ Scope 1+2 (tCO₂)", f"{co2_total:,.1f}")
        cd4.metric("CO₂ KPI (tCO₂/t)",            f"{co2_kpi_live:.4f}")
        st.divider()


        # SECTION 6 — Waste
        # ══════════════════════════════════════════════════════════════════════════
        st.markdown(f"""<div style="border-left:4px solid {CAT_WASTE};padding:4px 12px;margin:16px 0 8px">
          <b style="font-size:15px;color:{TEXT}">6. Waste Management</b>
          <div style="font-size:11px;color:{MUTED}">Metric tonnes</div>
        </div>""", unsafe_allow_html=True)

        ww1, ww2 = st.columns(2)
        waste_total = ww1.number_input(
            "Total amount of waste (metric T)", min_value=0.0,
            value=float(_num("waste_total")), step=10.0, format="%.0f",
            key=f"e_waste_total{_yk}")
        waste_recovery = ww2.number_input(
            "Amount sent to recovery (metric T)", min_value=0.0,
            value=float(_num("waste_recovery")), step=10.0, format="%.0f",
            key=f"e_waste_recovery{_yk}")
        units_selected["waste_total"]          = "metric T"
        units_selected["waste_recovery"]       = "metric T"
        corp_values_selected["waste_total"]    = waste_total
        corp_values_selected["waste_recovery"] = waste_recovery

        waste_elim   = max(waste_total - waste_recovery, 0)
        waste_rr_pct = round(waste_recovery / max(waste_total, 1) * 100, 1)
        wa1,wa2,wa3 = st.columns(3)
        wa1.metric("Sent to elimination (auto)", f"{waste_elim:,.0f} t")
        wa2.metric("Recovery rate (auto)",       f"{waste_rr_pct:.1f}%")
        wa3.metric("Waste intensity (kg/t)",     f"{waste_total/max(production,1)*1000:.1f}")
        if waste_recovery > waste_total > 0:
            st.error("Waste recovered cannot exceed total waste.")
        st.divider()

        # ══════════════════════════════════════════════════════════════════════════

    with tab_hns:

        # SECTION 7 — Health & Safety
        # ══════════════════════════════════════════════════════════════════════════
        st.markdown(f"""<div style="border-left:4px solid #0EA5E9;padding:4px 12px;margin:16px 0 8px">
          <b style="font-size:15px;color:{TEXT}">7. Health & Safety</b>
          <div style="font-size:11px;color:{MUTED}">Site-level audit coverage</div>
        </div>""", unsafe_allow_html=True)

        hs1, hs2, hs3 = st.columns(3)
        hs_total_sites = hs1.number_input("Total sites (H&S)", min_value=0,
            value=int(_num("", int(total_sites), "hs_total_sites") or int(total_sites)),
            step=1, key=f"e_hstot{_yk}", help="Defaults to total sites above")
        hs_external = hs2.number_input("Sites with external H&S audit", min_value=0,
            value=int(_num("", 0, "hs_external_audit")), step=1, key=f"e_hsext{_yk}")
        hs_internal = hs3.number_input("Sites with internal H&S audit", min_value=0,
            value=int(_num("", 0, "hs_internal_audit")), step=1, key=f"e_hsint{_yk}")

        hs_ext_pct = round(hs_external / max(hs_total_sites, 1) * 100, 1)
        hs_int_pct = round(hs_internal / max(hs_total_sites, 1) * 100, 1)
        ha1,ha2 = st.columns(2)
        ha1.metric("External audit coverage (auto)", f"{hs_ext_pct:.1f}%")
        ha2.metric("Internal audit coverage (auto)", f"{hs_int_pct:.1f}%")
        st.divider()

        # ══════════════════════════════════════════════════════════════════════════
        # SECTION 8 — Diversity & Inclusion
        # ══════════════════════════════════════════════════════════════════════════
        st.markdown(f"""<div style="border-left:4px solid #8B5CF6;padding:4px 12px;margin:16px 0 8px">
          <b style="font-size:15px;color:{TEXT}">8. Diversity & Inclusion</b>
        </div>""", unsafe_allow_html=True)

        di1,di2,di3,di4 = st.columns(4)
        total_employees = di1.number_input("Total employees", min_value=0,
            value=int(_num("", 0, "total_employees")), step=10, key=f"e_emp{_yk}")
        female_employees = di2.number_input("Total female employees", min_value=0,
            value=int(_num("", 0, "female_employees")), step=1, key=f"e_femp{_yk}")
        board_total  = di3.number_input("Total Board of Directors", min_value=0,
            value=int(_num("", 0, "board_total")), step=1, key=f"e_bod{_yk}")
        female_board = di4.number_input("Female Board of Directors", min_value=0,
            value=int(_num("", 0, "female_board")), step=1, key=f"e_fbod{_yk}")

        fem_emp_pct = round(female_employees / max(total_employees, 1) * 100, 1)
        fem_bod_pct = round(female_board / max(board_total, 1) * 100, 1)
        da1,da2 = st.columns(2)
        da1.metric("% Female employees (auto)", f"{fem_emp_pct:.1f}%")
        da2.metric("% Female BOD (auto)",       f"{fem_bod_pct:.1f}%")
        st.divider()

        # ══════════════════════════════════════════════════════════════════════════
        # SECTION 9 — Science-Based Targets
        # ══════════════════════════════════════════════════════════════════════════
        st.markdown(f"""<div style="border-left:4px solid #F59E0B;padding:4px 12px;margin:16px 0 8px">
          <b style="font-size:15px;color:{TEXT}">9. Science-Based Targets (SBTs)</b>
          <div style="font-size:11px;color:{MUTED}">Number of companies — enter 0 or 1 per field as applicable</div>
        </div>""", unsafe_allow_html=True)

        sb1,sb2,sb3,sb4 = st.columns(4)
        sbt_total      = sb1.number_input("Total with SBT", min_value=0,
            value=int(_num("", 0, "sbt_total")), step=1, key=f"e_sbttot{_yk}")
        sbt_validated  = sb2.number_input("Validated", min_value=0,
            value=int(_num("", 0, "sbt_validated")), step=1, key=f"e_sbtval{_yk}")
        sbt_committed  = sb3.number_input("Committed", min_value=0,
            value=int(_num("", 0, "sbt_committed")), step=1, key=f"e_sbtcom{_yk}")
        sbt_non        = sb4.number_input("Non-committed", min_value=0,
            value=int(max(_num("", 0, "sbt_total") - _num("", 0, "sbt_validated") - _num("", 0, "sbt_committed"), 0)),
            step=1, key=f"e_sbtnon{_yk}")

    # ══════════════════════════════════════════════════════════════════════════
    # CHANGE REASON (shown only when editing a PREVIOUS year's record)
    # ══════════════════════════════════════════════════════════════════════════
    change_reason = ""
    if is_editing_prior:
        st.divider()
        st.markdown(f"""<div style="border-left:4px solid {AMBER};padding:4px 12px;margin:16px 0 8px">
          <b style="font-size:14px;color:{TEXT}">Change Reason Required</b>
          <div style="font-size:11px;color:{MUTED}">
            Editing a previous year requires a reason. This will be sent to DSS for approval
            before the comment is visible in the template.</div>
        </div>""", unsafe_allow_html=True)
        change_reason = st.text_area(
            "Reason for updating this record",
            placeholder="e.g. Corrected energy consumption figure after audit — original data included double-counted site",
            key=f"entry_reason{_yk}", height=80,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # SUBMIT
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if is_editing_prior and not change_reason.strip():
        st.warning("Please enter a change reason before submitting.")
    submitted = st.button("Submit & Save Data", type="primary",
                          use_container_width=True, key=f"entry_submit_btn{_yk}")

    if submitted:
        if is_editing_prior and not change_reason.strip():
            st.error("A change reason is required when editing a previous year.")
            st.stop()

        # Build TemplateInputs (fields that formula engine knows about).
        # Coal and Fuel Oil now pass the granular sub-types directly (no more
        # blended coal_sub=/single fuel_oil_heavy_a= — formula_engine.calculate()
        # sums these itself into total_coal/total_fuel_oil with per-subtype EFs).
        inp = TemplateInputs(
            company=company, year=sel_yr,
            total_sites=total_sites, iso_sites=iso_sites,
            production=production,
            water_withdrawals=water_intake,
            renew_elec_purchased=renew_elec,
            nonrenew_elec_purchased=nonrenew_elec,
            self_gen_elec=self_gen,
            purchased_steam=purchased_steam,
            sold_electricity=sold_electricity,
            sold_steam=sold_steam,
            nat_gas=nat_gas, propane=propane,
            # Coal: prefer granular sub-types; fall back to direct total via coal_sub
            coal_sub=coal_sub_direct,            # legacy blended (used when sub-types=0)
            coal_sub_bituminous=coal_sub_bit,
            coal_brown_briquettes=coal_brown,
            coal_other_bituminous=coal_other,
            # Fuel Oil: Heavy A + Heavy C (total handled by coal_sub pattern above)
            fuel_oil_heavy_a=fuel_oil_a,
            fuel_oil_heavy_c=fuel_oil_c if (fuel_oil_a + fuel_oil_c) > 0 else fuel_oil_direct,
            diesel=diesel, petrol=petrol,
            biomass=biomass, waste_tires_mt=waste_tires,
            lpg=lpg, other_fuels=other_fuels,
            co2_scope2_steam=co2_scope2_steam,
            waste_total=waste_total, waste_recovery=waste_recovery,
        )
        out = calculate(inp)

        # Save supplementary fields. coal_sub_bituminous/brown/other are kept
        # here too (in addition to being real TemplateInputs fields now) so
        # any other still-unmigrated code reading them via supplementary
        # storage keeps working.
        supp_data = {
            "hs_total_sites":            hs_total_sites,
            "stress_water_withdrawal":   stress_wd,
            "non_stress_water_withdrawal": non_stress_wd,
            "coal_sub_bituminous":       coal_sub_bit,
            "coal_brown_briquettes":     coal_brown,
            "coal_other_bituminous":     coal_other,
            "fuel_oil_heavy_c":          fuel_oil_c,
            "elec_by_country_unit":      elec_by_country_unit,
            "hs_external_audit":         hs_external,
            "hs_internal_audit":         hs_internal,
            "total_employees":           total_employees,
            "female_employees":          female_employees,
            "board_total":               board_total,
            "female_board":              female_board,
            "sbt_total":                 sbt_total,
            "sbt_validated":             sbt_validated,
            "sbt_committed":             sbt_committed,
            "sbt_non_committed":         sbt_non,
        }
        # supplementary now saved via supp= param below (no separate CSV)

        # Save change reason. Two things happen when editing a previous year:
        # (1) one generic "Data Submission" comment always covers the whole
        #     event — same as before.
        # (2) one granular comment PER field that ACTUALLY changed, but only
        #     for the fixed whitelist below of real, user-entered KPI fields
        #     — not every TemplateInputs dataclass attribute. Walking every
        #     attribute previously produced false positives on identity
        #     fields (company, year) and internal/derived fields (e.g. the
        #     scope-2 emission factor, the unit dropdown) that were never
        #     actually "changed" by the user. This is what lets a specific
        #     historical cell (e.g. ISO certified sites, 2019) turn
        #     permanently red/bold and show the reason right next to it.
        if is_editing_prior and change_reason.strip():
            _save_change_comment(company, sel_yr, "SUBMISSION", "Data Submission",
                                 old_val="(previous values)", new_val="(updated values)",
                                 reason=change_reason.strip())

            _FIELD_LABELS = {
                "total_sites": "Total no. of sites", "iso_sites": "ISO 14001 certified sites",
                "production": "Production", "water_withdrawals": "Water withdrawals",
                "stress_water_withdrawal": "Stress water withdrawal",
                "non_stress_water_withdrawal": "Non-stress water withdrawal",
                "renew_elec_purchased": "Renewable electricity purchased",
                "nonrenew_elec_purchased": "Non-renewable electricity purchased",
                "self_gen_elec": "Self-generated renewable on-site",
                "purchased_steam": "Purchased Steam", "sold_steam": "Sold steam",
                "sold_electricity": "Sold electricity",
                "nat_gas": "Natural Gas", "propane": "Propane",
                "coal_sub": "Coal", "coal_sub_bituminous": "Coal — Sub-bituminous",
                "coal_brown_briquettes": "Coal — Brown briquettes",
                "coal_other_bituminous": "Coal — Other bituminous",
                "fuel_oil_heavy_a": "Fuel Oil — Heavy A", "fuel_oil_heavy_c": "Fuel Oil — Heavy C",
                "diesel": "Diesel", "petrol": "Petrol", "biomass": "Biomass",
                "waste_tires_mt": "Waste Tires (fuel)", "lpg": "LPG", "other_fuels": "Other fuels",
                "co2_scope2_steam": "CO₂ Scope 2 — Steam",
                "waste_total": "Total amount of waste",
                "waste_recovery": "Amount of waste sent to recovery",
                "hs_total_sites": "Total sites (H&S)",
                "hs_external_audit": "Externally audited H&S sites",
                "hs_internal_audit": "Internally audited H&S sites",
                "total_employees": "Total employees", "female_employees": "Female employees",
                "board_total": "Board of Directors (total)", "female_board": "Female Board members",
                "sbt_total": "Total with SBT", "sbt_validated": "Validated",
                "sbt_committed": "Committed", "sbt_non_committed": "Non-committed",
            }
            # Explicit whitelist of real, user-editable KPI fields — deliberately
            # excludes "company", "year", and any other TemplateInputs
            # attribute that isn't something the user actually types a value
            # into on this form.
            _MAIN_FIELDS = [
                "total_sites", "iso_sites", "production", "water_withdrawals",
                "stress_water_withdrawal", "non_stress_water_withdrawal",
                "renew_elec_purchased", "nonrenew_elec_purchased", "self_gen_elec",
                "purchased_steam", "sold_electricity", "sold_steam",
                "nat_gas", "propane", "coal_sub", "coal_sub_bituminous",
                "coal_brown_briquettes", "coal_other_bituminous",
                "fuel_oil_heavy_a", "fuel_oil_heavy_c", "diesel", "petrol",
                "biomass", "waste_tires_mt", "lpg", "other_fuels", "co2_scope2_steam",
            ]
            _WASTE_ONLY_FIELDS = ["waste_total", "waste_recovery"]
            _PG_FIELDS = [
                "hs_total_sites", "hs_external_audit", "hs_internal_audit",
                "total_employees", "female_employees", "board_total", "female_board",
                "sbt_total", "sbt_validated", "sbt_committed", "sbt_non_committed",
            ]
            _DUPLICATED_IN_WASTE_TAB = {"total_sites", "production"}  # also shown under Waste → Global Info

            def _fmt_val(v):
                try:
                    fv = float(v)
                    return f"{fv:,.0f}" if fv == int(fv) else f"{fv:,.2f}"
                except (TypeError, ValueError):
                    return str(v)

            def _changed(old, new):
                try:
                    return round(float(old or 0), 4) != round(float(new or 0), 4)
                except (TypeError, ValueError):
                    return str(old) != str(new)

            _old_vals = {**existing, **supp}
            _new_vals = {**{fld: getattr(inp, fld) for fld in state.VALID_TEMPLATE_FIELDS}, **supp_data}

            for _fk in _MAIN_FIELDS + _WASTE_ONLY_FIELDS + _PG_FIELDS:
                if _fk not in _new_vals:
                    continue
                _new_v = _new_vals[_fk]
                _old_v = _old_vals.get(_fk)
                if not _changed(_old_v, _new_v):
                    continue
                _label = _FIELD_LABELS.get(_fk, _fk.replace("_", " ").strip().capitalize())
                if _fk in _PG_FIELDS:
                    _targets = [f"pg:{_fk}"]
                elif _fk in _WASTE_ONLY_FIELDS:
                    _targets = [f"waste:{_fk}"]
                else:
                    _targets = [_fk]
                    if _fk in _DUPLICATED_IN_WASTE_TAB:
                        _targets.append(f"waste:{_fk}")
                for _target_key in _targets:
                    _save_change_comment(company, sel_yr, _target_key, _label,
                                         old_val=_fmt_val(_old_v), new_val=_fmt_val(_new_v),
                                         reason=change_reason.strip())

        # Save to master CSV via standard mechanism
        new_step_data = {fld: getattr(inp, fld) for fld in state.VALID_TEMPLATE_FIELDS}
        st.session_state.step_data          = new_step_data
        st.session_state["_codata_inp"]     = inp
        st.session_state["_codata_out"]     = out
        st.session_state.reporting_company  = company
        st.session_state.reporting_year     = sel_yr
        st.session_state.template_done      = True
        st.session_state.company_setup_done = True
        st.session_state.step               = 6
        for fld in state.VALID_TEMPLATE_FIELDS:
            st.session_state[fld] = getattr(inp, fld)

        msg = _save_submission_to_csv(
            inp, out,
            units=units_selected,
            supp=supp_data,
            corp_values=corp_values_selected,
            country_values_gj=elec_country_values,
        )
        st.session_state["_last_save_msg"] = msg
        if is_editing_prior and change_reason.strip():
            st.session_state["_last_save_msg"] += " · Change reason submitted for DSS review."

        # Persist the Electricity by Country values entered above (Section 3b).
        # Runs AFTER the main KPI save, since that's what guarantees the
        # company+year row already exists in the master CSV.
        if elec_country_values:
            _elec_msg = _save_country_electricity_values(company, sel_yr, elec_country_values)
            st.session_state["_last_save_msg"] += " · " + _elec_msg

        st.session_state.page = "my_records"
        st.session_state.pop("myrec_year", None)
        st.rerun()