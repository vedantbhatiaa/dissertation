"""
conversion_data.py — TIP ESG Platform · Unit Conversion & Grid Emission Factor Reference Data
==============================================================================
Extracted directly from the WBCSD TIP KPI Collection Tool workbook
(sheets: "Conversion tables", "Conversion table waste",
"Pathway 3 - Electricity input"). This is the single source of truth for:

  1. UNIT_CONVERSION_FACTORS — corporate-unit -> common-unit multiplier,
     keyed by (subsection, unit). E.g. ("Natural gas", "MWh LHV") -> 3.6
     means 1 MWh LHV of natural gas = 3.6 GJ LHV (the fixed common unit).

  2. ELECTRICITY_GRID_EF — IEA location-based grid emission factor
     (grams CO2 per kWh) per country/region per year, for calculating
     Scope 2 electricity emissions on a per-country basis instead of one
     blended global average.

  3. ELEC_COUNTRY_REGIONS — the full IEA country/region taxonomy (152
     entries) grouped into 8 macro-regions, replacing the old hardcoded
     31-country list. Most companies will only have non-zero data for a
     handful of these; the rest exist so the grid-EF lookup always resolves
     and so companies operating anywhere in the world can find their country.

On Azure migration / next factor refresh: this file is the one to edit.
Re-export from the workbook's "Conversion tables" sheet and re-run the
extraction script (kept in scripts/extract_conversion_data.py) rather than
hand-editing the dicts below, to avoid transcription errors.
"""
from __future__ import annotations

# ── Corporate-unit -> common-unit conversion factors ─────────────────────────
# Keyed by (subsection, unit). subsection matches the KPI field family
# (e.g. "Natural gas", "Total amount of waste"), NOT the formula_engine field
# name directly — see UNIT_SUBSECTION_MAP in formula_engine.py for that link.
UNIT_CONVERSION_FACTORS: dict[tuple[str, str], float] = {
    ('Production', 'kg'): 0.001,
    ('Production', 'tire/year'): 0.0076,
    ('Production', 'lb'): 0.000453592,
    ('Production', 'metric T'): 1,
    ('Production', 'short (US) T'): 0.9071847,
    ('Water intake', 'm3'): 1,
    ('Water intake', '10^6 L'): 1000,
    ('Water intake', 'gal US'): 0.003785412,
    ('Water intake', 'L'): 0.001,
    ('Total Purchased Electricity', 'TJ'): 1000,
    ('Total Purchased Electricity', 'GJ'): 1,
    ('Total Purchased Electricity', 'MWh'): 3.6,
    ('Total Purchased Electricity', 'kWh'): 0.0036,
    ('Total Purchased Electricity', 'BTU'): 1.05505585e-06,
    ('Self-generated AND consumed electricity on-site', 'TJ'): 1000,
    ('Self-generated AND consumed electricity on-site', 'GJ'): 1,
    ('Self-generated AND consumed electricity on-site', 'MWh'): 3.6,
    ('Self-generated AND consumed electricity on-site', 'kWh'): 0.0036,
    ('Self-generated AND consumed electricity on-site', 'BTU'): 1.05505585e-06,
    ('Purchased Steam', 'TJ'): 1000,
    ('Purchased Steam', 'GJ'): 1,
    ('Purchased Steam', 'MWh'): 3.6,
    ('Purchased Steam', 'kWh'): 0.0036,
    ('Purchased Steam', 'BTU'): 1.05505585e-06,
    ('Purchased Steam', 'kL'): 38.49056603773585,
    ('Sold Electricity', 'TJ'): 1000,
    ('Sold Electricity', 'GJ'): 1,
    ('Sold Electricity', 'MWh'): 3.6,
    ('Sold Electricity', 'kWh'): 0.0036,
    ('Sold Electricity', 'BTU'): 1.05505585e-06,
    ('Sold Steam', 'TJ'): 1000,
    ('Sold Steam', 'GJ'): 1,
    ('Sold Steam', 'MWh'): 3.6,
    ('Sold Steam', 'kWh'): 0.0036,
    ('Sold Steam', 'BTU'): 1.05505585e-06,
    ('Sold Steam', 'kL'): 38.49056603773585,
    ('Natural gas', 'TJ HHV'): 913.2420091324202,
    ('Natural gas', 'TJ LHV'): 1000,
    ('Natural gas', 'GJ HHV'): 0.9132420091324202,
    ('Natural gas', 'GJ LHV'): 1,
    ('Natural gas', 'MWh HHV'): 3.2876712328767126,
    ('Natural gas', 'MWh LHV'): 3.6,
    ('Natural gas', 'kWh HHV'): 0.0032876712328767125,
    ('Natural gas', 'kWh LHV'): 0.0036,
    ('Natural gas', 'Decatherm HHV'): 0.9635213242009133,
    ('Natural gas', 'Decatherm LHV'): 1.05505585,
    ('Natural gas', 'BTU HHV'): 9.635213242009133e-07,
    ('Natural gas', 'BTU LHV'): 1.05505585e-06,
    ('Natural gas', 'kL'): 0.0384905660377359,
    ('Diesel', 'TJ HHV'): 943.3962264150942,
    ('Diesel', 'TJ LHV'): 1000,
    ('Diesel', 'GJ HHV'): 0.9433962264150942,
    ('Diesel', 'GJ LHV'): 1,
    ('Diesel', 'MWh HHV'): 3.3962264150943393,
    ('Diesel', 'MWh LHV'): 3.6,
    ('Diesel', 'kWh HHV'): 0.003396226415094339,
    ('Diesel', 'kWh LHV'): 0.0036,
    ('Diesel', 'BTU HHV'): 9.953357075471698e-07,
    ('Diesel', 'BTU LHV'): 1.05505585e-06,
    ('Diesel', 'kL'): 38.49056603773585,
    ('Propane', 'TJ HHV'): 921.6589861751152,
    ('Propane', 'TJ LHV'): 1000,
    ('Propane', 'GJ HHV'): 0.9216589861751152,
    ('Propane', 'GJ LHV'): 1,
    ('Propane', 'MWh HHV'): 3.317972350230415,
    ('Propane', 'MWh LHV'): 3.6,
    ('Propane', 'kWh HHV'): 0.003317972350230415,
    ('Propane', 'kWh LHV'): 0.0036,
    ('Propane', 'BTU HHV'): 9.724017050691244e-07,
    ('Propane', 'BTU LHV'): 1.05505585e-06,
    ('Propane', 'kL'): 38.49056603773585,
    ('Petrol', 'TJ HHV'): 943.3962264150942,
    ('Petrol', 'TJ LHV'): 1000,
    ('Petrol', 'GJ HHV'): 0.9433962264150942,
    ('Petrol', 'GJ LHV'): 1,
    ('Petrol', 'MWh HHV'): 3.3962264150943393,
    ('Petrol', 'MWh LHV'): 3.6,
    ('Petrol', 'kWh HHV'): 0.003396226415094339,
    ('Petrol', 'kWh LHV'): 0.0036,
    ('Petrol', 'BTU HHV'): 9.953357075471698e-07,
    ('Petrol', 'BTU LHV'): 1.05505585e-06,
    ('Petrol', 'kL'): 38.49056603773585,
    ('Coal', 'TJ HHV'): 980.3921568627451,
    ('Coal', 'TJ LHV'): 1000,
    ('Coal', 'GJ HHV'): 0.9803921568627451,
    ('Coal', 'GJ LHV'): 1,
    ('Coal', 'MWh HHV'): 3.5294117647058822,
    ('Coal', 'MWh LHV'): 3.6,
    ('Coal', 'kWh HHV'): 0.003529411764705882,
    ('Coal', 'kWh LHV'): 0.0036,
    ('Coal', 'BTU HHV'): 1.0343684803921568e-06,
    ('Coal', 'BTU LHV'): 1.05505585e-06,
    ('Coal', 'metric T'): 24.485669786979432,
    ('Fuel Oil', 'TJ HHV'): 943.3962264150942,
    ('Fuel Oil', 'TJ LHV'): 1000,
    ('Fuel Oil', 'GJ HHV'): 0.9433962264150942,
    ('Fuel Oil', 'GJ LHV'): 1,
    ('Fuel Oil', 'MWh HHV'): 3.3962264150943393,
    ('Fuel Oil', 'MWh LHV'): 3.6,
    ('Fuel Oil', 'kWh HHV'): 0.003396226415094339,
    ('Fuel Oil', 'kWh LHV'): 0.0036,
    ('Fuel Oil', 'BTU HHV'): 9.953357075471698e-07,
    ('Fuel Oil', 'BTU LHV'): 1.05505585e-06,
    ('Fuel Oil', 'KL'): 38.4905660377359,
    ('Biomass', 'TJ HHV'): 823.0452674897118,
    ('Biomass', 'TJ LHV'): 1000,
    ('Biomass', 'GJ HHV'): 0.8230452674897119,
    ('Biomass', 'GJ LHV'): 1,
    ('Biomass', 'MWh HHV'): 2.962962962962963,
    ('Biomass', 'MWh LHV'): 3.6,
    ('Biomass', 'kWh HHV'): 0.002962962962962963,
    ('Biomass', 'kWh LHV'): 0.0036,
    ('Biomass', 'BTU HHV'): 8.683587242798353e-07,
    ('Biomass', 'BTU LHV'): 1.05505585e-06,
    ('Waste tires', 'TJ HHV'): 943.3962264150942,
    ('Waste tires', 'TJ LHV'): 1000,
    ('Waste tires', 'MWh HHV'): 3.3962264150943393,
    ('Waste tires', 'MWh LHV'): 3.6,
    ('Waste tires', 'kWh HHV'): 0.003396226415094339,
    ('Waste tires', 'kWh LHV'): 0.0036,
    ('Waste tires', 'BTU HHV'): 9.953357075471698e-07,
    ('Waste tires', 'BTU LHV'): 1.05505585e-06,
    ('Waste tires', 'GJ HHV'): 0.9433962264150942,
    ('Waste tires', 'GJ LHV'): 1,
    ('Waste tires', 'short (US) T'): 32.86404950943396,
    ('Waste tires', 'kg'): 0.036226415094339624,
    ('Waste tires', 'lb'): 0.016432012075471698,
    ('Waste tires', 'metric T'): 36.22641509433962,
    ('Waste tires', 'tire/year'): 0.27532075471698114,
    ('Renewable Electricity Purchased', 'TJ'): 1000,
    ('Renewable Electricity Purchased', 'GJ'): 1,
    ('Renewable Electricity Purchased', 'MWh'): 3.6,
    ('Renewable Electricity Purchased', 'kWh'): 0.0036,
    ('Renewable Electricity Purchased', 'BTU'): 1.05505585e-06,
    ('Non-Renewable Electricity Purchased', 'TJ'): 1000,
    ('Non-Renewable Electricity Purchased', 'GJ'): 1,
    ('Non-Renewable Electricity Purchased', 'MWh'): 3.6,
    ('Non-Renewable Electricity Purchased', 'kWh'): 0.0036,
    ('Non-Renewable Electricity Purchased', 'BTU'): 1.05505585e-06,
    ('Other', 'TJ HHV'): 943.3962264150942,
    ('Other', 'TJ LHV'): 1000,
    ('Other', 'GJ HHV'): 0.9433962264150942,
    ('Other', 'GJ LHV'): 1,
    ('Other', 'MWh HHV'): 3.3962264150943393,
    ('Other', 'MWh LHV'): 3.6,
    ('Other', 'kWh HHV'): 0.003396226415094339,
    ('Other', 'kWh LHV'): 0.0036,
    ('Other', 'BTU HHV'): 9.953357075471698e-07,
    ('Other', 'BTU LHV'): 1.05505585e-06,
    ('Other', 'kL'): 38.49056603773585,
    ('LPG', 'TJ HHV'): 921.6589861751152,
    ('LPG', 'TJ LHV'): 1000,
    ('LPG', 'GJ HHV'): 0.9216589861751152,
    ('LPG', 'GJ LHV'): 1,
    ('LPG', 'MWh HHV'): 3.317972350230415,
    ('LPG', 'MWh LHV'): 3.6,
    ('LPG', 'kWh HHV'): 0.003317972350230415,
    ('LPG', 'kWh LHV'): 0.0036,
    ('LPG', 'BTU HHV'): 9.724017050691244e-07,
    ('LPG', 'BTU LHV'): 1.05505585e-06,
    ('LPG', 'kL'): 38.49056603773585,
    ('Total amount of waste', 'metric T'): 1,
    ('Total amount of waste', 'kg'): 0.001,
    ('Total amount of waste', 'lb'): 0.000453592,
    ('Amount of waste sent to recovery', 'metric T'): 1,
    ('Amount of waste sent to recovery', 'kg'): 0.001,
    ('Amount of waste sent to recovery', 'lb'): 0.000453592,
    ('Amount of waste sent to elimination', 'metric T'): 1,
    ('Amount of waste sent to elimination', 'kg'): 0.001,
    ('Amount of waste sent to elimination', 'lb'): 0.000453592,
}

# ── Allowed corporate units per subsection (drives the unit dropdown) ────────
UNITS_BY_SUBSECTION: dict[str, list[str]] = {}
for _sec, _unit in UNIT_CONVERSION_FACTORS:
    UNITS_BY_SUBSECTION.setdefault(_sec, []).append(_unit)


def get_unit_conversion_factor(subsection: str, unit: str) -> float | None:
    """Corporate-unit -> common-unit multiplier for a given KPI field family.
    Returns None if the (subsection, unit) pair isn't recognised — callers
    should treat that as a data problem to surface, not silently assume 1.0."""
    return UNIT_CONVERSION_FACTORS.get((subsection, unit))


def to_common_unit(value: float, subsection: str, unit: str) -> float:
    """Convert a corporate-unit value to the fixed common unit for that
    subsection. Raises ValueError on an unrecognised unit, since silently
    returning the raw value would misreport actual quantities."""
    cf = get_unit_conversion_factor(subsection, unit)
    if cf is None:
        raise ValueError(f"No conversion factor for subsection={subsection!r}, unit={unit!r}")
    return value * cf

# ── Electricity grid emission factor (g CO2 / kWh), location-based ───────────
# IEA data, by country/region, year columns 2009-2025.
# Source: WBCSD TIP KPI Collection Tool, "Conversion tables" sheet,
# "Emission factor - Electricity grid" block.
GRID_EF_YEARS: list[int] = [2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

# {country_or_region: [gCO2/kWh for each year in GRID_EF_YEARS]}
ELECTRICITY_GRID_EF: dict[str, list[float]] = {
    'Canada': [174.9, 183, 168.1, 160.1, 152.4, 152.8, 154.1, 149.5, 149.5, 149.5, 149.5, 149.5, 119.5, 119.5, 117.7, 109.6, 109.6],
    'Chile': [376.6, 415.3, 447.6, 489.9, 481.8, 417.5, 438.3, 442.8, 442.8, 442.8, 442.8, 442.8, 418.1, 418.1, 372.7, 322.5, 322.5],
    'Mexico': [511.7, 502.3, 486.3, 501.1, 486.6, 464.1, 460.4, 464.3, 464.3, 464.3, 464.3, 464.3, 398.6, 398.6, 406.8, 367.3, 367.3],
    'United States': [525.9, 530.5, 510.8, 487.6, 489.4, 485.7, 455.7, 433.2, 433.2, 433.2, 433.2, 433.2, 353.4, 353.4, 367.8, 354.3, 354.3],
    'OECD Americas': [481.4, 488.1, 467.9, 449.1, 447.4, 442.4, 418, 399.9, 399.9, 399.9, 399.9, 399.9, 326.1, 326.1, 337.5, 322.5, 322.5],
    'Australia': [895.1, 833.4, 798.3, 803.6, 767.7, 736.6, 757.3, 758.7, 758.7, 758.7, 758.7, 758.7, 678.3, 678.3, 648.6, 607.8, 607.8],
    'Israel': [706.1, 698.1, 737.9, 780, 669, 635.8, 607.3, 566.2, 566.2, 566.2, 566.2, 566.2, 460.4, 460.4, 441.3, 436.1, 436.1],
    'Japan': [419.4, 425.4, 506.2, 559.3, 567.4, 556.7, 543.3, 543.8, 543.8, 543.8, 543.8, 543.8, 476.1, 476.1, 462.8, 464.5, 464.5],
    'Korea': [536.8, 546.3, 558.1, 552, 535.9, 517, 526.8, 521.4, 521.4, 521.4, 521.4, 521.4, 465.3, 465.3, 455.8, 430.7, 430.7],
    'New Zealand': [173, 156, 145.2, 176.8, 156.2, 131.2, 124.7, 104.7, 104.7, 104.7, 104.7, 104.7, 129.4, 129.4, 135.1, 94.9, 94.9],
    'OECD Asia Oceania': [514.4, 510, 557.3, 587.4, 578.3, 561.4, 558.8, 556.4, 556.4, 556.4, 556.4, 556.4, 491.7, 491.7, 476.9, 463.7, 463.7],
    'Austria': [168.4, 200.4, 217.9, 168.3, 165.3, 151.1, 164, 150.9, 150.9, 150.9, 150.9, 150.9, 119.3, 119.3, 132.3, 125.8, 125.8],
    'Belgium': [214.8, 222.3, 197.4, 216.7, 194.3, 207.7, 228.4, 171.8, 171.8, 171.8, 171.8, 171.8, 163.9, 163.9, 135.5, 147.6, 147.6],
    'Czech Republic': [598.6, 583.9, 569.4, 535.3, 503.7, 508, 520.4, 530.2, 530.2, 530.2, 530.2, 530.2, 409.7, 409.7, 422.9, 438.7, 438.7],
    'Denmark': [403.9, 362.4, 318.2, 259.1, 300.2, 254.4, 174.1, 206.6, 206.6, 206.6, 206.6, 206.6, 93.9, 93.9, 108.4, 98.9, 98.9],
    'Estonia': [1088.6, 1024.5, 956.9, 921.3, 1007.9, 984.8, 986, 942.8, 942.8, 942.8, 942.8, 942.8, 494.9, 494.9, 582.1, 652.2, 652.2],
    'Finland': [193.1, 233.8, 194.8, 137.4, 174.7, 147.3, 106.8, 116.6, 116.6, 116.6, 116.6, 116.6, 72.3, 72.3, 79.1, 69.6, 69.6],
    'France': [79.8, 79.7, 59.1, 66.8, 63.7, 44.1, 48.6, 52.3, 52.3, 52.3, 52.3, 52.3, 51.1, 51.1, 51.9, 63.8, 63.8],
    'Germany': [480.1, 474.5, 482.5, 485.2, 488.3, 473.2, 449.7, 446.7, 446.7, 446.7, 446.7, 446.7, 311, 311, 347.2, 365, 365],
    'Greece': [735.7, 729, 717.1, 694.2, 648.5, 667.1, 583.5, 520.3, 520.3, 520.3, 520.3, 520.3, 373, 373, 341.1, 339.4, 339.4],
    'Hungary': [314.5, 319.4, 318.4, 317, 292, 276.3, 273.7, 272.5, 272.5, 272.5, 272.5, 272.5, 219.8, 219.8, 190.6, 185, 185],
    'Iceland': [0.2, 0.2, 0.2, 0.2, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.1, 0.1, 0.1, 0.2, 0.2],
    'Ireland': [455, 466, 433.3, 465.2, 439.1, 429, 417.6, 413.4, 413.4, 413.4, 413.4, 413.4, 265.7, 265.7, 315.4, 288.8, 288.8],
    'Italy': [414.9, 409.9, 405.8, 392.6, 342.9, 331, 342.4, 330.6, 330.6, 330.6, 330.6, 330.6, 264.7, 264.7, 281.6, 311.6, 311.6],
    'Luxembourg': [343.9, 341, 339.3, 337.3, 307.6, 306.3, 281.2, 205.2, 205.2, 205.2, 205.2, 205.2, 107.8, 107.8, 100.2, 93.6, 93.6],
    'Netherlands': [427.1, 420.7, 409.6, 440.9, 444.7, 472.6, 489, 464.2, 464.2, 464.2, 464.2, 464.2, 301.8, 301.8, 311.1, 284.1, 284.1],
    'Norway': [11, 22.8, 16.5, 7.7, 8.7, 8.5, 8.5, 8, 8, 8, 8, 8, 6.5, 6.5, 6.2, 7, 7],
    'Poland': [816.7, 799.5, 798.3, 772.9, 772.3, 756.3, 730.3, 719.6, 719.6, 719.6, 719.6, 719.6, 622.8, 622.8, 647.5, 630.4, 630.4],
    'Portugal': [383.3, 257.5, 306.4, 368.3, 281.4, 270.6, 346.5, 286.7, 286.7, 286.7, 286.7, 286.7, 184, 184, 150.3, 156.2, 156.2],
    'Slovak Republic': [214.1, 201, 203.4, 198.3, 175.8, 162.2, 168.8, 157.8, 157.8, 157.8, 157.8, 157.8, 129.4, 129.4, 135.9, 121.8, 121.8],
    'Slovenia': [324.1, 330.6, 344.6, 337.7, 318.2, 225.7, 262.3, 258.7, 258.7, 258.7, 258.7, 258.7, 227.9, 227.9, 225.3, 210, 210],
    'Spain': [299.5, 239.8, 296.3, 309.7, 244.9, 255.3, 293.1, 245.8, 245.8, 245.8, 245.8, 245.8, 153.3, 153.3, 149.8, 170.4, 170.4],
    'Sweden': [18.6, 26.4, 17.3, 12.2, 13.3, 11.1, 10.8, 12.2, 12.2, 12.2, 12.2, 12.2, 10.3, 10.3, 11.3, 11.2, 11.2],
    'Switzerland': [23.6, 24.7, 26.6, 25.2, 23.8, 23, 24.2, 27.9, 27.9, 27.9, 27.9, 27.9, 24.3, 24.3, 25.3, 24.9, 24.9],
    'Republic of Türkiye': [506.1, 467.6, 479.6, 470, 441.7, 492.7, 446, 464.5, 464.5, 464.5, 464.5, 464.5, 412, 412, 421.5, 420.9, 420.9],
    'United Kingdom': [448.2, 452.2, 442.4, 489.1, 457.3, 414, 349.5, 278.2, 278.2, 278.2, 278.2, 278.2, 193.2, 193.2, 204.1, 194.8, 194.8],
    'OECD Europe': [344.5, 335.6, 336.3, 335.6, 321, 311.3, 302.1, 290.7, 290.7, 290.7, 290.7, 290.7, 217.5, 217.5, 230.2, 240.1, 240.1],
    'European Union - 27': [361.6, 351.7, 354.5, 355.3, 336.3, 321.7, 315, 299, 299, 299, 299, 299, 220.7, 220.7, 233.2, 248.2, 248.2],
    'Non-OECD': [623.4, 616.9, 626.8, 625.9, 619.5, 601.8, 584, 565.6, 565.6, 565.6, 565.6, 565.6, 553.5, 553.5, 553.1, 547.1, 547.1],
    'Albania': [1.2, 2, 7.4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'Armenia': [103, 92.7, 124.1, 177.5, 170.4, 199.1, 163.5, 161.8, 161.8, 161.8, 161.8, 161.8, 181.3, 181.3, 206.3, 181.5, 181.5],
    'Azerbaijan': [483.9, 433.4, 457.2, 496.4, 483.5, 477.2, 487.5, 478.9, 478.9, 478.9, 478.9, 478.9, 439.6, 439.6, 434.7, 421.3, 421.3],
    'Belarus': [467.8, 450.9, 443.4, 427.3, 419, 404.5, 387.1, 377.7, 377.7, 377.7, 377.7, 377.7, 363.5, 363.5, 319.6, 306.7, 306.7],
    'Bosnia and Herzegovina': [821.2, 736.9, 993.6, 993.2, 791.9, 719.3, 730.7, 770.6, 770.6, 770.6, 770.6, 770.6, 796, 796, 685.4, 781, 781],
    'Bulgaria': [551, 552.7, 602.5, 544, 505.6, 492.7, 496.8, 471.7, 471.7, 471.7, 471.7, 471.7, 373.3, 373.3, 408.4, 475.6, 475.6],
    'Croatia': [279.3, 226.9, 322.8, 309.7, 220.8, 192.7, 232.7, 229.5, 229.5, 229.5, 229.5, 229.5, 167.2, 167.2, 149.2, 184.9, 184.9],
    'Cyprus': [753.8, 712.1, 740.1, 734, 646.4, 658, 649.4, 657.6, 657.6, 657.6, 657.6, 657.6, 616.5, 616.5, 598.6, 587.4, 587.4],
    'Georgia': [123.9, 69.2, 102.1, 117.6, 85.2, 108.8, 117.7, 92.5, 92.5, 92.5, 92.5, 92.5, 109.5, 109.5, 77.9, 105, 105],
    'Gibraltar': [765.1, 752.1, 760.4, 756.4, 753.5, 750.5, 760.2, 755.7, 755.7, 755.7, 755.7, 755.7, 504.9, 504.9, 504.9, 504.9, 504.9],
    'Kazakhstan': [448.6, 416.3, 438.9, 470.7, 499.8, 513.9, 414.1, 504.7, 504.7, 504.7, 504.7, 504.7, 573, 573, 487.2, 536.2, 536.2],
    'Kosovo': [1309.3, 1311.1, 1127.4, 1043.8, 979.8, 1017.3, 1051.2, 1125.1, 1125.1, 1125.1, 1125.1, 1125.1, 954.3, 954.3, 941.8, 883.3, 883.3],
    'Kyrgyzstan': [74.7, 37.5, 31.5, 35.3, 33.4, 49.2, 92.4, 73.8, 73.8, 73.8, 73.8, 73.8, 54.7, 54.7, 97.4, 99.1, 99.1],
    'Latvia': [94.9, 118.2, 130.9, 89, 131.4, 127.6, 145.3, 117, 117, 117, 117, 117, 110.8, 110.8, 104, 72.3, 72.3],
    'Lithuania': [84.2, 340, 271.5, 272.6, 204.4, 183.7, 185.8, 139.4, 139.4, 139.4, 139.4, 139.4, 149, 149, 129.9, 99.9, 99.9],
    'Republic of North Macedonia': [811.1, 695.7, 841.9, 868.8, 756.3, 803, 683.2, 611.1, 611.1, 611.1, 611.1, 611.1, 634, 634, 562.5, 710, 710],
    'Malta': [859, 879.6, 874.4, 879.2, 727.8, 713.1, 652, 651.2, 651.2, 651.2, 651.2, 651.2, 383.1, 383.1, 351.5, 351.9, 351.9],
    'Republic of Moldova': [498.8, 488.5, 488.4, 499.8, 474.1, 492.4, 496.7, 501.4, 501.4, 501.4, 501.4, 501.4, 494.3, 494.3, 489.5, 484.2, 484.2],
    'Montenegro': [295.6, 429.7, 665.4, 554.4, 388.6, 468.2, 516.7, 386.8, 386.8, 386.8, 386.8, 386.8, 471, 471, 366.5, 447.3, 447.3],
    'Romania': [478.2, 416.8, 505.1, 486.5, 357.6, 321.1, 338.6, 320.6, 320.6, 320.6, 320.6, 320.6, 273.1, 273.1, 271.3, 276, 276],
    'Russian Federation': [406.8, 417.5, 443.1, 434.4, 438.7, 385.3, 395, 357.8, 357.8, 357.8, 357.8, 357.8, 359, 359, 362.7, 349.5, 349.5],
    'Serbia': [751.2, 721.1, 794.2, 769.6, 751.8, 691.6, 755.7, 729.2, 729.2, 729.2, 729.2, 729.2, 763.8, 763.8, 705.6, 764.6, 764.6],
    'Tajikistan': [3.6, 0.7, 0.8, 1.3, 1.4, 5.1, 7.6, 20.7, 20.7, 20.7, 20.7, 20.7, 71.7, 71.7, 54.9, 60.4, 60.4],
    'Turkmenistan': [870, 958.6, 988.7, 992, 944.9, 890.3, 893.1, 893.1, 893.1, 893.1, 893.1, 893.1, 698.8, 698.8, 674.1, 760, 760],
    'Ukraine': [420.4, 425.2, 460.4, 470.7, 473.2, 438.7, 396.6, 422.7, 422.7, 422.7, 422.7, 422.7, 333, 333, 288.6, 267.1, 267.1],
    'Uzbekistan': [557.5, 543.9, 556.5, 543.8, 544.7, 546.2, 552.9, 495.5, 495.5, 495.5, 495.5, 495.5, 468.6, 468.6, 524, 482.5, 482.5],
    'Non-OECD Europe and Eurasia': [432.1, 433.6, 465.5, 458.6, 453.6, 413.7, 413.6, 394, 394, 394, 394, 394, 384.4, 384.4, 374.7, 376.2, 376.2],
    'Algeria': [640.8, 548.7, 549.1, 539, 502.6, 508.1, 534.7, 509.5, 509.5, 509.5, 509.5, 509.5, 486.7, 486.7, 509.9, 508.8, 508.8],
    'Angola': [470.2, 434.8, 394.5, 297.1, 283.1, 363.1, 386.6, 383.1, 383.1, 383.1, 383.1, 383.1, 238.6, 238.6, 240.6, 235.4, 235.4],
    'Benin': [726.9, 725.4, 730.7, 668.4, 697.5, 724.9, 675.5, 677.9, 677.9, 677.9, 677.9, 677.9, 510.9, 510.9, 464, 509.2, 509.2],
    'Botswana': [1513.3, 1065.8, 2242.2, 5896, 2506.8, 1621.1, 1285.2, 1347.7, 1347.7, 1347.7, 1347.7, 1347.7, 1351, 1351, 1347.6, 1348.4, 1348.4],
    'Cameroon': [198.1, 209.2, 161.2, 184.3, 223.4, 240.4, 246.4, 246.1, 246.1, 246.1, 246.1, 246.1, 274.8, 274.8, 259.8, 206.2, 206.2],
    'Republic of the Congo': [246.1, 268.9, 231.4, 246.3, 253.6, 266, 274, 266, 266, 266, 266, 266, 580.5, 580.5, 572.3, 590.7, 590.7],
    'Democratic Republic of the Congo': [6.7, 6.6, 6.7, 0.4, 0.4, 0.8, 1.3, 1.1, 1.1, 1.1, 1.1, 1.1, 0.4, 0.4, 0.1, 0.3, 0.3],
    "Cote d'Ivoire": [393, 463.2, 439.1, 493.3, 449.4, 454.3, 435.4, 368.9, 368.9, 368.9, 368.9, 368.9, 315.7, 315.7, 336.7, 344.6, 344.6],
    'Egypt': [469.7, 426.7, 423.9, 446.1, 447.4, 459.6, 461.6, 459.5, 459.5, 459.5, 459.5, 459.5, 382.6, 382.6, 401.9, 404.1, 404.1],
    'Eritrea': [841.8, 859.5, 858.4, 858.3, 858.3, 859, 859.8, 858.9, 858.9, 858.9, 858.9, 858.9, 822.6, 822.6, 862.9, 879.2, 879.2],
    'Ethiopia': [221.3, 11.1, 7.6, 3, 1.1, 0.7, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.1, 0.1],
    'Gabon': [355.7, 395, 423, 402.4, 373.5, 406.2, 409.7, 408.7, 408.7, 408.7, 408.7, 408.7, 579.2, 579.2, 515.7, 456.8, 456.8],
    'Ghana': [189.9, 297.2, 216.9, 251.4, 273.2, 251.2, 285.7, 200.1, 200.1, 200.1, 200.1, 200.1, 322.8, 322.8, 334, 303.2, 303.2],
    'Kenya': [406.5, 281.1, 301, 228.9, 279.3, 168.5, 113.5, 188.2, 188.2, 188.2, 188.2, 188.2, 61, 61, 95.6, 115.9, 115.9],
    'Libya': [727.2, 690.4, 680.5, 673.5, 653.4, 629.8, 633.5, 514.8, 514.8, 514.8, 514.8, 514.8, 630.9, 630.9, 630.3, 626.5, 626.5],
    'Morocco': [709.2, 694.6, 745.8, 707.7, 638.1, 702, 701.8, 680.9, 680.9, 680.9, 680.9, 680.9, 715.9, 715.9, 717.3, 754.5, 754.5],
    'Mozambique': [0.5, 0.7, 0.9, 1.2, 11.8, 49.1, 65.2, 67.2, 67.2, 67.2, 67.2, 67.2, 78.1, 78.1, 79.2, 86.1, 86.1],
    'Namibia': [72.9, 24, 13.7, 56.2, 57.1, 9, 25.3, 58.5, 58.5, 58.5, 58.5, 58.5, 43.9, 43.9, 36.9, 24.7, 24.7],
    'Nigeria': [389.3, 381.7, 395, 405.4, 411.8, 416.1, 413, 413.6, 413.6, 413.6, 413.6, 413.6, 417.4, 417.4, 406.5, 394.6, 394.6],
    'Senegal': [727, 679.9, 626.5, 608.8, 615.8, 617.6, 654.5, 668.1, 668.1, 668.1, 668.1, 668.1, 556.5, 556.5, 586.2, 549, 549],
    'South Africa': [924.2, 945.9, 887.2, 925.4, 941.4, 1001, 931.1, 945.2, 945.2, 945.2, 945.2, 945.2, 923.8, 923.8, 895.8, 987.1, 987.1],
    'Sudan': [416.9, 145, 196.5, 204.1, 170.9, 187.1, 302.9, 420.9, 420.9, 420.9, 420.9, 420.9, 305.7, 305.7, 264.4, 206.7, 206.7],
    'United Republic of Tanzania': [253.9, 279.1, 376.4, 445.7, 479.1, 389.4, 433.1, 251.9, 251.9, 251.9, 251.9, 251.9, 334.9, 334.9, 320.7, 351.9, 351.9],
    'Togo': [231.8, 375.4, 125.2, 173.1, 206.6, 132.5, 237.2, 82.8, 82.8, 82.8, 82.8, 82.8, 331.1, 331.1, 348.9, 422.4, 422.4],
    'Tunisia': [490.5, 482.7, 471.1, 463.3, 464.6, 477.5, 468.8, 434.9, 434.9, 434.9, 434.9, 434.9, 423.4, 423.4, 421.4, 400.5, 400.5],
    'Zambia': [2.2, 2.4, 3, 2.6, 2.4, 18.4, 21.4, 52.9, 52.9, 52.9, 52.9, 52.9, 158.3, 158.3, 88.3, 160.7, 160.7],
    'Zimbabwe': [372.2, 558.2, 644.8, 602.1, 700.2, 674.6, 733.8, 868.6, 868.6, 868.6, 868.6, 868.6, 572.7, 572.7, 458.6, 474.8, 474.8],
    'Other Africa': [443.2, 430.5, 438.1, 449.4, 424.7, 452.9, 373.1, 371.1, 371.1, 371.1, 371.1, 371.1, 393.9, 393.9, 406.4, 385.6, 385.6],
    'Africa': [640.9, 625.2, 597.9, 610.7, 605, 620.5, 595.5, 589.4, 589.4, 589.4, 589.4, 589.4, 541.7, 541.7, 534.5, 551.2, 551.2],
    'Bangladesh': [573.4, 591.4, 569.6, 578.9, 582.2, 586.8, 567.4, 561.9, 561.9, 561.9, 561.9, 561.9, 543.7, 543.7, 579.4, 590.1, 590.1],
    'Brunei Darussalam': [792.9, 734, 720.6, 726.5, 620.2, 625.7, 566.6, 605.4, 605.4, 605.4, 605.4, 605.4, 891.2, 891.2, 795.1, 765.1, 765.1],
    'Cambodia': [818.5, 807.7, 796.1, 534.8, 379.3, 396.6, 569.1, 534, 534, 534, 534, 534, 493.7, 493.7, 397.3, 332.8, 332.8],
    'Chinese Taipei': [644.1, 633, 609, 590.9, 575.5, 581, 583.3, 587, 587, 587, 587, 587, 546, 546, 569, 552.4, 552.4],
    'India': [830, 805.5, 777.1, 853.6, 813.2, 835, 775.8, 725.8, 725.8, 725.8, 725.8, 725.8, 689.3, 689.3, 712.9, 731.6, 731.6],
    'Indonesia': [757.7, 722.6, 762, 719.9, 665.5, 741.2, 732.8, 729.1, 729.1, 729.1, 729.1, 729.1, 770.7, 770.7, 778.4, 786.8, 786.8],
    "Democratic People's Republic of Korea": [390.9, 352.2, 287.4, 290.2, 217.8, 254.5, 262.6, 242.8, 242.8, 242.8, 242.8, 242.8, 203.2, 203.2, 454.9, 458.4, 458.4],
    'Malaysia': [636.3, 769.1, 682.7, 681.2, 693.2, 665.7, 687.1, 654.9, 654.9, 654.9, 654.9, 654.9, 651, 651, 617.9, 628.6, 628.6],
    'Mongolia': [1096.9, 1158.5, 1169.2, 1199.6, 1345.3, 1311.2, 1232.9, 1194.6, 1194.6, 1194.6, 1194.6, 1194.6, 1089.7, 1089.7, 1078.6, 1094.5, 1094.5],
    'Myanmar': [201.3, 264.8, 192.3, 218.4, 214.8, 279.3, 304.4, 352.2, 352.2, 352.2, 352.2, 352.2, 413.4, 413.4, 442.3, 333.1, 333.1],
    'Nepal': [3.3, 1.1, 0, 3.9, 1.9, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'Pakistan': [461.3, 428.1, 412.8, 420.6, 418.5, 411.9, 396.7, 391.8, 391.8, 391.8, 391.8, 391.8, 394.5, 394.5, 368.6, 394.2, 394.2],
    'Philippines': [482.6, 488.8, 500.3, 510.2, 577, 603.9, 614.4, 606.7, 606.7, 606.7, 606.7, 606.7, 708.4, 708.4, 707.4, 695, 695],
    'Singapore': [477.7, 485.3, 487.9, 468.6, 455.6, 441, 396, 393.6, 393.6, 393.6, 393.6, 393.6, 384.1, 384.1, 382, 378.9, 378.9],
    'Sri Lanka': [408.2, 312.4, 441, 544, 336, 545.3, 513.7, 606.8, 606.8, 606.8, 606.8, 606.8, 605.7, 605.7, 503.3, 461.6, 461.6],
    'Thailand': [518.9, 518.3, 528.1, 506.1, 529.6, 535.4, 511.5, 477.2, 477.2, 477.2, 477.2, 477.2, 471.8, 471.8, 465.7, 481.2, 481.2],
    'Viet nam': [389.1, 437.3, 387, 352.6, 368.7, 383.1, 470.3, 448.6, 448.6, 448.6, 448.6, 448.6, 628.4, 628.4, 561.9, 508.1, 508.1],
    'Other Asia': [318.9, 318, 296.8, 298.2, 287.9, 311.7, 376.8, 657.6, 657.6, 657.6, 657.6, 657.6, 0, 0, 306.8, 0, 0],
    'Asia (UN)': [674.7, 663.8, 682.5, 684.8, 673.7, 654.6, 631.6, 614.5, 614.5, 614.5, 614.5, 614.5, 590.4, 590.4, 587, 579.7, 579.7],
    "People's Rep. Of China": [768.4, 749.3, 763.3, 739.2, 723.9, 678.2, 649.9, 626.7, 626.7, 626.7, 626.7, 626.7, 614.4, 614.4, 587, 588.7, 588.7],
    'Hong Kong, China': [776.7, 733.8, 780.1, 771.2, 782.4, 794.3, 735.3, 734.8, 734.8, 734.8, 734.8, 734.8, 639.1, 639.1, 638.4, 643.6, 643.6],
    'China': [768.4, 749.3, 763.3, 739.2, 723.9, 678.2, 649.9, 626.7, 626.7, 626.7, 626.7, 626.7, 614.4, 614.4, 609.4, 588.9, 588.9],
    'Argentina': [361.6, 363.5, 388.2, 401, 373.7, 376.6, 377.1, 376, 376, 376, 376, 376, 272.6, 272.6, 308.2, 310.6, 310.6],
    'Bolivia': [395.3, 431.7, 435.8, 428.6, 393.8, 423, 412, 483.3, 483.3, 483.3, 483.3, 483.3, 318.2, 318.2, 298.7, 293.2, 293.2],
    'Brazil': [64.9, 87.2, 68.7, 99.5, 135.2, 160.4, 156.6, 120, 120, 120, 120, 120, 93.1, 93.1, 133.9, 74.4, 74.4],
    'Colombia': [178.1, 180.7, 105.6, 123.8, 192.6, 218.5, 215.8, 220.2, 220.2, 220.2, 220.2, 220.2, 229.3, 229.3, 151.9, 147.8, 147.8],
    'Costa Rica': [40.1, 56.3, 64.4, 54.9, 80.5, 72.7, 6.6, 12, 12, 12, 12, 12, 1.8, 1.8, 0.4, 0.3, 0.3],
    'Cuba': [729, 861.5, 798.2, 779.9, 714.7, 788.1, 657, 543.2, 543.2, 543.2, 543.2, 543.2, 675.6, 675.6, 596.6, 657.4, 657.4],
    'Dominican Republic': [607.5, 599.6, 600.1, 559.1, 522.1, 583.3, 603.6, 598.5, 598.5, 598.5, 598.5, 598.5, 532.6, 532.6, 571, 629.6, 629.6],
    'Ecuador': [328.2, 413.7, 336.8, 313.5, 349.1, 352.8, 335.2, 279.5, 279.5, 279.5, 279.5, 279.5, 145.3, 145.3, 138.6, 168.3, 168.3],
    'El Salvador': [276.2, 222.6, 234.8, 237, 259.5, 264.5, 265.5, 262.6, 262.6, 262.6, 262.6, 262.6, 116.4, 116.4, 104, 111.2, 111.2],
    'Guatemala': [353.3, 288, 277.4, 291.1, 361.7, 313.4, 404.5, 407.7, 407.7, 407.7, 407.7, 407.7, 287.9, 287.9, 293.9, 142.9, 142.9],
    'Haiti': [361.5, 472.2, 403.5, 625.1, 629.6, 783.1, 910.9, 884, 884, 884, 884, 884, 815.2, 815.2, 817, 817, 817],
    'Honduras': [343.8, 337.1, 378.2, 372.3, 406, 386.5, 386.1, 385, 385, 385, 385, 385, 325.4, 325.4, 275.3, 286.1, 286.1],
    'Jamaica': [648.6, 659.8, 647.2, 694.9, 661.9, 615.4, 644.4, 656.8, 656.8, 656.8, 656.8, 656.8, 486.9, 486.9, 509.6, 522.7, 522.7],
    'Netherlands Antilles': [678.4, 679.7, 678.7, 550.5, 536, 517.4, 500.9, 510.4, 510.4, 510.4, 510.4, 510.4, 530.7, 530.7, 311.1, 606.3, 606.3],
    'Nicaragua': [511.1, 464.9, 475.8, 410.9, 337.9, 327.4, 358.3, 345.5, 345.5, 345.5, 345.5, 345.5, 224.7, 224.7, 226.8, 239.9, 239.9],
    'Panama': [350.9, 369.6, 395.3, 326.1, 325.1, 352, 313, 241.1, 241.1, 241.1, 241.1, 241.1, 329.7, 329.7, 290, 272.6, 272.6],
    'Paraguay': [0, 0, 0, 0, 0, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0, 0, 0, 0, 0],
    'Peru': [255.4, 292.3, 299.6, 286.9, 250.1, 253.1, 244.4, 263.9, 263.9, 263.9, 263.9, 263.9, 177.2, 177.2, 185.6, 211.6, 211.6],
    'Trinidad and Tobago': [713.1, 703.6, 706, 680, 651.6, 619.7, 584.1, 538.1, 538.1, 538.1, 538.1, 538.1, 526, 526, 546.7, 563.3, 563.3],
    'Uruguay': [255.5, 79.6, 197.9, 276.3, 128.5, 44.9, 53.9, 26.2, 26.2, 26.2, 26.2, 26.2, 39.3, 39.3, 89.8, 53.6, 53.6],
    'Venezuela': [208.9, 245.7, 223.4, 254, 247.7, 239, 296.2, 301.1, 301.1, 301.1, 301.1, 301.1, 95.8, 95.8, 147.3, 157.2, 157.2],
    'Other Non-OECD Americas': [247.2, 246.9, 288.4, 283, 356.6, 348.2, 343.6, 341.7, 341.7, 341.7, 341.7, 341.7, 608.2, 608.2, 613.6, 614.8, 614.8],
    'Non-OECD Americas': [178.7, 192.9, 181.7, 200.4, 216.3, 230.1, 233.6, 213, 213, 213, 213, 213, 156, 156, 187.3, 153.6, 153.6],
    'Bahrain': [788.7, 754.7, 754.5, 759, 760, 754.3, 717.8, 704.6, 704.6, 704.6, 704.6, 704.6, 698.7, 698.7, 698.6, 698, 698],
    'Islamic Republic of Iran': [582.8, 569, 581.8, 574.3, 582.3, 567.5, 551.2, 531.3, 531.3, 531.3, 531.3, 531.3, 491.9, 491.9, 482.1, 536.7, 536.7],
    'Iraq': [1212.4, 1094.7, 970.6, 1281.9, 1182.8, 1177, 1144.7, 1056.3, 1056.3, 1056.3, 1056.3, 1056.3, 663, 663, 663, 678.8, 678.8],
    'Jordan': [587.3, 579.6, 643.4, 641.8, 639.7, 656.2, 588.4, 496.7, 496.7, 496.7, 496.7, 496.7, 390.7, 390.7, 663, 376.8, 376.8],
    'Kuwait': [877.9, 764.4, 738.2, 609.3, 781.2, 633.1, 675.4, 620.7, 620.7, 620.7, 620.7, 620.7, 614.6, 614.6, 610.8, 546.3, 546.3],
    'Lebanon': [724.2, 716.1, 714.4, 814.1, 740.7, 713.5, 702.4, 706.5, 706.5, 706.5, 706.5, 706.5, 707, 707, 610.8, 451.8, 451.8],
    'Oman': [647.5, 638.8, 614.3, 602.2, 568.4, 548.9, 509.2, 471.1, 471.1, 471.1, 471.1, 471.1, 391.2, 391.2, 394.1, 370.5, 370.5],
    'Qatar': [509.7, 495.6, 492.3, 495.6, 496.7, 497.2, 486.4, 486.4, 486.4, 486.4, 486.4, 486.4, 484.9, 484.9, 394.1, 473.7, 473.7],
    'Saudi Arabia': [763.4, 742.8, 760.7, 744.3, 727.1, 711.2, 726.3, 713.6, 713.6, 713.6, 713.6, 713.6, 610.5, 610.5, 611.2, 620.8, 620.8],
    'Syrian Arab Republic': [634.3, 599, 602.6, 594.9, 562.1, 560, 628, 633.8, 633.8, 633.8, 633.8, 633.8, 669.5, 669.5, 664.6, 829.9, 829.9],
    'United Arab Emirates': [634.7, 601.1, 600.6, 641.2, 620.3, 607.4, 568.1, 660.8, 660.8, 660.8, 660.8, 660.8, 527.8, 527.8, 474.1, 418.9, 418.9],
    'Yemen': [828.8, 789.3, 853.3, 821.4, 747.7, 726.7, 665.1, 632.1, 632.1, 632.1, 632.1, 632.1, 647.5, 647.5, 632.4, 641, 641],
    'Middle East': [705.2, 678.3, 680.2, 683.2, 688.3, 670.1, 662.8, 655.2, 655.2, 655.2, 655.2, 655.2, 562.1, 562.1, 549.8, 562.1, 562.1],
}


def get_grid_ef(country: str, year: int) -> float | None:
    """g CO2/kWh for a country/region in a given year. None if unknown.
    Clamps to the nearest available year if the exact year is outside
    GRID_EF_YEARS (factors are republished periodically, not annually)."""
    vals = ELECTRICITY_GRID_EF.get(country)
    if not vals:
        return None
    yr = max(GRID_EF_YEARS[0], min(year, GRID_EF_YEARS[-1]))
    idx = GRID_EF_YEARS.index(yr)
    return vals[idx]


# ── Full electricity-by-country taxonomy, grouped into macro-regions ─────────
# Replaces the old hardcoded 31-country list. ~150 entries because this is the
# full IEA reference taxonomy (incl. regional rollups like "OECD Americas")
# so the grid-EF lookup always resolves regardless of where a company operates.
ELEC_COUNTRY_REGIONS: dict[str, list[str]] = {
    'Americas': ['Canada', 'Chile', 'Mexico', 'United States', 'OECD Americas'],
    'Asia-Pacific (OECD)': ['Australia', 'Israel', 'Japan', 'Korea', 'New Zealand', 'OECD Asia Oceania'],
    'Europe (OECD)': ['Austria', 'Belgium', 'Czech Republic', 'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece', 'Hungary', 'Iceland', 'Ireland', 'Italy', 'Luxembourg', 'Netherlands', 'Norway', 'Poland', 'Portugal', 'Slovak Republic', 'Slovenia', 'Spain', 'Sweden', 'Switzerland', 'Turkey', 'United Kingdom', 'OECD Europe', 'European Union - 27'],
    'Non-OECD Europe & Eurasia': ['Albania', 'Armenia', 'Azerbaijan', 'Belarus', 'Bosnia and Herzegovina', 'Bulgaria', 'Croatia', 'Cyprus', 'Georgia', 'Gibraltar', 'Kazakhstan', 'Kosovo', 'Kyrgyzstan', 'Latvia', 'Lithuania', 'FYR of Macedonia', 'Malta', 'Republic of Moldova', 'Montenegro', 'Romania', 'Russian Federation', 'Serbia', 'Tajikistan', 'Turkmenistan', 'Ukraine', 'Uzbekistan', 'Non-OECD Europe and Eurasia'],
    'Africa': ['Algeria', 'Angola', 'Benin', 'Botswana', 'Cameroon', 'Congo', 'Dem. Rep. Of Congo', "Côte d'Ivoire", 'Egypt', 'Eritrea', 'Ethiopia', 'Gabon', 'Ghana', 'Kenya', 'Libya', 'Morocco', 'Mozambique', 'Namibia', 'Nigeria', 'Senegal', 'South Africa', 'Sudan', 'United Rep. Of Tanzania', 'Togo', 'Tunisia', 'Zambia', 'Zimbabwe', 'Other Africa', 'Africa'],
    'Non-OECD Asia': ['Bangladesh', 'Brunei Darussalam', 'Cambodia', 'Chinese Taipei', 'India', 'Indonesia', 'DPR of Korea', 'Malaysia', 'Mongolia', 'Myanmar', 'Nepal', 'Pakistan', 'Philippines', 'Singapore', 'Sri Lanka', 'Thailand', 'Vietnam', 'Other Asia', 'Asia'],
    'Non-OECD Americas': ["People's Rep. Of China", 'Hong Kong, China', 'China', 'Argentina', 'Bolivia', 'Brazil', 'Colombia', 'Costa Rica', 'Cuba', 'Dominican Republic', 'Ecuador', 'El Salvador', 'Guatemala', 'Haiti', 'Honduras', 'Jamaica', 'Netherlands Antilles', 'Nicaragua', 'Panama', 'Paraguay', 'Peru', 'Trinidad and Tobago', 'Uruguay', 'Venezuela', 'Other Non-OECD Americas', 'Non-OECD Americas'],
    'Middle East': ['Bahrain', 'Islamic Republic of Iran', 'Iraq', 'Jordan', 'Kuwait', 'Lebanon', 'Oman', 'Qatar', 'Saudi Arabia', 'Syrian Arab Republic', 'United Arab Emirates', 'Yemen', 'Middle East'],
}

ELEC_ALL_COUNTRIES: list[str] = [c for _countries in ELEC_COUNTRY_REGIONS.values() for c in _countries]

def _elec_col(country: str) -> str:
    """Canonical master CSV column name for a country's electricity (GJ)."""
    safe = (country.replace(" ", "_").replace(",", "").replace("'", "")
                   .replace("(", "").replace(")", "").replace(".", ""))
    return "Elec_" + safe + "_GJ"

ELEC_COUNTRY_COLS: dict[str, str] = {c: _elec_col(c) for c in ELEC_ALL_COUNTRIES}