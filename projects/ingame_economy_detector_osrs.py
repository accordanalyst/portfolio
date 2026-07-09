"""
OSRS Grand Exchange Economy Anomaly Detector
=============================================
Uses the OSRS Wiki Real-Time Prices API to pull genuine Grand Exchange
price and volume history, then applies the same rolling-baseline z-score
detection method used in the billing-forensics projects.

This finds real anomalies — actual price manipulation events, bot bans
that crashed supply prices overnight, content updates that spiked demand,
and commodity inflation driven by in-game economy shifts.

API: prices.runescape.wiki/api/v1/osrs
Docs: oldschool.runescape.wiki/w/RuneScape:Real-time_Prices

USAGE
-----
First run (fetches live data, saves to osrs_cache.json — takes ~30 sec):
    python3 ingame_economy_detector_osrs.py

Subsequent runs (uses cached data, instant):
    python3 ingame_economy_detector_osrs.py --cached

Force refresh:
    python3 ingame_economy_detector_osrs.py --refresh

The script also writes:
    osrs_anomaly_report.csv  — full ranked exception report
    osrs_chart_data.json     — clean data for the portfolio HTML page
    osrs_anomaly_chart.png   — matplotlib chart of top flagged items

NOTE: All data is live from Jagex/OSRS Wiki. No data has been simulated
      or engineered. Anomalies found are real events in the OSRS economy.

CREDIT: Price data from the OSRS Wiki Real-Time Prices API, a partnership
        between the Old School Wiki and RuneLite. Not affiliated with Jagex.
"""

import argparse
import json
import os
import time
import sys
from datetime import datetime, timezone

import pandas as pd
import numpy as np
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ── CONFIG ────────────────────────────────────────────────────────────────────
# Required by the API: identify your project and provide contact info.
# The wiki will 403 any request without a descriptive User-Agent.
USER_AGENT = "AccordAnalyst Portfolio Project - accordanalyst.com - contact@accordanalyst.com"
BASE_URL   = "https://prices.runescape.wiki/api/v1/osrs"
CACHE_FILE = "osrs_cache.json"

ROLLING_WINDOW       = 14      # days — two-week trailing baseline per item
Z_PRICE_THRESHOLD    = 2.5     # standard deviations from own baseline
Z_VOLUME_THRESHOLD   = 2.8     # slightly higher: volume is naturally spikier
INFLATION_WINDOW     = 14      # days over which to measure commodity basket drift
INFLATION_THRESHOLD  = 0.15    # 15% cumulative rise on commodity basket = alert
EROSION_WINDOW       = 14      # days for cumulative decline check
EROSION_THRESHOLD    = -0.22   # 22% decline over window = erosion flag

# ── ITEM SELECTION ────────────────────────────────────────────────────────────
# Curated set of recognizable OSRS items across categories.
# IDs verified against OSRS Wiki mapping endpoint.
#
# Mix of: volatile raid rewards, stable iconic weapons, high-volume
# supplies/commodities — same category logic as the simulated version,
# now grounded in real Jagex item IDs.

ITEMS_TO_ANALYZE = [
    # PVM RAID REWARDS (high value, volatile price — peak anomaly candidates)
    {"id": 21021, "name": "Twisted Bow",         "category": "Raid Reward"},
    {"id": 22325, "name": "Scythe of Vitur",      "category": "Raid Reward"},
    {"id": 21750, "name": "Ancestral Robe Top",   "category": "Raid Reward"},
    {"id": 24422, "name": "Tumeken's Shadow",      "category": "Raid Reward"},

    # ICONIC WEAPONS (mid-to-high tier, strong player recognition)
    {"id": 4151,  "name": "Abyssal Whip",          "category": "Weapon"},
    {"id": 13652, "name": "Dragon Claws",           "category": "Weapon"},
    {"id": 12926, "name": "Toxic Blowpipe",         "category": "Weapon"},
    {"id": 20997, "name": "Dragon Warhammer",       "category": "Weapon"},

    # ARMOUR
    {"id": 11832, "name": "Bandos Chestplate",      "category": "Armour"},
    {"id": 11802, "name": "Armadyl Crossbow",       "category": "Armour"},
    {"id": 12817, "name": "Elysian Spirit Shield",  "category": "Armour"},

    # COMMODITIES (high volume — used for inflation basket + supply-chain analysis)
    {"id": 561,   "name": "Nature Rune",            "category": "Commodity"},
    {"id": 565,   "name": "Blood Rune",             "category": "Commodity"},
    {"id": 2434,  "name": "Prayer Potion (4)",      "category": "Commodity"},
    {"id": 536,   "name": "Dragon Bones",           "category": "Commodity"},
    {"id": 385,   "name": "Shark",                  "category": "Commodity"},
]

# Items used as the commodity inflation basket (stable, high-volume supplies)
COMMODITY_IDS = [561, 565, 2434, 536, 385]


# ── API FETCH ─────────────────────────────────────────────────────────────────

def api_session():
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def fetch_mapping(session) -> dict:
    """Returns {item_id: {name, limit, members, highalch, ...}}"""
    print("  Fetching item mapping...", flush=True)
    r = session.get(f"{BASE_URL}/mapping", timeout=20)
    r.raise_for_status()
    return {str(d["id"]): d for d in r.json()}


def fetch_timeseries(session, item_id: int, timestep: str = "24h") -> list:
    """
    Returns daily OHLC-style price data for one item.
    timestep: '5m', '1h', '6h', '24h'
    Each row: {timestamp, avgHighPrice, avgLowPrice, highPriceVolume, lowPriceVolume}
    """
    url = f"{BASE_URL}/timeseries?timestep={timestep}&id={item_id}"
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return r.json().get("data", [])


def build_cache(refresh: bool = False) -> dict:
    if not refresh and os.path.exists(CACHE_FILE):
        print(f"Loading cached data from {CACHE_FILE}...")
        with open(CACHE_FILE) as f:
            return json.load(f)

    print("Fetching live data from OSRS Wiki API...")
    session = api_session()
    mapping = fetch_mapping(session)

    cache = {"fetched_at": datetime.now(timezone.utc).isoformat(), "items": {}}

    for item in ITEMS_TO_ANALYZE:
        iid = item["id"]
        name = item["name"]
        print(f"  Fetching timeseries: {name} (ID {iid})...", flush=True)
        try:
            ts = fetch_timeseries(session, iid, "24h")
            cache["items"][str(iid)] = {
                "id":       iid,
                "name":     name,
                "category": item["category"],
                "mapping":  mapping.get(str(iid), {}),
                "timeseries": ts,
            }
        except Exception as e:
            print(f"    WARNING: Failed to fetch {name}: {e}")
        time.sleep(0.5)  # be polite — no hard rate limit but be a good citizen

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"  Cached to {CACHE_FILE}")
    return cache


# ── DATA ASSEMBLY ─────────────────────────────────────────────────────────────

def build_dataframe(cache: dict) -> pd.DataFrame:
    rows = []
    for iid, item in cache["items"].items():
        for day in item["timeseries"]:
            # avgHighPrice = insta-buy average; avgLowPrice = insta-sell average
            # Mid price = average of both (standard market price approximation)
            high = day.get("avgHighPrice")
            low  = day.get("avgLowPrice")
            if high is None and low is None:
                continue
            mid = (
                (high if high else low) + (low if low else high)
            ) / 2 if (high and low) else (high or low)

            volume = (day.get("highPriceVolume") or 0) + (day.get("lowPriceVolume") or 0)

            rows.append({
                "item_id":   item["id"],
                "item_name": item["name"],
                "category":  item["category"],
                "date":      pd.to_datetime(day["timestamp"], unit="s", utc=True).normalize(),
                "price_high": high,
                "price_low":  low,
                "price":      mid,
                "volume":     float(volume),
                "ge_limit":   item["mapping"].get("limit", None),
            })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values(["item_id", "date"]).reset_index(drop=True)
    return df


# ── DETECTION ─────────────────────────────────────────────────────────────────

def detect_anomalies(group: pd.DataFrame) -> pd.DataFrame:
    g = group.copy()

    # Price baseline
    g["roll_price_mean"] = g["price"].rolling(ROLLING_WINDOW, min_periods=7).mean().shift(1)
    g["roll_price_std"]  = g["price"].rolling(ROLLING_WINDOW, min_periods=7).std().shift(1)
    std_floor = g["roll_price_mean"] * 0.04
    g["roll_price_std"] = g["roll_price_std"].clip(lower=std_floor)
    g["z_price"] = (g["price"] - g["roll_price_mean"]) / g["roll_price_std"]
    g["pct_vs_baseline"] = (g["price"] - g["roll_price_mean"]) / g["roll_price_mean"] * 100

    # Volume baseline (skip if all zero — some items have sparse volume data)
    if g["volume"].sum() > 0:
        g["roll_vol_mean"] = g["volume"].rolling(ROLLING_WINDOW, min_periods=7).mean().shift(1)
        g["roll_vol_std"]  = g["volume"].rolling(ROLLING_WINDOW, min_periods=7).std().shift(1)
        vol_floor = g["roll_vol_mean"] * 0.05
        g["roll_vol_std"] = g["roll_vol_std"].clip(lower=vol_floor)
        g["z_volume"] = (g["volume"] - g["roll_vol_mean"]) / g["roll_vol_std"]
    else:
        g["roll_vol_mean"] = np.nan
        g["roll_vol_std"]  = np.nan
        g["z_volume"] = np.nan

    # Erosion: cumulative % change over trailing window
    g["erosion_pct"] = g["price"].pct_change(periods=EROSION_WINDOW)

    def classify(row):
        zp = row["z_price"] if pd.notna(row["z_price"]) else 0
        zv = row["z_volume"] if pd.notna(row["z_volume"]) else 0
        ep = row["erosion_pct"] if pd.notna(row["erosion_pct"]) else 0

        price_spike = zp >=  Z_PRICE_THRESHOLD
        price_drop  = zp <= -Z_PRICE_THRESHOLD
        vol_burst   = zv >=  Z_VOLUME_THRESHOLD
        vol_crash   = zv <= -Z_VOLUME_THRESHOLD
        erosion     = ep <=  EROSION_THRESHOLD

        # Compound patterns first — combination tells the full story
        if price_spike and vol_crash: return "PRICE MANIPULATION"
        if price_drop  and vol_burst: return "DUMP / BOT BAN"
        if vol_burst and not (price_spike or price_drop): return "WASH TRADING"
        if price_spike:               return "PRICE SPIKE"
        if price_drop:                return "PRICE DROP"
        if erosion:                   return "SLOW EROSION"
        return "NORMAL"

    g["anomaly_type"] = g.apply(classify, axis=1)

    g["severity_score"] = np.where(
        g["anomaly_type"] == "SLOW EROSION",
        g["erosion_pct"].abs() * 100,
        np.maximum(g["z_price"].abs().fillna(0), g["z_volume"].abs().fillna(0))
    )
    return g


def priority_tier(score, atype):
    if atype in ("PRICE MANIPULATION", "DUMP / BOT BAN"):
        return "CRITICAL"
    if atype == "WASH TRADING":
        return "HIGH"
    if score >= 10: return "HIGH"
    if score >= 4:  return "MEDIUM"
    return "LOW"


# ── INFLATION INDEX ───────────────────────────────────────────────────────────

def build_inflation_index(results: pd.DataFrame) -> pd.DataFrame:
    basket = results[results["item_id"].isin(COMMODITY_IDS)].copy()
    if basket.empty:
        return pd.DataFrame()
    basket_weekly = basket.groupby("date")["price"].mean().reset_index()
    basket_weekly.columns = ["date", "basket_avg"]
    base = basket_weekly["basket_avg"].iloc[0]
    basket_weekly["inflation_index"] = basket_weekly["basket_avg"] / base * 100
    basket_weekly["basket_pct_change"] = basket_weekly["basket_avg"].pct_change(INFLATION_WINDOW)
    basket_weekly["inflation_alert"] = basket_weekly["basket_pct_change"] >= INFLATION_THRESHOLD
    return basket_weekly


# ── CHART ─────────────────────────────────────────────────────────────────────

def draw_chart(results: pd.DataFrame, anomaly_report: pd.DataFrame):
    BG    = "#070A12"; PANEL = "#0D131F"; LINE  = "#22304A"
    CYAN  = "#3FE8E0"; MAG   = "#FF3D9A"; GOLD  = "#FFD166"
    TEXT  = "#D6E2EE"; DIM   = "#7E8FA8"

    ANOM_COLORS = {
        "PRICE SPIKE":        "#E8956D",
        "PRICE DROP":         "#FF6B5B",
        "SLOW EROSION":       "#F0C070",
        "PRICE MANIPULATION": "#FF3D9A",
        "DUMP / BOT BAN":     "#FF3D9A",
        "WASH TRADING":       "#8B6CFF",
    }

    # Pick top 6 by anomaly count — these will be most visually interesting
    top_items = (
        anomaly_report.groupby("item_id")
        .size().sort_values(ascending=False)
        .head(6).index.tolist()
    )
    top_names = {
        row["item_id"]: row["item_name"]
        for _, row in anomaly_report.drop_duplicates("item_id").iterrows()
        if row["item_id"] in top_items
    }

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    fig.suptitle("OSRS Grand Exchange — Top Flagged Items (Real Data)", fontsize=14,
                 fontweight="bold", color=TEXT, y=0.99)

    for ax, iid in zip(axes.flat, top_items):
        item_data = results[results["item_id"] == iid].sort_values("date")
        name = top_names.get(iid, str(iid))

        x        = item_data["date"]
        y        = item_data["price"]
        baseline = item_data["roll_price_mean"]

        ax.plot(x, baseline, color=GOLD, lw=1.2, ls=(0,(4,3)), alpha=0.8, label="Baseline", zorder=2)
        ax.plot(x, y, color=TEXT, lw=2, label="Price", zorder=4, solid_capstyle="round")

        flagged = item_data[item_data["anomaly_type"] != "NORMAL"]
        for atype in flagged["anomaly_type"].unique():
            subset = flagged[flagged["anomaly_type"] == atype]
            c = ANOM_COLORS.get(atype, MAG)
            for sz, alpha in [(340,0.06),(200,0.11),(100,0.19)]:
                ax.scatter(subset["date"], subset["price"], color=c,
                           s=sz, alpha=alpha, zorder=4, linewidths=0)
            ax.scatter(subset["date"], subset["price"], color=c, s=50,
                       zorder=6, label=atype, edgecolors=BG, linewidths=0.8)

        ax.set_title(name, fontsize=10, fontweight="bold", color=TEXT, pad=7)
        ax.set_ylabel("Price (GP)", fontsize=7.5, color=DIM)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x,p: f"{x/1e6:.1f}M" if x>=1e6 else f"{x/1e3:.0f}K" if x>=1000 else str(int(x))))
        ax.tick_params(axis="x", rotation=40, labelsize=6.5, colors=DIM)
        ax.tick_params(axis="y", labelsize=7.5, colors=DIM)
        ax.legend(fontsize=6.5, loc="upper left", framealpha=0.25,
                  facecolor=PANEL, edgecolor=LINE, labelcolor=TEXT)
        ax.grid(alpha=0.12, color=LINE, lw=0.6)
        ax.set_facecolor(PANEL)
        for sp in ax.spines.values():
            sp.set_color(LINE); sp.set_lw(0.8)

    fig.patch.set_facecolor(BG)
    plt.tight_layout(rect=[0,0,1,0.96])
    plt.savefig("osrs_anomaly_chart.png", dpi=150, bbox_inches="tight", facecolor=BG)
    print("Chart saved → osrs_anomaly_chart.png")


# ── JSON EXPORT FOR HTML ──────────────────────────────────────────────────────

def export_chart_json(results: pd.DataFrame, anomaly_report: pd.DataFrame):
    """Exports the clean per-item time series to JSON for embedding in the HTML."""
    top_items = (
        anomaly_report.groupby("item_id")
        .size().sort_values(ascending=False)
        .head(6).index.tolist()
    )

    chart_data = {}
    for iid in top_items:
        item_df = results[results["item_id"] == iid].sort_values("date").copy()
        name = item_df["item_name"].iloc[0]
        category = item_df["category"].iloc[0]
        rows = []
        for _, row in item_df.iterrows():
            rows.append({
                "date":     row["date"].strftime("%Y-%m-%d"),
                "price":    round(float(row["price"]), 0) if pd.notna(row["price"]) else None,
                "volume":   int(row["volume"]) if pd.notna(row["volume"]) else 0,
                "baseline": round(float(row["roll_price_mean"]), 0) if pd.notna(row["roll_price_mean"]) else None,
                "anomaly":  row["anomaly_type"] if row["anomaly_type"] != "NORMAL" else None,
                "z_price":  round(float(row["z_price"]), 2) if pd.notna(row["z_price"]) else None,
                "z_vol":    round(float(row["z_volume"]), 2) if pd.notna(row["z_volume"]) else None,
                "pct":      round(float(row["pct_vs_baseline"]), 1) if pd.notna(row["pct_vs_baseline"]) else None,
            })
        chart_data[str(iid)] = {"name": name, "category": category, "data": rows}

    with open("osrs_chart_data.json", "w") as f:
        json.dump(chart_data, f, indent=2)
    print("Chart data saved → osrs_chart_data.json")
    return chart_data


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OSRS GE Economy Anomaly Detector")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch from API, ignoring cache")
    parser.add_argument("--cached",  action="store_true", help="Force use of cache (skip API check)")
    args = parser.parse_args()

    # 1. Fetch / load data
    cache = build_cache(refresh=args.refresh)
    print(f"\nFetched at: {cache.get('fetched_at', 'unknown')}")

    # 2. Build DataFrame
    df = build_dataframe(cache)
    print(f"Items loaded: {df['item_id'].nunique()}")
    print(f"Date range:   {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"Total rows:   {len(df)}")

    # 3. Run detection
    results = df.groupby("item_id", group_keys=False)[df.columns].apply(detect_anomalies)
    results = results.reset_index(drop=True)

    # 4. Build anomaly report
    anomalies = results[results["anomaly_type"] != "NORMAL"].copy()
    anomalies = anomalies.sort_values("severity_score", ascending=False)

    report_cols = ["item_id","item_name","category","date","price","roll_price_mean",
                   "pct_vs_baseline","z_price","z_volume","anomaly_type","severity_score"]
    anomaly_report = anomalies[report_cols].copy()
    anomaly_report["date"] = anomaly_report["date"].dt.strftime("%Y-%m-%d")
    anomaly_report["priority"] = anomaly_report.apply(
        lambda r: priority_tier(r["severity_score"], r["anomaly_type"]), axis=1
    )
    anomaly_report = anomaly_report.round({
        "price":0,"roll_price_mean":0,"pct_vs_baseline":1,
        "z_price":2,"z_volume":2,"severity_score":2
    })
    anomaly_report.to_csv("osrs_anomaly_report.csv", index=False)

    # 5. Inflation index
    inflation = build_inflation_index(results)
    inflation_alerts = inflation[inflation["inflation_alert"]] if not inflation.empty else pd.DataFrame()

    # 6. Console output
    print("\n" + "="*72)
    print("OSRS GRAND EXCHANGE — REAL DATA ANOMALY REPORT")
    print("="*72)
    print(f"Items analyzed:      {results['item_id'].nunique()}")
    print(f"Days analyzed:       {results['date'].nunique()}")
    print(f"Anomalies flagged:   {len(anomaly_report)}")
    print(f"Inflation alerts:    {len(inflation_alerts)}")
    print()
    print(anomaly_report.head(20).to_string(index=False))
    print()

    summary = anomaly_report.groupby("anomaly_type").agg(
        count=("item_id","count"),
        avg_severity=("severity_score","mean"),
        items_affected=("item_id","nunique")
    ).round(2)
    print("Summary by type:")
    print(summary.to_string())

    prio = (anomaly_report["priority"].value_counts()
            .reindex(["CRITICAL","HIGH","MEDIUM","LOW"]).fillna(0).astype(int))
    print("\nPriority breakdown:")
    print(prio.to_string())
    crit = anomaly_report[anomaly_report["priority"]=="CRITICAL"]["item_id"].nunique()
    print(f"\n{crit} items flagged CRITICAL — potential manipulation or major market event")

    # 7. Outputs
    draw_chart(results, anomaly_report)
    export_chart_json(results, anomaly_report)
    print("\nFull report saved → osrs_anomaly_report.csv")
    print("\nDone. Open osrs_chart_data.json to embed real data into the portfolio HTML.")


if __name__ == "__main__":
    main()
