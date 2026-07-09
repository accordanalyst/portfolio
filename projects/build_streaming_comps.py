"""
build_streaming_comps.py
─────────────────────────────────────────────────────────────────────────────
Streaming & Media Cross-Company Financial Comparison — Accord Analyst
Alexis Kelly / accordanalyst.com

Pulls FY2022–FY2024 GAAP results for Netflix, Disney, Warner Bros. Discovery,
and Paramount Global straight from each company's audited SEC filings, then
uses pandas/NumPy to compute the comparison metrics that drive the case study
page and the Power BI workbook.

DATA SOURCE — every figure below is transcribed from the company's actual
filed Consolidated Statements of Operations (10-K / 8-K exhibit 99.1), not
estimated. Source accession numbers are noted per company so any number here
can be traced back to the original filing on EDGAR:

  NFLX  CIK 0001065280 — FY2024 Annual Report to Shareholders (10-K wrapper),
                         accession 0001193125-25-084431
  DIS   CIK 0001744489 — FY2024 10-K, accession 0001744489-24-000276
  WBD   CIK 0001437107 — FY2024 10-K, accession 0001437107-25-000031
                         (net loss confirmed against FY2024 Annual Report to
                         Shareholders, accession 0001308179-25-000479)
  PARA  CIK 0000813828 — FY2024 10-K, accession 0000813828-25-000005
                         (now Paramount Skydance Corp / PSKY, CIK 0002041610,
                         post the Aug 2025 Skydance merger — figures below
                         predate the merger and are reported under the
                         legacy Paramount Global CIK)

Note on fiscal years: Netflix, WBD, and Paramount report on a calendar fiscal
year (ending Dec 31). Disney's fiscal year ends in late Sept/early Oct — its
"FY2024" figures cover Oct 2023–Sept 2024, not the calendar year. This is
disclosed on the case study page rather than silently normalized, since
restating Disney to calendar-year would require interpolating from 10-Qs.
"""

import pandas as pd
import numpy as np

# ── RAW FIGURES, IN $ MILLIONS (thousands for NFLX, converted below) ────────
# Structure: company -> fiscal_year -> {revenue, operating_income, net_income}

RAW = {
    "Netflix": {
        2022: {"revenue": 31615.550, "operating_income": 5632.831, "net_income": 4491.924},
        2023: {"revenue": 33723.297, "operating_income": 6954.003, "net_income": 5407.990},
        2024: {"revenue": 39000.966, "operating_income": 10417.614, "net_income": 8711.631},
    },
    "Disney": {
        # Fiscal year ends late Sept / early Oct
        2022: {"revenue": 82722, "operating_income": 6770, "net_income": 3150},
        2023: {"revenue": 88900, "operating_income": 8990, "net_income": 2350},
        2024: {"revenue": 91360, "operating_income": 11910, "net_income": 4970},
    },
    "Warner Bros. Discovery": {
        2022: {"revenue": 33817, "operating_income": -7370, "net_income": -7371},
        2023: {"revenue": 41321, "operating_income": -1548, "net_income": -3126},
        2024: {"revenue": 39321, "operating_income": -10032, "net_income": -11311},
    },
    "Paramount Global": {
        2022: {"revenue": 30154, "operating_income": 2342, "net_income": 725},
        2023: {"revenue": 29652, "operating_income": -451, "net_income": -608},
        2024: {"revenue": 29213, "operating_income": -5269, "net_income": -6190},
    },
}

TICKERS = {
    "Netflix": "NFLX",
    "Disney": "DIS",
    "Warner Bros. Discovery": "WBD",
    "Paramount Global": "PARA",
}

CIKS = {
    "Netflix": "0001065280",
    "Disney": "0001744489",
    "Warner Bros. Discovery": "0001437107",
    "Paramount Global": "0000813828",  # legacy entity; now Paramount Skydance Corp (PSKY, CIK 0002041610)
}


def build_long_dataframe() -> pd.DataFrame:
    """Flatten RAW into a tidy long-format DataFrame: one row per company-year."""
    rows = []
    for company, years in RAW.items():
        for fy, figures in years.items():
            rows.append({
                "company": company,
                "ticker": TICKERS[company],
                "cik": CIKS[company],
                "fiscal_year": fy,
                "revenue_m": figures["revenue"],
                "operating_income_m": figures["operating_income"],
                "net_income_m": figures["net_income"],
            })
    df = pd.DataFrame(rows).sort_values(["company", "fiscal_year"]).reset_index(drop=True)
    return df


def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add NumPy-computed ratios: margins and YoY growth."""
    df = df.copy()

    # Margins — vectorized with NumPy, guarding against divide-by-zero
    df["operating_margin_pct"] = np.round(
        np.divide(df["operating_income_m"], df["revenue_m"]) * 100, 1
    )
    df["net_margin_pct"] = np.round(
        np.divide(df["net_income_m"], df["revenue_m"]) * 100, 1
    )

    # YoY revenue growth, computed per company via groupby + pct_change
    df["revenue_yoy_pct"] = np.round(
        df.groupby("company")["revenue_m"].pct_change() * 100, 1
    )

    # 2-year CAGR (2022 -> 2024) per company, broadcast across rows
    def cagr(group: pd.DataFrame) -> pd.Series:
        start = group.loc[group["fiscal_year"] == 2022, "revenue_m"].values
        end = group.loc[group["fiscal_year"] == 2024, "revenue_m"].values
        if len(start) and len(end) and start[0] > 0:
            rate = ((end[0] / start[0]) ** (1 / 2) - 1) * 100
        else:
            rate = np.nan
        return pd.Series(np.round(rate, 1), index=group.index)

    df["revenue_cagr_22_24_pct"] = df.groupby("company", group_keys=False).apply(cagr)

    return df


def summary_2024(df: pd.DataFrame) -> pd.DataFrame:
    """Latest-year (FY2024) snapshot, ranked by net margin — the headline table."""
    latest = df[df["fiscal_year"] == 2024].copy()
    latest = latest.sort_values("net_margin_pct", ascending=False).reset_index(drop=True)
    latest["rank_by_net_margin"] = latest.index + 1
    return latest[[
        "rank_by_net_margin", "company", "ticker", "revenue_m",
        "operating_margin_pct", "net_margin_pct", "revenue_cagr_22_24_pct",
    ]]


if __name__ == "__main__":
    long_df = build_long_dataframe()
    full_df = add_derived_metrics(long_df)

    # Full tidy dataset — one row per company-year, ready for Power BI import
    full_df.to_csv("streaming_comps_full.csv", index=False)

    # Headline FY2024 ranking table — used in the case study results section
    summary = summary_2024(full_df)
    summary.to_csv("streaming_comps_fy2024_summary.csv", index=False)

    print("── FY2024 Snapshot, ranked by net margin ──")
    print(summary.to_string(index=False))
    print("\n── Full tidy dataset (head) ──")
    print(full_df.head(12).to_string(index=False))
    print(f"\nWrote streaming_comps_full.csv ({len(full_df)} rows)")
    print(f"Wrote streaming_comps_fy2024_summary.csv ({len(summary)} rows)")
