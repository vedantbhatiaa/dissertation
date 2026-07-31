"""
scripts/setup_data.py — TIP ESG Platform · Data Bootstrap & Integrity Check
============================================================================
The ONE script you need to know about.  Replaces build_esg_master.py (which
only handled dummy data up to 2023 and is now retired).

WHEN TO RUN
-----------
Almost never — the platform keeps all master files in sync automatically
every time a user saves data (data_utils.py writes to both the wide CSV and
the long-form CSV in lock-step).

Run this script ONLY when:
  1. Setting up a brand-new developer environment (first clone of the repo)
  2. Recovering from a corrupted or missing wide CSV
  3. You've manually edited ESG_LONG_FORM_MASTER.csv outside the platform
     and need to regenerate the wide CSV from scratch

The Azure App Service startup does NOT need to run this — app.py already
contains a lightweight guard (_ensure_master_csv_exists) that calls
pivot_to_wide() automatically if the wide CSV is missing.

WHAT IT DOES
------------
Reads  : data_storage/master/ESG_LONG_FORM_MASTER.csv
Writes :
  • data_storage/master/ESG_MASTER_WIDE_ALL_COMPANIES_<yr_min>_<yr_max>.csv
  • data_storage/master/ESG_MASTER_WIDE_PER_COMPANY_<yr_min>_<yr_max>.xlsx

The electricity-by-country columns ("Corporate units - <Country>" in the
long form) are correctly mapped to the Elec_<Country>_GJ column names that
the app reads, with the MWh-value stored in the long-form converted to GJ.

INCREMENTAL SAFETY
------------------
The long-form CSV is the canonical source of truth.  Every time a client
saves data on the platform, data_utils.py updates BOTH the long-form CSV AND
the wide CSV on disk (and in-memory).  Re-running this script after client
saves will regenerate the wide CSV correctly because the long-form was also
updated — no data loss.

Usage:
    python scripts/setup_data.py
    python scripts/setup_data.py /path/to/custom_long_form.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import re

import pandas as pd

# ── Path setup — works whether run from project root or scripts/ dir ───────────
_SCRIPT_DIR  = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent if _SCRIPT_DIR.name == "scripts" else _SCRIPT_DIR
sys.path.insert(0, str(_PROJECT_DIR))

import field_registry as fr
import conversion_data as cd

MASTER_DIR       = _PROJECT_DIR / "data_storage" / "master"
DEFAULT_LF_PATH  = MASTER_DIR / "ESG_LONG_FORM_MASTER.csv"

# ── Country column mapping ─────────────────────────────────────────────────────
# Long-form stores electricity-by-country as "Corporate units - <Country>"
# The app reads them as "Elec_<Country>_GJ" (see state.ELEC_COUNTRY_COLS).
# Values in the long-form are in MWh (as entered by the company); the wide CSV
# stores them in GJ (multiply by 3.6).
_MWH_TO_GJ = 3.6

def _corp_unit_to_elec_col(kpi_name: str) -> str | None:
    """Map 'Corporate units - Canada' → 'Elec_Canada_GJ'.
    Returns None for non-electricity KPIs."""
    if not kpi_name.startswith("Corporate units -"):
        return None
    country = kpi_name[len("Corporate units - "):].strip()
    safe    = re.sub(r"[^A-Za-z0-9]+", "_", country).strip("_")
    return f"Elec_{safe}_GJ"


def build_wide_from_longform(long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert long-form (Company, Year, KPI_Name, Value, Unit) to wide form.

    • Unit-bearing KPIs (23 fields in field_registry): common-unit value
      written to the canonical column name; also writes _CorporateValue and
      _Unit companion columns for the Corporate / Common Units toggle in My
      Records.
    • Electricity-by-country ("Corporate units - <Country>"): mapped to
      Elec_<Country>_GJ with MWh → GJ conversion.
    • All other KPIs: pass through as-is, column = KPI_Name.
    """
    long_df = long_df.copy()
    long_df["KPI_Name"] = long_df["KPI_Name"].astype(str).str.strip()
    long_df["Value"]    = pd.to_numeric(long_df["Value"], errors="coerce")

    rows: dict[tuple, dict] = {}
    n_converted = n_unit_missing = n_elec = 0

    for _, r in long_df.iterrows():
        key = (r["Company"], int(r["Year"]))
        rows.setdefault(key, {"Company": r["Company"], "Year": int(r["Year"])})
        out = rows[key]

        kpi   = r["KPI_Name"]
        value = r["Value"]

        # ── 1. Electricity-by-country ("Corporate units - Canada") ────────────
        elec_col = _corp_unit_to_elec_col(kpi)
        if elec_col is not None:
            # Long-form value is MWh; wide CSV stores GJ
            out[elec_col] = float(value) * _MWH_TO_GJ if pd.notna(value) else None
            n_elec += 1
            continue

        # ── 2. Unit-bearing field (field_registry UNIT_FIELDS) ────────────────
        uf = fr.BY_KPI_NAME.get(kpi)
        if uf is not None:
            corp_val = value
            unit     = r.get("Unit")
            out[fr.corporate_col(uf)] = corp_val
            out[fr.unit_col(uf)]      = unit

            if pd.isna(corp_val):
                out[uf.wide_col] = None
            elif pd.isna(unit) or not unit:
                # No unit recorded — assume value is already in common units
                # (historical-data backfill convention, same as build_master_from_longform.py)
                out[uf.wide_col] = corp_val
            else:
                cf = cd.get_unit_conversion_factor(uf.subsection, unit)
                if cf is None:
                    n_unit_missing += 1
                    out[uf.wide_col] = None
                else:
                    out[uf.wide_col] = corp_val * cf
                    n_converted += 1
            continue

        # ── 3. Everything else (counts, %, CO2 sub-totals, etc.) ─────────────
        out[kpi] = value

    print(f"  Unit conversions applied : {n_converted}")
    print(f"  Unrecognised unit pairs  : {n_unit_missing}")
    print(f"  Elec-by-country cols     : {n_elec} rows mapped to Elec_*_GJ")

    wide = pd.DataFrame(list(rows.values()))

    # Compute Total_Electricity_by_Country_GJ from the Elec_*_GJ columns
    elec_country_cols = [c for c in wide.columns
                         if c.startswith("Elec_") and c.endswith("_GJ")]
    if elec_country_cols:
        wide["Total_Electricity_by_Country_GJ"] = (
            wide[elec_country_cols].apply(pd.to_numeric, errors="coerce")
            .sum(axis=1, min_count=1).round(4)
        )

    return wide.sort_values(["Company", "Year"]).reset_index(drop=True)


def main() -> None:
    lf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LF_PATH

    print(f"\n{'='*60}")
    print("TIP ESG Platform — Data Setup")
    print(f"{'='*60}")
    print(f"\n[1/3] Reading long-form master: {lf_path}")
    if not lf_path.exists():
        print(f"\n  ❌  File not found: {lf_path}")
        print("  Make sure ESG_LONG_FORM_MASTER.csv is in data_storage/master/")
        sys.exit(1)

    lf_df = pd.read_csv(lf_path)
    print(f"  {len(lf_df):,} rows | "
          f"{lf_df['Company'].nunique()} companies | "
          f"{int(lf_df['Year'].min())}–{int(lf_df['Year'].max())}")

    print("\n[2/3] Building wide-form with unit conversion + Elec column mapping…")
    wide = build_wide_from_longform(lf_df)
    print(f"  Output: {wide.shape[0]} rows × {wide.shape[1]} columns")

    print("\n[3/3] Writing outputs…")
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    yr_min = int(wide["Year"].min())
    yr_max = int(wide["Year"].max())

    # ── Wide CSV ──────────────────────────────────────────────────────────────
    # Filename pattern MUST match data_loader._get_csv_candidates() glob:
    # "ESG_MASTER_WIDE_ALL_COMPANIES_*.csv"
    wide_csv = MASTER_DIR / f"ESG_MASTER_WIDE_ALL_COMPANIES_{yr_min}_{yr_max}.csv"
    wide.to_csv(wide_csv, index=False)
    print(f"  → {wide_csv.name}")

    # ── Per-company Excel ─────────────────────────────────────────────────────
    wide_xlsx = MASTER_DIR / f"ESG_MASTER_WIDE_PER_COMPANY_{yr_min}_{yr_max}.xlsx"
    try:
        with pd.ExcelWriter(wide_xlsx, engine="openpyxl") as writer:
            for company in sorted(wide["Company"].unique()):
                co_df = wide[wide["Company"] == company].reset_index(drop=True)
                # Drop Elec_ country cols that are all-zero for this company
                zero_elec = [c for c in co_df.columns
                             if c.startswith("Elec_") and c.endswith("_GJ")
                             and c != "Total_Electricity_by_Country_GJ"
                             and co_df[c].fillna(0).eq(0).all()]
                co_df.drop(columns=zero_elec, inplace=True)
                co_df.to_excel(writer, sheet_name=company[:31], index=False)
        print(f"  → {wide_xlsx.name}")
    except Exception as e:
        print(f"  ⚠  Per-company Excel skipped ({e}) — wide CSV is the source of truth")

    print(f"\n✅  Done.  Startup command remains: python -m streamlit run app.py")
    print(f"   (No need to run this script before every app start — the app\n"
          f"    updates these files automatically when users save data.)\n")


if __name__ == "__main__":
    main()