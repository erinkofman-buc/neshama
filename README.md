# NESHAMA BACKEND

Complete backend system for aggregating Jewish funeral home obituaries in Toronto.

## What's Included

- **database_setup.py** - SQLite database creation and management
- **steeles_scraper.py** - Scraper for Steeles Memorial Chapel
- **benjamins_scraper.py** - Scraper for Benjamin's Park Memorial Chapel
- **master_scraper.py** - Runs all scrapers and provides management commands
- **setup.sh** - One-command setup script
- **requirements.txt** - Python dependencies

## Quick Start

### 1. Run Setup (One Command)
```bash
chmod +x setup.sh
./setup.sh
```

### 2. Run Scrapers
```bash
# Run all scrapers
python3 master_scraper.py

# Run a specific scraper
python3 master_scraper.py steeles
python3 master_scraper.py benjamins

# Check database status
python3 master_scraper.py status
```

## Database

The system uses SQLite (`neshama.db`) with three tables:
- **obituaries** - All scraped obituary data
- **comments** - Condolence messages linked to obituaries
- **scraper_log** - Scraper run history for monitoring
