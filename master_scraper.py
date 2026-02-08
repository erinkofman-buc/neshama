#!/usr/bin/env python3
"""
Neshama Master Scraper
Runs all funeral home scrapers and manages scheduling
"""

import time
from datetime import datetime
import sys
import os

# Import individual scrapers
from steeles_scraper import SteelesScraper
from benjamins_scraper import BenjaminsScraper
from database_setup import NeshamaDatabase

class MasterScraper:
    def __init__(self):
        self.scrapers = [
            ('Steeles', SteelesScraper()),
            ('Benjamin\'s', BenjaminsScraper())
        ]
        self.db = NeshamaDatabase()

    def run_all_scrapers(self):
        """Run all scrapers sequentially"""
        print(f"\n{'='*70}")
        print(f" NESHAMA MASTER SCRAPER")
        print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

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
                print(f"\n▶ Starting {name} scraper...")
                stats = scraper.run()

                total_stats['scrapers_run'] += 1
                total_stats['scrapers_succeeded'] += 1
                total_stats['total_found'] += stats.get('found', 0)
                total_stats['total_new'] += stats.get('new', 0)
                total_stats['total_updated'] += stats.get('updated', 0)

            except Exception as e:
                total_stats['scrapers_run'] += 1
                total_stats['scrapers_failed'] += 1
                print(f"\n❌ {name} scraper failed: {str(e)}\n")

                # Continue with next scraper even if one fails
                continue

        # Print summary
        print(f"\n{'='*70}")
        print(f" SUMMARY")
        print(f"{'='*70}")
        print(f" Scrapers run:      {total_stats['scrapers_run']}")
        print(f" Succeeded:         {total_stats['scrapers_succeeded']}")
        print(f" Failed:            {total_stats['scrapers_failed']}")
        print(f" Total found:       {total_stats['total_found']}")
        print(f" New obituaries:    {total_stats['total_new']}")
        print(f" Updated:           {total_stats['total_updated']}")
        print(f"{'='*70}\n")

        return total_stats

    def run_single_scraper(self, scraper_name):
        """Run a specific scraper by name"""
        scraper_name_lower = scraper_name.lower()

        for name, scraper in self.scrapers:
            if name.lower().startswith(scraper_name_lower):
                print(f"\nRunning {name} scraper...\n")
                stats = scraper.run()
                return stats

        print(f"❌ Scraper '{scraper_name}' not found")
        print("Available scrapers: steeles, benjamins")
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
            print(f"\n{'='*70}")
            print(f" DATABASE STATUS")
            print(f"{'='*70}")
            print(f"\n Total obituaries:  {total_obits}")
            print(f" Total comments:    {total_comments}\n")

            print(f" By source:")
            for source, count in by_source:
                print(f"   • {source}: {count}")

            if recent:
                print(f"\n Most recent obituaries:")
                for name, source, updated in recent:
                    print(f"   • {name} ({source})")
                    print(f"     Updated: {updated}")

            if last_runs:
                print(f"\n Last scraper runs:")
                for source, run_time, status in last_runs:
                    status_icon = "✅" if status == "success" else "❌"
                    print(f"   {status_icon} {source}: {run_time}")

            print(f"{'='*70}\n")

        except Exception as e:
            print(f"❌ Error checking database: {str(e)}")

def main():
    """Main entry point"""
    master = MasterScraper()

    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == 'status':
            master.check_database_status()
        elif command in ['steeles', 'benjamins']:
            master.run_single_scraper(command)
        elif command == 'all':
            master.run_all_scrapers()
        else:
            print("Usage: python master_scraper.py [command]")
            print("\nCommands:")
            print("  all         - Run all scrapers (default)")
            print("  steeles     - Run Steeles scraper only")
            print("  benjamins   - Run Benjamin's scraper only")
            print("  status      - Show database statistics")
    else:
        # Default: run all scrapers
        master.run_all_scrapers()

if __name__ == '__main__':
    main()
