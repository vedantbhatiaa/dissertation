"""
scripts/build_master_from_longform.py — TIP ESG Platform · Wide-Form Builder
=============================================================================
Replaces build_esg_master.py (which was built around the old dummy-data
Excel and is no longer relevant now that real company data is long-form).

Reads the long-form master CSV (Company, Year, KPI_Name, Value, Unit) and
produces:
  1. data_storage/master/ESG_MASTER_WIDE_ALL_COMPANIES.csv — one row per
     Company+Year, one column per KPI. For the 23 unit-bearing fields
     (see field_registry.py), THREE columns are written:
       <Field>                — common-unit value (unchanged name, so every
                                 existing reader — formula_engine, render
                                 tabs, graphs — keeps working untouched)
       <Field>_CorporateValue — the raw number the company reported
       <Field>_Unit           — which unit they used
  2. data_storage/master/ESG_MASTER_WIDE_PER_COMPANY.xlsx — same data, one
     sheet per company, for easy manual inspection / Azure SQL staging.

Non-unit-bearing fields (counts, percentages, electricity-by-country,
already-fixed-unit fields like CO2 figures) pass through unchanged — exactly
as they exist in the long-form file, one column each.

Run from the project root:
    python scripts/build_master_from_longform.py [path/to/long_form.csv]
"""
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import field_registry as fr
import conversion_data as cd

DEFAULT_LONG_FORM = Path("data_storage/master/ESG_LONG_FORM_MASTER.csv")
OUT_DIR = Path("data_storage/master")


def pivot_to_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    """Long-form (Company, Year, KPI_Name, Value, Unit) -> wide-form
    (one row per Company+Year). Unit-bearing fields get 3 columns; everything
    else gets 1, matching its KPI_Name as the column name directly."""
    long_df = long_df.copy()
    long_df["KPI_Name"] = long_df["KPI_Name"].astype(str).str.strip()
    long_df["Value"] = pd.to_numeric(long_df["Value"], errors="coerce")

    rows: dict[tuple, dict] = {}
    n_converted, n_unit_missing = 0, 0

    for _, r in long_df.iterrows():
        key = (r["Company"], r["Year"])
        rows.setdefault(key, {"Company": r["Company"], "Year": r["Year"]})
        out_row = rows[key]

        kpi_name = r["KPI_Name"]
        uf = fr.BY_KPI_NAME.get(kpi_name)

        if uf is None:
            # Not a unit-bearing field — pass through as-is, one column.
            out_row[kpi_name] = r["Value"]
            continue

        unit = r.get("Unit")
        corporate_value = r["Value"]
        out_row[fr.corporate_col(uf)] = corporate_value
        out_row[fr.unit_col(uf)] = unit

        if pd.isna(corporate_value):
            out_row[uf.wide_col] = None
            continue

        if pd.isna(unit) or not unit:
            # No unit recorded — assume the value is already a common-unit
            # figure (historical-data fallback agreed for the backfill).
            out_row[uf.wide_col] = corporate_value
            continue

        cf = cd.get_unit_conversion_factor(uf.subsection, unit)
        if cf is None:
            n_unit_missing += 1
            out_row[uf.wide_col] = None
            continue

        out_row[uf.wide_col] = corporate_value * cf
        n_converted += 1

    print(f"[pivot] {n_converted} unit conversions applied, "
          f"{n_unit_missing} rows had an unrecognised (subsection, unit) pair")

    wide = pd.DataFrame(list(rows.values()))
    return wide.sort_values(["Company", "Year"]).reset_index(drop=True)


def validate_against_ground_truth(long_df: pd.DataFrame, wide: pd.DataFrame) -> None:
    """If the long-form file carries a GroundTruthCommonValue column (only
    present in the synthetic multi-unit test fixture, not real data), check
    that every converted value round-trips back to it. Real production runs
    of this script won't have this column — validation is skipped silently."""
    if "GroundTruthCommonValue" not in long_df.columns:
        return
    long_df = long_df.copy()
    long_df["KPI_Name"] = long_df["KPI_Name"].astype(str).str.strip()
    mismatches = []
    for _, r in long_df.iterrows():
        if pd.isna(r.get("GroundTruthCommonValue")):
            continue
        uf = fr.BY_KPI_NAME.get(r["KPI_Name"])
        if uf is None:
            continue
        wrow = wide[(wide["Company"] == r["Company"]) & (wide["Year"] == r["Year"])]
        if wrow.empty:
            continue
        got = wrow.iloc[0].get(uf.wide_col)
        expected = r["GroundTruthCommonValue"]
        if got is None or pd.isna(got):
            mismatches.append((r["Company"], r["Year"], r["KPI_Name"], expected, got))
            continue
        if abs(float(got) - float(expected)) > max(1e-6, abs(float(expected)) * 1e-6):
            mismatches.append((r["Company"], r["Year"], r["KPI_Name"], expected, got))

    if mismatches:
        print(f"[validate] ❌ {len(mismatches)} round-trip mismatches:")
        for m in mismatches[:20]:
            print("   ", m)
        raise SystemExit(1)
    print(f"[validate] ✅ All round-trip checks passed against ground truth.")


def main():
    long_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LONG_FORM
    print(f"[1/4] Reading long-form master: {long_path}")
    long_df = pd.read_csv(long_path)
    print(f"    -> {len(long_df)} rows, {long_df['Company'].nunique()} companies, "
          f"{long_df['KPI_Name'].nunique()} unique KPI_Name values")

    print("[2/4] Pivoting to wide form with unit conversion...")
    wide = pivot_to_wide(long_df)
    print(f"    -> {wide.shape[0]} rows x {wide.shape[1]} columns")

    print("[3/4] Validating round-trip accuracy (if ground-truth column present)...")
    validate_against_ground_truth(long_df, wide)

    print("[4/4] Writing outputs...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    yr_min, yr_max = int(wide["Year"].min()), int(wide["Year"].max())
    # Filename MUST match data_loader.py's glob pattern
    # ("ESG_MASTER_WIDE_ALL_COMPANIES_*.csv") or the app won't find it.
    wide_csv = OUT_DIR / f"ESG_MASTER_WIDE_ALL_COMPANIES_{yr_min}_{yr_max}.csv"
    wide.to_csv(wide_csv, index=False)
    print(f"    -> wide CSV: {wide_csv}")

    wide_xlsx = OUT_DIR / f"ESG_MASTER_WIDE_PER_COMPANY_{yr_min}_{yr_max}.xlsx"
    with pd.ExcelWriter(wide_xlsx, engine="openpyxl") as writer:
        for company in sorted(wide["Company"].unique()):
            co_df = wide[wide["Company"] == company].reset_index(drop=True)
            co_df.to_excel(writer, sheet_name=company[:31], index=False)
    print(f"    -> per-company Excel: {wide_xlsx}")

    print("\n✅ Done.")


if __name__ == "__main__":
    main()