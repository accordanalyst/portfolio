# OSRS GE Economy Anomaly Detector — Setup & Usage

## What this does

Pulls **real Grand Exchange price and volume history** from the OSRS Wiki
Real-Time Prices API, then applies the same rolling-baseline z-score anomaly
detection method from the billing-forensics projects to find actual market
events: price manipulation, bot ban supply crashes, content update demand
spikes, and commodity inflation.

No data is simulated. Anomalies found are real events that happened in the
OSRS economy.

---

## Quick start (run this on your local machine)

```bash
# 1. Install dependencies (one time)
pip install requests pandas numpy matplotlib

# 2. First run — fetches live data from the API (~30 sec)
python3 ingame_economy_detector_osrs.py

# 3. Subsequent runs — uses cached data (instant)
python3 ingame_economy_detector_osrs.py --cached

# 4. Force-refresh from the API
python3 ingame_economy_detector_osrs.py --refresh
```

---

## Files produced

| File | What it is |
|---|---|
| `osrs_cache.json` | Raw API response cache — don't delete if you want fast reruns |
| `osrs_anomaly_report.csv` | Full ranked anomaly report — all flagged items sorted by severity |
| `osrs_chart_data.json` | Clean per-item time series for embedding in the portfolio HTML |
| `osrs_anomaly_chart.png` | Matplotlib chart of the top 6 flagged items |

---

## Updating the portfolio HTML

Once you have `osrs_chart_data.json` from a local run:

1. Open `ingame-economy-detector.html`
2. Find the line: `const CHART_DATA = ...`
3. Replace the embedded JSON with the contents of `osrs_chart_data.json`
4. The chart will now show real OSRS data instead of the simulated NeonRift data

Or: re-run `build_html.py` (which embeds the chart data automatically)
after replacing `chart_data.json` with `osrs_chart_data.json`.

---

## Items analyzed

| Item | ID | Category | Why included |
|---|---|---|---|
| Twisted Bow | 21021 | Raid Reward | Most expensive ranged weapon — extreme price volatility |
| Scythe of Vitur | 22325 | Raid Reward | Theatre of Blood reward — major price swings |
| Ancestral Robe Top | 21750 | Raid Reward | Chambers reward — reflects raid meta shifts |
| Tumeken's Shadow | 24422 | Raid Reward | Newest high-end BiS mage weapon |
| Abyssal Whip | 4151 | Weapon | Iconic slayer reward — decades of price history |
| Dragon Claws | 13652 | Weapon | PK spec weapon — bot-ban sensitive |
| Toxic Blowpipe | 12926 | Weapon | High-volume weapon — scale/dart supply driven |
| Dragon Warhammer | 20997 | Weapon | BiS spec weapon — drop rate dependent |
| Bandos Chestplate | 11832 | Armour | GWD armour — content update sensitive |
| Armadyl Crossbow | 11802 | Armour | Ranged BiS spec — frequently manipulated |
| Elysian Spirit Shield | 12817 | Armour | Rarest shield — long-term deflation subject |
| Nature Rune | 561 | Commodity | High-alch staple — inflation basket |
| Blood Rune | 565 | Commodity | High-volume magic rune — inflation basket |
| Prayer Potion (4) | 2434 | Commodity | Prayer training staple — demand-driven inflation |
| Dragon Bones | 536 | Commodity | Prayer XP supply — bot-ban crash indicator |
| Shark | 385 | Commodity | Food — proxy for overall economy supply health |

---

## API credit

Data from the [OSRS Wiki Real-Time Prices API](https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices),
a partnership between the Old School Wiki and RuneLite.  
Not affiliated with Jagex Ltd.

Per the API docs: don't loop over all 3,700+ items with individual requests —
always fetch all items in a single `/latest` call and loop locally. This script
follows that guidance by fetching timeseries per item (required), with 0.5s
sleep between requests to be a good API citizen.
