"""
scripts/generate_dummy_companies.py — TIP ESG Platform · Synthetic Test Data
==============================================================================
Generates 7 fictional companies (Apex Tire Co, Meridian Rubber Group,
NorthStar Tyres, Summit Polymer Industries, TerraGrip Industries, Velocity
Rubber Corp, Pinnacle Elastomers — none are real tire manufacturers, picked
deliberately to avoid resembling Bridgestone/Goodyear/Michelin/Continental/
Pirelli/etc.) to bring the long-form master up to 10 companies total.

Unlike the 3 real companies, these are entirely synthetic: smooth random-walk
trends per KPI (2009-2025), each assigned a DIFFERENT reporting unit per
category (deliberately covering unit choices the 3 real companies didn't
use — TJ, kWh HHV, Decatherm, kL, tire/year, 10^6 L — for the widest possible
conversion-path test coverage). All energy/CO2/waste-derived figures are run
through formula_engine.calculate() so the synthetic data is internally
consistent (Total Energy really does equal the sum of its parts, CO2 really
does use the right emission factor per fuel sub-type, etc.) rather than being
independently-invented numbers that happen to share a row.

Run from the project root:
    python scripts/generate_dummy_companies.py
Appends to data_storage/master/ESG_LONG_FORM_MASTER.csv (3 real + 7 dummy = 10).
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import field_registry as fr
import conversion_data as cd
from formula_engine import TemplateInputs, calculate

YEARS = list(range(2009, 2026))
RNG = np.random.default_rng(42)  # reproducible

COMPANIES = [
    # name, scale (production base, metric T/yr), countries with operations
    ("Apex Tire Co",            1_400_000, ["United States", "Mexico", "Canada"]),
    ("Meridian Rubber Group",   2_100_000, ["Germany", "France", "Poland", "Spain"]),
    ("NorthStar Tyres",           950_000, ["Sweden", "Norway", "Finland"]),
    ("Summit Polymer Industries",1_800_000,["China", "India", "Thailand", "Vietnam"]),
    ("TerraGrip Industries",    1_250_000, ["Brazil", "Argentina", "Mexico"]),
    ("Velocity Rubber Corp",    2_600_000, ["United States", "Canada", "Japan"]),
    ("Pinnacle Elastomers",       780_000, ["South Africa", "Egypt", "Morocco"]),
]

# Each company reports in a different unit per category — deliberately
# including units the 3 real companies (Bridgestone/Goodyear/Michelin)
# didn't already exercise, for the widest conversion-path test coverage.
COMPANY_UNIT_PLANS = [
    {  # Apex Tire Co
        "Production": "lb", "Water intake": "10^6 L",
        "Renewable Electricity Purchased": "TJ", "Non-Renewable Electricity Purchased": "TJ",
        "Self-generated AND consumed electricity on-site": "TJ",
        "Purchased Steam": "TJ", "Sold Electricity": "TJ", "Sold Steam": "TJ",
        "Natural gas": "Decatherm LHV", "Coal": "kWh HHV", "Propane": "kL",
        "Fuel Oil": "kL", "Diesel": "kL", "Petrol": "kL",
        "Biomass": "TJ LHV", "Waste tires": "tire/year", "LPG": "kL", "Other": "TJ LHV",
        "Total amount of waste": "metric T", "Amount of waste sent to recovery": "metric T",
    },
    {  # Meridian Rubber Group
        "Production": "metric T", "Water intake": "m3",
        "Renewable Electricity Purchased": "kWh", "Non-Renewable Electricity Purchased": "kWh",
        "Self-generated AND consumed electricity on-site": "kWh",
        "Purchased Steam": "kWh", "Sold Electricity": "kWh", "Sold Steam": "kWh",
        "Natural gas": "kWh HHV", "Coal": "metric T", "Propane": "GJ LHV",
        "Fuel Oil": "GJ LHV", "Diesel": "GJ LHV", "Petrol": "GJ LHV",
        "Biomass": "GJ HHV", "Waste tires": "metric T", "LPG": "GJ LHV", "Other": "GJ LHV",
        "Total amount of waste": "kg", "Amount of waste sent to recovery": "kg",
    },
    {  # NorthStar Tyres
        "Production": "short (US) T", "Water intake": "gal US",
        "Renewable Electricity Purchased": "BTU", "Non-Renewable Electricity Purchased": "BTU",
        "Self-generated AND consumed electricity on-site": "BTU",
        "Purchased Steam": "BTU", "Sold Electricity": "BTU", "Sold Steam": "BTU",
        "Natural gas": "BTU LHV", "Coal": "BTU HHV", "Propane": "BTU LHV",
        "Fuel Oil": "BTU LHV", "Diesel": "BTU LHV", "Petrol": "BTU LHV",
        "Biomass": "BTU HHV", "Waste tires": "BTU LHV", "LPG": "BTU LHV", "Other": "BTU LHV",
        "Total amount of waste": "lb", "Amount of waste sent to recovery": "lb",
    },
    {  # Summit Polymer Industries
        "Production": "metric T", "Water intake": "L",
        "Renewable Electricity Purchased": "MWh", "Non-Renewable Electricity Purchased": "MWh",
        "Self-generated AND consumed electricity on-site": "MWh",
        "Purchased Steam": "MWh", "Sold Electricity": "MWh", "Sold Steam": "MWh",
        "Natural gas": "GJ LHV", "Coal": "GJ LHV", "Propane": "GJ LHV",
        "Fuel Oil": "GJ LHV", "Diesel": "GJ LHV", "Petrol": "GJ LHV",
        "Biomass": "GJ LHV", "Waste tires": "GJ LHV", "LPG": "GJ LHV", "Other": "GJ LHV",
        "Total amount of waste": "metric T", "Amount of waste sent to recovery": "metric T",
    },
    {  # TerraGrip Industries
        "Production": "kg", "Water intake": "m3",
        "Renewable Electricity Purchased": "GJ", "Non-Renewable Electricity Purchased": "GJ",
        "Self-generated AND consumed electricity on-site": "GJ",
        "Purchased Steam": "GJ", "Sold Electricity": "GJ", "Sold Steam": "GJ",
        "Natural gas": "MWh HHV", "Coal": "MWh HHV", "Propane": "MWh HHV",
        "Fuel Oil": "MWh HHV", "Diesel": "MWh HHV", "Petrol": "MWh HHV",
        "Biomass": "MWh HHV", "Waste tires": "short (US) T", "LPG": "MWh HHV", "Other": "MWh HHV",
        "Total amount of waste": "kg", "Amount of waste sent to recovery": "kg",
    },
    {  # Velocity Rubber Corp
        "Production": "metric T", "Water intake": "m3",
        "Renewable Electricity Purchased": "GJ", "Non-Renewable Electricity Purchased": "GJ",
        "Self-generated AND consumed electricity on-site": "GJ",
        "Purchased Steam": "GJ", "Sold Electricity": "GJ", "Sold Steam": "GJ",
        "Natural gas": "TJ LHV", "Coal": "TJ HHV", "Propane": "TJ LHV",
        "Fuel Oil": "TJ LHV", "Diesel": "TJ LHV", "Petrol": "TJ LHV",
        "Biomass": "TJ LHV", "Waste tires": "kg", "LPG": "TJ LHV", "Other": "TJ LHV",
        "Total amount of waste": "metric T", "Amount of waste sent to recovery": "metric T",
    },
    {  # Pinnacle Elastomers
        "Production": "tire/year", "Water intake": "m3",
        "Renewable Electricity Purchased": "kWh", "Non-Renewable Electricity Purchased": "kWh",
        "Self-generated AND consumed electricity on-site": "kWh",
        "Purchased Steam": "kWh", "Sold Electricity": "kWh", "Sold Steam": "kWh",
        "Natural gas": "GJ HHV", "Coal": "GJ HHV", "Propane": "GJ HHV",
        "Fuel Oil": "GJ HHV", "Diesel": "GJ HHV", "Petrol": "GJ HHV",
        "Biomass": "GJ HHV", "Waste tires": "lb", "LPG": "GJ HHV", "Other": "GJ HHV",
        "Total amount of waste": "lb", "Amount of waste sent to recovery": "lb",
    },
]


def smooth_walk(base: float, n: int, pct_noise: float = 0.06, drift: float = 0.01) -> np.ndarray:
    """A plausible-looking multi-year trend: small drift + random walk, never negative."""
    vals = [base]
    for _ in range(n - 1):
        vals.append(max(0.0, vals[-1] * (1 + drift + RNG.normal(0, pct_noise))))
    return np.array(vals)


def generate_company_long_rows(name: str, base_production: float, countries: list[str]) -> list[dict]:
    n = len(YEARS)
    production   = smooth_walk(base_production, n)
    total_sites  = np.round(smooth_walk(base_production / 60_000, n, 0.02, 0.0)).clip(min=3)
    iso_sites    = np.round(total_sites * RNG.uniform(0.7, 0.95)).clip(max=total_sites)
    water        = production * RNG.uniform(7, 12) * smooth_walk(1.0, n, 0.05, -0.002)

    renew_elec    = production * RNG.uniform(0.3, 1.0) * smooth_walk(1.0, n, 0.08, 0.02)
    nonrenew_elec = production * RNG.uniform(2.0, 4.0) * smooth_walk(1.0, n, 0.05, -0.01)
    self_gen      = production * RNG.uniform(0.0, 0.3) * smooth_walk(1.0, n, 0.1, 0.0)
    purch_steam   = production * RNG.uniform(0.1, 0.6) * smooth_walk(1.0, n, 0.06, 0.0)
    sold_elec     = production * RNG.uniform(0.0, 0.05) * smooth_walk(1.0, n, 0.1, 0.0)
    sold_steam    = np.zeros(n)

    nat_gas   = production * RNG.uniform(1.5, 3.0) * smooth_walk(1.0, n, 0.05, -0.005)
    coal_sb   = production * RNG.uniform(0.0, 0.4) * smooth_walk(1.0, n, 0.08, -0.02)
    coal_bb   = production * RNG.uniform(0.0, 0.2) * smooth_walk(1.0, n, 0.08, -0.02)
    coal_ob   = production * RNG.uniform(0.0, 0.15) * smooth_walk(1.0, n, 0.08, -0.02)
    propane   = production * RNG.uniform(0.05, 0.3) * smooth_walk(1.0, n, 0.07, 0.0)
    fo_a      = production * RNG.uniform(0.1, 0.5) * smooth_walk(1.0, n, 0.07, -0.01)
    fo_c      = production * RNG.uniform(0.05, 0.3) * smooth_walk(1.0, n, 0.07, -0.01)
    diesel    = production * RNG.uniform(0.1, 0.4) * smooth_walk(1.0, n, 0.06, 0.0)
    petrol    = production * RNG.uniform(0.01, 0.1) * smooth_walk(1.0, n, 0.06, 0.0)
    biomass   = production * RNG.uniform(0.0, 0.2) * smooth_walk(1.0, n, 0.1, 0.03)
    waste_tires_mt = production * RNG.uniform(0.005, 0.03) * smooth_walk(1.0, n, 0.1, 0.0)
    lpg       = production * RNG.uniform(0.02, 0.15) * smooth_walk(1.0, n, 0.07, 0.0)
    other     = production * RNG.uniform(0.0, 0.1) * smooth_walk(1.0, n, 0.1, 0.0)

    waste_total    = production * RNG.uniform(0.08, 0.18) * smooth_walk(1.0, n, 0.06, -0.01)
    waste_recovery = waste_total * RNG.uniform(0.55, 0.85)

    total_employees  = np.round(total_sites * RNG.uniform(150, 500))
    female_employees = np.round(total_employees * RNG.uniform(0.18, 0.42))
    board_total      = RNG.integers(7, 15)
    female_board     = RNG.integers(1, max(2, int(board_total * 0.4)))
    sbt_total        = total_sites
    sbt_validated     = np.round(sbt_total * RNG.uniform(0.3, 0.8))
    sbt_committed     = np.round((sbt_total - sbt_validated) * RNG.uniform(0.3, 0.7))

    rows = []
    for i, yr in enumerate(YEARS):
        inp = TemplateInputs(
            company=name, year=yr, production=production[i],
            water_withdrawals=water[i],
            renew_elec_purchased=renew_elec[i], nonrenew_elec_purchased=nonrenew_elec[i],
            self_gen_elec=self_gen[i], purchased_steam=purch_steam[i],
            sold_electricity=sold_elec[i], sold_steam=sold_steam[i],
            nat_gas=nat_gas[i],
            coal_sub_bituminous=coal_sb[i], coal_brown_briquettes=coal_bb[i],
            coal_other_bituminous=coal_ob[i],
            propane=propane[i], fuel_oil_heavy_a=fo_a[i], fuel_oil_heavy_c=fo_c[i],
            diesel=diesel[i], petrol=petrol[i], biomass=biomass[i],
            waste_tires_mt=waste_tires_mt[i], lpg=lpg[i], other_fuels=other[i],
            waste_total=waste_total[i], waste_recovery=waste_recovery[i],
        )
        out = calculate(inp)

        def add(kpi_name, value):
            rows.append({"Company": name, "Year": yr, "KPI_Name": kpi_name, "Value": value})

        add("Total no. of sites", total_sites[i])
        add("ISO 14001 sites", iso_sites[i])
        add("% certified sites", out.pct_certified)
        add("Production", production[i])
        add("Water intake", water[i])
        add("Water intake - KPI", out.water_kpi)
        add("Total Purchased Electricity", out.total_electricity)
        add("Renewable Electricity Purchased", renew_elec[i])
        add("Non-Renewable Electricity Purchased", nonrenew_elec[i])
        add("Self-generated AND consumed electricity on-site", self_gen[i])
        add("Purchased Steam", purch_steam[i])
        add("Sold Electricity", sold_elec[i])
        add("Sold Steam", sold_steam[i])
        add("Energy - Natural Gas", nat_gas[i])
        add("Energy - Sub bituminous coal", coal_sb[i])
        add("Energy - Brown coal briquettes", coal_bb[i])
        add("Energy - Other bituminous coal", coal_ob[i])
        add("Energy - Total Coal", out.total_coal)
        add("Energy - Propane", propane[i])
        add("Energy - Fuel Oil Heavy A", fo_a[i])
        add("Energy - Fuel Oil Heavy C", fo_c[i])
        add("Energy - Fuel Oil", out.total_fuel_oil)
        add("Energy - Diesel", diesel[i])
        add("Energy - Petrol", petrol[i])
        add("Energy - Biomass", biomass[i])
        add("Energy - Waste tires", waste_tires_mt[i])
        add("Energy - LPG", lpg[i])
        add("Energy - Other", other[i])
        add("Total energy", out.total_energy)
        add("Total energy - KPI", out.energy_kpi)
        add("CO2 - Natural Gas", out.co2_nat_gas)
        add("CO2 - Sub bituminous coal", out.co2_coal_sub_bituminous)
        add("CO2 - Brown coal briquettes", out.co2_coal_brown_briquettes)
        add("CO2 - Other bituminous coal", out.co2_coal_other_bituminous)
        add("CO2 - Coal", out.co2_coal)
        add("CO2 - Propane", out.co2_propane)
        add("CO2 - Fuel Oil Heavy A", out.co2_fuel_oil_heavy_a)
        add("CO2 - Fuel Oil Heavy C", out.co2_fuel_oil_heavy_c)
        add("CO2 - Fuel Oil", out.co2_fuel_oil)
        add("CO2 - Diesel", out.co2_diesel)
        add("CO2 - Petrol", out.co2_petrol)
        add("CO2 - Biomass", out.co2_biomass)
        add("CO2 - Waste Tires", out.co2_waste_tires)
        add("CO2 - LPG", out.co2_lpg)
        add("CO2 - Other", out.co2_other)
        add("Total CO2 - Scope 1", out.total_co2_scope1)
        add("Total CO2 - Scope 2", out.total_co2_scope2)
        add("Total CO2", out.total_co2)
        add("Total CO2 - KPI", out.co2_kpi)

        # Electricity by country — split nonrenew_elec across this company's
        # countries of operation (the rest of the ~150-entry taxonomy stays 0,
        # same sparse pattern as the real companies).
        shares = RNG.dirichlet(np.ones(len(countries)))
        for c, share in zip(countries, shares):
            add(f"Corporate units - {c}", nonrenew_elec[i] * share)

        add("Waste Production", production[i])
        add("Total amount of Waste", waste_total[i])
        add("Amount of waste sent to recovery", waste_recovery[i])
        add("Amount of waste sent to elimination", out.waste_elimination)
        add("Waste recovery %", out.waste_recovery_pct)
        add("Waste elimination %", 1 - out.waste_recovery_pct)
        add("Waste Intensity - KPI", waste_total[i] / production[i] if production[i] else 0)

        add("HS External Audit Sites", np.round(total_sites[i] * RNG.uniform(0.5, 0.9)))
        add("HS Internal Audit Sites", total_sites[i])
        add("HS External Audit %", RNG.uniform(0.5, 0.9))
        add("HS Internal Audit %", 1.0)
        add("Total Employees", total_employees[i])
        add("Female Employees", female_employees[i])
        add("Female Employees %", female_employees[i] / total_employees[i] if total_employees[i] else 0)
        add("Board Total", board_total)
        add("Female Board", female_board)
        add("Female Board %", female_board / board_total if board_total else 0)
        add("SBT Total", sbt_total[i])
        add("SBT Validated", sbt_validated[i])
        add("SBT Committed", sbt_committed[i])
        add("SBT Non-Committed", max(0, sbt_total[i] - sbt_validated[i] - sbt_committed[i]))

    return rows


def apply_units(rows: list[dict], unit_plan: dict) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["Unit"] = None
    df["GroundTruthCommonValue"] = None
    for idx, row in df.iterrows():
        uf = fr.BY_KPI_NAME.get(row["KPI_Name"])
        if uf is None:
            continue
        unit = unit_plan.get(uf.subsection)
        if not unit or pd.isna(row["Value"]):
            continue
        cf = cd.get_unit_conversion_factor(uf.subsection, unit)
        if not cf:
            continue
        common_value = float(row["Value"])
        df.at[idx, "Value"] = common_value / cf
        df.at[idx, "Unit"] = unit
        df.at[idx, "GroundTruthCommonValue"] = common_value
    return df


def main():
    all_rows = []
    for (name, base_prod, countries), unit_plan in zip(COMPANIES, COMPANY_UNIT_PLANS):
        print(f"Generating {name} ({len(countries)} countries, base production {base_prod:,})...")
        rows = generate_company_long_rows(name, base_prod, countries)
        df = apply_units(rows, unit_plan)
        all_rows.append(df)

    new_long = pd.concat(all_rows, ignore_index=True)
    print(f"\nGenerated {len(new_long)} rows for {len(COMPANIES)} dummy companies "
          f"({len(new_long) // len(YEARS)} fields/company/year)")

    existing_path = Path("data_storage/master/ESG_LONG_FORM_MASTER.csv")
    existing = pd.read_csv(existing_path)
    combined = pd.concat([existing, new_long], ignore_index=True)
    combined.to_csv(existing_path, index=False)
    print(f"Appended to {existing_path} — now {combined['Company'].nunique()} companies total:")
    print(" ", ", ".join(sorted(combined["Company"].unique())))


if __name__ == "__main__":
    main()