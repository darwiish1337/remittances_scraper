# M-D Remittances Intelligence Engine

![Python](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python)
![Pandas](https://img.shields.io/badge/Pandas-Latest-red?style=for-the-badge&logo=pandas)
![Status](https://img.shields.io/badge/Status-Research%20Preview-orange?style=for-the-badge)

A specialized data intelligence engine designed to collect and analyze global remittance data from the most reputable international sources. This project aims to provide a comprehensive dataset for researchers and financial analysts.

## Key Features
- **Automated Scraping:** Direct integration with World Bank, IMF, United Nations, and FRED.
- **Interactive CLI:** A user-friendly interface to select years, countries, and geographic regions.
- **Smart Merging:** Synthesizes all sources into a single file with automatic missing value imputation.
- **Comprehensive Coverage:** Includes over 40 economic and social indicators for every country.

## Data Sources
- **World Bank:** Macroeconomic indicators, migration, and financial inclusion.
- **IMF:** Inflation, sovereign debt, and GDP data.
- **RPW (World Bank):** Transaction costs for sending remittances across global corridors.
- **FRED (St. Louis Fed):** Currency exchange rates against the USD.
- **UN SDG (United Nations):** Sustainable Development Goal indicators related to remittances.

## Installation and Usage
1. Install the required libraries:
```bash
pip install -r requirements.txt
```
2. Run the program:
```bash
python main.py
```

## Project Structure
- `scrapers/`: Contains data scraping engines for each source.
- `data/raw/`: Stores the raw extracted data files.
- `data/merged/`: Contains the final synthesized file `master_remittances_dataset.csv`.
- `logs/`: Operation logs for tracking errors and technical details.

## Notes
- The project is currently in a Research Preview stage.
- Ensure an active internet connection for the APIs to function correctly.

---
Developed to support scientific research in international finance and migration.
