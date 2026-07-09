"""
pull_edgar_live.py
─────────────────────────────────────────────────────────────────────────────
Live SEC EDGAR XBRL puller — run this locally to refresh streaming_comps_full.csv
with the current filed figures straight from data.sec.gov. No API key needed.

This is the "real" version of the data pipeline. It was not runnable inside
the sandboxed browsing tool used to build this project (data.sec.gov isn't on
that tool's fetch allowlist), so the case study itself ships with figures
transcribed directly from each company's filed 10-K/8-K exhibits instead —
see build_streaming_comps.py for those, with accession numbers cited. This
script pulls the same concepts live from the API for whenever you want to
refresh the numbers (e.g. once FY2025 10-Ks are filed).

Usage:
    pip install requests pandas --break-system-packages   # if needed
    python pull_edgar_live.py

Docs: https://www.sec.gov/edgar/sec-api-documentation
Rate limit: 10 requests/second. A descriptive User-Agent is mandatory or
EDGAR returns 403.
"""

import time
import requests
import pandas as pd

# IMPORTANT: replace with your own name + email. SEC blocks generic/missing
# User-Agents — this is their fair-access policy, not a formality.
HEADERS = {"User-Agent": "Alexis Kelly accordanalyst.com contact@accordanalyst.com"}

COMPANIES = {
    "Netflix":                {"ticker": "NFLX", "cik": "0001065280"},
    "Disney":                 {"ticker": "DIS",  "cik": "0001744489"},
    "Warner Bros. Discovery": {"ticker": "WBD",  "cik": "0001437107"},
    "Paramount Global":       {"ticker": "PARA", "cik": "0000813828"},
    # Paramount Global merged with Skydance in Aug 2025 and now files as
    # Paramount Skydance Corp — CIK 0002041610, ticker PSKY — going forward.
}

# XBRL tags to pull. Companies don't always use the same tag for the same
# line item, so we try a few candidates per concept and take the first that
# has data. This is the single biggest source of friction with this API.
CONCEPT_CANDIDATES = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
    ],
}


def get_company_concept(cik: str, tag: str) -> dict | None:
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return None
    return resp.json()


def annual_10k_values(concept_json: dict) -> pd.DataFrame:
    """Filter a companyconcept payload down to clean annual (10-K, full-year) values."""
    usd = concept_json.get("units", {}).get("USD", [])
    df = pd.DataFrame(usd)
    if df.empty:
        return df
    df = df[df["form"] == "10-K"]
    # Keep only full-year duration facts (~350-380 days) to exclude quarterly
    # comparatives that ride along inside 10-K XBRL — a classic EDGAR API gotcha.
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])
    df["duration_days"] = (df["end"] - df["start"]).dt.days
    df = df[df["duration_days"].between(350, 380)]
    # De-duplicate: keep the most recently filed value per fiscal-period end
    df = df.sort_values("filed").drop_duplicates(subset="end", keep="last")
    return df[["end", "val", "fy", "form", "filed", "accn"]].sort_values("end")


def pull_all() -> pd.DataFrame:
    rows = []
    for company, meta in COMPANIES.items():
        cik = meta["cik"]
        print(f"Pulling {company} ({meta['ticker']}, CIK {cik})...")
        metric_frames = {}
        for metric, tags in CONCEPT_CANDIDATES.items():
            for tag in tags:
                data = get_company_concept(cik, tag)
                time.sleep(0.15)  # stay well under the 10 req/sec fair-access limit
                if data is None:
                    continue
                annual = annual_10k_values(data)
                if not annual.empty:
                    metric_frames[metric] = annual.set_index("end")["val"]
                    break  # first matching tag wins

        if not metric_frames:
            print(f"  no data found for {company} — check CIK / tags")
            continue

        merged = pd.DataFrame(metric_frames)
        merged["company"] = company
        merged["ticker"] = meta["ticker"]
        merged["cik"] = cik
        merged = merged.reset_index().rename(columns={"end": "period_end"})
        rows.append(merged)

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


if __name__ == "__main__":
    df = pull_all()
    if df.empty:
        print("No data pulled — check network access and CIKs.")
    else:
        # Convert to $ millions to match build_streaming_comps.py's convention
        for col in ("revenue", "operating_income", "net_income"):
            if col in df.columns:
                df[col + "_m"] = df[col] / 1_000_000
        df.to_csv("streaming_comps_live_pull.csv", index=False)
        print(f"\nWrote streaming_comps_live_pull.csv ({len(df)} rows)")
        print(df.to_string(index=False))
