# ─────────────────────────────────────────────────────────────────────────
# pull_bls_live.R
# Live BLS Public Data API puller — run locally to refresh the JOLTS dataset
# with current figures straight from api.bls.gov. Free tier needs no key
# (25 queries/day, 20 years history); a free registration key raises that
# to 500 queries/day and unlocks year-over-year calculations.
#
# This is the "real" version of the pipeline. It wasn't runnable inside the
# sandboxed tool used to build this project (api.bls.gov isn't on that
# tool's fetch allowlist), so the case study ships with figures transcribed
# from EPI's published BLS-sourced JOLTS compilation instead — see
# labor_market_analysis.R and its source comment. Run this script locally
# any time you want to pull the latest month directly from BLS.
#
# Register for a free key at: https://data.bls.gov/registrationEngine/
# Docs: https://www.bls.gov/developers/api_signature_v2.htm
# ─────────────────────────────────────────────────────────────────────────

# install.packages(c("httr", "jsonlite"))  # if needed
library(httr)
library(jsonlite)

BLS_API_KEY <- Sys.getenv("BLS_API_KEY")  # optional — set via Sys.setenv() or .Renviron

# Confirmed real BLS series IDs (verified against data.bls.gov/timeseries/):
SERIES <- c(
  hires_rate    = "JTS000000000000000HIR",  # Total nonfarm, hires rate, SA
  quits_rate    = "JTS000000000000000QUR",  # Total nonfarm, quits rate, SA
  layoffs_rate  = "JTS000000000000000LDR",  # Total nonfarm, layoffs & discharges rate, SA
  openings_rate = "JTS000000000000000JOR",  # Total nonfarm, job openings rate, SA
  openings_lvl  = "JTS000000000000000JOL",  # Total nonfarm, job openings level (thousands), SA
  unemployment  = "LNS13000000"              # Unemployment level (thousands), SA — from CPS, not JOLTS
)

fetch_bls_series <- function(series_ids, start_year, end_year, api_key = "") {
  url <- "https://api.bls.gov/publicAPI/v2/timeseries/data/"
  body <- list(
    seriesid  = as.list(unname(series_ids)),
    startyear = as.character(start_year),
    endyear   = as.character(end_year)
  )
  if (nzchar(api_key)) body$registrationkey <- api_key

  resp <- POST(url, body = toJSON(body, auto_unbox = TRUE), encode = "raw",
               content_type_json())
  parsed <- fromJSON(content(resp, "text", encoding = "UTF-8"), flatten = TRUE)

  if (parsed$status != "REQUEST_SUCCEEDED") {
    stop("BLS API error: ", paste(unlist(parsed$message), collapse = "; "))
  }

  results <- parsed$Results$series
  out <- list()
  for (i in seq_len(nrow(results))) {
    sid  <- results$seriesID[i]
    name <- names(series_ids)[series_ids == sid]
    df   <- results$data[[i]]
    df$series <- name
    out[[name]] <- df
  }
  out
}

current_year <- as.integer(format(Sys.Date(), "%Y"))
data_list <- fetch_bls_series(SERIES, current_year - 4, current_year, BLS_API_KEY)

# Reshape into one wide monthly data frame
library(dplyr)
library(tidyr)

combined <- bind_rows(data_list) %>%
  filter(period != "M13") %>%                     # drop annual-average rows
  mutate(
    month_num   = as.integer(sub("M", "", period)),
    month_start = as.Date(sprintf("%s-%02d-01", year, month_num)),
    value       = as.numeric(value)
  ) %>%
  select(month_start, series, value) %>%
  pivot_wider(names_from = series, values_from = value) %>%
  arrange(month_start)

write.csv(combined, "labor_market_live_pull.csv", row.names = FALSE)
cat("Wrote labor_market_live_pull.csv (", nrow(combined), "rows )\n")
print(tail(combined))
