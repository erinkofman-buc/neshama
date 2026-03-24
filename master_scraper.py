import logging
#!/usr/bin/env python3
"""
Neshama Master Scraper
Runs all funeral home scrapers and manages scheduling
"""

import time
from datetime import datetime
import sys
import os

# Import individual scrapers (original 4 — Toronto + Montreal)
from steeles_scraper import SteelesScraper
from benjamins_scraper import BenjaminsScraper
from paperman_scraper import PapermanScraper
from misaskim_scraper import MisakimScraper
from database_setup import NeshamaDatabase

# Import city config and expansion scrapers
from city_config import CITIES

# Map of scraper type keywords to their scraper classes.
# When a city in city_config lists a scraper name here, the master
# scraper will automatically instantiate and run it.
EXPANSION_SCRAPER_REGISTRY = {}

try:
    from dignity_memorial_scraper import DignityMemorialScraper
    EXPANSION_SCRAPER_REGISTRY['dignity_memorial'] = DignityMemorialScraper
except ImportError:
    pass  # dignity_memorial_scraper not available


class MasterScraper:
    def __init__(self):
        # Original 4 scrapers — unchanged
        self.scrapers = [
            ('Steeles', SteelesScraper()),
            ('Benjamin\'s', BenjaminsScraper()),
            ('Paperman', PapermanScraper()),
            ('Misaskim', MisakimScraper())
        ]
        self.db = NeshamaDatabase()

    def run_all_scrapers(self):
        """Run all scrapers sequentially"""
        logging.info(f"\n{'='*70}")
        logging.info(f" NESHAMA MASTER SCRAPER")
        logging.info(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"{'='*70}\n")

        total_stats = {
            'scrapers_run': 0,
            'scrapers_succeeded': 0,
            'scrapers_failed': 0,
            'total_found': 0,
            'total_new': 0,
            'total_updated': 0
        }

        for name, scraper in self.scrapers:
            try:
                logging.info(f"\n▶ Starting {name} scraper...")
                stats = scraper.run()

                total_stats['scrapers_run'] += 1
                total_stats['scrapers_succeeded'] += 1
                total_stats['total_found'] += stats.get('found', 0)
                total_stats['total_new'] += stats.get('new', 0)
                total_stats['total_updated'] += stats.get('updated', 0)

            except Exception as e:
                total_stats['scrapers_run'] += 1
                total_stats['scrapers_failed'] += 1
                logging.info(f"\n❌ {name} scraper failed: {str(e)}\n")

                # Continue with next scraper even if one fails
                continue

        # ── Run expansion scrapers from city_config ──
        # These are cities that define scraper types in EXPANSION_SCRAPER_REGISTRY
        # (e.g. 'dignity_memorial' for South Florida, NYC, LA).
        for city_slug, city_cfg in CITIES.items():
            for scraper_key in city_cfg.get('scrapers', []):
                if scraper_key in EXPANSION_SCRAPER_REGISTRY:
                    scraper_cls = EXPANSION_SCRAPER_REGISTRY[scraper_key]
                    display = f"{scraper_key} ({city_cfg['display_name']})"
                    try:
                        logging.info(f"\n>> Starting expansion scraper: {display}...")
                        # Expansion scrapers with run_for_city() class method
                        if hasattr(scraper_cls, 'run_for_city'):
                            stats = scraper_cls.run_for_city(city_slug)
                        else:
                            # Fallback: instantiate directly
                            scraper_instance = scraper_cls(city_slug=city_slug)
                            stats = scraper_instance.run()

                        total_stats['scrapers_run'] += 1
                        total_stats['scrapers_succeeded'] += 1
                        total_stats['total_found'] += stats.get('found', 0)
                        total_stats['total_new'] += stats.get('new', 0)
                        total_stats['total_updated'] += stats.get('updated', 0)

                    except Exception as e:
                        total_stats['scrapers_run'] += 1
                        total_stats['scrapers_failed'] += 1
                        logging.info(f"\n!! {display} scraper failed: {str(e)}\n")
                        continue

        # Print summary
        logging.info(f"\n{'='*70}")
        logging.info(f" SUMMARY")
        logging.info(f"{'='*70}")
        logging.info(f" Scrapers run:      {total_stats['scrapers_run']}")
        logging.info(f" Succeeded:         {total_stats['scrapers_succeeded']}")
        logging.info(f" Failed:            {total_stats['scrapers_failed']}")
        logging.info(f" Total found:       {total_stats['total_found']}")
        logging.info(f" New obituaries:    {total_stats['total_new']}")
        logging.info(f" Updated:           {total_stats['total_updated']}")
        logging.info(f"{'='*70}\n")

        return total_stats

    def run_single_scraper(self, scraper_name):
        """Run a specific scraper by name"""
        scraper_name_lower = scraper_name.lower()

        # Check original 4 scrapers
        for name, scraper in self.scrapers:
            if name.lower().startswith(scraper_name_lower):
                logging.info(f"\nRunning {name} scraper...\n")
                stats = scraper.run()
                return stats

        # Check expansion scrapers (e.g. 'dignity_memorial')
        if scraper_name_lower in EXPANSION_SCRAPER_REGISTRY:
            scraper_cls = EXPANSION_SCRAPER_REGISTRY[scraper_name_lower]
            logging.info(f"\nRunning {scraper_name_lower} expansion scraper for all configured cities...\n")
            combined_stats = {'found': 0, 'new': 0, 'updated': 0, 'errors': 0}
            for city_slug, city_cfg in CITIES.items():
                if scraper_name_lower in city_cfg.get('scrapers', []):
                    if hasattr(scraper_cls, 'run_for_city'):
                        stats = scraper_cls.run_for_city(city_slug)
                    else:
                        stats = scraper_cls(city_slug=city_slug).run()
                    for k in combined_stats:
                        combined_stats[k] += stats.get(k, 0)
            return combined_stats

        available = ['steeles', 'benjamins', 'paperman', 'misaskim']
        available.extend(EXPANSION_SCRAPER_REGISTRY.keys())
        logging.info(f"Scraper '{scraper_name}' not found")
        logging.info(f"Available scrapers: {', '.join(available)}")
        return None

    def check_database_status(self):
        """Display current database statistics"""
        try:
            self.db.connect()

            # Count total obituaries
            self.db.cursor.execute('SELECT COUNT(*) FROM obituaries')
            total_obits = self.db.cursor.fetchone()[0]

            # Count by source
            self.db.cursor.execute('''
                SELECT source, COUNT(*)
                FROM obituaries
                GROUP BY source
            ''')
            by_source = self.db.cursor.fetchall()

            # Count total comments
            self.db.cursor.execute('SELECT COUNT(*) FROM comments')
            total_comments = self.db.cursor.fetchone()[0]

            # Recent obituaries
            self.db.cursor.execute('''
                SELECT deceased_name, source, last_updated
                FROM obituaries
                ORDER BY last_updated DESC
                LIMIT 5
            ''')
            recent = self.db.cursor.fetchall()

            # Last scraper runs
            self.db.cursor.execute('''
                SELECT source, run_time, status
                FROM scraper_log
                ORDER BY run_time DESC
                LIMIT 5
            ''')
            last_runs = self.db.cursor.fetchall()

            self.db.close()

            # Display stats
            logging.info(f"\n{'='*70}")
            logging.info(f" DATABASE STATUS")
            logging.info(f"{'='*70}")
            logging.info(f"\n Total obituaries:  {total_obits}")
            logging.info(f" Total comments:    {total_comments}\n")

            logging.info(f" By source:")
            for source, count in by_source:
                logging.info(f"   • {source}: {count}")

            if recent:
                logging.info(f"\n Most recent obituaries:")
                for name, source, updated in recent:
                    logging.info(f"   • {name} ({source})")
                    logging.info(f"     Updated: {updated}")

            if last_runs:
                logging.info(f"\n Last scraper runs:")
                for source, run_time, status in last_runs:
                    status_icon = "✅" if status == "success" else "❌"
                    logging.info(f"   {status_icon} {source}: {run_time}")

            logging.info(f"{'='*70}\n")

        except Exception as e:
            logging.info(f"❌ Error checking database: {str(e)}")

def main():
    """Main entry point"""
    master = MasterScraper()

    # Build list of all valid scraper commands
    core_scrapers = ['steeles', 'benjamins', 'paperman', 'misaskim']
    expansion_scrapers = list(EXPANSION_SCRAPER_REGISTRY.keys())
    all_scraper_names = core_scrapers + expansion_scrapers

    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == 'status':
            master.check_database_status()
        elif command in all_scraper_names:
            master.run_single_scraper(command)
        elif command == 'all':
            master.run_all_scrapers()
        else:
            logging.info("Usage: python master_scraper.py [command]")
            logging.info("\nCommands:")
            logging.info("  all              - Run all scrapers (default)")
            logging.info("  steeles          - Run Steeles scraper only")
            logging.info("  benjamins        - Run Benjamin's scraper only")
            logging.info("  paperman         - Run Paperman scraper only")
            logging.info("  misaskim         - Run Misaskim scraper only")
            for name in expansion_scrapers:
                logging.info(f"  {name:<16} - Run {name} expansion scraper")
            logging.info("  status           - Show database statistics")
    else:
        # Default: run all scrapers
        master.run_all_scrapers()

if __name__ == '__main__':
    main()
