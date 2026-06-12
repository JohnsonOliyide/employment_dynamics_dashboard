
import csv
import json
import time
import datetime as dt
from pathlib import Path
import requests


BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
OUT_DIR = Path("data")
OUT_DIR.mkdir(exist_ok=True)

START_YEAR = "2015"
END_YEAR = str(dt.date.today().year)

NATIONAL_SERIES = {
    "Total nonfarm": "CES0000000001",
    "Construction": "CES2000000001",
    "Manufacturing": "CES3000000001",
    "Wholesale trade": "CES4142000001",
    "Retail trade": "CES4200000001",
    "Transportation and warehousing": "CES4300000001",
    "Information": "CES5000000001",
    "Financial activities": "CES5500000001",
    "Professional and business services": "CES6000000001",
    "Education and health services": "CES6500000001",
    "Leisure and hospitality": "CES7000000001",
    "Other services": "CES8000000001",
    "Government": "CES9000000001",
}

STATES = {
    "Alabama": "SMS01000000000000001",
    "Alaska": "SMS02000000000000001",
    "Arizona": "SMS04000000000000001",
    "Arkansas": "SMS05000000000000001",
    "California": "SMS06000000000000001",
    "Colorado": "SMS08000000000000001",
    "Connecticut": "SMS09000000000000001",
    "Delaware": "SMS10000000000000001",
    "District of Columbia": "SMS11000000000000001",
    "Florida": "SMS12000000000000001",
    "Georgia": "SMS13000000000000001",
    "Hawaii": "SMS15000000000000001",
    "Idaho": "SMS16000000000000001",
    "Illinois": "SMS17000000000000001",
    "Indiana": "SMS18000000000000001",
    "Iowa": "SMS19000000000000001",
    "Kansas": "SMS20000000000000001",
    "Kentucky": "SMS21000000000000001",
    "Louisiana": "SMS22000000000000001",
    "Maine": "SMS23000000000000001",
    "Maryland": "SMS24000000000000001",
    "Massachusetts": "SMS25000000000000001",
    "Michigan": "SMS26000000000000001",
    "Minnesota": "SMS27000000000000001",
    "Mississippi": "SMS28000000000000001",
    "Missouri": "SMS29000000000000001",
    "Montana": "SMS30000000000000001",
    "Nebraska": "SMS31000000000000001",
    "Nevada": "SMS32000000000000001",
    "New Hampshire": "SMS33000000000000001",
    "New Jersey": "SMS34000000000000001",
    "New Mexico": "SMS35000000000000001",
    "New York": "SMS36000000000000001",
    "North Carolina": "SMS37000000000000001",
    "North Dakota": "SMS38000000000000001",
    "Ohio": "SMS39000000000000001",
    "Oklahoma": "SMS40000000000000001",
    "Oregon": "SMS41000000000000001",
    "Pennsylvania": "SMS42000000000000001",
    "Rhode Island": "SMS44000000000000001",
    "South Carolina": "SMS45000000000000001",
    "South Dakota": "SMS46000000000000001",
    "Tennessee": "SMS47000000000000001",
    "Texas": "SMS48000000000000001",
    "Utah": "SMS49000000000000001",
    "Vermont": "SMS50000000000000001",
    "Virginia": "SMS51000000000000001",
    "Washington": "SMS53000000000000001",
    "West Virginia": "SMS54000000000000001",
    "Wisconsin": "SMS55000000000000001",
    "Wyoming": "SMS56000000000000001",
}

STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME",
    "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


def fetch_bls(series_dict):
    series_ids = list(series_dict.values())
    payload = {
        "seriesid": series_ids,
        "startyear": START_YEAR,
        "endyear": END_YEAR,
    }

    print(f"Requesting {len(series_ids)} BLS series...")

    response = requests.post(
        BLS_API_URL,
        data=json.dumps(payload),
        headers={"Content-type": "application/json"},
        timeout=120,
    )
    response.raise_for_status()

    data = response.json()

    if data.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(data)

    out = {}

    reverse = {v: k for k, v in series_dict.items()}

    for series in data["Results"]["series"]:
        name = reverse[series["seriesID"]]
        rows = []

        for item in series["data"]:
            period = item["period"]

            if not period.startswith("M") or period == "M13":
                continue

            year = int(item["year"])
            month = int(period[1:])
            date = f"{year}-{month:02d}-01"
            value = float(item["value"])

            rows.append((date, value))

        out[name] = dict(sorted(rows))

    return out


def pct_change(current, previous):
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100


def write_industry_data(industry_data):
    total = industry_data["Total nonfarm"]
    dates = sorted(total.keys())

    rows = []

    for i, date in enumerate(dates):
        total_emp = total[date]
        total_prev = total[dates[i - 1]] if i >= 1 else None
        total_yoy = total[dates[i - 12]] if i >= 12 else None

        total_mom_change = total_emp - total_prev if total_prev is not None else None
        total_yoy_change = total_emp - total_yoy if total_yoy is not None else None

        for sector, values in industry_data.items():
            if sector == "Total nonfarm":
                continue

            emp = values.get(date)
            prev = values.get(dates[i - 1]) if i >= 1 else None
            yoy = values.get(dates[i - 12]) if i >= 12 else None

            mom_change = emp - prev if emp is not None and prev is not None else None
            yoy_change = emp - yoy if emp is not None and yoy is not None else None

            rows.append({
                "date": date,
                "sector": sector,
                "employment_thousands": emp,
                "total_nonfarm_thousands": total_emp,
                "mom_change_thousands": mom_change,
                "yoy_change_thousands": yoy_change,
                "mom_contribution_pct": None if not total_mom_change else (mom_change / total_mom_change) * 100,
                "yoy_contribution_pct": None if not total_yoy_change else (yoy_change / total_yoy_change) * 100,
                "share_pct": None if not total_emp else (emp / total_emp) * 100,
            })

    write_csv(
        OUT_DIR / "industry_employment.csv",
        rows,
        [
            "date",
            "sector",
            "employment_thousands",
            "total_nonfarm_thousands",
            "mom_change_thousands",
            "yoy_change_thousands",
            "mom_contribution_pct",
            "yoy_contribution_pct",
            "share_pct",
        ],
    )


def write_state_data(state_data, national_data):
    total = national_data["Total nonfarm"]
    dates = sorted(total.keys())

    rows = []

    for state_name, values in state_data.items():
        for i, date in enumerate(dates):
            emp = values.get(date)
            prev = values.get(dates[i - 1]) if i >= 1 else None
            yoy = values.get(dates[i - 12]) if i >= 12 else None
            us_emp = total.get(date)

            rows.append({
                "date": date,
                "state": state_name,
                "abbr": STATE_ABBR[state_name],
                "employment_thousands": emp,
                "mom_change_thousands": None if emp is None or prev is None else emp - prev,
                "yoy_change_thousands": None if emp is None or yoy is None else emp - yoy,
                "mom_growth_pct": pct_change(emp, prev),
                "yoy_growth_pct": pct_change(emp, yoy),
                "share_us_pct": None if not us_emp or emp is None else (emp / us_emp) * 100,
            })

    write_csv(
        OUT_DIR / "state_employment.csv",
        rows,
        [
            "date",
            "state",
            "abbr",
            "employment_thousands",
            "mom_change_thousands",
            "yoy_change_thousands",
            "mom_growth_pct",
            "yoy_growth_pct",
            "share_us_pct",
        ],
    )


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            clean = {}

            for key in fieldnames:
                value = row.get(key)

                if isinstance(value, float):
                    clean[key] = f"{value:.6f}"
                elif value is None:
                    clean[key] = ""
                else:
                    clean[key] = value

            writer.writerow(clean)

    print(f"Wrote {path}")


def main():
    print("Starting employment dynamics data update...")

    print("Downloading national industry data...")
    industry_data = fetch_bls(NATIONAL_SERIES)

    print("Downloading state employment data...")
    state_data = fetch_bls(STATES)

    print("Writing industry CSV...")
    write_industry_data(industry_data)

    print("Writing state CSV...")
    write_state_data(state_data, industry_data)

    print("Done.")


if __name__ == "__main__":
    main()
