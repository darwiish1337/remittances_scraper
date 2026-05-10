"""
FRED Data Scraper (Federal Reserve Economic Data)
================================================
Extracts financial and macroeconomic data from the St. Louis Fed FRED API.
Focuses on exchange rates for major remittance-receiving countries and US macro indicators.

Data Source: https://fred.stlouisfed.org
Documentation: https://fred.stlouisfed.org/docs/api/fred/
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from io import StringIO
from .base import BaseScraper

# Constant for raw data storage
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"

# Optional API Key - fallback to CSV endpoints if not provided
FRED_API_KEY = ""


class FREDScraper(BaseScraper):
    """
    Scraper implementation for FRED.
    Provides automated extraction of currency exchange rates and US macroeconomic data.
    """

    SOURCE_NAME = "fred"
    BASE_URL = "https://api.stlouisfed.org/fred"

    # Mapping of currencies to FRED series IDs (USD base)
    FX_SERIES_MAP = {
        "EGP": "CCUSSP02EGM650N",   # Egypt
        "MXN": "DEXMXUS",           # Mexico
        "INR": "DEXINUS",           # India
        "PHP": "DEXPHIS",           # Philippines
        "PKR": "CCUSSP02PKM650N",   # Pakistan
        "BDT": "CCUSSP02BDM650N",   # Bangladesh
        "NGN": "CCUSSP02NGM650N",   # Nigeria
        "VND": "CCUSSP02VNM650N",   # Vietnam
        "MAD": "CCUSSP02MAM650N",   # Morocco
        "EUR": "DEXUSEU",           # Euro Area
        "GBP": "DEXUSUK",           # UK
        "JPY": "DEXJPUS",           # Japan
        "SAR": "DEXSAUS",           # Saudi Arabia
        "AED": "CCUSSP02AEM650N",   # UAE
        "TRY": "DEXTUR",            # Turkey
        "BRL": "DEXBZUS",           # Brazil
        "ZAR": "DEXSFUS",           # South Africa
    }

    # US macroeconomic indicators relevant to global remittance flows
    MACRO_SERIES_MAP = {
        "us_unemployment_rate":   "UNRATE",
        "us_inflation_cpi":       "CPIAUCSL",
        "us_fed_funds_rate":      "FEDFUNDS",
        "us_gdp_billions":        "GDP",
        "us_personal_income":     "PI",
    }

    def scrape(self, start_date: str = "2000-01-01", end_date: str = "2024-01-01") -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Orchestrates the scraping of both FX and Macro datasets from FRED.
        
        Args:
            start_date: Format 'YYYY-MM-DD'.
            end_date: Format 'YYYY-MM-DD'.
            
        Returns:
            A tuple containing (fx_dataframe, macro_dataframe).
        """
        self.log.info(f"Initiating FRED data sequence for period: {start_date} to {end_date}")

        fx_df = self._scrape_exchange_rates(start_date, end_date)
        macro_df = self._scrape_macro_indicators(start_date, end_date)

        # Persistence of individual datasets
        if not fx_df.empty:
            fx_output = RAW_DATA_DIR / "fred_exchange_rates.csv"
            fx_df.to_csv(fx_output, index=False)
            self.log.info(f"FRED FX sequence finalized: {len(fx_df):,} records persisted")

        if not macro_df.empty:
            macro_output = RAW_DATA_DIR / "fred_macro_usa.csv"
            macro_df.to_csv(macro_output, index=False)
            self.log.info(f"FRED Macro sequence finalized: {len(macro_df):,} records persisted")

        return fx_df, macro_df

    # ── Internal Implementation Details ──────────────────────────

    def _scrape_exchange_rates(self, start: str, end: str) -> pd.DataFrame:
        """Collects exchange rate data for all mapped currencies."""
        all_currency_dfs = []
        for currency, series_id in self.FX_SERIES_MAP.items():
            self.log.info(f"Extracting FX series: {currency} [{series_id}]")
            df = self._fetch_series_data(series_id, start, end)
            
            if df is not None:
                df["currency"] = currency
                df["series_id"] = series_id
                df = df.rename(columns={"value": "fx_rate_vs_usd"})
                all_currency_dfs.append(df)
            else:
                self.log.warning(f"  No valid FX data found for {currency}")

        return pd.concat(all_currency_dfs, ignore_index=True) if all_currency_dfs else pd.DataFrame()

    def _scrape_macro_indicators(self, start: str, end: str) -> pd.DataFrame:
        """Collects and merges US macroeconomic indicators."""
        indicator_dfs = []
        for col_name, series_id in self.MACRO_SERIES_MAP.items():
            self.log.info(f"Extracting Macro series: {col_name} [{series_id}]")
            df = self._fetch_series_data(series_id, start, end)
            
            if df is not None:
                df = df.rename(columns={"value": col_name})
                indicator_dfs.append(df)

        if not indicator_dfs:
            return pd.DataFrame()

        # Merge all macro series on date
        consolidated_macro = indicator_dfs[0]
        for next_df in indicator_dfs[1:]:
            consolidated_macro = consolidated_macro.merge(next_df, on="date", how="outer")

        consolidated_macro["source_engine"] = "fred_stlouisfed"
        return consolidated_macro

    def _fetch_series_data(self, series_id: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """Handles retrieval via either API or fallback CSV export."""
        # Use a fresh session for FRED to avoid connection reuse issues
        with requests.Session() as fred_session:
            # Add randomized delay to avoid rate limiting
            time.sleep(random.uniform(2.0, 5.0))
            
            # Use the base headers but rotate for each series
            from .base import get_random_headers
            fred_session.headers.update(get_random_headers())
            fred_session.headers.update({
                "Referer": "https://fred.stlouisfed.org/",
                "Origin": "https://fred.stlouisfed.org"
            })
            
            if FRED_API_KEY:
                request_url = f"{self.BASE_URL}/series/observations"
                params = {
                    "series_id":         series_id,
                    "api_key":           FRED_API_KEY,
                    "file_type":         "json",
                    "observation_start": start,
                    "observation_end":   end,
                }
                try:
                    response = fred_session.get(request_url, params=params, timeout=45)
                    response.raise_for_status()
                except Exception:
                    return None
            else:
                request_url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}&coed={end}"
                try:
                    response = fred_session.get(request_url, timeout=45)
                    response.raise_for_status()
                except Exception:
                    return None

            try:
                if FRED_API_KEY:
                    payload = response.json()
                    observations = payload.get("observations", [])
                    rows = []
                    for obs in observations:
                        try:
                            rows.append({"date": obs["date"], "value": float(obs["value"])})
                        except (ValueError, KeyError):
                            continue
                    return pd.DataFrame(rows) if rows else None
                else:
                    df = pd.read_csv(StringIO(response.text))
                    df.columns = ["date", "value"]
                    df["value"] = pd.to_numeric(df["value"], errors="coerce")
                    return df.dropna(subset=["value"])
            except Exception as err:
                self.log.error(f"Data parsing failed for series {series_id}: {err}")
                return None
