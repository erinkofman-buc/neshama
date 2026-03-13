import logging
#!/usr/bin/env python3
"""
Neshama Vendor Directory - Seed Script
Creates vendors and vendor_leads tables, populates with Toronto and Montreal food vendors.
Run: python seed_vendors.py
"""

import sqlite3
import os
import re
from datetime import datetime

DB_PATH = os.environ.get('DATABASE_PATH', 'neshama.db')

# Vendors to remove from DB (permanently closed)
VENDORS_TO_REMOVE = [
    "My Zaidy's Pizza",       # Closed Jan 2026
    "Yehudales Falafel and Pizza",  # Closed Dec 2025
    "Pizza Pita",             # No longer exists per Jordana Mar 2026
    "Shwarma Express",        # No longer exists per Jordana Mar 2026
    "Pita Box",               # No longer exists per Jordana Mar 2026
    "Miami Grill",            # No longer exists per Jordana Mar 9
    "Village Pizza Kosher",   # No longer exists per Jordana Mar 9
    "Citrus Traiteur",        # Removed per Jordana Mar 9
    "24-Hour Yahrzeit Memorial Candles (Multipack)",  # Removed per Jordana Mar 9
    "Bubby's New York Bagels",  # Duplicate of Bubby's Bagels
]


def slugify(name):
    """Convert vendor name to URL slug"""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def create_tables(conn):
    """Create vendors and vendor_leads tables"""
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            vendor_type TEXT DEFAULT 'food',
            description TEXT,
            address TEXT,
            neighborhood TEXT,
            phone TEXT,
            website TEXT,
            kosher_status TEXT DEFAULT 'not_certified',
            delivery INTEGER DEFAULT 0,
            delivery_area TEXT,
            image_url TEXT,
            featured INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_vendor_slug ON vendors(slug)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_vendor_category ON vendors(category)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_vendor_kosher ON vendors(kosher_status)
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendor_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            vendor_name TEXT,
            contact_name TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            event_type TEXT,
            event_date TEXT,
            estimated_guests INTEGER,
            message TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_leads_vendor ON vendor_leads(vendor_id)
    ''')

    # Migration: add vendor_type column if missing
    try:
        cursor.execute('SELECT vendor_type FROM vendors LIMIT 1')
    except Exception:
        cursor.execute("ALTER TABLE vendors ADD COLUMN vendor_type TEXT DEFAULT 'food'")

    # Migration: add delivery_area column if missing
    try:
        cursor.execute('SELECT delivery_area FROM vendors LIMIT 1')
    except Exception:
        cursor.execute("ALTER TABLE vendors ADD COLUMN delivery_area TEXT")

    # Migration: add email column if missing
    try:
        cursor.execute('SELECT email FROM vendors LIMIT 1')
    except Exception:
        cursor.execute("ALTER TABLE vendors ADD COLUMN email TEXT")

    # Migration: add instagram column if missing
    try:
        cursor.execute('SELECT instagram FROM vendors LIMIT 1')
    except Exception:
        cursor.execute("ALTER TABLE vendors ADD COLUMN instagram TEXT")

    # Create vendor_clicks table for click tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendor_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_slug TEXT NOT NULL,
            destination_url TEXT,
            referrer_page TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_clicks_vendor ON vendor_clicks(vendor_slug)
    ''')

    # Create vendor_views table for page view tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendor_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_slug TEXT NOT NULL,
            referrer_page TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_views_vendor ON vendor_views(vendor_slug)
    ''')

    conn.commit()


# 53 Toronto-area food vendors
VENDORS = [
    # Bagel Shops / Bakeries
    {
        'name': 'What A Bagel',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Toronto institution serving fresh-baked bagels, spreads, and deli platters. Multiple locations across the GTA. Great for shiva breakfast platters and bagel trays.',
        'address': '2900 Steeles Ave W, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 738-9888',
        'website': 'https://www.whatabagel.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
    },
    {
        'name': 'Gryfe\'s Bagel Bakery',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Legendary Toronto bagel bakery since 1915. Famous for their hand-rolled, kettle-boiled bagels. A community staple for over a century.',
        'address': '3421 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 783-1552',
        'website': 'https://www.gryfes.ca',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Kiva\'s Bagels',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Fresh bagels and baked goods in the heart of the Jewish community. Known for their challah, rugelach, and deli-style platters.',
        'address': '1027 Steeles Ave W, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 663-9933',
        'website': 'https://kivasbagels.ca',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Hermes Bakery',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Full-service kosher bakery offering cakes, pastries, challah, and dessert platters. Perfect for shiva dessert trays and Shabbat baking.',
        'address': '3489 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 781-1156',
        'website': 'http://hermesbakery.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'United Bakers Dairy Restaurant',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Iconic Toronto dairy restaurant and bakery since 1912. Famous for their blintzes, pierogies, and homestyle Jewish comfort food.',
        'address': '506 Lawrence Ave W, Toronto, ON',
        'neighborhood': 'Lawrence Park',
        'phone': '(416) 789-0519',
        'website': 'https://www.unitedbakers.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    # Kosher Restaurants & Caterers
    {
        'name': 'Jem Salads',
        'category': 'Restaurants & Delis',
        'description': 'Fresh, wholesome salad platters and prepared meals with generous portions. Great option for lighter shiva meals. Platters for 10-50+ guests with flexible delivery timing.',
        'address': '441 Clark Ave W, Toronto, ON',
        'neighborhood': 'North York',
        'phone': '(416) 886-1804',
        'email': 'jem.salads@gmail.com',
        'website': 'https://www.jemsalads.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA',
        'featured': 0,
    },
    {
        'name': 'Bistro Grande',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Upscale kosher dining and catering. Offers elegant plated meals, buffet setups, and family-style dinners suitable for shiva gatherings.',
        'address': '1000 Eglinton Ave W, Toronto, ON',
        'neighborhood': 'Forest Hill',
        'phone': '(416) 782-3302',
        'website': 'https://bistrogrande.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    # Miami Grill — REMOVED Mar 9 (no longer exists, per Jordana)

    {
        'name': 'Tov-Li Pizza & Falafel',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Kosher pizza, falafel, and Israeli favourites. Great for casual shiva meals and feeding a crowd on a budget. Party trays available.',
        'address': '3457 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 782-2522',
        'website': 'https://tov-li.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Matti\'s Kitchen',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Home-style kosher cooking with a modern twist. Specializes in comforting meals perfect for shiva — soups, stews, roasted chicken, and side dishes.',
        'address': '3006 Bathurst St, Toronto, ON',
        'neighborhood': 'Lawrence Heights',
        'phone': '(416) 792-0606',
        'website': 'https://bistrogrande.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'The Chicken Nest',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Glatt kosher restaurant and caterer serving Toronto for over 30 years. Known for rotisserie chicken, ribs, schnitzel, wings, and Middle Eastern dishes. Dedicated catering menu for shiva, Shabbos, and events. Delivery and takeout available.',
        'address': '3038 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 787-6378',
        'website': 'https://thechickennest.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
    },
    {
        'name': "Milk 'N Honey",
        'category': 'Kosher Restaurants & Caterers',
        'description': "Toronto's longest-serving kosher dairy caterer. Specializing in shiva meals, Shabbat catering, and lifecycle events. COR dairy certified.",
        'address': '3457 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 789-7651',
        'website': 'https://milknhoney.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
    },
    {
        'name': 'Kosher Gourmet',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'COR-certified kosher catering specializing in shiva meals. Delivery available across Toronto and the GTA. Known for quality prepared meals and reliable service.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '(416) 781-9900',
        'website': 'https://koshergourmet.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
    },
    {
        'name': 'Yummy Market',
        'category': 'Caterers',
        'description': 'European food grocer with an extensive prepared foods section, scratch-made kitchen, and patisserie. Hot meals, salad bar, deli counter, and catering platters for any size gathering.',
        'address': '4400 Dufferin St, North York, ON',
        'neighborhood': 'North York',
        'phone': '(416) 665-0040',
        'website': 'https://yummymarket.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': "Daiter's Kitchen",
        'category': 'Kosher Restaurants & Caterers',
        'description': 'COR-certified kosher deli and butcher shop. Deli platters, prepared meats, and classic comfort food. A go-to for shiva deli trays.',
        'address': '3535 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 789-1280',
        'website': 'https://www.daiterskitchen.ca',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Orly\'s Kitchen',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Homestyle kosher Israeli and Mediterranean cooking. Fresh salads, grilled meats, and hearty mains. Catering available for shiva meals.',
        'address': '3413 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 792-0052',
        'website': 'http://hermesbakery.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Cafe Sheli',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Kosher dairy cafe offering light meals, salads, fish dishes, and baked goods. Ideal for lighter shiva lunches and dessert platters.',
        'address': '4750 Dufferin St, Toronto, ON',
        'neighborhood': 'North York',
        'phone': '(416) 663-5553',
        'website': 'https://cafesheli.com',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
    },
    # Caterers (dedicated catering companies)
    {
        'name': 'Main Event Catering',
        'category': 'Caterers',
        'description': 'Experienced kosher caterer handling events from 20 to 500 guests. Full-service catering including staff, setup, and rentals. Known for reliability and quality.',
        'address': 'Thornhill, ON',
        'neighborhood': 'GTA-wide',
        'phone': '(905) 881-2222',
        'website': 'https://maineventmauzone.shop',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': 'Sonny Langers Dairy & Vegetarian Caterers',
        'category': 'Caterers',
        'description': 'Full-service dairy and vegetarian catering since 1985. Dedicated shiva menu includes smoked salmon, egg salad, bagels, fruit display, coffee service, and baked goods. Minimum 10 people.',
        'address': '180 Steeles Ave W Unit 12, Thornhill ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 881-4356',
        'website': 'http://www.sonnylangers.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York,Thornhill/Vaughan,Hamilton,GTA',
    },
    # Italian
    # Village Pizza Kosher — REMOVED Mar 9 (no longer exists, per Jordana)

    # Pizza Pita — REMOVED (no longer exists, per Jordana Mar 2026)
    {
        'name': 'Paisanos',
        'category': 'Italian',
        'description': 'Italian restaurant with catering services. Pasta trays, chicken parmigiana, Caesar salads, and tiramisu. Generous portions for family-style meals.',
        'address': '624 College St, Toronto, ON',
        'neighborhood': 'Little Italy',
        'phone': '(416) 534-2801',
        'website': 'https://thepaisanos.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    {
        'name': 'Terroni',
        'category': 'Italian',
        'description': 'Beloved Toronto Italian restaurant group. Offers catering with authentic pasta, antipasti platters, and rustic Italian dishes. Multiple locations.',
        'address': '720 Queen St W, Toronto, ON',
        'neighborhood': 'Queen West',
        'phone': '(416) 504-0320',
        'website': 'https://www.terroni.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    {
        'name': 'Tutto Pronto',
        'category': 'Italian',
        'description': 'Modern southern Italian catering in North York. Known for arancini, pasta, veal, eggplant parm, and fresh salads. Popular for shiva in the Avenue Rd corridor. All food prepared fresh day-of.',
        'address': '1718 Avenue Rd, North York ON',
        'neighborhood': 'North York',
        'phone': '(416) 782-2227',
        'website': 'https://tuttopronto.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
    # Middle Eastern / Israeli
    {
        'name': 'Wok & Bowl',
        'category': 'Kosher Restaurants & Caterers',
        'description': "Toronto's first COR-certified kosher pho and ramen restaurant. Asian fusion including Chinese dishes, dumplings, noodles, and fried rice. Catering available. Great option for families who want something different at shiva.",
        'address': '3022 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 783-2323',
        'website': 'https://wokandbowl.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
    },
    {
        'name': 'Dr. Laffa',
        'category': 'Middle Eastern & Israeli',
        'description': 'Popular Israeli restaurant serving fresh laffa wraps, shawarma, hummus, and Middle Eastern platters. Great for casual, flavourful shiva meals.',
        'address': '3027 Bathurst St, Toronto, ON',
        'neighborhood': 'Lawrence Heights',
        'phone': '(416) 792-8989',
        'website': 'https://drlaffa.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Aish Tanoor',
        'category': 'Middle Eastern & Israeli',
        'description': 'Authentic Iraqi-Jewish cuisine. Homestyle cooking including kubba, t\'beet, and traditional Iraqi dishes. A unique and comforting option for the community. Catering and delivery available.',
        'address': '994 Eglinton Ave W, Toronto, ON',
        'neighborhood': 'Forest Hill',
        'phone': '(647) 352-5535',
        'website': 'https://aishtanoor.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    {
        'name': 'Parallel',
        'category': 'Middle Eastern & Israeli',
        'description': 'Modern Israeli-Mediterranean restaurant with vibrant salads, grilled meats, and creative mezze. Offers catering platters that are colourful and delicious.',
        'address': '3268 Yonge St, Toronto, ON',
        'neighborhood': 'Lawrence Park',
        'phone': '(416) 488-7700',
        'website': 'https://www.parallelrestaurant.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    # Shwarma Express — REMOVED (no longer exists, per Jordana Mar 2026)
    {
        'name': 'Me-Va-Me',
        'category': 'Middle Eastern & Israeli',
        'description': 'Israeli grill and shawarma with generous portions and bold flavours. Family meal combos and party platters available. Multiple GTA locations.',
        'address': '7241 Bathurst St, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 889-5559',
        'website': 'https://www.mevame.com/',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
    },
    # Pita Box — REMOVED (no longer exists, per Jordana Mar 2026)
    # ── New vendors added per Jordana feedback — Mar 2026 ──
    # My Zaidy's Pizza — removed Mar 2026 (permanently closed per Yelp Jan 2026)
    # More diverse options
    {
        'name': 'Sushi Inn',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Kosher sushi and Japanese-inspired cuisine. Sushi platters and bento boxes are a refreshing alternative for shiva meals. Party trays available.',
        'address': '3461 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 792-0004',
        'website': 'https://www.sushiinn.net/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Summerhill Market',
        'category': 'Caterers',
        'description': 'Premium Toronto grocer and caterer. Beautifully prepared platters, entrees, and desserts. Known for high-quality ingredients and elegant presentation.',
        'address': '446 Summerhill Ave, Toronto, ON',
        'neighborhood': 'Summerhill',
        'phone': '(416) 921-1714',
        'website': 'https://www.summerhillmarket.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    {
        'name': 'Pickle Barrel',
        'category': 'Caterers',
        'description': 'Large-format restaurant with extensive catering menu. Sandwich platters, salads, hot entrees, and dessert trays. Reliable for feeding large groups.',
        'address': '2901 Bayview Ave, Toronto, ON',
        'neighborhood': 'Bayview Village',
        'phone': '(416) 221-0200',
        'website': 'https://www.picklebarrel.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Harbord Bakery',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Beloved neighbourhood bakery with Jewish roots. Famous challah, rye bread, rugelach, and pastries. A Toronto classic since 1945.',
        'address': '115 Harbord St, Toronto, ON',
        'neighborhood': 'Harbord Village',
        'phone': '(416) 922-5767',
        'website': 'https://www.harbordbakery.ca/',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Centre Street Deli',
        'category': 'Restaurants & Delis',
        'description': 'Classic Jewish deli in Thornhill since 1988. Montreal-style smoked meat, corned beef, matzo ball soup, and all the deli favourites. Catering platters and party trays available.',
        'address': '1136 Centre St, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 731-8037',
        'website': 'https://www.centrestreetdeli.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York,Toronto',
    },
    {
        'name': 'Nortown Foods',
        'category': 'Caterers',
        'description': 'Premium grocer with full catering services, butcher shop, and prepared foods counter. Hot meals, salads, deli platters, and baked goods. Over 50 years serving the Toronto Jewish community.',
        'address': '892 Eglinton Ave W, Toronto, ON',
        'neighborhood': 'Eglinton West',
        'phone': '(416) 789-2921',
        'website': 'https://www.nortownfoods.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'featured': 1,
    },
    {
        'name': 'Cheese Boutique',
        'category': 'Caterers',
        'description': 'World-renowned artisanal cheese shop and gourmet caterer. Stunning cheese boards, charcuterie, and gift baskets. A premium, thoughtful gift for a shiva home.',
        'address': '45 Ripley Ave, Toronto, ON',
        'neighborhood': 'Liberty Village',
        'phone': '(416) 762-6292',
        'website': 'https://www.cheeseboutique.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    # Additional vendors — Feb 2026
    {
        'name': 'The Food Dudes',
        'category': 'Caterers',
        'description': 'Full-service catering company known for creative menus and polished events. From intimate dinners to large gatherings of 2,000+, they handle everything including food trucks and corporate catering.',
        'address': '24 Carlaw Ave, Unit 2, Toronto, ON',
        'neighborhood': 'Leslieville',
        'phone': '(647) 340-3833',
        'website': 'https://thefooddudes.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': "Pusateri's Fine Foods",
        'category': 'Caterers',
        'description': "Toronto's premier gourmet grocer and caterer. Beautifully prepared platters, artisan cheeses, charcuterie, and catered meals for any occasion. Avenue Road flagship at Lawrence.",
        'address': '1539 Avenue Rd, Toronto, ON',
        'neighborhood': 'Lawrence Park',
        'phone': '(416) 785-9100',
        'website': 'https://www.pusateris.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    {
        'name': 'Schmaltz Appetizing',
        'category': 'Restaurants & Delis',
        'description': 'Jewish-style appetizing shop specializing in smoked fish, bagel sandwiches, cream cheeses, and deli platters. Catering for groups of 10+. A modern take on classic Jewish comfort food.',
        'address': '414 Dupont St, Toronto, ON',
        'neighborhood': 'Annex',
        'phone': '(647) 350-4261',
        'website': 'https://schmaltzappetizing.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Whole Foods Market Yorkville',
        'category': 'Caterers',
        'description': 'Full-service grocery with catering platters, prepared foods, and party trays. Fresh fruit, cheese boards, sandwich platters, and hot entrees for any size gathering.',
        'address': '87 Avenue Rd, Toronto, ON',
        'neighborhood': 'Yorkville',
        'phone': '(416) 944-0500',
        'website': 'https://www.wholefoodsmarket.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    {
        'name': 'Paramount Fine Foods',
        'category': 'Middle Eastern & Israeli',
        'description': 'Lebanese and Middle Eastern restaurant group with multiple Toronto locations. Catering for corporate and social events with customizable packages. Generous platters of shawarma, grilled meats, and mezze.',
        'address': '10 Four Seasons Pl, Suite 601, Toronto, ON',
        'neighborhood': 'GTA-wide',
        'phone': '(416) 695-8900',
        'website': 'https://paramountfinefoods.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    # Beloved Toronto Restaurants & Non-Kosher Caterers
    {
        'name': 'Scaramouche Restaurant',
        'category': 'Restaurants & Delis',
        'description': "Iconic Toronto fine dining restaurant with sweeping city views since 1980. Celebrated for impeccable cuisine and legendary coconut cream pie. Off-site catering available through Scaramouche Catering.",
        'address': '1 Benvenuto Pl, Toronto, ON',
        'neighborhood': 'Summerhill',
        'phone': '(416) 961-8011',
        'website': 'https://www.scaramoucherestaurant.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Daniel et Daniel Catering',
        'category': 'Caterers',
        'description': "One of Toronto's most respected catering companies for over 35 years. Elegant, seasonal menus for private events, corporate functions, and celebrations. Known for exceptional quality and polished service.",
        'address': '248 Carlton St, Toronto, ON',
        'neighborhood': 'Cabbagetown',
        'phone': '(416) 968-9275',
        'website': 'https://www.danieletdaniel.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': 'McEwan Fine Foods',
        'category': 'Caterers',
        'description': "Chef Mark McEwan's gourmet food shop and catering service. Premium prepared meals, charcuterie, cheese, and catering platters. A go-to for high-quality meals and entertaining.",
        'address': '788 Don Mills Rd, Toronto, ON',
        'neighborhood': 'Don Mills',
        'phone': '(416) 421-6900',
        'website': 'https://www.mcewangroup.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': "Longo's",
        'category': 'Caterers',
        'description': "Family-owned Italian grocery chain with full-service catering. Sandwich platters, pasta trays, hot meals, fruit and cheese boards. Reliable catering at multiple GTA locations.",
        'address': 'Multiple GTA locations',
        'neighborhood': 'GTA-wide',
        'phone': '(905) 264-4892',
        'website': 'https://www.longos.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': "Cumbrae's",
        'category': 'Caterers',
        'description': "Premium Toronto butcher offering sustainably sourced meats and gourmet prepared foods. Heat-and-serve dinners, charcuterie boards, and meal packages. A thoughtful, high-quality option for feeding a household.",
        'address': '481 Church St, Toronto, ON',
        'neighborhood': 'Church-Wellesley',
        'phone': '(416) 923-5600',
        'website': 'https://www.cumbraes.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    # ── New verified vendors — Feb 2026 (Sprint 6) ──
    {
        'name': "Ely's Fine Foods",
        'category': 'Kosher Restaurants & Caterers',
        'description': 'COR-certified kosher grocery, deli, and caterer serving the Toronto Jewish community since 1993. Fresh daily prepared foods, deli counter, retail store, and full catering services. Available on DoorDash.',
        'address': '3537A Bathurst St, North York, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 782-3231',
        'website': 'https://elysfinefoods.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Grodzinski Bakery',
        'category': 'Bagel Shops & Bakeries',
        'description': 'One of Toronto\'s oldest kosher bakeries, operating since 1888. Famous for challah, pastries, and sandwich platters. Completely nut-free facility. Two locations: Bathurst St and Thornhill.',
        'address': '3437 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 789-0785',
        'website': 'https://www.grodzinskibakery.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Ba-Li Laffa',
        'category': 'Middle Eastern & Israeli',
        'description': 'COR-certified kosher Israeli/Mediterranean restaurant known for fresh-baked laffas, falafel, shawarma, kebabs, and hummus. Also serves Asian-fusion dishes. Delivery via DoorDash and SkipTheDishes.',
        'address': '7117 Bathurst St, Unit 110, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 597-7720',
        'website': 'https://www.balilaffa.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
    },
    {
        'name': 'PRC Caterers',
        'category': 'Caterers',
        'description': 'Toronto\'s leading COR-certified kosher full-service caterer with 15+ years of experience. Specializes in shiva meals, weddings, bar/bat mitzvahs, corporate events, and Shabbat dinners. Retail products available at select locations.',
        'address': '4478 Chesswood Dr, Unit 4, Toronto, ON',
        'neighborhood': 'North York',
        'phone': '(416) 787-9889',
        'website': 'https://prccaterers.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': 'Beyond Delish',
        'category': 'Caterers',
        'description': 'Boutique COR-certified kosher catering and takeout. Stylish, seasonal gourmet prepared meals with customized menus for shiva, intimate dinners, corporate events, and celebrations.',
        'address': '9699 Bathurst St, Richmond Hill, ON',
        'neighborhood': 'Richmond Hill',
        'phone': '(905) 884-7700',
        'website': 'https://www.beyonddelish.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': 'Marron Bistro',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Upscale COR-certified kosher fine dining in Forest Hill. Globally-inspired meat and fish dishes. Often called the best kosher restaurant in Canada. Elegant option for catered shiva meals.',
        'address': '992 Eglinton Ave W, Toronto, ON',
        'neighborhood': 'Forest Hill',
        'phone': '(416) 784-0128',
        'website': 'https://www.marronbistro.com',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
    },
    # ── New vendors added Mar 9, 2026 (per Jordana) ──
    {
        'name': 'Pizza Cafe',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'COR-certified kosher pizza restaurant. Pizza, pasta, and Italian favourites. Affordable catering options for shiva meals.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://www.pizzacafe.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    {
        'name': 'Aroma Espresso Bar',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Israeli-born cafe chain with kosher-certified locations. Coffee, pastries, salads, sandwiches, and shakshuka. A warm, familiar option for lighter shiva meals.',
        'address': 'Multiple locations, Toronto, ON',
        'neighborhood': 'GTA',
        'phone': '',
        'website': 'https://www.aromaespressobar.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Chop Hop',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Kosher restaurant offering fresh, flavourful meals. A great option for shiva catering and family-style meals.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://www.chophop.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    # ── Outscraper pipeline vendors — Mar 9, 2026 ──
    # Beyond Delish duplicate removed — already listed above (line ~737)
    {
        'name': 'Apex Kosher Catering',
        'category': 'Caterers',
        'description': 'Kosher caterer in North York offering full-service catering for lifecycle events. Professional team, flexible menus, and reliable service for families who need it most.',
        'address': '100 Elder St, North York, ON M3H 5G7',
        'neighborhood': 'North York',
        'phone': '',
        'website': 'https://www.apexkoshercatering.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York,Thornhill/Vaughan',
    },
    {
        'name': 'Mitzuyan Kosher Catering',
        'category': 'Caterers',
        'description': "Toronto's modern kosher catering company. Full-service catering with contemporary menus and professional execution. A fresh option for shiva meals and community gatherings.",
        'address': '18 Reiner Rd, Toronto, ON M3H 2K9',
        'neighborhood': 'North York',
        'phone': '',
        'website': 'https://mitzuyankoshercatering.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'F + B Kosher Catering',
        'category': 'Caterers',
        'description': 'COR-certified kosher caterer on Dufferin. The caterer of choice at many top venues throughout the GTA. Professional service for weddings, bar/bat mitzvahs, and community events.',
        'address': '5000 Dufferin St Unit P, North York, ON M3H 5T5',
        'neighborhood': 'North York',
        'phone': '',
        'website': 'https://fbkosher.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York,GTA-wide',
    },
    {
        'name': 'Menchens Glatt Kosher Catering',
        'category': 'Caterers',
        'description': "Glatt kosher catering in North York. Gourmet menus for weddings, bar/bat mitzvahs, and milestone events. A long-standing name in Toronto's kosher catering community.",
        'address': '470 Glencairn Ave, North York, ON M5N 1V8',
        'neighborhood': 'North York',
        'phone': '',
        'website': 'http://menchens.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York,Thornhill/Vaughan,GTA-wide',
    },
    {
        'name': 'Noah Kosher Sushi',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'COR-certified kosher sushi in the Bathurst corridor. A unique and crowd-pleasing option for shiva meals — sushi platters that everyone appreciates.',
        'address': '4119 Bathurst St, North York, ON M3H 3P4',
        'neighborhood': 'Bathurst Manor',
        'phone': '',
        'website': 'http://www.noahkoshersushi.ca',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': 'North York',
    },
    {
        'name': 'Royal Dairy Cafe & Catering',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Kosher dairy cafe and catering in Thornhill. Light meals, salads, fish, and baked goods. A warm, welcoming option for dairy shiva meals and lighter gatherings.',
        'address': '10 Disera Dr Unit 100, Thornhill, ON L4J 0A7',
        'neighborhood': 'Thornhill',
        'phone': '',
        'website': 'https://royaldairycafe.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
    },
    {
        'name': "Pancer's Original Deli",
        'category': 'Restaurants & Delis',
        'description': 'Legendary Toronto Jewish deli on Bathurst. Smoked meat, corned beef, and classic deli platters that have served the community for decades. A comforting, familiar choice for shiva catering.',
        'address': '3856 Bathurst St, North York, ON M3H 3N3',
        'neighborhood': 'Bathurst Manor',
        'phone': '',
        'website': 'http://www.pancersoriginaldeli.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': "Zelden's Deli and Desserts",
        'category': 'Restaurants & Delis',
        'description': 'Jewish-style deli and desserts on Yonge. Sandwiches, salads, baked goods, and catering platters. A dependable choice when you need food for the family.',
        'address': '1446 Yonge St, Toronto, ON M4T 1Y5',
        'neighborhood': 'Midtown',
        'phone': '',
        'website': 'http://www.zeldensdelianddesserts.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    {
        'name': 'Richmond Kosher Bakery',
        'category': 'Bagel Shops & Bakeries',
        'description': 'COR-certified kosher bakery on Bathurst. Fresh breads, challahs, pastries, and cakes. A neighbourhood staple for Shabbat baking and shiva dessert trays.',
        'address': '4119 Bathurst St Unit 1, North York, ON M3H 3P4',
        'neighborhood': 'Bathurst Manor',
        'phone': '',
        'website': 'http://richmondkosherbakery.com',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': 'North York',
    },
    {
        'name': "Aba's Bagel Company",
        'category': 'Bagel Shops & Bakeries',
        'description': 'Fresh bagels and baked goods on Eglinton West. Hand-rolled, kettle-boiled bagels with a loyal following. Platters available for gatherings.',
        'address': '884A Eglinton Ave W, Toronto, ON M6C 2B6',
        'neighborhood': 'Midtown',
        'phone': '',
        'website': 'https://abasbagel.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': 'Toronto',
    },
    {
        'name': 'Zuchter Berk Kosher Caterers',
        'category': 'Caterers',
        'description': "Established kosher caterer serving Toronto's Jewish community. Full-service catering for lifecycle events, shiva meals, and community gatherings.",
        'address': '2301 Keele St, Toronto, ON M6M 3Z9',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'http://www.zbcaterers.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York,GTA-wide',
    },
    # ── New Toronto vendors from COR research — Mar 4, 2026 ──
    {
        'name': "Howie T's Burger Bar",
        'category': 'Kosher Restaurants & Caterers',
        'description': 'COR-certified kosher burger restaurant in Thornhill. Burgers, hot dogs, fries, and classic comfort food. A crowd-pleasing option for casual shiva meals.',
        'address': '115-1 Promenade Circle, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 597-1606',
        'website': 'https://howiets.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan',
    },
    {
        'name': 'Umami Sushi',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'COR-certified kosher sushi restaurant serving Toronto since 2001. Poke bowls, maki combos, udon, soba noodles, and sushi burritos. Catering platters available.',
        'address': '3459 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 782-3375',
        'website': 'https://www.umamisushi.ca/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Haymishe Bakery',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Classic kosher bakery on Bathurst. Known for hamantaschen, pastries, and traditional Jewish baked goods. A neighbourhood staple since 1957.',
        'address': '3031 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 781-4212',
        'website': 'https://www.haymishebakery.com/',
        'instagram': 'haymishebakeryto',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': "Bubby's Bagels",
        'category': 'Restaurants & Delis',
        'description': 'COR-certified deli with two locations. NY-style bagels and bialys on Bathurst, plus sandwiches, burgers, tacos, and onion rings at the larger Lawrence Ave diner.',
        'address': '3030 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 862-2435',
        'website': 'https://www.bubbysbagels.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Golden Chopsticks',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Glatt kosher Chinese restaurant. Chinese dishes, fried rice, and Asian comfort food. Relocated to Spring Farm Marketplace in Thornhill.',
        'address': '441 Clark Ave W, Unit 15, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 760-2789',
        'website': 'https://goldenchopstick.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    # Yehudales Falafel and Pizza — removed Mar 2026 (permanently closed per Yelp Dec 2025)
    {
        'name': 'Shalom India',
        'category': 'Kosher Restaurants & Caterers',
        'description': "COR-certified kosher Indian restaurant — Toronto's only one. Curries, tandoori, biryani, and vegetarian options — a unique and flavourful choice for shiva meals.",
        'address': '7700 Bathurst St, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 597-3323',
        'website': 'https://shalomindia.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    # Mediterranean / Turkish
    {
        'name': 'Sofram Restaurant',
        'category': 'Mediterranean',
        'description': 'Turkish and Mediterranean cuisine in North York. Known for generous portions, fresh-baked pide, grilled kebabs, hummus, and mixed grill platters. Reasonably priced and popular for shiva catering orders.',
        'address': '5849 Leslie St, North York, ON',
        'neighborhood': 'North York',
        'phone': '(416) 223-1818',
        'website': 'https://www.sofram.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
    # Italian
    {
        'name': 'Paese Ristorante',
        'category': 'Italian',
        'description': 'Upscale Italian restaurant on Bloor West. Known for housemade pastas, wood-fired pizzas, and refined Italian dishes. A popular choice for shiva catering in the Bloor-Annex neighbourhood.',
        'address': '3827 Bloor St W, Etobicoke, ON',
        'neighborhood': 'Bloor West',
        'phone': '(416) 207-9995',
        'website': 'https://www.paeseristorante.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
]


# 30 Montreal-area food vendors
MONTREAL_VENDORS = [
    # Kosher Caterers
    {
        'name': 'Blossom by La Plaza',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'One of Montreal\'s premier kosher caterers, specializing in elegant event planning and gourmet cuisine. Full-service catering for shiva meals, lifecycle events, and community gatherings.',
        'address': '5458 Avenue Westminster, Côte-Saint-Luc, QC',
        'neighborhood': 'Côte-Saint-Luc',
        'phone': '(514) 489-7111',
        'website': 'https://www.blossombylaplaza.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Côte-Saint-Luc,Westmount',
    },
    {
        'name': 'Paradise Kosher Catering',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Full-service kosher caterer offering prepared meals, bakery goods, and catering for shiva, Shabbat, and lifecycle events. Provides an à la carte order form for easy meal planning. MK certified.',
        'address': '11608 Boulevard de Salaberry, Dollard-des-Ormeaux, QC',
        'neighborhood': 'Dollard-des-Ormeaux',
        'phone': '(514) 421-0421',
        'website': 'https://www.paradisekosher.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Côte-Saint-Luc,Hampstead,Snowdon',
    },
    {
        'name': 'Kosher Quality Bakery & Deli',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Iconic Montreal kosher destination offering bakery, butcher, deli, and full catering. Known for challah, prepared Shabbat meals, smoked fish platters, and party sandwiches. MK certified.',
        'address': '5855 Avenue Victoria, Montréal, QC',
        'neighborhood': 'Snowdon',
        'phone': '(514) 731-7883',
        'website': 'https://www.bubbysbagels.com/',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Snowdon,Côte-Saint-Luc',
    },
    # Jewish Delis
    {
        'name': 'Snowdon Deli',
        'category': 'Restaurants & Delis',
        'description': 'A Montreal institution since 1946, beloved for classic smoked meat, deli sandwiches, and homestyle Jewish comfort food. Catering platters ideal for shiva meals.',
        'address': '5265 Boulevard Décarie, Montréal, QC',
        'neighborhood': 'Snowdon',
        'phone': '(514) 488-9129',
        'website': 'https://www.snowdondeli.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal',
    },
    {
        'name': 'Deli 365',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'MK-certified kosher smoked meat deli on Bernard Street. Take-out sandwiches, burgers, and prepared platters. Reliable for kosher deli trays and comfort food for shiva meals.',
        'address': '365 Rue Bernard Ouest, Montréal, QC',
        'neighborhood': 'Outremont',
        'phone': '(514) 544-3354',
        'website': 'https://deli365.ca',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Outremont,Mile End',
    },
    {
        'name': 'Schwartz\'s Deli',
        'category': 'Restaurants & Delis',
        'description': 'World-famous Montreal smoked meat restaurant since 1928. An iconic Jewish culinary landmark on Boulevard Saint-Laurent. Not kosher certified but deeply rooted in Montreal Jewish food tradition.',
        'address': '3895 Boulevard Saint-Laurent, Montréal, QC',
        'neighborhood': 'Plateau Mont-Royal',
        'phone': '(514) 842-4813',
        'website': 'https://schwartzsdeli.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Lester\'s Deli',
        'category': 'Restaurants & Delis',
        'description': 'Established in 1951, a beloved Outremont smoked meat institution known for hand-cut fries and community spirit. Catering, take-out, and delivery available.',
        'address': '1057 Avenue Bernard, Outremont, QC',
        'neighborhood': 'Outremont',
        'phone': '(514) 213-1313',
        'website': 'https://lestersdeli.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal,Outremont',
    },
    # Bagel Shops & Bakeries
    {
        'name': 'Boulangerie Cheskie',
        'category': 'Bagel Shops & Bakeries',
        'description': 'MK-certified kosher bakery and Montreal institution. Famous for babka, challah, rugelach, and cheese crowns. Perfect for shiva dessert platters and Shabbat bread.',
        'address': '359 Rue Bernard Ouest, Montréal, QC',
        'neighborhood': 'Outremont',
        'phone': '(514) 271-2253',
        'website': '',
        'instagram': 'cheskiebakery',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Outremont,Mile End',
    },
    {
        'name': 'St-Viateur Bagel',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Legendary wood-fired bagel bakery operating 24/7 since 1957. Hand-rolled Montreal-style bagels baked in a wood-burning oven. A cornerstone of Montreal Jewish food culture.',
        'address': '263 Rue Saint-Viateur Ouest, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 276-8044',
        'website': 'https://stviateurbagel.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal,Canada-wide',
    },
    {
        'name': 'Fairmount Bagel',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Montreal\'s original bagel bakery, open 24 hours since 1919. Hand-made, wood-fired bagels. A quintessential Montreal Jewish food experience for bagel platters.',
        'address': '74 Avenue Fairmount Ouest, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 272-0667',
        'website': 'https://fairmountbagel.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal',
    },
    {
        'name': 'Montreal Kosher Bakery',
        'category': 'Bagel Shops & Bakeries',
        'description': 'The largest kosher bakery in Montreal and all of Canada, operating since 1976. Freshly baked muffins, danishes, breads, bagels, and dinner rolls daily. MK certified.',
        'address': '7005 Avenue Victoria, Montréal, QC',
        'neighborhood': 'Côte-des-Neiges',
        'phone': '(514) 739-3651',
        'website': 'https://montrealkosher.ca',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Côte-des-Neiges,Snowdon',
    },
    # Comfort Food & Prepared Meals
    {
        'name': 'Nosherz',
        'category': 'Caterers',
        'description': 'A Côte-Saint-Luc institution for over 50 years. Homemade baked goods, gourmet prepared meals, comfort food, soups, sandwiches, salads, and fresh deli. Perfect for shiva meal platters.',
        'address': '5800 Avenue Westminster, Côte-Saint-Luc, QC',
        'neighborhood': 'Côte-Saint-Luc',
        'phone': '(514) 484-0445',
        'website': 'https://nosherz.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal,Côte-Saint-Luc,Hampstead',
    },
    # Iconic Montreal Restaurants
    {
        'name': "Mandy's",
        'category': 'Restaurants & Delis',
        'description': "Montreal's beloved gourmet salad destination with multiple locations. Creative, hearty salads and grain bowls — a fresh, healthy option for feeding a crowd. Catering platters available for groups.",
        'address': '2067 Rue Crescent, Montréal, QC',
        'neighborhood': 'Downtown',
        'phone': '(514) 289-0202',
        'website': 'https://www.mandys.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal',
    },
    {
        'name': "Gibby's",
        'category': 'Restaurants & Delis',
        'description': "Iconic Montreal steakhouse in a historic 200-year-old stone building in Old Montreal. Premium steaks, seafood, and classic sides. Private dining and catering for special occasions.",
        'address': "298 Place D'Youville, Montréal, QC",
        'neighborhood': 'Old Montreal',
        'phone': '(514) 282-1837',
        'website': 'https://www.gibbys.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Moishes',
        'category': 'Restaurants & Delis',
        'description': "Legendary Montreal steakhouse and a fixture of the city's Jewish community since 1938. Now at their new downtown location. Famous for dry-aged steaks and old-school elegance.",
        'address': '1001 Rue du Square-Victoria, Montréal, QC',
        'neighborhood': 'Downtown',
        'phone': '(514) 360-4221',
        'website': 'https://www.moishes.ca',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': "Beauty's Luncheonette",
        'category': 'Restaurants & Delis',
        'description': "A Montreal Jewish institution since 1942. Famous for bagels, lox, eggs, and brunch classics. Founded by Hymie Sckolnick — a beloved gathering place for generations of Montreal families.",
        'address': '93 Avenue du Mont-Royal Ouest, Montréal, QC',
        'neighborhood': 'Plateau Mont-Royal',
        'phone': '(514) 849-8883',
        'website': 'https://www.beautys.ca/',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': "Wilensky's Light Lunch",
        'category': 'Restaurants & Delis',
        'description': "Iconic Montreal lunch counter since 1932, immortalized in Mordecai Richler's novels. Famous for 'The Special' — a pressed salami and bologna sandwich. A living piece of Montreal Jewish heritage.",
        'address': '34 Avenue Fairmount Ouest, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 271-0247',
        'website': 'http://www.wilenskys.com/',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Rôtisserie Laurier',
        'category': 'Restaurants & Delis',
        'description': "Classic Montreal rotisserie chicken restaurant, a neighbourhood staple for decades. Whole roast chickens, ribs, and comfort food platters — perfect for feeding a crowd.",
        'address': '381 Avenue Laurier Ouest, Montréal, QC',
        'neighborhood': 'Outremont',
        'phone': '(514) 273-3671',
        'website': 'https://www.lauriergordonramsay.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal,Outremont,Mile End',
    },
    {
        'name': 'Europea',
        'category': 'Caterers',
        'description': "Award-winning fine dining restaurant and full-service catering by Chef Jérôme Ferrer. Europea Catering offers elegant, customized menus for private events and celebrations of any size.",
        'address': '1227 Rue de la Montagne, Montréal, QC',
        'neighborhood': 'Downtown',
        'phone': '(514) 398-9229',
        'website': 'https://jeromeferrer.ca/en/',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal',
    },
    {
        'name': 'Lemeac',
        'category': 'Restaurants & Delis',
        'description': "Beloved Outremont French bistro, a neighbourhood favourite for over 20 years. Refined yet accessible cuisine with private dining available for gatherings and celebrations.",
        'address': '1045 Avenue Laurier Ouest, Montréal, QC',
        'neighborhood': 'Outremont',
        'phone': '(514) 270-0999',
        'website': 'https://www.restaurantlemeac.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Arthurs Nosh Bar',
        'category': 'Restaurants & Delis',
        'description': "Jewish-inspired brunch and comfort food. Latkes, smoked fish, shakshuka, and creative deli dishes. A modern take on Montreal's rich Jewish food traditions.",
        'address': '4621 Rue Notre-Dame Ouest, Montréal, QC',
        'neighborhood': 'Saint-Henri',
        'phone': '(514) 757-5190',
        'website': 'https://www.arthursmtl.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Hof Kelsten',
        'category': 'Bagel Shops & Bakeries',
        'description': "Award-winning artisan bakery and deli in Mile End. Sourdough breads, croissants, smoked meat sandwiches, and pastries. A modern Montreal bakery with deep respect for tradition.",
        'address': '4524 Boulevard Saint-Laurent, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 277-7700',
        'website': 'https://www.hofkelsten.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Olive et Gourmando',
        'category': 'Bagel Shops & Bakeries',
        'description': "Beloved Old Montreal bakery and café known for artisan breads, gourmet sandwiches, and beautiful pastries. A go-to for high-quality baked goods and catering platters.",
        'address': '351 Rue Saint-Paul Ouest, Montréal, QC',
        'neighborhood': 'Old Montreal',
        'phone': '(514) 350-1083',
        'website': 'https://oliveetgourmando.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal',
    },
    # ── New verified Montreal vendors — Feb 2026 (Sprint 6) ──
    {
        'name': 'District Bagel',
        'category': 'Bagel Shops & Bakeries',
        'description': 'The only MK-certified wood-fired Montreal-style bagel bakery. Three locations across Montreal with a 100% kosher menu. Online ordering, catering for corporate events, school lunches, and celebrations.',
        'address': '709 Chemin Lucerne, Mount Royal, QC',
        'neighborhood': 'Mount Royal',
        'phone': '(514) 735-1174',
        'website': 'https://districtbagel.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Mount Royal,Snowdon',
    },
    {
        'name': "JoJo's Pizza",
        'category': 'Italian',
        'description': 'New York-style kosher pizza in Mile End under the highest level of MK Mehadrin kosher supervision. Thin-crust pies, dine-in, takeout, and delivery via Uber Eats and DoorDash.',
        'address': '355 Rue Bernard Ouest, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 975-2770',
        'website': 'https://www.umamisushi.ca/',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Mile End,Outremont',
    },
    {
        'name': 'La Marguerite Catering',
        'category': 'Caterers',
        'description': 'Montreal\'s premier Glatt Kosher caterer for over 30 years. MK-supervised Moroccan-inspired delicacies, slow-cooked dishes, and full-service catering for elegant events and shiva meals. Free delivery on orders over $250.',
        'address': '6630 Chemin de la Côte-Saint-Luc, Montréal, QC',
        'neighborhood': 'Côte-Saint-Luc',
        'phone': '(514) 488-4111',
        'website': 'https://www.lamarguerite.ca',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Côte-Saint-Luc,Hampstead,Westmount',
    },
    {
        'name': "Oineg's Kosher",
        'category': 'Kosher Restaurants & Caterers',
        'description': 'A Mile End staple for prepared kosher Shabbat meals. MK-certified meat restaurant known for cholent, sandwiches, dips, and liver. Full Shabbos takeout, dine-in, and catering services.',
        'address': '360 Rue Saint-Viateur Ouest, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 277-3600',
        'website': 'https://www.oinegshabbes.com/',
        'instagram': 'oinegskosher',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Mile End,Outremont',
    },
    {
        'name': "Chenoy's Deli",
        'category': 'Restaurants & Delis',
        'description': 'Legendary Montreal Jewish-style deli open since 1936. Famous for Montreal-style smoked meat sandwiches. The last remaining Chenoy\'s location in Dollard-des-Ormeaux. Open 24/7.',
        'address': '3616 Boulevard Saint-Jean, Dollard-des-Ormeaux, QC',
        'neighborhood': 'Dollard-des-Ormeaux',
        'phone': '(514) 620-2584',
        'website': 'https://chenoys-deli.goto-where.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    # ── New Montreal vendors from MK research — Mar 4, 2026 ──
    # Citrus Traiteur — REMOVED Mar 9 (per Jordana)

    {
        'name': 'Mehadrin Meats',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'MK-certified kosher butcher, takeout, and full-service caterer in the Mile End area. Prepared Shabbos meals, deli meats, and catering for shiva and lifecycle events.',
        'address': '8600 8e Ave, Montréal, QC',
        'neighborhood': 'Outremont',
        'phone': '(514) 321-8000',
        'website': 'https://mehadrinmeats.ca',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Outremont,Mile End,Côte-Saint-Luc',
    },
    # ── Montreal restaurants (MK-certified, added Mar 4 research) ──
    {
        'name': 'Benny & Fils (Queen Mary)',
        'category': 'Middle Eastern & Israeli',
        'description': 'Family-run kosher grill serving shawarma, falafel, schnitzel, and Mediterranean-style meat dishes on Queen Mary Road.',
        'address': '4944 Queen Mary Rd, Montreal, QC H3W 1X2',
        'neighborhood': 'Snowdon',
        'phone': '(514) 735-5858',
        'website': 'https://www.bennyetfils.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Snowdon,Cote-des-Neiges,Hampstead,Cote-Saint-Luc',
    },
    {
        'name': 'Benny & Fils (Downtown)',
        'category': 'Middle Eastern & Israeli',
        'description': 'Downtown branch of the popular kosher grill near McGill University, serving shawarma, falafel, and fried chicken.',
        'address': '575 Boul. de Maisonneuve Ouest, Montreal, QC H3A 1L8',
        'neighborhood': 'Downtown Montreal',
        'phone': '(514) 842-7575',
        'website': 'https://www.bennyetfils.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Downtown Montreal,Plateau,Westmount',
    },
    {
        'name': 'Deli 770',
        'category': 'Delis & Smoked Meat',
        'description': 'Chabad-inspired kosher deli in the Westbury complex specializing in Montreal-style smoked meat sandwiches and gourmet grill fusions.',
        'address': '5193 Avenue de Courtrai, Montreal, QC H3W 2X7',
        'neighborhood': 'Snowdon',
        'phone': '(514) 335-4770',
        'website': 'https://deli770.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Snowdon,Cote-des-Neiges,Cote-Saint-Luc',
    },
    {
        'name': 'Deli Boyz',
        'category': 'Delis & Smoked Meat',
        'description': 'Kosher deli in Quartier Cavendish Mall serving smoked meat, schnitzel, burgers, wraps, and salads.',
        'address': '5800 Cavendish Blvd, Cote-Saint-Luc, QC H4W 2T5',
        'neighborhood': 'Cote-Saint-Luc',
        'phone': '(514) 303-2699',
        'website': 'https://restaurantdeliboyz.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Cote-Saint-Luc,Hampstead,Snowdon',
    },
    {
        'name': 'Chiyoko',
        'category': 'Japanese & Sushi',
        'description': 'Upscale kosher Japanese restaurant in Ville Saint-Laurent serving sushi-grade fish and fine cuts of meat in an elegant setting.',
        'address': '2113 Rue Saint-Louis, Saint-Laurent, QC H4M 1P1',
        'neighborhood': 'Saint-Laurent',
        'phone': '(514) 804-0581',
        'website': 'https://www.chiyokosushi.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Saint-Laurent,Cote-des-Neiges,Town of Mount Royal',
    },
    {
        'name': 'LeFalafel Plus',
        'category': 'Middle Eastern & Israeli',
        'description': 'Israeli-style MK Mehadrin kosher restaurant on Decarie serving high-quality falafel, shawarma, schnitzel, and Middle Eastern dishes.',
        'address': '6245 Decarie Blvd, Montreal, QC H3W 3E1',
        'neighborhood': 'Snowdon',
        'phone': '(514) 731-1221',
        'website': 'http://www.wilenskys.com/',
        'instagram': 'lefalafelmontreal',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Snowdon,Cote-des-Neiges,Cote-Saint-Luc,Hampstead',
    },
    {
        'name': 'Pizza Gourmetti',
        'category': 'Pizza & Dairy',
        'description': 'Authentic New York-style kosher Cholov Yisroel pizza restaurant in Saint-Laurent serving thin-crust pizzas, salads, and sandwiches since 2009.',
        'address': '2075 Rue Saint-Louis, Saint-Laurent, QC H4W 1S5',
        'neighborhood': 'Saint-Laurent',
        'phone': '(514) 739-7707',
        'website': 'https://www.pizzagourmetti.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Saint-Laurent,Cote-des-Neiges,Town of Mount Royal',
    },
    {
        'name': 'Pizza Pita Prime',
        'category': 'Pizza & Dairy',
        'description': 'Long-standing kosher pizzeria run by the Shpiegelman family for three decades, serving pizza, pasta, and dairy dishes with catering services.',
        'address': '5345 Vezina, Montreal, QC H3X 4A8',
        'neighborhood': 'Snowdon',
        'phone': '(514) 731-7482',
        'website': 'https://pizzapitaprime.order-online.ai/',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Snowdon,Cote-des-Neiges,Cote-Saint-Luc,Hampstead',
    },
    # Gift Baskets
    {
        'name': 'Gifting Kosher Canada',
        'category': 'Gift Baskets',
        'vendor_type': 'gift',
        'description': 'Canada\'s leading online retailer of kosher shiva gift baskets. Gourmet food, wine, cakes, chocolates, and customizable baskets. Same-day and next-day delivery to Montreal.',
        'address': 'Online — ships Canada-wide',
        'neighborhood': 'Montreal',
        'phone': '1-(800) 548-9624',
        'website': 'https://giftingkosher.ca',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Canada-wide',
    },
    # ── Jordana additions — Mar 12, 2026 (food vendors, NOT gift) ──
    {
        'name': 'Me Va Mi Kitchen Express',
        'category': 'Caterers',
        'description': 'Kosher kitchen offering fresh prepared meals, catering trays, and family-style platters. Convenient pickup and delivery for shiva homes and community events.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://mevamekitchenexpress.ca/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    {
        'name': "Orly's Kitchen",
        'category': 'Caterers',
        'description': 'Home-style kosher cooking with heart. Full catering menus for shiva meals, family gatherings, and community events.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://orlyskitchen.com/',
        'kosher_status': 'Kosher',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    # Umami Sushi already exists above (line ~945) with full details — removed duplicate
    {
        'name': 'Pantry Foods',
        'category': 'Caterers',
        'description': 'Kosher grocery and prepared foods. Ready-made meals, platters, and pantry staples delivered to shiva homes.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://pantryfoods.ca/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
]


# 25 gift vendors (local, lead capture, affiliate)
GIFT_VENDORS = [
    {
        'name': 'Baskets n\' Stuf',
        'category': 'Gift Baskets',
        'description': 'Kosher gift baskets and shiva platters. Beautiful arrangements with fresh fruit, baked goods, and gourmet treats. Experienced in shiva deliveries.',
        'address': '6237 Bathurst St, North York, ON',
        'neighborhood': 'North York',
        'phone': '(416) 250-9116',
        'website': 'https://orly-grill.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
    {
        'name': 'Ely\'s Fine Foods Gift Baskets',
        'category': 'Gift Baskets',
        'description': 'Kosher shiva platters and fine food gift baskets from Ely\'s Fine Foods. COR-certified prepared meals, deli trays, and curated gift packages for mourning families.',
        'address': '3537A Bathurst St, North York, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 782-3231',
        'website': 'https://elysfinefoods.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
    {
        'name': 'Nutcracker Sweet / Baskits',
        'category': 'Gift Baskets',
        'description': 'Premium gift baskets and gourmet packages. Known for stunning presentation and high-quality products. Ships Canada-wide. Kosher options available.',
        'address': '3717 Chesswood Dr, Toronto, ON',
        'neighborhood': 'North York',
        'phone': '(416) 782-3232',
        'website': 'https://www.baskits.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA + Canada-wide',
    },
    {
        'name': 'Romi\'s Bakery',
        'category': 'Gift Baskets',
        'description': 'Artisanal baked goods and pastries. Beautiful cookie boxes, cakes, and pastry platters. A warm, personal touch for a shiva home.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://romisbakery.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Local',
    },
    {
        'name': 'Edible Arrangements',
        'category': 'Fruit',
        'description': 'Fresh fruit arrangements and bouquets. Same-day delivery available at 7 GTA locations. Fruit is inherently kosher — a safe, universally appreciated gift.',
        'address': 'Multiple GTA locations',
        'neighborhood': 'GTA',
        'phone': '',
        'website': 'https://www.ediblearrangements.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA + same-day',
    },
    {
        'name': 'Fruitate',
        'category': 'Fruit',
        'description': 'Beautiful fruit arrangements and displays. Fresh, colourful, and healthy. A thoughtful and refreshing gift for a shiva home.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': '',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Local',
    },
    {
        'name': 'Epic Baskets',
        'category': 'Fruit',
        'description': 'Fresh fruit baskets and gourmet gift packages. Same-day delivery in GTA. Beautiful presentation for a meaningful gift.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA',
        'phone': '',
        'website': '',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA + same-day',
    },
    {
        'name': 'My Baskets',
        'category': 'Fruit',
        'description': 'Fruit and gift baskets with free delivery over $100 in the GTA. Wide variety of sympathy and condolence baskets.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA',
        'phone': '',
        'website': '',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA (free over $100)',
    },
    # 24-Hour Yahrzeit Memorial Candles — REMOVED Mar 9 (per Jordana)

    # Chocolate & Sweets
    {
        'name': 'Purdys Chocolatier',
        'category': 'Chocolate & Sweets',
        'description': 'Premium Canadian chocolatier since 1907. Beautiful gift boxes, truffles, and chocolate assortments. Ships Canada-wide. A thoughtful, universally appreciated condolence gift.',
        'address': 'Multiple locations across Canada',
        'neighborhood': 'GTA',
        'phone': '1-888-478-7397',
        'website': 'https://www.purdys.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Canada-wide',
    },
    {
        'name': 'Laura Secord',
        'category': 'Chocolate & Sweets',
        'description': 'Iconic Canadian chocolate and candy company since 1913. Classic boxed chocolates, fudge, and sweet gift sets. Multiple GTA retail locations plus online ordering.',
        'address': 'Multiple GTA locations',
        'neighborhood': 'GTA',
        'phone': '',
        'website': 'https://www.laurasecord.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Canada-wide',
    },
    # ── New gift basket vendors (Sprint 5 follow-up) ──
    {
        'name': 'Baskets Galore',
        'category': 'Gift Baskets',
        'description': 'Elegant gift baskets for every occasion including sympathy and condolence. Gourmet food, fruit, chocolate, and spa baskets with Canada-wide delivery.',
        'address': 'Online — ships Canada-wide',
        'neighborhood': 'Online',
        'phone': '',
        'website': 'https://basketsgalore.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Canada-wide',
    },
    {
        'name': 'Indigo',
        'category': 'Gift Baskets',
        'description': 'Books, cozy blankets, candles, and curated gift boxes. A warm, comforting gift for a grieving family. Gift cards also available. Canada\'s largest bookstore chain.',
        'address': 'Multiple locations across Canada',
        'neighborhood': 'GTA',
        'phone': '',
        'website': 'https://www.indigo.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Canada-wide',
    },
    {
        'name': 'Harry & David',
        'category': 'Gift Baskets',
        'description': 'Premium fruit, gourmet food, and sympathy gift baskets since 1934. Known for signature Royal Riviera pears and tower gift boxes. Ships to Canada.',
        'address': 'Online — ships to Canada',
        'neighborhood': 'Online',
        'phone': '',
        'website': 'https://www.harryanddavid.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'North America',
    },
    {
        'name': 'The Fruit Company',
        'category': 'Fruit',
        'description': 'Premium fresh fruit gift boxes and baskets. Orchard-direct seasonal fruit from Oregon. Sympathy and comfort collections available. Ships to Canada.',
        'address': 'Online — ships to Canada',
        'neighborhood': 'Online',
        'phone': '',
        'website': 'https://www.thefruitcompany.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'North America',
    },
    {
        'name': 'Hickory Farms',
        'category': 'Gift Baskets',
        'description': 'Classic gourmet gift baskets with sausage, cheese, crackers, and sweets. Sympathy and comfort food collections. A familiar, crowd-pleasing gift choice.',
        'address': 'Online + seasonal retail locations',
        'neighborhood': 'Online',
        'phone': '',
        'website': 'https://www.hickoryfarms.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'North America',
    },
    {
        'name': '1-800-Baskets',
        'category': 'Gift Baskets',
        'description': 'Wide selection of sympathy and condolence gift baskets. Gourmet food, fruit, chocolate, and comfort care packages. Same-day delivery available in many areas.',
        'address': 'Online — ships North America',
        'neighborhood': 'Online',
        'phone': '',
        'website': 'https://www.1800baskets.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'North America',
    },
    {
        'name': 'Wolferman\'s Bakery',
        'category': 'Baked Goods',
        'description': 'Artisan English muffins, pastries, and baked goods gift boxes since 1888. Breakfast and brunch baskets — a warm, practical gift for a mourning household.',
        'address': 'Online — ships North America',
        'neighborhood': 'Online',
        'phone': '',
        'website': 'https://www.wolfermans.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'North America',
    },
    {
        'name': 'Cheryl\'s Cookies',
        'category': 'Baked Goods',
        'description': 'Gourmet cookies, brownies, and baked goods gift boxes. Sympathy cookie tins and comfort food packages. A sweet, comforting gesture for a shiva home.',
        'address': 'Online — ships North America',
        'neighborhood': 'Online',
        'phone': '',
        'website': 'https://www.cheryls.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'North America',
    },
    # Bubby's New York Bagels — REMOVED Mar 9 (duplicate of Bubby's Bagels in Restaurants & Delis)

    {
        'name': 'Good Person Biscotti',
        'category': 'Baked Goods',
        'description': 'Artisan biscotti — a perfect accompaniment to coffee and tea during shiva. A thoughtful, comforting gift.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': '',
        'instagram': 'goodpersonbiscotti',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'AB Cookies',
        'category': 'Baked Goods',
        'description': 'Beautiful custom cookies and sweet treats. Gift boxes perfect for bringing something special to a shiva home.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://abcookies.co',
        'instagram': 'abcookies.co',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    # Skye Dough stays in GIFT_VENDORS (it's a gift/cookie company)
    {
        'name': 'Skye Dough Cookies',
        'category': 'Gift Baskets',
        'description': 'Beautiful custom cookies and cookie gift boxes. A sweet, thoughtful gift to bring to a shiva home.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': '',
        'instagram': 'skyedoughcookies',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
]


def seed_vendors(db_path=None):
    """Seed the vendors table with food and gift vendor data"""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    create_tables(conn)

    cursor = conn.cursor()
    now = datetime.now().isoformat()
    inserted = 0
    skipped = 0

    # Seed food vendors (Toronto + Montreal)
    all_food_vendors = VENDORS + MONTREAL_VENDORS
    for v in all_food_vendors:
        # RULE: Every vendor must have a website or instagram for tracking
        if not v.get('website', '').strip() and not v.get('instagram', '').strip():
            print(f"  SKIPPED (no website or instagram): {v['name']}")
            skipped += 1
            continue

        slug = slugify(v['name'])
        # Check if already exists
        cursor.execute('SELECT id FROM vendors WHERE slug = ?', (slug,))
        if cursor.fetchone():
            skipped += 1
            continue

        vendor_type = v.get('vendor_type', 'food')
        cursor.execute('''
            INSERT INTO vendors (name, slug, category, vendor_type, description, address, neighborhood,
                                 phone, website, instagram, kosher_status, delivery, delivery_area, image_url, featured, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            v['name'],
            slug,
            v['category'],
            vendor_type,
            v.get('description', ''),
            v.get('address', ''),
            v.get('neighborhood', ''),
            v.get('phone', ''),
            v.get('website', ''),
            v.get('instagram', ''),
            v.get('kosher_status', 'not_certified'),
            v.get('delivery', 0),
            v.get('delivery_area', ''),
            v.get('image_url'),
            v.get('featured', 0),
            now,
        ))
        inserted += 1

    # Seed gift vendors
    gift_inserted = 0
    for v in GIFT_VENDORS:
        # RULE: Every vendor must have a website or instagram for tracking
        if not v.get('website', '').strip() and not v.get('instagram', '').strip():
            print(f"  SKIPPED (no website or instagram): {v['name']}")
            skipped += 1
            continue

        slug = slugify(v['name'])
        cursor.execute('SELECT id FROM vendors WHERE slug = ?', (slug,))
        if cursor.fetchone():
            skipped += 1
            continue

        cursor.execute('''
            INSERT INTO vendors (name, slug, category, vendor_type, description, address, neighborhood,
                                 phone, website, instagram, kosher_status, delivery, delivery_area, image_url, featured, created_at)
            VALUES (?, ?, ?, 'gift', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            v['name'],
            slug,
            v['category'],
            v.get('description', ''),
            v.get('address', ''),
            v.get('neighborhood', ''),
            v.get('phone', ''),
            v.get('website', ''),
            v.get('instagram', ''),
            v.get('kosher_status', 'not_certified'),
            v.get('delivery', 0),
            v.get('delivery_area', ''),
            v.get('image_url'),
            v.get('featured', 0),
            now,
        ))
        gift_inserted += 1
        inserted += 1

    # Remove closed/defunct vendors
    removed = 0
    for name in VENDORS_TO_REMOVE:
        slug = slugify(name)
        cursor.execute('DELETE FROM vendors WHERE slug = ?', (slug,))
        if cursor.rowcount > 0:
            removed += cursor.rowcount
            logging.info(f"Removed closed vendor: {name}")

    conn.commit()
    conn.close()
    logging.info(f"Vendor seed complete: {inserted} inserted ({gift_inserted} gift), {skipped} skipped, {removed} removed")
    return inserted


def backfill_vendor_emails(db_path=None):
    """Backfill vendor emails from caterer_partners where names match"""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Ensure email column exists
    try:
        cursor.execute('SELECT email FROM vendors LIMIT 1')
    except Exception:
        cursor.execute("ALTER TABLE vendors ADD COLUMN email TEXT")
        conn.commit()

    # Check if caterer_partners table exists
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='caterer_partners'")
        if not cursor.fetchone():
            logging.info("No caterer_partners table found. Skipping email backfill.")
            conn.close()
            return 0
    except Exception:
        conn.close()
        return 0

    # Count before
    cursor.execute("SELECT COUNT(*) FROM vendors WHERE email IS NOT NULL AND email != ''")
    before = cursor.fetchone()[0]

    # Match vendors to caterer_partners by business name
    cursor.execute('''
        UPDATE vendors SET email = (
            SELECT cp.email FROM caterer_partners cp
            WHERE LOWER(TRIM(cp.business_name)) = LOWER(TRIM(vendors.name))
            AND cp.email IS NOT NULL AND cp.email != ''
            LIMIT 1
        )
        WHERE (vendors.email IS NULL OR vendors.email = '')
        AND EXISTS (
            SELECT 1 FROM caterer_partners cp
            WHERE LOWER(TRIM(cp.business_name)) = LOWER(TRIM(vendors.name))
            AND cp.email IS NOT NULL AND cp.email != ''
        )
    ''')
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM vendors WHERE email IS NOT NULL AND email != ''")
    after = cursor.fetchone()[0]
    updated = after - before

    conn.close()
    logging.info(f"Email backfill: {updated} vendor(s) updated from caterer_partners ({after} total with email)")
    return updated


if __name__ == '__main__':
    seed_vendors()
    backfill_vendor_emails()
