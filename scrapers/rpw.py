"""
Remittance Prices Worldwide (RPW) Scraper
========================================
Extracts remittance cost data across global corridors from the World Bank RPW database.
Provides granular insights into total costs, fees, and foreign exchange margins.

Data Source: https://remittanceprices.worldbank.org
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List
from .base import BaseScraper

# Constant for raw data storage
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"


class RPWScraper(BaseScraper):
    """
    Scraper implementation for Remittance Prices Worldwide.
    Analyzes sending/receiving country corridors to determine average transaction costs.
    """

    SOURCE_NAME = "rpw"
    BASE_URL = "https://remittanceprices.worldbank.org"

    # Selection of high-volume global remittance corridors
    # Format: (Sending Country ISO-2, Receiving Country ISO-2)
    GLOBAL_CORRIDORS = [
        # North America Focus
        ("US", "MX"), ("US", "PH"), ("US", "IN"), ("US", "CN"), ("US", "VN"),
        ("US", "EG"), ("US", "NG"), ("US", "GH"), ("US", "PK"), ("US", "BD"),
        # Middle East Focus
        ("AE", "IN"), ("AE", "PK"), ("AE", "BD"), ("AE", "PH"), ("AE", "EG"),
        ("SA", "IN"), ("SA", "PK"), ("SA", "EG"), ("SA", "PH"), ("SA", "BD"),
        ("KW", "IN"), ("KW", "EG"), ("QA", "IN"), ("QA", "PH"),
        # Europe Focus
        ("GB", "IN"), ("GB", "PK"), ("GB", "NG"), ("GB", "PH"),
        ("DE", "TR"), ("DE", "PL"), ("DE", "RO"), ("FR", "MA"), ("FR", "SN"),
        ("IT", "RO"), ("ES", "MA"),
        # Asia & Pacific
        ("JP", "PH"), ("JP", "VN"), ("KR", "VN"), ("AU", "PH"), ("AU", "IN"),
        # Regional & CIS
        ("RU", "UZ"), ("RU", "KG"), ("RU", "TJ"), ("ZA", "ZW"), ("ZA", "MZ"),
    ]

    def scrape(self, start: int = 2010, end: int = 2023) -> pd.DataFrame:
        """
        Orchestrates the extraction of cost data using multiple fallback methods.
        """
        self.log.info(f"Initiating RPW cost synchronization for {start}-{end}")
        
        # Strategy 1: Direct indicator extraction via World Bank API (V2)
        # We'll try multiple indicators that might contain cost data
        cost_indicators = [
            "SI.RMT.COST.ZS",    # Average transaction cost of sending remittances (%)
            "SI.RMT.COST.IB.ZS", # Inward remittance cost
            "SI.RMT.COST.OB.ZS", # Outward remittance cost
        ]
        
        self.log.info(f"Attempting Strategy 1: World Bank API V2 for {len(cost_indicators)} indicators")
        all_cost_data = []
        for ind in cost_indicators:
            df = self._fetch_wdi_indicator(ind, start, end)
            if not df.empty:
                all_cost_data.append(df)
                self.log.info(f"  Captured {len(df)} records for {ind}")
        
        if all_cost_data:
            final_df = pd.concat(all_cost_data).drop_duplicates(subset=["receiving_country", "period"])
            self.log.info(f"  Strategy 1 Success: Total unique records: {len(final_df)}")
            output_file = RAW_DATA_DIR / "rpw_corridor_costs.csv"
            final_df.to_csv(output_file, index=False)
            return final_df

        # Strategy 2: Data360 API (Aggregate Costs)
        # Using a more robust Data360 endpoint
        self.log.info("Attempting Strategy 2: Data360 API (Alternative Endpoints)")
        # Indicator 448 is the most common for RPW in Data360
        data360_endpoints = [
            "https://data360api.worldbank.org/api/v1/data?indicatorId=448",
            "https://data360api.worldbank.org/api/v1/data?indicatorId=1393", # Another common cost indicator
        ]
        
        for url in data360_endpoints:
            payload = self.get_json(url)
            if payload and isinstance(payload, dict) and 'data' in payload:
                observations = []
                for entry in payload['data']:
                    try:
                        year = int(entry.get("year", 0))
                        if start <= year <= end:
                            observations.append({
                                "receiving_country": entry.get("countryISO3", entry.get("country", "")).upper(),
                                "period":            str(year),
                                "avg_total_cost_pct": entry.get("value"),
                                "source_engine":     "worldbank_data360"
                            })
                    except Exception: continue
                if observations:
                    df = pd.DataFrame(observations)
                    self.log.info(f"  Strategy 2 Success ({url}): Captured {len(df)} records")
                    output_file = RAW_DATA_DIR / "rpw_corridor_costs.csv"
                    df.to_csv(output_file, index=False)
                    return df

        # Strategy 3: Legacy Corridor Sync (Fallback)
        self.log.info("Attempting Strategy 3: Legacy Corridor Sync")
        consolidated_observations = []
        for sender, receiver in self.GLOBAL_CORRIDORS:
            corridor_data = self._fetch_corridor_intelligence(sender, receiver)
            if corridor_data:
                consolidated_observations.extend(corridor_data)
        
        if consolidated_observations:
            df = pd.DataFrame(consolidated_observations)
            df["source_engine"] = "rpw_worldbank_v1"
            output_file = RAW_DATA_DIR / "rpw_corridor_costs.csv"
            df.to_csv(output_file, index=False)
            return df

        self.log.error("Critical failure: All RPW strategies failed")
        return pd.DataFrame()

    # ── Internal Implementation Details ──────────────────────────

    def _fetch_wdi_indicator(self, indicator: str, start: int, end: int) -> pd.DataFrame:
        """
        Helper to fetch a specific indicator using World Bank V2 API.
        """
        observations = []
        url = f"https://api.worldbank.org/v2/country/all/indicator/{indicator}?format=json&date={start}:{end}&per_page=1000"
        
        payload = self.get_json(url)
        if payload and isinstance(payload, list) and len(payload) >= 2 and payload[1]:
            for record in payload[1]:
                if record.get("value") is not None:
                    observations.append({
                        "receiving_country": record["country"]["id"].upper(),
                        "period":            str(record["date"]),
                        "avg_total_cost_pct": float(record["value"]),
                        "source_engine":     "worldbank_api_v2"
                    })
        return pd.DataFrame(observations)

    def __init__(self, delay: float = 2.0, retries: int = 5):
        super().__init__(delay=delay, retries=retries)
        # RPW is sensitive, use a very specific browser-like header
        self.session.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://remittanceprices.worldbank.org/en/corridors",
            "X-Requested-With": "XMLHttpRequest"
        })

    def _fetch_corridor_intelligence(self, send: str, recv: str) -> List[Dict]:
        """
        Internal method to query RPW API endpoints with fallback logic.
        """
        # Attempt primary API endpoint
        api_url = f"{self.BASE_URL}/api/v1/corridors/{send.lower()}/{recv.lower()}"
        payload = self.get_json(api_url)
        
        # Fallback 1: JSON endpoint
        if not payload:
            api_url = f"{self.BASE_URL}/api/json/corridor"
            query_params = {"sc": send.lower(), "rc": recv.lower()}
            payload = self.get_json(api_url, params=query_params)

        # Fallback 2: Try Data360 API (World Bank's more modern data portal)
        if not payload:
            # Indicator 448 is "Average cost of sending $200"
            data360_url = f"https://data360api.worldbank.org/api/v1/data?indicatorId=448&countries={send},{recv}"
            payload = self.get_json(data360_url)
            if payload and isinstance(payload, dict) and 'data' in payload:
                # Transform data360 format to our expected format
                observations = []
                for entry in payload['data']:
                    observations.append({
                        "sending_country":   send.upper(),
                        "receiving_country": recv.upper(),
                        "corridor_id":       f"{send.upper()}->{recv.upper()}",
                        "period":            str(entry.get("year", "")),
                        "avg_total_cost_pct": entry.get("value"),
                        "source_engine":     "worldbank_data360"
                    })
                return observations

        # Fallback 3: Try with uppercase if lowercase failed
        if not payload:
            api_url = f"{self.BASE_URL}/api/v1/corridors/{send.upper()}/{recv.upper()}"
            payload = self.get_json(api_url)
            
        if not payload or not isinstance(payload, (dict, list)):
            return []

        observations = []
        # Support various API response structures (periods vs root list)
        data_points = payload.get("periods", []) if isinstance(payload, dict) else []
        if not data_points and isinstance(payload, list):
            data_points = payload
            
        for point in data_points:
            if not isinstance(point, dict):
                continue
                
            try:
                observations.append({
                    "sending_country":          send.upper(),
                    "receiving_country":        recv.upper(),
                    "corridor_id":              f"{send.upper()}->{recv.upper()}",
                    "period":                   str(point.get("period", point.get("quarter", ""))),
                    "avg_total_cost_pct":       self._to_float(point.get("avg_total_cost", point.get("avg_cost"))),
                    "avg_fee_usd":              self._to_float(point.get("avg_fee")),
                    "avg_fx_margin_pct":        self._to_float(point.get("avg_fx_margin")),
                    "service_provider_count":   self._to_int(point.get("num_services", 0)),
                    "min_cost_pct":             self._to_float(point.get("min_total_cost", point.get("min_cost"))),
                    "reference_amount_usd":     self._to_float(point.get("reference_amount")),
                })
            except Exception:
                continue
        return observations

    @staticmethod
    def _to_float(value) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
