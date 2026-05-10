# 📁 Data Repository Guide

This directory contains all extracted and synthesized data.

## 📂 raw/
Contains raw files extracted directly from the APIs:
- `worldbank_indicators.csv`: World Bank indicators.
- `imf_indicators.csv`: IMF macroeconomic data.
- `un_sdg_indicators.csv`: UN Sustainable Development Goals data.
- `rpw_corridor_costs.csv`: Remittance cost data.
- `fred_exchange_rates.csv`: Exchange rate series.

## 📂 merged/
Contains the final synthesized dataset:
- `master_remittances_dataset.csv`: This is the primary file to be used for analysis. It merges all raw sources into a single, organized table.
