"""
Master Dataset Integration Engine
================================
Synthesizes multiple raw data sources into a unified remittances intelligence dataset.
Implements robust filtering, missing value imputation, and geographic standardization.
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Module-level logger
logger = logging.getLogger("integration_engine")

# Data directory configuration
PROJECT_ROOT = Path(__file__).parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
MERGED_DIR = PROJECT_ROOT / "data" / "merged"
MERGED_DIR.mkdir(exist_ok=True)

def load_source_csv(file_name: str) -> Optional[pd.DataFrame]:
    """Safely loads a CSV file from the raw data repository."""
    path = RAW_DIR / file_name
    if path.exists():
        df = pd.read_csv(path)
        logger.info(f"Synchronized {file_name} | Observations: {len(df):,}")
        return df
    logger.warning(f"Required source not found: {file_name}")
    return None

def merge_master(filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """Orchestrates the synthesis of the master dataset with advanced filtering."""
    logger.info("Initiating master synthesis sequence...")

    # Phase 1: Base Dataset Initialization (World Bank)
    base_df = load_source_csv("worldbank_indicators.csv")
    if base_df is None:
        raise FileNotFoundError("Critical integration failure: Base dataset missing.")

    # Standardize types and clean primary keys (ISO code and Year)
    base_df["year"] = base_df["year"].astype(int)
    base_df = base_df.dropna(subset=["country_code"]).copy()
    base_df["country_code"] = base_df["country_code"].str.upper()

    # Fill critical gaps using cross-source intelligence
    # Example: Filling inflation gaps from IMF if World Bank data is missing
    imf_df = load_source_csv("imf_indicators.csv")
    if imf_df is not None:
        imf_df["year"] = imf_df["year"].astype(int)
        imf_df["country_code"] = imf_df["country_code"].str.upper()
        
        if "inflation_avg_pct" in imf_df.columns:
            inf_map = imf_df.set_index(["country_code", "year"])["inflation_avg_pct"].to_dict()
            base_df["inflation_cpi_pct"] = base_df.apply(
                lambda x: inf_map.get((x["country_code"], x["year"]), x["inflation_cpi_pct"]), axis=1
            )

    # Impute missing geographic metadata with default values
    metadata_fields = ["region", "income_group", "capital_city"]
    for field in metadata_fields:
        base_df[field] = base_df[field].fillna("Unknown")
    
    base_df["latitude"] = base_df["latitude"].fillna(0.0)
    base_df["longitude"] = base_df["longitude"].fillna(0.0)

    # Apply User-Defined Filtering from the CLI interface
    if filters:
        logger.info(f"Applying intelligent filters: {filters}")
        # Temporal filtering
        if "start_year" in filters and "end_year" in filters:
            base_df = base_df[
                (base_df["year"] >= filters["start_year"]) & 
                (base_df["year"] <= filters["end_year"])
            ]
        
        # Geographic filtering
        if filters.get("countries"):
            base_df = base_df[base_df["country_code"].isin([c.upper() for c in filters["countries"]])]
            
        # Regional filtering
        if filters.get("region"):
            base_df = base_df[base_df["region"].str.contains(filters["region"], case=False, na=False)]

    master_df = base_df.copy()
    logger.info(f"Integration base established: {master_df.shape}")

    # Phase 2: IMF Integration
    imf_df = load_source_csv("imf_indicators.csv")
    if imf_df is not None:
        imf_df["year"] = imf_df["year"].astype(int)
        imf_df["country_code"] = imf_df["country_code"].str.upper()
        
        # Merge only unique columns to prevent collision
        unique_cols = [c for c in imf_df.columns if c not in master_df.columns or c in ["country_code", "year"]]
        imf_subset = imf_df[unique_cols].drop_duplicates(subset=["country_code", "year"])
        
        master_df = master_df.merge(imf_subset, on=["country_code", "year"], how="left", suffixes=("", "_imf"))
        logger.info(f"IMF synthesis complete | New shape: {master_df.shape}")

    # Phase 3: FRED Financial Integration (FX Rates)
    fred_fx_df = load_source_csv("fred_exchange_rates.csv")
    if fred_fx_df is not None:
        fred_fx_df["date"] = pd.to_datetime(fred_fx_df["date"], errors="coerce")
        fred_fx_df["year"] = fred_fx_df["date"].dt.year
        
        # Aggregating daily/monthly rates to annual average
        fx_annual = (fred_fx_df.groupby(["currency", "year"])["fx_rate_vs_usd"]
                     .mean().reset_index()
                     .rename(columns={"fx_rate_vs_usd": "annual_avg_fx_rate"}))
        
        # Currency to ISO3 Mapping for global alignment
        iso_map = {
            "EGP":"EGY","MXN":"MEX","INR":"IND","PHP":"PHL","PKR":"PAK",
            "BDT":"BGD","NGN":"NGA","VND":"VNM","MAD":"MAR","EUR":"EMU",
            "GBP":"GBR","JPY":"JPN","SAR":"SAU","AED":"ARE","TRY":"TUR",
            "BRL":"BRA","ZAR":"ZAF","USA":"USA",
        }
        fx_annual["country_code"] = fx_annual["currency"].map(iso_map)
        fx_subset = fx_annual.dropna(subset=["country_code"])[
            ["country_code", "year", "annual_avg_fx_rate"]
        ].drop_duplicates(subset=["country_code", "year"])
        
        master_df = master_df.merge(fx_subset, on=["country_code", "year"], how="left")
        logger.info(f"FRED synthesis complete | New shape: {master_df.shape}")

    # Phase 4: RPW Cost Integration
    rpw_df = load_source_csv("rpw_corridor_costs.csv")
    if rpw_df is not None:
        # Transforming corridor data into country-level cost indices
        rpw_df["year"] = rpw_df["period"].str[:4].astype(int, errors="ignore")
        rpw_indices = (rpw_df.groupby(["receiving_country", "year"])
                       .agg(
                           avg_inbound_cost_pct=("avg_total_cost_pct", "mean"),
                           min_inbound_cost_pct=("min_cost_pct", "min"),
                       ).reset_index()
                       .rename(columns={"receiving_country": "iso2"}))
        
        # ISO2 to ISO3 normalization
        iso2_3_normalization = {
            "MX":"MEX","PH":"PHL","IN":"IND","CN":"CHN","VN":"VNM",
            "EG":"EGY","NG":"NGA","GH":"GHA","PK":"PAK","BD":"BGD",
            "MA":"MAR","TR":"TUR","PL":"POL","RO":"ROU","UZ":"UZB",
            "KG":"KGZ","TJ":"TJK","MD":"MDA","AE":"ARE","SA":"SAU",
            "ZA":"ZAF","ZW":"ZWE","MZ":"MOZ","LS":"LSO",
        }
        rpw_indices["country_code"] = rpw_indices["iso2"].map(iso2_3_normalization)
        rpw_subset = rpw_indices.dropna(subset=["country_code"])[
            ["country_code", "year", "avg_inbound_cost_pct", "min_inbound_cost_pct"]
        ].drop_duplicates(subset=["country_code", "year"])
        
        master_df = master_df.merge(rpw_subset, on=["country_code", "year"], how="left")
        logger.info(f"RPW synthesis complete | New shape: {master_df.shape}")

    # Phase 5: UN SDG Integration
    sdg_df = load_source_csv("un_sdg_indicators.csv")
    if sdg_df is not None:
        sdg_df["year"] = sdg_df["year"].astype(int)
        
        unique_cols = [c for c in sdg_df.columns if c not in master_df.columns or c in ["country_name", "year"]]
        sdg_subset = sdg_df[unique_cols].drop_duplicates(subset=["country_name", "year"])
        
        master_df = master_df.merge(sdg_subset, on=["country_name", "year"], how="left")
        logger.info(f"UN SDG synthesis complete | New shape: {master_df.shape}")

    # Phase 6: Final Cleansing & Standardization
    master_df = master_df.sort_values(["country_code", "year"])
    
    validation_targets = ["country_name", "region", "income_group"]
    for target in validation_targets:
        master_df[target] = master_df[target].fillna("Unknown")

    # Persistence of Integrated Dataset to data/merged directory
    master_output_path = MERGED_DIR / "master_remittances_dataset.csv"
    master_df.to_csv(master_output_path, index=False)
    
    logger.info(f"Master intelligence sequence finalized. Dataset available at: {master_output_path}")
    return master_df
