"""
formula_engine.py — TIP ESG Platform · KPI Calculation Engine
==============================================================
Pure calculation logic — no Streamlit or file I/O dependencies.
Defines: TemplateInputs, TemplateOutputs, calculate(), validate_submission(),
         get_benchmarks(), BenchmarkResult, fmt_num(), yoy_change()

Emission factors (EF) and conversion constants are defined at module level.
To update factors: edit the EF dict and WASTE_TIRE_HV below.

Coal and Fuel Oil are tracked as sub-types (Coal: Sub-Bituminous / Brown
Briquettes / Other Bituminous; Fuel Oil: Heavy A / Heavy C) rather than one
blended field each — this matches the real WBCSD TIP KPI Collection Tool
master schema (224 fields/company/year), which has no single "coal" or
"fuel oil" input field; "Total Coal" and the fuel-oil total are themselves
calculated sums, exposed here as TemplateOutputs.total_coal/total_fuel_oil.
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np

# ── Emission factors (T.CO2 per GJ LHV) ─────────────────────────────────────
# Coal and Fuel Oil are split into sub-types because the real TIP KPI Collection
# Tool master schema tracks them separately (224 fields/company/year) — Coal's
# three sub-types genuinely have different factors (96.1 / 97.5 / 94.6 kgCO2/GJ
# LHV in the source IPCC table); Fuel Oil Heavy A and Heavy C currently share
# the same factor but are kept as separate calculations so a future change to
# just one doesn't require touching the other.
EF = {
    "Natural Gas":            0.0561,
    "Coal Sub-Bituminous":    0.0961,
    "Coal Brown Briquettes":  0.0975,
    "Coal Other Bituminous":  0.0946,
    "Propane":                0.0631,
    "Fuel Oil Heavy A":       0.0774,
    "Fuel Oil Heavy C":       0.0774,
    "Diesel":                 0.0741,
    "Petrol":                 0.0693,
    "Biomass":                0.0,
    "Waste tires":            0.04748,
    "LPG":                    0.0561,
    "Other":                  0.0719,
    # LEGACY — only used when a caller sets coal_sub (blended total) instead
    # of the 3 granular sub-types. Equal to the old pre-this-change "Coal"
    # factor, kept only so 15 other files that haven't been migrated yet
    # don't silently get a different number than before.
    "Coal Legacy Blended":    0.0961,
}

WASTE_TIRE_HV = 36.23          # GJ per metric T of waste tires.
# Kept for reference/cross-check only — no longer applied inside calculate().
# The real conversion now happens upstream via conversion_data.py's
# "Waste tires" subsection (metric T CF = 36.226, same number). If that
# factor ever changes, update conversion_data.py, not this constant.
GJ_TO_MWH    = 1 / 3.6

# Default Scope 2 electricity emission factor (T.CO2/MWh).
# This is the European average.  Override per company via
# TemplateInputs.scope2_elec_ef when country-specific factors are known.
_DEFAULT_SCOPE2_ELEC_EF = 0.45


@dataclass
class TemplateInputs:
    company: str  = ""
    year:    int  = 2023

    total_sites: float = 0
    iso_sites:   float = 0
    production:  float = 0

    water_withdrawals: float = 0

    renew_elec_purchased:    float = 0
    nonrenew_elec_purchased: float = 0
    self_gen_elec:           float = 0
    purchased_steam:         float = 0
    sold_electricity:        float = 0
    sold_steam:              float = 0

    nat_gas:                 float = 0
    # Coal — 3 sub-types tracked separately when known (real schema has no
    # single "coal" input; "Total Coal" is a calculated sum). `coal_sub` is
    # kept as a LEGACY fallback for the ~15 other files in this codebase that
    # still construct TemplateInputs with a single blended coal_sub= value —
    # calculate() uses the granular sub-types if any are set, else falls back
    # to coal_sub with a single approximate EF (see EF["Coal Legacy Blended"]).
    coal_sub:                float = 0   # LEGACY — prefer the 3 fields below
    coal_sub_bituminous:     float = 0
    coal_brown_briquettes:   float = 0
    coal_other_bituminous:   float = 0
    propane:                 float = 0
    # Fuel Oil — Heavy A and Heavy C tracked separately (real schema has no
    # single "fuel oil" input; total is calculated, see total_fuel_oil below).
    # fuel_oil_heavy_a already existed before this change, so no legacy bridge
    # needed there — old callers that only set fuel_oil_heavy_a (never
    # fuel_oil_heavy_c, which defaults to 0) get identical behavior to before.
    fuel_oil_heavy_a:        float = 0
    fuel_oil_heavy_c:        float = 0
    diesel:                  float = 0
    petrol:                  float = 0
    biomass:                 float = 0
    waste_tires_mt:          float = 0
    lpg:                     float = 0
    other_fuels:             float = 0

    co2_scope2_steam: float = 0

    waste_total:    float = 0
    waste_recovery: float = 0

    # M4 FIX — configurable per company/region instead of a hardcoded global.
    # Defaults to 0.45 (EU average) so existing call-sites need no changes.
    scope2_elec_ef: float = _DEFAULT_SCOPE2_ELEC_EF


@dataclass
class TemplateOutputs:
    pct_certified:   float = 0.0
    water_kpi:       float = 0.0

    total_electricity: float = 0.0
    waste_tires_gj:    float = 0.0
    total_coal:        float = 0.0   # sum of the 3 coal sub-types (GJ LHV)
    total_fuel_oil:    float = 0.0   # Heavy A + Heavy C (GJ LHV)
    total_energy:      float = 0.0
    energy_kpi:        float = 0.0

    co2_nat_gas:    float = 0.0
    # Granular per-subtype CO2 (each can use a different EF)
    co2_coal_sub_bituminous:   float = 0.0
    co2_coal_brown_briquettes: float = 0.0
    co2_coal_other_bituminous: float = 0.0
    co2_coal:       float = 0.0   # sum of the 3 sub-types above
    co2_propane:    float = 0.0
    co2_fuel_oil_heavy_a: float = 0.0
    co2_fuel_oil_heavy_c: float = 0.0
    co2_fuel_oil:   float = 0.0   # sum of Heavy A + Heavy C above
    co2_diesel:     float = 0.0
    co2_petrol:     float = 0.0
    co2_biomass:    float = 0.0
    co2_waste_tires:float = 0.0
    co2_lpg:        float = 0.0
    co2_other:      float = 0.0

    total_co2_scope1: float = 0.0
    total_co2_scope2: float = 0.0
    total_co2:        float = 0.0
    co2_kpi:          float = 0.0

    waste_elimination:   float = 0.0
    waste_recovery_pct:  float = 0.0

    # M1 FIX — check_waste now carries meaning (see calculate())
    check_waste: bool = True
    check_iso:   bool = True


def calculate(d: TemplateInputs) -> TemplateOutputs:
    def sdiv(a, b): return a / b if b else 0.0

    pct_cert  = sdiv(d.iso_sites, d.total_sites)
    water_kpi = sdiv(d.water_withdrawals, d.production)

    total_elec = (d.renew_elec_purchased
                  + d.nonrenew_elec_purchased
                  + d.self_gen_elec)

    # NOTE: waste_tires_mt is, despite its name, expected to already be a
    # common-unit (GJ) value by the time it reaches here — the mass->energy
    # step that WASTE_TIRE_HV used to do inline now happens upstream, via
    # conversion_data.py's "Waste tires" subsection conversion factor (its
    # "metric T" CF is 36.226, the same number WASTE_TIRE_HV always was).
    # Do NOT multiply by WASTE_TIRE_HV here — that would double-convert.
    wt_gj = d.waste_tires_mt

    # Coal and Fuel Oil totals are SUMS of their sub-types when known. If a
    # caller only set the legacy coal_sub= (hasn't been migrated to the 3
    # granular fields yet), fall back to treating it as one blended total
    # with the old single EF — same number those 15 files always got before.
    total_coal_granular = d.coal_sub_bituminous + d.coal_brown_briquettes + d.coal_other_bituminous
    using_granular_coal  = total_coal_granular > 0
    total_coal     = total_coal_granular if using_granular_coal else d.coal_sub
    total_fuel_oil = d.fuel_oil_heavy_a + d.fuel_oil_heavy_c

    total_e = (total_elec + d.purchased_steam
               + d.nat_gas + total_coal + d.propane
               + total_fuel_oil + d.diesel + d.petrol
               + d.biomass + wt_gj + d.lpg + d.other_fuels
               - d.sold_electricity - d.sold_steam)

    e_kpi = sdiv(total_e, d.production)

    s1_ng    = d.nat_gas               * EF["Natural Gas"]
    if using_granular_coal:
        s1_coal_sb = d.coal_sub_bituminous   * EF["Coal Sub-Bituminous"]
        s1_coal_bb = d.coal_brown_briquettes * EF["Coal Brown Briquettes"]
        s1_coal_ob = d.coal_other_bituminous * EF["Coal Other Bituminous"]
    else:
        # Legacy fallback — one blended total, can't break down by sub-type,
        # so all of the CO2 is attributed to the "Sub-Bituminous" bucket for
        # display purposes (the TOTAL co2_coal below is correct either way).
        s1_coal_sb = d.coal_sub * EF["Coal Legacy Blended"]
        s1_coal_bb = 0.0
        s1_coal_ob = 0.0
    s1_coal    = s1_coal_sb + s1_coal_bb + s1_coal_ob
    s1_prop  = d.propane               * EF["Propane"]
    s1_fo_a  = d.fuel_oil_heavy_a       * EF["Fuel Oil Heavy A"]
    s1_fo_c  = d.fuel_oil_heavy_c       * EF["Fuel Oil Heavy C"]
    s1_fo    = s1_fo_a + s1_fo_c
    s1_die   = d.diesel                * EF["Diesel"]
    s1_pet   = d.petrol                * EF["Petrol"]
    s1_bio   = d.biomass               * EF["Biomass"]
    s1_wt    = wt_gj                   * EF["Waste tires"]
    s1_lpg   = d.lpg                   * EF["LPG"]
    s1_oth   = d.other_fuels           * EF["Other"]

    scope1 = (s1_ng + s1_coal + s1_prop + s1_fo + s1_die
              + s1_pet + s1_bio + s1_wt + s1_lpg + s1_oth)

    # M4 FIX — use instance-level EF (defaults to 0.45 if not overridden)
    scope2 = (d.co2_scope2_steam
              + (d.nonrenew_elec_purchased * GJ_TO_MWH) * d.scope2_elec_ef)

    total_co2 = scope1 + scope2
    co2_kpi   = sdiv(total_co2, d.production)

    w_elim = d.waste_total - d.waste_recovery

    # M1 FIX — previous check was abs(total - recovery - w_elim) < 1 which
    # is always True because w_elim = total - recovery (a tautology).
    # Correct intent: if a user also enters waste_elimination separately we
    # would compare; here we validate that recovery cannot exceed total,
    # and that waste_total is a positive number when recovery is non-zero.
    check_waste = (
        d.waste_total >= 0
        and d.waste_recovery >= 0
        and d.waste_recovery <= d.waste_total
    )

    return TemplateOutputs(
        pct_certified=pct_cert,       water_kpi=water_kpi,
        total_electricity=total_elec, waste_tires_gj=wt_gj,
        total_coal=total_coal,        total_fuel_oil=total_fuel_oil,
        total_energy=total_e,         energy_kpi=e_kpi,
        co2_nat_gas=s1_ng,
        co2_coal_sub_bituminous=s1_coal_sb,
        co2_coal_brown_briquettes=s1_coal_bb,
        co2_coal_other_bituminous=s1_coal_ob,
        co2_coal=s1_coal,             co2_propane=s1_prop,
        co2_fuel_oil_heavy_a=s1_fo_a, co2_fuel_oil_heavy_c=s1_fo_c,
        co2_fuel_oil=s1_fo,           co2_diesel=s1_die,   co2_petrol=s1_pet,
        co2_biomass=s1_bio,  co2_waste_tires=s1_wt,
        co2_lpg=s1_lpg,      co2_other=s1_oth,
        total_co2_scope1=scope1,  total_co2_scope2=scope2,
        total_co2=total_co2,      co2_kpi=co2_kpi,
        waste_elimination=w_elim,
        waste_recovery_pct=sdiv(d.waste_recovery, d.waste_total),
        check_waste=check_waste,
        check_iso=(d.iso_sites <= d.total_sites),
    )


@dataclass
class ValidationFlag:
    severity: str
    message:  str
    detail:   str = ""


def validate_submission(inp, out, prev_out=None, threshold=20.0):
    flags = []

    # M1 FIX — this now actually catches waste_recovery > waste_total
    if not out.check_waste:
        flags.append(ValidationFlag(
            "error",
            "Waste consistency FAIL",
            f"Recovery {inp.waste_recovery:,.0f} T exceeds total {inp.waste_total:,.0f} T"
            if inp.waste_recovery > inp.waste_total
            else "Negative waste values entered",
        ))

    if not out.check_iso:
        flags.append(ValidationFlag("error", "ISO sites > total sites", ""))

    if prev_out:
        for name, cur, prev in [
            ("Total Energy", out.total_energy, prev_out.total_energy),
            ("Total CO2",    out.total_co2,    prev_out.total_co2),
        ]:
            if prev and abs(cur - prev) / max(abs(prev), 1) * 100 > threshold:
                pct = (cur - prev) / abs(prev) * 100
                flags.append(ValidationFlag(
                    "warning", f"{name}: {pct:+.1f}% YoY", ""
                ))

    if not flags:
        flags.append(ValidationFlag("ok", "All checks passed", ""))

    return flags


@dataclass
class BenchmarkResult:
    kpi_name:       str
    company_value:  float
    q25:            float
    median:         float
    q75:            float
    unit:           str
    lower_is_better:bool


def get_benchmarks(out, bench_df=None):
    STATIC = {
        "co2_kpi":    (0.55,  0.68, 0.82,  "T.CO2/T", True),
        "energy_kpi": (8.0,   9.2,  10.5,  "GJ/T",    True),
        "water_kpi":  (5.5,   7.0,   9.0,  "m3/T",    True),
    }
    results = []
    for col, (fq25, fmed, fq75, unit, lb) in STATIC.items():
        q25, med, q75 = fq25, fmed, fq75
        if bench_df is not None and not bench_df.empty and col in bench_df.columns:
            vals = bench_df[col].dropna().values
            if len(vals) >= 4:
                q25 = float(np.percentile(vals, 25))
                med = float(np.percentile(vals, 50))
                q75 = float(np.percentile(vals, 75))
        results.append(BenchmarkResult(
            col, getattr(out, col, 0.0), q25, med, q75, unit, lb
        ))
    return results


def fmt_num(val, decimals=0):
    try:
        return (f"{float(val):,.{decimals}f}" if decimals
                else f"{float(val):,.0f}")
    except Exception:
        return str(val)


def yoy_change(current, previous):
    try:
        if previous and abs(float(previous)) > 0:
            return (float(current) - float(previous)) / abs(float(previous)) * 100
    except Exception:
        pass
    return None


def build_template_dataframe(inp, out):
    import pandas as pd
    return pd.DataFrame([{
        "Company":          inp.company,
        "Year":             inp.year,
        "production":       inp.production,
        "water_kpi":        out.water_kpi,
        "total_energy":     out.total_energy,
        "energy_kpi":       out.energy_kpi,
        "total_co2_scope1": out.total_co2_scope1,
        "total_co2_scope2": out.total_co2_scope2,
        "total_co2":        out.total_co2,
        "co2_kpi":          out.co2_kpi,
        "waste_recovery_pct": out.waste_recovery_pct,
    }])