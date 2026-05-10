"""
World Bank Data Scraper
=======================
Retrieves comprehensive macroeconomic and social indicators from the World Bank Open Data API.
Includes indicators for remittances, GDP, population, labor, and development metadata.

Data Source: https://api.worldbank.org/v2
Documentation: https://datahelpdesk.worldbank.org/knowledgebase/articles/898581
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List
from .base import BaseScraper

# Constant for raw data storage
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"


class WorldBankScraper(BaseScraper):
    """
    Scraper implementation for World Bank API.
    Handles multi-indicator extraction with automated pagination and metadata mapping.
    """

    SOURCE_NAME = "world_bank"
    BASE_URL = "https://api.worldbank.org/v2"

    # Core indicators categorized by domain
    INDICATORS = {
        # Remittances Data
        "remittances_received_usd":   "BX.TRF.PWKR.CD.DT",
        "remittances_paid_usd":       "BM.TRF.PWKR.CD.DT",
        "remittances_pct_gdp":        "BX.TRF.PWKR.DT.GD.ZS",
        
        # Macroeconomic Indicators
        "gdp_usd":                    "NY.GDP.MKTP.CD",
        "gdp_per_capita_usd":         "NY.GDP.PCAP.CD",
        "gdp_growth_pct":             "NY.GDP.MKTP.KD.ZG",
        "gni_per_capita_usd":         "NY.GNP.PCAP.CD",
        "inflation_cpi_pct":          "FP.CPI.TOTL.ZG",
        "unemployment_pct":           "SL.UEM.TOTL.ZS",
        "current_account_pct_gdp":    "BN.CAB.XOKA.GD.ZS",
        
        # Demographics & Development
        "population_total":           "SP.POP.TOTL",
        "population_growth_pct":      "SP.POP.GROW",
        "urban_population_pct":       "SP.URB.TOTL.IN.ZS",
        # Remittances Detail
        "personal_remittances_recv":  "BX.TRF.PWKR.CD.DT",
        "personal_remittances_paid":  "BM.TRF.PWKR.CD.DT",
        "remittances_pct_gdp":        "BX.TRF.PWKR.DT.GD.ZS",
        "net_migration":              "SM.POP.NETM",
        "migrant_stock_total":        "SM.POP.TOTL",
        "refugee_pop_by_asylum":      "SM.POP.REFG",
        "refugee_pop_by_origin":      "SM.POP.REFG.OR",
        "poverty_headcount_pct":      "SI.POV.DDAY",
        "life_expectancy_years":      "SP.DYN.LE00.IN",
        
        # Costs & Financial Inclusion
        "avg_remittance_cost_pct":    "SI.RMT.COST.ZS",
        "remittance_cost_inward_pct":  "SI.RMT.COST.IB.ZS",
        "remittance_cost_outward_pct": "SI.RMT.COST.OB.ZS",
        "forex_reserves_usd":         "FI.RES.TOTL.CD",
        "fdi_inflows_usd":            "BX.KLT.DINV.CD.WD",
        "bank_branches_per_100k":     "FB.CBK.BRCH.P5",
        "atms_per_100k":              "FB.ATM.TOTL.P5",
        "mobile_money_accounts_pct":  "IT.MLT.MAIN.P2", # Proxy for mobile money
        
        # Findex (Financial Inclusion) - Every 3 years
        "received_remittances_pct":   "account.receive_remittances.t.e.15plus",
        "has_bank_account_pct":       "account.t.e.15plus",
        "saved_at_financial_inst_pct": "saved.t.e.15plus",
    }

    def scrape(self, start: int = 2000, end: int = 2023) -> pd.DataFrame:
        """
        Executes the full scraping sequence for all configured indicators.
        
        Args:
            start: The beginning year of the data range.
            end: The ending year of the data range.
            
        Returns:
            A consolidated DataFrame containing all retrieved indicators and metadata.
        """
        self.log.info(f"Initiating World Bank data sequence: {len(self.INDICATORS)} indicators for {start}-{end}")

        # Phase 1: Geographic Metadata Retrieval
        country_metadata = self._fetch_geographic_metadata()
        self.log.info(f"Synchronized metadata for {len(country_metadata)} geographic entities")

        # Phase 2: Indicator Data Extraction
        indicator_dataframes: List[pd.DataFrame] = []
        for col_name, indicator_code in self.INDICATORS.items():
            self.log.info(f"Extracting indicator: {col_name} [{indicator_code}]")
            df = self._fetch_indicator_paged(indicator_code, col_name, start, end)
            
            if df is not None and not df.empty:
                indicator_dataframes.append(df)
                self.log.info(f"  Captured {len(df):,} observations")
            else:
                self.log.warning(f"  No valid observations found for {col_name}")

        if not indicator_dataframes:
            self.log.error("Critical failure: No data points retrieved from World Bank API")
            return pd.DataFrame()

        # Phase 3: Data Consolidation & Enrichment
        self.log.info("Synthesizing multi-indicator dataset...")
        primary_keys = ["country_code", "year"]
        consolidated_df = indicator_dataframes[0]
        
        for next_df in indicator_dataframes[1:]:
            consolidated_df = consolidated_df.merge(next_df, on=primary_keys, how="outer")

        # Mapping metadata and standardizing fields
        consolidated_df["country_name"] = consolidated_df["country_code"].map(
            lambda x: country_metadata.get(x, {}).get("name", x)
        )
        consolidated_df["region"] = consolidated_df["country_code"].map(
            lambda x: country_metadata.get(x, {}).get("region", "Unknown")
        )
        consolidated_df["income_group"] = consolidated_df["country_code"].map(
            lambda x: country_metadata.get(x, {}).get("income_group", "Unknown")
        )
        consolidated_df["capital_city"] = consolidated_df["country_code"].map(
            lambda x: country_metadata.get(x, {}).get("capital", "Unknown")
        )
        consolidated_df["latitude"] = consolidated_df["country_code"].map(
            lambda x: country_metadata.get(x, {}).get("lat", 0.0)
        )
        consolidated_df["longitude"] = consolidated_df["country_code"].map(
            lambda x: country_metadata.get(x, {}).get("lon", 0.0)
        )
        consolidated_df["source_engine"] = "world_bank_v2"

        # Phase 4: Feature Engineering
        consolidated_df = consolidated_df.sort_values(["country_code", "year"])
        
        if "remittances_received_usd" in consolidated_df.columns and "population_total" in consolidated_df.columns:
            consolidated_df["remittances_per_capita_usd"] = (
                consolidated_df["remittances_received_usd"] / consolidated_df["population_total"]
            ).round(4)
            
        if "remittances_received_usd" in consolidated_df.columns:
            consolidated_df["remittances_growth_yoy"] = (
                consolidated_df.groupby("country_code")["remittances_received_usd"]
                .pct_change() * 100
            ).round(2)

        # Phase 5: Persistence
        consolidated_df = consolidated_df.sort_values(["country_name", "year"]).reset_index(drop=True)
        output_file = RAW_DATA_DIR / "worldbank_indicators.csv"
        consolidated_df.to_csv(output_file, index=False)
        
        self.log.info(f"World Bank sequence finalized. Persisted {len(consolidated_df):,} rows to {output_file.name}")
        return consolidated_df

    # ── Internal Implementation Details ──────────────────────────

    def _fetch_indicator_paged(self, indicator: str, column_label: str, 
                                start_yr: int, end_yr: int) -> Optional[pd.DataFrame]:
        """
        Internal utility for paginated indicator retrieval from the API.
        """
        observations = []
        current_page = 1

        while True:
            # Direct URL construction for better control over query parameters
            request_url = (
                f"{self.BASE_URL}/country/all/indicator/{indicator}"
                f"?format=json&date={start_yr}:{end_yr}&per_page=1000&page={current_page}"
            )
            
            payload = self.get_json(request_url)
            if not payload or not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
                break

            api_meta, api_records = payload[0], payload[1]
            for record in api_records:
                if record.get("value") is None:
                    continue
                observations.append({
                    "country_code": record["country"]["id"].upper(),
                    "year":         int(record["date"]),
                    column_label:   float(record["value"]),
                })

            if current_page >= api_meta.get("pages", 1):
                break
            current_page += 1

        return pd.DataFrame(observations) if observations else None

    def _fetch_geographic_metadata(self) -> Dict[str, Dict]:
        """
        Retrieves global country metadata from the World Bank registry.
        """
        registry_url = f"{self.BASE_URL}/country?format=json&per_page=500"
        response_data = self.get_json(registry_url)

        metadata_registry = {}
        if not response_data or not isinstance(response_data, list) or len(response_data) < 2:
            self.log.error("Unable to synchronize geographic metadata from World Bank registry")
            return metadata_registry

        for entity in response_data[1]:
            iso_code = entity.get("id", "").upper()
            if not iso_code or len(iso_code) != 3:
                continue
                
            metadata_registry[iso_code] = {
                "name":         entity.get("name", "Unknown"),
                "region":       entity.get("region", {}).get("value", "Unknown"),
                "income_group": entity.get("incomeLevel", {}).get("value", "Unknown"),
                "capital":      entity.get("capitalCity", "Unknown"),
                "lat":          float(entity["latitude"]) if entity.get("latitude") else 0.0,
                "lon":          float(entity["longitude"]) if entity.get("longitude") else 0.0,
            }
        return metadata_registry
