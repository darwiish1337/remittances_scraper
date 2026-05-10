"""
IMF DataMapper Scraper
=======================
Fetches key macroeconomic datasets from the IMF DataMapper API.
Includes indicators for Balance of Payments, GDP growth, inflation, and unemployment.

Data Source: https://www.imf.org/external/datamapper/api/v1
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List
from .base import BaseScraper

# Constant for raw data storage
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"


class IMFScraper(BaseScraper):
    """
    Scraper implementation for IMF DataMapper API.
    Handles extraction of time-series data for multiple macroeconomic indicators.
    """

    SOURCE_NAME = "imf"
    BASE_URL = "https://www.imf.org/external/datamapper/api/v1"

    def __init__(self, delay: float = 2.0, retries: int = 5):
        """
        Initializes the IMF scraper with specific headers required for DataMapper access.
        """
        super().__init__(delay=delay, retries=retries)
        # We'll use the base headers but ensure Accept is set for JSON when needed

    # Core indicators categorized by IMF codes
    INDICATORS = {
        "current_account_pct_gdp":   "BCA_NGDPD",
        "fx_rate_vs_usd":            "ENDA_XDC_USD_RATE",
        "gdp_usd_bn":                "NGDPD",
        "gdp_growth_pct":            "NGDP_RPCH",
        "inflation_avg_pct":         "PCPIPCH",
        "unemployment_pct":          "LUR",
        "govt_gross_debt_gdp":       "GGXWDG_NGDP",
        "population_millions":       "LP",
    }

    def scrape(self, start: int = 2000, end: int = 2023) -> pd.DataFrame:
        """
        Executes the scraping sequence for IMF indicators.
        
        Args:
            start: The beginning year of the data range.
            end: The ending year of the data range.
            
        Returns:
            A consolidated DataFrame containing IMF data points.
        """
        self.log.info(f"Initiating IMF data sequence: {len(self.INDICATORS)} indicators for {start}-{end}")

        indicator_dataframes: List[pd.DataFrame] = []
        for col_name, indicator_code in self.INDICATORS.items():
            self.log.info(f"Extracting IMF indicator: {col_name} [{indicator_code}]")
            df = self._fetch_indicator_data(indicator_code, col_name, start, end)
            
            if df is not None and not df.empty:
                indicator_dataframes.append(df)
                self.log.info(f"  Captured {len(df):,} observations")
            else:
                self.log.warning(f"  No valid observations found for {col_name}")

        if not indicator_dataframes:
            self.log.error("Critical failure: No data points retrieved from IMF API")
            return pd.DataFrame()

        # Data Consolidation
        self.log.info("Synthesizing IMF multi-indicator dataset...")
        primary_keys = ["country_code", "year"]
        consolidated_df = indicator_dataframes[0]
        
        for next_df in indicator_dataframes[1:]:
            consolidated_df = consolidated_df.merge(next_df, on=primary_keys, how="outer")

        consolidated_df["source_engine"] = "imf_datamapper_v1"
        consolidated_df = consolidated_df.sort_values(["country_code", "year"]).reset_index(drop=True)

        # Persistence
        output_file = RAW_DATA_DIR / "imf_indicators.csv"
        consolidated_df.to_csv(output_file, index=False)
        
        self.log.info(f"IMF sequence finalized. Persisted {len(consolidated_df):,} rows to {output_file.name}")
        return consolidated_df

    # ── Internal Implementation Details ──────────────────────────

    def _fetch_indicator_data(self, ind_code: str, column_label: str, 
                               start_yr: int, end_yr: int) -> Optional[pd.DataFrame]:
        """
        Retrieves and parses indicator-specific data from the IMF API.
        """
        request_url = f"{self.BASE_URL}/data/{ind_code}"
        # Use a specific Referer for each indicator to look more natural
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": f"https://www.imf.org/external/datamapper/datasets/{ind_code}",
            "X-Requested-With": "XMLHttpRequest"
        }
        payload = self.get_json(request_url, headers=headers)
        
        if not payload or not isinstance(payload, dict):
            return None

        # DataMapper nests values: payload['values'][ind_code][country_code][year]
        try:
            values_root = payload.get("values", {}).get(ind_code, {})
            if not values_root:
                values_root = payload.get(ind_code, {}) # Fallback structure
        except Exception:
            return None

        if not values_root:
            return None

        observations = []
        for country_code, year_data in values_root.items():
            if not isinstance(year_data, dict):
                continue
                
            for year_str, value in year_data.items():
                try:
                    year_val = int(year_str)
                    if start_yr <= year_val <= end_yr and value is not None:
                        # Skip empty strings or non-numeric values
                        val_float = float(value)
                        observations.append({
                            "country_code": country_code.upper(),
                            "year":         year_val,
                            column_label:   val_float,
                        })
                except (ValueError, TypeError):
                    continue

        return pd.DataFrame(observations) if observations else None
