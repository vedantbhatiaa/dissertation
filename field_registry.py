"""
field_registry.py — TIP ESG Platform · Canonical Field Mapping
================================================================
Single source of truth linking together the four different names every
unit-bearing KPI field has across the system:

  1. `field`       — the TemplateInputs attribute name (formula_engine.py)
  2. `kpi_name`     — the exact KPI_Name string in the long-form master file
                      (matches the real WBCSD TIP KPI Collection Tool schema,
                      224 fields/company/year — see Bridgestone_Master.xlsx)
  3. `subsection`   — the key into conversion_data.UNIT_CONVERSION_FACTORS /
                      UNITS_BY_SUBSECTION, used to look up the conversion
                      factor and the allowed-units dropdown list
  4. `wide_col`     — the column name used in the wide master CSV / per-company
                      sheet for the COMMON-unit value (unchanged from before
                      this unit-conversion work existed, so nothing already
                      reading the wide CSV breaks)

page_entry.py, the long-form-to-wide pivot script, and render_template_table.py
should all import UNIT_FIELDS from here rather than each keeping their own
copy of this mapping — three independent copies of the same list is exactly
how a field quietly drifts out of sync between Submit Data and the display
tables.

Only the 23 fields a company directly types a number into are listed here.
Calculated fields (Total Coal, Total Energy, Total CO2, % certified sites,
Amount of waste sent to elimination, etc.) are never unit-selected — they're
derived from the fields below, see formula_engine.calculate().
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class UnitField:
    field:      str   # TemplateInputs attribute name
    kpi_name:   str   # exact long-form KPI_Name string
    subsection: str   # conversion_data.py lookup key
    wide_col:   str   # wide master CSV column name (common-unit value)


UNIT_FIELDS: list[UnitField] = [
    UnitField("production",             "Production",
              "Production", "Production"),
    UnitField("water_withdrawals",       "Water intake",
              "Water intake", "Water intake"),

    UnitField("renew_elec_purchased",    "Renewable Electricity Purchased",
              "Renewable Electricity Purchased", "Renewable Electricity Purchased"),
    UnitField("nonrenew_elec_purchased", "Non-Renewable Electricity Purchased",
              "Non-Renewable Electricity Purchased", "Non-Renewable Electricity Purchased"),
    UnitField("self_gen_elec",           "Self-generated AND consumed electricity on-site",
              "Self-generated AND consumed electricity on-site",
              "Self-generated AND consumed electricity on-site"),
    UnitField("purchased_steam",         "Purchased Steam",
              "Purchased Steam", "Purchased Steam"),
    UnitField("sold_electricity",        "Sold Electricity",
              "Sold Electricity", "Sold Electricity"),
    UnitField("sold_steam",              "Sold Steam",
              "Sold Steam", "Sold Steam"),

    UnitField("nat_gas",                 "Energy - Natural Gas",
              "Natural gas", "Energy - Natural Gas"),
    UnitField("coal_sub_bituminous",     "Energy - Sub bituminous coal",
              "Coal", "Energy - Sub bituminous coal"),
    UnitField("coal_brown_briquettes",   "Energy - Brown coal briquettes",
              "Coal", "Energy - Brown coal briquettes"),
    UnitField("coal_other_bituminous",   "Energy - Other bituminous coal",
              "Coal", "Energy - Other bituminous coal"),
    UnitField("propane",                 "Energy - Propane",
              "Propane", "Energy - Propane"),
    UnitField("fuel_oil_heavy_a",        "Energy - Fuel Oil Heavy A",
              "Fuel Oil", "Energy - Fuel Oil Heavy A"),
    UnitField("fuel_oil_heavy_c",        "Energy - Fuel Oil Heavy C",
              "Fuel Oil", "Energy - Fuel Oil Heavy C"),
    UnitField("diesel",                  "Energy - Diesel",
              "Diesel", "Energy - Diesel"),
    UnitField("petrol",                  "Energy - Petrol",
              "Petrol", "Energy - Petrol"),
    UnitField("biomass",                 "Energy - Biomass",
              "Biomass", "Energy - Biomass"),
    UnitField("waste_tires_mt",          "Energy - Waste tires",
              "Waste tires", "Energy - Waste tires"),
    UnitField("lpg",                     "Energy - LPG",
              "LPG", "Energy - LPG"),
    UnitField("other_fuels",             "Energy - Other",
              "Other", "Energy - Other"),

    UnitField("waste_total",             "Total amount of Waste",
              "Total amount of waste", "Total amount of Waste"),
    UnitField("waste_recovery",          "Amount of waste sent to recovery",
              "Amount of waste sent to recovery", "Amount of waste sent to recovery"),
]

# Fast lookups
BY_FIELD:    dict[str, UnitField] = {u.field: u for u in UNIT_FIELDS}
BY_KPI_NAME: dict[str, UnitField] = {u.kpi_name: u for u in UNIT_FIELDS}

# Coal and Fuel Oil sub-types feed into a single combined "Total Coal" /
# "Total Fuel Oil" — useful for the pivot script and display tables to know
# which raw fields roll up into which calculated field.
COAL_SUBTYPE_FIELDS     = ["coal_sub_bituminous", "coal_brown_briquettes", "coal_other_bituminous"]
FUEL_OIL_SUBTYPE_FIELDS = ["fuel_oil_heavy_a", "fuel_oil_heavy_c"]


def corporate_col(uf: "UnitField | str") -> str:
    """Wide-CSV column name holding the raw corporate-unit value."""
    wide_col = uf.wide_col if isinstance(uf, UnitField) else BY_FIELD[uf].wide_col
    return f"{wide_col}_CorporateValue"


def unit_col(uf: "UnitField | str") -> str:
    """Wide-CSV column name holding which unit the company used."""
    wide_col = uf.wide_col if isinstance(uf, UnitField) else BY_FIELD[uf].wide_col
    return f"{wide_col}_Unit"