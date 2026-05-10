"""
UN SDG Data Scraper
===================
Retrieves Sustainable Development Goal (SDG) indicators related to remittances and migration.
Focuses on Goal 10.c.1 (Remittance costs).

Data Source: https://unstats.un.org/SDGAPI/v1
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List
from .base import BaseScraper

# Constant for raw data storage
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"

class UNSDGScraper(BaseScraper):
    """
    Scraper for UN SDG API.
    """
    SOURCE_NAME = "un_sdg"
    BASE_URL = "https://unstats.un.org/SDGAPI/v1"

    # Important SDG indicators for remittances/migration
    INDICATORS = {
        "remittance_cost_pct": "SI_RMT_COST", # Goal 10.c.1
        "recruitment_cost_pct": "SI_RMT_RECR", # Recruitment cost borne by employee
    }

    def scrape(self, start: int = 2010, end: int = 2023) -> pd.DataFrame:
        self.log.info(f"Initiating UN SDG data sequence for {start}-{end}")
        
        all_data = []
        for col_name, series_code in self.INDICATORS.items():
            self.log.info(f"Extracting SDG Series: {series_code}")
            # Correct endpoint for Series Data
            request_url = f"{self.BASE_URL}/sdg/Series/{series_code}/GeoAreas" # First get areas
            
            areas_payload = self.get_json(request_url)
            if not areas_payload or not isinstance(areas_payload, list):
                # Fallback to direct data call if geoareas fails
                request_url = f"{self.BASE_URL}/sdg/Series/Data?seriesCode={series_code}"
            else:
                # Use a more reliable way to get data if we have areas
                request_url = f"{self.BASE_URL}/sdg/Series/Data?seriesCode={series_code}&pageSize=1000"

            payload = self.get_json(request_url)
            self.log.info(f"  API Response received for {series_code}")
            
            # UN SDG API structure is often: payload['data'] directly or inside a list
            data_list = []
            if isinstance(payload, dict):
                data_list = payload.get('data', [])
            elif isinstance(payload, list) and len(payload) > 0:
                data_list = payload[0].get('data', [])
            
            if not data_list and isinstance(payload, list):
                # Sometimes the list itself contains the data points
                data_list = payload

            if not data_list:
                self.log.warning(f"  No data found for SDG series {series_code}. Payload type: {type(payload)}")
                continue

            captured_for_series = 0
            for entry in data_list:
                try:
                    # Handle multiple possible keys for year and value
                    year_str = entry.get('timePeriodStart', entry.get('timeDetail', entry.get('year', '0')))
                    year = int(year_str)
                    
                    value = entry.get('value', entry.get('obsValue'))
                    
                    if start <= year <= end and value is not None:
                        all_data.append({
                            "country_code": entry.get('geoAreaCode', entry.get('spatial')),
                            "country_name": entry.get('geoAreaName', entry.get('location')),
                            "year": year,
                            col_name: float(value),
                            "source_engine": "un_sdg_api"
                        })
                        captured_for_series += 1
                except (ValueError, TypeError):
                    continue
            
            self.log.info(f"  Captured {captured_for_series} observations for {series_code}")
        
        if not all_data:
            self.log.error("No data retrieved from UN SDG API")
            return pd.DataFrame()
            
        df = pd.DataFrame(all_data)
        output_file = RAW_DATA_DIR / "un_sdg_indicators.csv"
        df.to_csv(output_file, index=False)
        self.log.info(f"UN SDG sequence finalized: {len(df)} records persisted")
        return df
