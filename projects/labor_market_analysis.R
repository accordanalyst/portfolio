# ─────────────────────────────────────────────────────────────────────────
# labor_market_analysis.R
# Labor Market Analytics — Accord Analyst
# Alexis Kelly / accordanalyst.com
#
# Real JOLTS (Job Openings and Labor Turnover Survey) data, compiled by the
# Economic Policy Institute from Bureau of Labor Statistics source files.
# Source: https://www.epi.org/indicators/jolts/ (EPI analysis of BLS JOLTS)
# National, seasonally adjusted, Jan 2022 - Apr 2026.
#
# Two real statistical methods that Python/Pandas z-score work doesn't cover:
#   1. STL decomposition  — separate trend / seasonal / remainder in the
#      quits rate, since JOLTS series are seasonally adjusted but still
#      carry residual monthly noise worth isolating.
#   2. Beveridge curve regression — the classic labor-economics relationship
#      between job openings and unemployment. A negative, statistically
#      significant slope is the textbook signature of a functioning labor
#      market; a flattening slope is the signature economists watch for
#      when diagnosing a "no vacancy, no unemployment" soft landing.
# ─────────────────────────────────────────────────────────────────────────

rates <- read.csv("jolts_rates_raw.csv", stringsAsFactors = FALSE)
rates$month_start <- as.Date(rates$month_start)

bev <- read.csv("beveridge_raw.csv", stringsAsFactors = FALSE)
bev$month_start <- as.Date(bev$month_start)

# ── 1. STL DECOMPOSITION OF THE QUITS RATE ─────────────────────────────────
# Quits rate is the labor-market-confidence indicator: people quit when they
# believe they can get a better job elsewhere. Decomposing it isolates the
# underlying trend from seasonal hiring-cycle noise (e.g. January churn).
quits_ts <- ts(rates$quits_rate, start = c(2022, 1), frequency = 12)
quits_stl <- stl(quits_ts, s.window = "periodic")

stl_df <- data.frame(
  month_start = rates$month_start,
  quits_rate  = rates$quits_rate,
  trend       = as.numeric(quits_stl$time.series[, "trend"]),
  seasonal    = as.numeric(quits_stl$time.series[, "seasonal"]),
  remainder   = as.numeric(quits_stl$time.series[, "remainder"])
)
write.csv(stl_df, "quits_rate_stl_decomposition.csv", row.names = FALSE)

# ── 2. BEVERIDGE CURVE REGRESSION ──────────────────────────────────────────
# openings_k ~ unemployment_2mo_avg_k
# Textbook relationship is negative and convex; we fit the simple linear
# form here to get a clean slope + significance test for the case study.
bev_model <- lm(openings_k ~ unemployment_2mo_avg_k, data = bev)
bev_summary <- summary(bev_model)

cat("── Beveridge Curve Regression ──\n")
print(bev_summary)

slope       <- coef(bev_model)[["unemployment_2mo_avg_k"]]
intercept   <- coef(bev_model)[["(Intercept)"]]
r_squared   <- bev_summary$r.squared
p_value     <- coef(bev_summary)["unemployment_2mo_avg_k", "Pr(>|t|)"]
conf_int    <- confint(bev_model, "unemployment_2mo_avg_k", level = 0.95)

bev$fitted    <- fitted(bev_model)
bev$vu_ratio  <- round(bev$openings_k / bev$unemployment_2mo_avg_k, 2)
write.csv(bev, "beveridge_curve_fitted.csv", row.names = FALSE)

regression_summary <- data.frame(
  metric = c("slope", "intercept", "r_squared", "p_value",
             "ci_95_lower", "ci_95_upper", "n_obs"),
  value  = c(round(slope, 3), round(intercept, 1), round(r_squared, 3),
             signif(p_value, 3), round(conf_int[1], 3), round(conf_int[2], 3),
             nrow(bev))
)
write.csv(regression_summary, "beveridge_regression_summary.csv", row.names = FALSE)

# ── 3. QUITS RATE AS A LEADING INDICATOR OF LAYOFFS (3-MONTH LAG TEST) ─────
# Hypothesis: a cooling quits rate (falling worker confidence) precedes a
# rise in layoffs a few months later, rather than moving in lockstep.
rates$layoffs_lead3 <- c(rates$layoffs_rate[4:nrow(rates)], rep(NA, 3))
lead_model <- lm(layoffs_lead3 ~ quits_rate, data = rates)
lead_summary <- summary(lead_model)

cat("\n── Quits Rate -> Layoffs Rate (3-Month Lead) Regression ──\n")
print(lead_summary)

lead_out <- data.frame(
  metric = c("slope", "r_squared", "p_value", "n_obs"),
  value  = c(round(coef(lead_model)[["quits_rate"]], 3),
             round(lead_summary$r.squared, 3),
             signif(coef(lead_summary)["quits_rate", "Pr(>|t|)"], 3),
             sum(!is.na(rates$layoffs_lead3)))
)
write.csv(lead_out, "quits_leads_layoffs_summary.csv", row.names = FALSE)

# ── 4. TIDY EXPORT FOR EXCEL ────────────────────────────────────────────────
# Single clean table: one row per month, every rate plus the derived V/U
# ratio, ready to load into Excel as a proper table for PivotTables/slicers.
excel_export <- merge(rates[, c("month_start","hires_rate","quits_rate","layoffs_rate")],
                       bev[, c("month_start","unemployment_2mo_avg_k","openings_k","vu_ratio")],
                       by = "month_start", all.x = TRUE)
excel_export <- excel_export[order(excel_export$month_start), ]
write.csv(excel_export, "labor_market_full.csv", row.names = FALSE)

cat("\nWrote quits_rate_stl_decomposition.csv (", nrow(stl_df), "rows)\n")
cat("Wrote beveridge_curve_fitted.csv (", nrow(bev), "rows)\n")
cat("Wrote beveridge_regression_summary.csv\n")
cat("Wrote quits_leads_layoffs_summary.csv\n")
cat("Wrote labor_market_full.csv (", nrow(excel_export), "rows) — load this one into Excel\n")
