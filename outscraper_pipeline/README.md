# Neshama Vendor Pipeline

7-step pipeline to build the vendor directory from Google Maps data via Outscraper.

## Quick Start

```bash
# Step 1: Scrape Google Maps (requires Outscraper API key)
export OUTSCRAPER_API_KEY=your_key_here
python step1_scrape.py --category shiva --city toronto --dry-run  # preview
python step1_scrape.py --category shiva --city toronto            # run

# Step 2: Clean & deduplicate
python step2_clean.py --input data/step1_raw_shiva_toronto_*.csv

# ⏸ REVIEW cleaned CSV before continuing

# Steps 3-7: Run via Claude Code (enrichment, images, filters, areas)
# See agent: neshama-outscraper-pipeline

# Import to database
python import_vendors.py --input data/step7_directory_ready.csv --dry-run
python import_vendors.py --input data/step7_directory_ready.csv
```

## Prerequisites
```bash
pip install outscraper
```

## Cost
~$10-15 per category per city on Outscraper.
