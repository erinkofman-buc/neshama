#!/bin/bash

# Neshama Backend Setup Script
# This script sets up the complete backend environment

echo "======================================================================"
echo " NESHAMA BACKEND SETUP"
echo "======================================================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    echo "Please install Python 3.8 or higher and try again"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed"
    echo "Please install pip3 and try again"
    exit 1
fi

echo "✅ pip3 found"
echo ""

# Install required Python packages
echo "Installing Python dependencies..."
echo "----------------------------------------------------------------------"

pip3 install --break-system-packages requests beautifulsoup4 lxml schedule 2>&1 | grep -v "Requirement already satisfied" || true

echo ""
echo "✅ Dependencies installed"
echo ""

# Initialize database
echo "Initializing database..."
echo "----------------------------------------------------------------------"

python3 database_setup.py

echo ""

# Create data directory for backups
echo "Creating backup directory..."
mkdir -p backups
echo "✅ Backup directory created"
echo ""

# Test scrapers (optional - comment out if you want to skip)
echo "Testing scrapers..."
echo "----------------------------------------------------------------------"
echo ""
echo "Would you like to run a test scrape now? (y/n)"
read -r response

if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo ""
    echo "Running test scrape..."
    python3 master_scraper.py all
else
    echo "Skipping test scrape"
fi

echo ""
echo "======================================================================"
echo " SETUP COMPLETE!"
echo "======================================================================"
echo ""
echo "Your Neshama backend is ready to use."
echo ""
echo "Next steps:"
echo "  1. Run scrapers manually:     python3 master_scraper.py"
echo "  2. Check database status:     python3 master_scraper.py status"
echo "  3. Run specific scraper:      python3 master_scraper.py steeles"
echo ""
echo "The database file 'neshama.db' has been created in this directory."
echo ""
echo "======================================================================"
