import csv
import datetime as dt
import json
import os
import time
from pathlib import Path

import requests

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
OUT_DIR = Path("data")
OUT_DIR.mkdir(exist_ok=True)

CURRENT_YEAR = dt.date.today().year
START_YEAR = int(os.environ.get("START_YEAR", "2015"))
END_YEAR = int(os.environ.get("END_YEAR", str(CURRENT_YEAR)))
BLS_API_KEY = os.environ.get("BLS_API_KEY")

NATIONAL_SERIES = {
    "Total nonfarm": "CES0000000001",
    "Mining and logging": "CES1000000001",
    "Construction": "CES2000000001",
    "Manufacturing": "CES3000000001",
    "Wholesale trade": "CES4142000001",
    "Retail trade": "CES4200000001",
    "Transportation and warehousing": "CES4300000001",
    "Utilities": "CES4422000001",
    "Information": "CES5000000001",
    "Financial activities": "CES5500000001",
    "Professional and business services": "CES6000000001",
    "Education and health services": "CES6500000001",
    "Leisure and hospitality": "CES7000000001",
    "Other services": "CES8000000001",
    "Government": "CES9000000001",
}

STATES = [
    ("01", "Alabama", "AL"), ("02", "Alaska", "AK"), ("04", "Arizona", "AZ"),
    ("05", "Arkansas", "AR"), ("06", "California", "CA"), ("08", "Colorado", "CO"),
    ("09", "Connecticut", "CT"), ("10", "Delaware", "DE"), ("11", "District of Columbia", "DC"),
    ("12", "Florida", "FL"), ("13", "Georgia", "GA"), ("15", "Hawaii", "HI"),
    ("16", "Idaho", "ID"), ("17", "Illinois", "IL"), ("18", "Indiana", "IN"),
    ("19", "Iowa", "IA"), ("20", "Kansas", "KS"), ("21", "Kentucky", "KY"),
    ("22", "Louisiana", "LA"), ("23", "Maine", "ME"), ("24", "Maryland", "MD"),
    ("25", "Massachusetts", "MA"), ("26", "Michigan", "MI"), ("27", "Minnesota", "MN"),
    ("28", "Mississippi", "MS"), ("29", "Missouri", "MO"), ("30", "Montana", "MT"),
    ("31", "Nebraska", "NE"), ("32", "Nevada", "NV"), ("33", "New Hampshire", "NH"),
    ("34", "New Jersey", "NJ"), ("35", "New Mexico", "NM"), ("36", "New York", "NY"),
    ("37", "North Carolina", "NC"), ("38", "North Dakota", "ND"), ("39", "Ohio", "OH"),
    ("40", "Oklahoma", "OK"), ("41", "Oregon", "OR"), ("42", "Pennsylvania", "PA"),
    ("44", "Rhode Island", "RI"), ("45", "South Carolina", "SC"), ("46", "South Dakota", "SD"),
    ("47", "Tennessee", "TN"), ("48", "Texas", "TX"), ("49", "Utah", "UT"),
    ("50", "Vermont", "VT"), ("51", "Virginia", "VA"), ("53", "Washington", "WA"),
    ("54", "West Virginia", "WV"), ("55", "Wisconsin", "WI"), ("56", "Wyoming", "WY"),
]
STATE_SERIES = {name: {"series_id": f"SMS{fips}000000000000001", "fips": fips, "abbr": abbr} for fips, name, abbr in STATES}

def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]

def fetch_bls_series(series_ids, start_year, end_year, max_retries=3):
    all_results = {}
    for batch in chunked(series_ids, 25):
        payload = {"seriesid": batch, "startyear": str(start_year), "endyear": str(end_year)}
        if BLS_API_KEY:
            payload["registrationkey"] = BLS_API_KEY
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                print(f"Requesting {len(batch)} BLS series, attempt {attempt}...")
                response = requests.post(
                    BLS_API_URL,
                    data=json.dumps(payload),
                    headers={"Content-type": "application/json"},
                    timeout=60,
                )
                response.raise_for_status()
                parsed = response.json()
                if parsed.get("status") != "REQUEST_SUCCEEDED":
                    raise RuntimeError(f"BLS request failed: {parsed}")
                for item in parsed.get("Results", {}).get("series", []):
                    sid = item["seriesID"]
                    obs = []
                    for row in item.get("data", []):
                        period = row.get("period")
                        if not period or not period.startswith("M") or period == "M13":
                            continue
                        date = f'{int(row["year"])}-{int(period[1:]):02d}-01'
                        obs.append((date, float(row["value"])))
                    all_results[sid] = sorted(obs)
                break
            except Exception as e:
                last_error = e
                print(f"Attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    time.sleep(5)
        missing = [sid for sid in batch if sid not in all_results]
        if missing:
            raise RuntimeError(f"Could not retrieve series {missing}") from last_error
    return all_results

def series_to_dict(obs):
    return {date: value for date, value in obs}

def pct_change(current, previous):
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / previous * 100

def write_rows(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            clean = {}
            for k in fieldnames:
                v = row.get(k)
                if isinstance(v, float):
                    clean[k] = f"{v:.6f}"
                elif v is None:
                    clean[k] = ""
                else:
                    clean[k] = v
            writer.writerow(clean)

def write_industry_csv(results):
    total_sid = NATIONAL_SERIES["Total nonfarm"]
    total = series_to_dict(results[total_sid])
    all_dates = sorted(total.keys())
    sector_maps = {sector: series_to_dict(results[sid]) for sector, sid in NATIONAL_SERIES.items() if sector != "Total nonfarm"}
    rows = []
    for idx, date in enumerate(all_dates):
        total_emp = total.get(date)
        total_prev = total.get(all_dates[idx - 1]) if idx >= 1 else None
        total_yoy = total.get(all_dates[idx - 12]) if idx >= 12 else None
        total_mom_change = None if total_prev is None else total_emp - total_prev
        total_yoy_change = None if total_yoy is None else total_emp - total_yoy
        included_emp_sum = included_mom_sum = included_yoy_sum = 0.0
        for sector, smap in sector_maps.items():
            emp = smap.get(date)
            prev = smap.get(all_dates[idx - 1]) if idx >= 1 else None
            yoy = smap.get(all_dates[idx - 12]) if idx >= 12 else None
            mom_change = None if emp is None or prev is None else emp - prev
            yoy_change = None if emp is None or yoy is None else emp - yoy
            if emp is not None: included_emp_sum += emp
            if mom_change is not None: included_mom_sum += mom_change
            if yoy_change is not None: included_yoy_sum += yoy_change
            rows.append({
                "date": date, "sector": sector, "employment_thousands": emp,
                "total_nonfarm_thousands": total_emp, "mom_change_thousands": mom_change,
                "yoy_change_thousands": yoy_change,
                "mom_contribution_pct": None if not total_mom_change else mom_change / total_mom_change * 100,
                "yoy_contribution_pct": None if not total_yoy_change else yoy_change / total_yoy_change * 100,
                "share_pct": None if not total_emp else emp / total_emp * 100,
            })
        residual_emp = total_emp - included_emp_sum if total_emp is not None else None
        residual_mom = total_mom_change - included_mom_sum if total_mom_change is not None else None
        residual_yoy = total_yoy_change - included_yoy_sum if total_yoy_change is not None else None
        if residual_emp is not None and abs(residual_emp) > 0.05:
            rows.append({
                "date": date, "sector": "Residual / Other", "employment_thousands": residual_emp,
                "total_nonfarm_thousands": total_emp, "mom_change_thousands": residual_mom,
                "yoy_change_thousands": residual_yoy,
                "mom_contribution_pct": None if not total_mom_change else residual_mom / total_mom_change * 100,
                "yoy_contribution_pct": None if not total_yoy_change else residual_yoy / total_yoy_change * 100,
                "share_pct": None if not total_emp else residual_emp / total_emp * 100,
            })
    write_rows(OUT_DIR / "industry_employment.csv", rows, [
        "date", "sector", "employment_thousands", "total_nonfarm_thousands",
        "mom_change_thousands", "yoy_change_thousands",
        "mom_contribution_pct", "yoy_contribution_pct", "share_pct"
    ])
    print("Wrote data/industry_employment.csv")

def write_state_csv(results, national_total_results):
    total_us = series_to_dict(national_total_results[NATIONAL_SERIES["Total nonfarm"]])
    rows = []
    for state_name, meta in STATE_SERIES.items():
        sid = meta["series_id"]
        if sid not in results:
            print(f"WARNING: Missing state series {sid} for {state_name}")
            continue
        obs = sorted(results[sid])
        smap = series_to_dict(obs)
        dates = [d for d, _ in obs]
        for idx, date in enumerate(dates):
            emp = smap.get(date)
            prev = smap.get(dates[idx - 1]) if idx >= 1 else None
            yoy = smap.get(dates[idx - 12]) if idx >= 12 else None
            us_emp = total_us.get(date)
            mom_change = None if emp is None or prev is None else emp - prev
            yoy_change = None if emp is None or yoy is None else emp - yoy
            rows.append({
                "date": date, "state": state_name, "abbr": meta["abbr"], "fips": meta["fips"],
                "employment_thousands": emp, "mom_change_thousands": mom_change,
                "yoy_change_thousands": yoy_change, "mom_growth_pct": pct_change(emp, prev),
                "yoy_growth_pct": pct_change(emp, yoy),
                "share_us_pct": None if not us_emp else emp / us_emp * 100,
            })
    write_rows(OUT_DIR / "state_employment.csv", rows, [
        "date", "state", "abbr", "fips", "employment_thousands",
        "mom_change_thousands", "yoy_change_thousands", "mom_growth_pct", "yoy_growth_pct", "share_us_pct"
    ])
    print("Wrote data/state_employment.csv")

def main():
    print(f"Building U.S. Employment Dynamics data, {START_YEAR}-{END_YEAR}")
    national_results = fetch_bls_series(list(NATIONAL_SERIES.values()), START_YEAR, END_YEAR)
    state_results = fetch_bls_series([m["series_id"] for m in STATE_SERIES.values()], START_YEAR, END_YEAR)
    write_industry_csv(national_results)
    write_state_csv(state_results, national_results)
    print("Employment dynamics data update complete.")

if __name__ == "__main__":
    main()
