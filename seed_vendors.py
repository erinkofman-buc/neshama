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
import sys
from datetime import datetime

DB_PATH = os.environ.get('DATABASE_PATH', 'neshama.db')

# Vendors to remove from DB (permanently closed or fail Option B — do not serve shiva meals)
VENDORS_TO_REMOVE = [
    # Permanently closed
    "My Zaidy's Pizza",       # Closed Jan 2026
    "Yehudales Falafel and Pizza",  # Closed Dec 2025
    # "Pizza Pita",           # Re-added Mar 22, 2026
    "Shwarma Express",        # No longer exists per Jordana Mar 2026
    "Pita Box",               # No longer exists per Jordana Mar 2026
    "Miami Grill",            # No longer exists per Jordana Mar 9
    "Village Pizza Kosher",   # No longer exists per Jordana Mar 9
    "Citrus Traiteur",        # Removed per Jordana Mar 9
    "24-Hour Yahrzeit Memorial Candles (Multipack)",  # Removed per Jordana Mar 9
    "Bubby's New York Bagels",  # Duplicate of Bubby's Bagels
    "Main Event Catering",      # Removed per Jordana Mar 25
    "Paramount Fine Foods",     # Removed per Jordana Mar 25
    "Aish Tanoor",              # Closed — confirmed by Jordana/research Apr 2026
    # NOTE: Zuchter Berk Kosher Caterers — REINSTATED (research confirmed active, est. 1936)
    # Option B drops (Apr 18, 2026) — vendors who don't serve shiva meals (dine-in only, no trays/delivery/catering)
    "Moishes",                  # Montreal steakhouse, dine-in only — Option B
    "Beauty's Luncheonette",    # Montreal brunch diner, dine-in only — Option B
    "Wilensky's Light Lunch",   # Montreal sandwich counter, no trays/delivery — Option B
    "Lemeac",                   # Montreal French bistro, dine-in only — Option B
    "Arthurs Nosh Bar",         # Montreal brunch spot, dine-in only — Option B
    "Hof Kelsten",              # Montreal artisan bakery, no delivery/trays — Option B
    "Jerusalem Restaurant",     # Toronto Middle Eastern, dine-in only — Option B
    "Clarke Cafe",              # Montreal Italian cafe, not shiva-adjacent — Option B
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

    # Migration: add city column if missing
    try:
        cursor.execute('SELECT city FROM vendors LIMIT 1')
    except Exception:
        cursor.execute("ALTER TABLE vendors ADD COLUMN city TEXT")

    # Migration: add min_order column if missing (e.g. "$300 minimum")
    try:
        cursor.execute('SELECT min_order FROM vendors LIMIT 1')
    except Exception:
        cursor.execute("ALTER TABLE vendors ADD COLUMN min_order TEXT")

    # Migration: add lead_time column if missing (e.g. "48 hours notice")
    try:
        cursor.execute('SELECT lead_time FROM vendors LIMIT 1')
    except Exception:
        cursor.execute("ALTER TABLE vendors ADD COLUMN lead_time TEXT")

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
        'category': 'Restaurants',
        'description': 'Toronto institution serving fresh-baked bagels, spreads, and deli platters. Multiple locations across the GTA. Great for shiva breakfast platters and bagel trays.',
        'address': '2900 Steeles Ave W, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 738-9888',
        'website': 'https://www.whatabagel.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
        'image_url': 'https://www.whatabagel.com/wp-content/uploads/2019/07/slider-home-01.jpg',
    },
    {
        'name': 'Gryfe\'s Bagel Bakery',
        'category': 'Restaurants',
        'description': 'Legendary Toronto bagel bakery since 1915. Famous for their hand-rolled, kettle-boiled bagels. A community staple for over a century.',
        'address': '3421 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 783-1552',
        'website': 'https://www.gryfes.ca',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://cdn.prod.website-files.com/6654f491939825e5141cd118/66552bd504426dcc82487a15_IMG_6348%201.png',
    },
    {
        'name': 'Kiva\'s Bagels',
        'category': 'Restaurants',
        'description': 'Fresh bagels and baked goods in the heart of the Jewish community. Known for their challah, rugelach, and deli-style platters.',
        'address': '1027 Steeles Ave W, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 663-9933',
        'website': 'https://kivasbagels.ca',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://www.restaurantcateringsystems.com/web/documents/kivasbb/images/kiva_home_page.jpg',
    },
    {
        'name': 'Hermes Bakery',
        'category': 'Restaurants',
        'description': 'Full-service kosher bakery offering cakes, pastries, challah, and dessert platters. Perfect for shiva dessert trays and Shabbat baking.',
        'address': '3489 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 781-1156',
        'website': 'http://hermesbakery.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': 'http://hermesbakery.com/wp-content/uploads/2015/01/sweet-table-1.jpg',
    },
    {
        'name': 'United Bakers Dairy Restaurant',
        'category': 'Restaurants',
        'description': 'Iconic Toronto dairy restaurant and bakery since 1912. Famous for their blintzes, pierogies, and homestyle Jewish comfort food.',
        'address': '506 Lawrence Ave W, Toronto, ON',
        'neighborhood': 'Lawrence Park',
        'phone': '(416) 789-0519',
        'website': 'https://www.unitedbakers.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
        'image_url': 'https://unitedbakers.ca/cdn/shop/files/united-bakers-catering-for-30_1200x.jpg?v=1748883399',
    },
    # Caterers (kosher + non-kosher, distinguished by kosher_status field)
    {
        'name': 'Jem Salads',
        'category': 'Restaurants',
        'description': 'Fresh, wholesome salad platters and prepared meals with generous portions. Great option for lighter shiva meals. Platters for 10-50+ guests with flexible delivery timing.',
        'address': '441 Clark Ave W, Toronto, ON',
        'neighborhood': 'North York',
        'phone': '(416) 886-1804',
        'email': 'jem.salads@gmail.com',
        'website': 'https://www.jemsalads.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'accepts_online_orders': 1,
        'delivery_area': 'GTA',
        'featured': 0,
        'image_url': 'https://static.wixstatic.com/media/597c20_4c0a53468f474a85b30efaffe597bfab~mv2.png/v1/fill/w_326,h_380,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/IMG_5640.png',
    },
    {
        'name': 'Bistro Grande',
        'category': 'Caterers',
        'description': 'Upscale kosher dining and catering. Offers elegant plated meals, buffet setups, and family-style dinners suitable for shiva gatherings.',
        'address': '1000 Eglinton Ave W, Toronto, ON',
        'neighborhood': 'Forest Hill',
        'phone': '(416) 782-3302',
        'website': 'https://bistrogrande.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': 'https://bistrogrande.com/wp-content/uploads/2020/02/mil6277_sm-scaled.jpg',
    },
    # Miami Grill — REMOVED Mar 9 (no longer exists, per Jordana)

    {
        'name': 'Tov-Li Pizza & Falafel',
        'category': 'Caterers',
        'description': 'Kosher pizza, falafel, and Israeli favourites. Great for casual shiva meals and feeding a crowd on a budget. Party trays available.',
        'address': '3457 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 782-2522',
        'website': 'https://tov-li.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': '',
    },
    {
        'name': 'Matti\'s Kitchen',
        'category': 'Caterers',
        'description': 'Home-style kosher cooking with a modern twist. Specializes in comforting meals perfect for shiva — soups, stews, roasted chicken, and side dishes.',
        'address': '3006 Bathurst St, Toronto, ON',
        'neighborhood': 'Lawrence Heights',
        'phone': '(416) 792-0606',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'The Chicken Nest',
        'category': 'Caterers',
        'description': 'Glatt kosher restaurant and caterer serving Toronto for over 30 years. Known for rotisserie chicken, ribs, schnitzel, wings, and Middle Eastern dishes. Dedicated catering menu for shiva, Shabbos, and events. Delivery and takeout available.',
        'address': '3038 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 787-6378',
        'website': 'https://thechickennest.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
        'image_url': 'https://static3.grubbio.com/10522g-albums-2.jpg',
    },
    {
        'name': "Milk 'N Honey",
        'category': 'Caterers',
        'description': "Toronto's longest-serving kosher dairy caterer. Specializing in shiva meals, Shabbat catering, and lifecycle events. COR dairy certified.",
        'address': '3457 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 789-7651',
        'website': 'https://milknhoney.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
        'image_url': 'https://milknhoney.ca/wp-content/uploads/2016/12/IMG_3118-Small.jpg',
    },
    {
        'name': 'Kosher Gourmet',
        'category': 'Caterers',
        'description': 'COR-certified kosher catering specializing in shiva meals. Delivery available across Toronto and the GTA. Known for quality prepared meals and reliable service.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '(416) 781-9900',
        'website': 'https://koshergourmet.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
        'image_url': 'https://cdn11.bigcommerce.com/s-93wuni90xs/images/stencil/390x485/products/176/487/Chicken_Wrap_Box__60284.1686677424.jpg?c=1',
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
        'image_url': 'https://yummymarket.com/wp-content/uploads/2020/10/partyplatters-header.jpg',
    },
    {
        'name': "Daiter's Kitchen",
        'category': 'Caterers',
        'description': 'COR-certified kosher deli and butcher shop. Deli platters, prepared meats, and classic comfort food. A go-to for shiva deli trays.',
        'address': '3535 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 789-1280',
        'website': 'https://www.daiterskitchen.ca',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://www.daiterskitchen.ca/media/2020/03/daiters-675x450.jpg',
    },
    {
        'name': 'Orly\'s Kitchen',
        'category': 'Caterers',
        'description': 'Homestyle kosher Israeli and Mediterranean cooking. Fresh salads, grilled meats, and hearty mains. Catering available for shiva meals.',
        'address': '3413 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 792-0052',
        'website': 'https://orlyskitchen.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': 'https://orlyskitchen.com/assets/hero-bg-TNk09rP1.jpg',
    },
    {
        'name': 'Cafe Sheli',
        'category': 'Caterers',
        'description': 'Kosher dairy cafe offering light meals, salads, fish dishes, and baked goods. Ideal for lighter shiva lunches and dessert platters.',
        'address': '4750 Dufferin St, Toronto, ON',
        'neighborhood': 'North York',
        'phone': '(416) 663-5553',
        'website': 'https://cafesheli.com',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://cafesheli.com/wp-content/uploads/2024/04/cafe-sheli-catering-bg-scaled.jpg',
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
        'image_url': '',
    },
    # Italian & Pizza
    # Village Pizza Kosher — REMOVED Mar 9 (no longer exists, per Jordana)

    # Pizza Pita — Re-added Mar 22, 2026 (see MONTREAL_VENDORS below)
    {
        'name': 'Paisanos',
        'category': 'Restaurants',
        'description': 'Italian restaurant with catering services. Pasta trays, chicken parmigiana, Caesar salads, and tiramisu. Generous portions for family-style meals.',
        'address': '624 College St, Toronto, ON',
        'neighborhood': 'Little Italy',
        'phone': '(416) 534-2801',
        'website': 'https://thepaisanos.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
        'image_url': '',
    },
    {
        'name': 'Terroni',
        'category': 'Restaurants',
        'description': 'Beloved Toronto Italian restaurant group. Offers catering with authentic pasta, antipasti platters, and rustic Italian dishes. Multiple locations.',
        'address': '720 Queen St W, Toronto, ON',
        'neighborhood': 'Queen West',
        'phone': '(416) 504-0320',
        'website': 'https://www.terroni.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
        'image_url': 'https://labottegaditerroni.com/cdn/shop/files/Catering_Hero_2_300x.jpg?v=1746822618',
    },
    {
        'name': 'Tutto Pronto',
        'category': 'Restaurants',
        'description': 'Modern southern Italian catering in North York. Known for arancini, pasta, veal, eggplant parm, and fresh salads. Popular for shiva in the Avenue Rd corridor. All food prepared fresh day-of.',
        'address': '1718 Avenue Rd, North York ON',
        'neighborhood': 'North York',
        'phone': '(416) 782-2227',
        'website': 'https://tuttopronto.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA',
        'image_url': 'https://tuttopronto.ca/wp-content/uploads/2019/11/header-platters.jpg',
    },
    # Middle Eastern / Israeli
    {
        'name': 'Wok & Bowl',
        'category': 'Caterers',
        'description': "Toronto's first COR-certified kosher pho and ramen restaurant. Asian fusion including Chinese dishes, dumplings, noodles, and fried rice. Catering available. Great option for families who want something different at shiva.",
        'address': '3022 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 783-2323',
        'website': 'https://wokandbowl.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
        'image_url': 'https://s3.amazonaws.com/curbngo-menu-items/thumbs/76416CEB-E44C-440C-AB7E-BBDA1195DE5B.jpeg',
    },
    {
        'name': 'Dr. Laffa',
        'category': 'Restaurants',
        'description': 'Popular Israeli restaurant serving fresh laffa wraps, shawarma, hummus, and Middle Eastern platters. Great for casual, flavourful shiva meals.',
        'address': '3027 Bathurst St, Toronto, ON',
        'neighborhood': 'Lawrence Heights',
        'phone': '(416) 792-8989',
        'website': 'https://drlaffa.com/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': '',
    },
    {
        'name': 'Aish Tanoor',
        'category': 'Restaurants',
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
        'category': 'Restaurants',
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
        'category': 'Restaurants',
        'description': 'Israeli grill and shawarma with generous portions and bold flavours. Family meal combos and party platters available. Multiple GTA locations.',
        'address': '7241 Bathurst St, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 889-5559',
        'website': 'https://www.mevame.com/',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
        'image_url': 'https://lirp.cdn-website.com/ed3e1e79/dms3rep/multi/opt/BANNER-BOWLS-2304w.jpg',
    },
    # Pita Box — REMOVED (no longer exists, per Jordana Mar 2026)
    # ── New vendors added per Jordana feedback — Mar 2026 ──
    # My Zaidy's Pizza — removed Mar 2026 (permanently closed per Yelp Jan 2026)
    # More diverse options
    {
        'name': 'Sushi Inn',
        'category': 'Caterers',
        'description': 'Kosher sushi and Japanese-inspired cuisine. Sushi platters and bento boxes are a refreshing alternative for shiva meals. Party trays available.',
        'address': '3461 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 792-0004',
        'website': 'https://www.sushiinn.net/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': '',
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
        'image_url': 'http://static1.squarespace.com/static/6478a38999812546babb8e36/t/67bf42b0d7ee0406f0c5f769/1724096196631/5.png?format=1500w',
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
        'image_url': 'https://picklebarrelcatering.com/wp-content/uploads/2022/03/breakfast-category-300x300.jpg',
    },
    {
        'name': 'Harbord Bakery',
        'category': 'Restaurants',
        'description': 'Beloved neighbourhood bakery with Jewish roots. Famous challah, rye bread, rugelach, and pastries. A Toronto classic since 1945.',
        'address': '115 Harbord St, Toronto, ON',
        'neighborhood': 'Harbord Village',
        'phone': '(416) 922-5767',
        'website': 'https://www.harbordbakery.ca/',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://www.harbordbakery.ca/images/cakes.jpg',
    },
    {
        'name': 'Centre Street Deli',
        'category': 'Restaurants',
        'description': 'Classic Jewish deli in Thornhill since 1988. Montreal-style smoked meat, corned beef, matzo ball soup, and all the deli favourites. Catering platters and party trays available.',
        'address': '1136 Centre St, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 731-8037',
        'website': 'https://www.centrestreetdeli.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York,Toronto',
        'image_url': 'https://static.wixstatic.com/media/a9a0b8_55595057ce8349c4b65d2b44ccb65580~mv2.jpg/v1/crop/x_126,y_1,w_1201,h_792/fill/w_896,h_591,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/pic14_edited.jpg',
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
        'image_url': '',
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
        'image_url': '',
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
        'image_url': 'https://x56.wpenginepowered.com/wp-content/uploads/2023/10/2.2.Catering-Edited-1.jpg',
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
        'image_url': '',
    },
    {
        'name': 'Schmaltz Appetizing',
        'category': 'Restaurants',
        'description': 'Jewish-style appetizing shop specializing in smoked fish, bagel sandwiches, cream cheeses, and deli platters. Catering for groups of 10+. A modern take on classic Jewish comfort food.',
        'address': '414 Dupont St, Toronto, ON',
        'neighborhood': 'Annex',
        'phone': '(647) 350-4261',
        'website': 'https://schmaltzappetizing.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': 'https://ambassador-media-library-assets.s3.amazonaws.com/f707f9af-c2f0-490f-ac3a-8062ca793982.jpg',
    },
    {
        'name': 'Paramount Fine Foods',
        'category': 'Restaurants',
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
        'image_url': 'https://www.danieletdaniel.ca/wp-content/themes/lambda-child-theme/assets/images/Catering-Toronto-Events.jpg',
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
        'image_url': 'https://abc1b6b80c540b51da78.cdn6.editmysite.com/uploads/b/abc1b6b80c540b51da789408a28545b34ec20047c9af1dec09dea835a581d0ec/IG_4.7.2026_69d56d7acbbe64.15870355.jpeg?width=2400&optimize=medium',
    },
    {
        'name': 'Toben Food by Design',
        'category': 'Caterers',
        'description': 'Full-service caterer with 15+ years experience catering shiva and celebrations of life. High-end, customized menus with dietary accommodations including gluten-free and vegan options.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '(647) 344-8323',
        'website': 'https://tobenfoodbydesign.com',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
        'image_url': 'https://e7ovatjya3o.exactdn.com/site-content/uploads/2021/12/GORGEOUS-PLATE-GROUPING-BY-PATTY-OF-NEXT-MAINS-scaled.jpg',
    },
    # ── New verified vendors — Feb 2026 (Sprint 6) ──
    {
        'name': "Ely's Fine Foods",
        'category': 'Caterers',
        'description': 'COR-certified kosher grocery, deli, and caterer serving the Toronto Jewish community since 1993. Fresh daily prepared foods, deli counter, retail store, and full catering services. Available on DoorDash.',
        'address': '3537A Bathurst St, North York, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 782-3231',
        'website': 'https://elysfinefoods.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': 'https://cdn.shopify.com/s/files/1/0405/2896/9883/files/slider-4_e2eee44d-db56-4c79-8384-9bd5625e8c4d.jpg',
    },
    {
        'name': 'Grodzinski Bakery',
        'category': 'Restaurants',
        'description': 'One of Toronto\'s oldest kosher bakeries, operating since 1888. Famous for challah, pastries, and sandwich platters. Completely nut-free facility. Two locations: Bathurst St and Thornhill.',
        'address': '3437 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 789-0785',
        'website': 'https://www.grodzinskibakery.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': 'http://www.grodzinskibakery.com/uploads/upload/Katan%20studios-70.jpg',
    },
    {
        'name': 'Ba-Li Laffa',
        'category': 'Restaurants',
        'description': 'COR-certified kosher Israeli/Mediterranean restaurant known for fresh-baked laffas, falafel, shawarma, kebabs, and hummus. Also serves Asian-fusion dishes. Delivery via DoorDash and SkipTheDishes.',
        'address': '7117 Bathurst St, Unit 110, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 597-7720',
        'website': 'https://www.balilaffa.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
        'image_url': '',
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
        'image_url': 'https://prccaterers.com/wp-content/uploads/2024/09/01HERB1-scaled.jpg',
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
        'image_url': '',
    },
    {
        'name': 'Marron Bistro',
        'category': 'Caterers',
        'description': 'Upscale COR-certified kosher fine dining in Forest Hill. Globally-inspired meat and fish dishes. Often called the best kosher restaurant in Canada. Elegant option for catered shiva meals.',
        'address': '992 Eglinton Ave W, Toronto, ON',
        'neighborhood': 'Forest Hill',
        'phone': '(416) 784-0128',
        'website': 'https://www.marronbistro.com',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://www.marronbistro.com/wp-content/uploads/2016/11/catering_001.jpg',
    },
    # ── New vendors added Mar 9, 2026 (per Jordana) ──
    {
        'name': 'Pizza Cafe',
        'category': 'Caterers',
        'description': 'COR-certified kosher pizza restaurant. Pizza, pasta, and Italian favourites. Affordable catering options for shiva meals.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://www.pizzacafe.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto',
        'image_url': '',
    },
    {
        'name': 'Aroma Espresso Bar',
        'category': 'Restaurants',
        'description': 'Israeli-born cafe chain with multiple locations. Coffee, pastries, salads, sandwiches, and shakshuka. A warm, familiar option for lighter shiva meals.',
        'address': 'Multiple locations, Toronto, ON',
        'neighborhood': 'GTA',
        'phone': '',
        'website': 'https://www.aromaespressobar.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': 'https://www.aromaespressobar.ca/wp-content/uploads/2024/11/Bowls-x-3-scene.jpg',
    },
    {
        'name': 'Chop Hop',
        'category': 'Restaurants',
        'description': 'Fresh, flavourful salads and bowls. A great option for lighter shiva meals and family-style gatherings.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://www.chophop.com',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Toronto',
        'image_url': 'https://d24gls5t8gwt4z.cloudfront.net/images/item/86e281b4-3d39-4ff0-8c71-22acbc66ed66',
    },
    {
        'name': 'Slice n Bites',
        'category': 'Caterers',
        'description': 'COR-certified kosher restaurant. Pizza, wraps, and fresh bites. A convenient option for shiva meals and casual gatherings.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://slicenbites.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto',
        'image_url': 'https://slicenbites.com/wp-content/uploads/2023/01/g02-scaled.jpg',
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
        'image_url': 'https://static.wixstatic.com/media/58d4dc_f8ae1ad9eed84dd1980cdaa6f070869f~mv2.jpg/v1/fill/w_247,h_247,q_75,enc_avif,quality_auto/58d4dc_f8ae1ad9eed84dd1980cdaa6f070869f~mv2.jpg',
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
        'image_url': 'https://mitzuyankoshercatering.com/wp-content/uploads/2023/02/Pulled-Brisket_Mitzuyan-Kosher_Catering.jpg',
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
        'image_url': '',
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
        'image_url': 'https://menchens.ca/img/cocktail_reception1.jpg',
    },
    {
        'name': 'Noah Kosher Sushi',
        'category': 'Caterers',
        'description': 'COR-certified kosher sushi in the Bathurst corridor. A unique and crowd-pleasing option for shiva meals — sushi platters that everyone appreciates.',
        'address': '4119 Bathurst St, North York, ON M3H 3P4',
        'neighborhood': 'Bathurst Manor',
        'phone': '',
        'website': 'http://www.noahkoshersushi.ca',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': 'North York',
        'image_url': 'https://noah-kosher-sushi.vercel.app/images/og-thumbnail.webp',
    },
    {
        'name': 'Royal Dairy Cafe & Catering',
        'category': 'Caterers',
        'description': 'Kosher dairy cafe and catering in Thornhill. Light meals, salads, fish, and baked goods. A warm, welcoming option for dairy shiva meals and lighter gatherings.',
        'address': '10 Disera Dr Unit 100, Thornhill, ON L4J 0A7',
        'neighborhood': 'Thornhill',
        'phone': '',
        'website': 'https://royaldairycafe.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
        'image_url': 'https://royaldairycafe.com/wp-content/uploads/2025/12/RDC-Salad-800600px-v2-copy.webp',
    },
    {
        'name': "Pancer's Original Deli",
        'category': 'Restaurants',
        'description': 'Legendary Toronto Jewish deli on Bathurst. Smoked meat, corned beef, and classic deli platters that have served the community for decades. A comforting, familiar choice for shiva catering.',
        'address': '3856 Bathurst St, North York, ON M3H 3N3',
        'neighborhood': 'Bathurst Manor',
        'phone': '',
        'website': 'http://www.pancersoriginaldeli.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': '',
    },
    {
        'name': "Zelden's Deli and Desserts",
        'category': 'Restaurants',
        'description': 'Jewish-style deli and desserts on Yonge. Sandwiches, salads, baked goods, and catering platters. A dependable choice when you need food for the family.',
        'address': '1446 Yonge St, Toronto, ON M4T 1Y5',
        'neighborhood': 'Midtown',
        'phone': '',
        'website': 'http://www.zeldensdelianddesserts.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
        'image_url': '',
    },
    {
        'name': 'Richmond Kosher Bakery',
        'category': 'Restaurants',
        'description': 'COR-certified kosher bakery on Bathurst. Fresh breads, challahs, pastries, and cakes. A neighbourhood staple for Shabbat baking and shiva dessert trays.',
        'address': '4119 Bathurst St Unit 1, North York, ON M3H 3P4',
        'neighborhood': 'Bathurst Manor',
        'phone': '(647) 776-5995',
        'website': 'http://richmondkosherbakery.com',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': 'North York',
        'image_url': 'https://richmondkosherbakery.com/wp-content/uploads/2023/08/rustic-baguettes-baked-in-bakery-country-kitchen-FLZTJXD-768x512.jpg',
    },
    {
        'name': "Aba's Bagel Company",
        'category': 'Restaurants',
        'description': 'Fresh bagels and baked goods on Eglinton West. Hand-rolled, kettle-boiled bagels with a loyal following. Platters available for gatherings.',
        'address': '884A Eglinton Ave W, Toronto, ON M6C 2B6',
        'neighborhood': 'Midtown',
        'phone': '',
        'website': 'https://abasbagel.com',
        'kosher_status': '',
        'delivery': 0,
        'delivery_area': 'Toronto',
        'image_url': 'https://img1.wsimg.com/isteam/ip/b9fc4f49-b834-4894-b337-fadb0b8205fa/Aba-0140.jpg/:/cr=t:5.36%25,l:20.23%25,w:59.54%25,h:89.29%25/rs=w:360,h:360,cg:true,m',
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
        'category': 'Caterers',
        'description': 'COR-certified kosher burger restaurant in Thornhill. Burgers, hot dogs, fries, and classic comfort food. A crowd-pleasing option for casual shiva meals.',
        'address': '115-1 Promenade Circle, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 597-1606',
        'website': 'https://howiets.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan',
        'image_url': '',
    },
    {
        'name': 'Umami Sushi',
        'category': 'Caterers',
        'description': 'COR-certified kosher sushi restaurant serving Toronto since 2001. Poke bowls, maki combos, udon, soba noodles, and sushi burritos. Catering platters available.',
        'address': '3459 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 782-3375',
        'website': 'https://www.umamisushi.ca/',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': 'https://www.umamisushi.ca/sites/default/files/imagecache/page_header-display/front-page-images/image_gallery/front-page-images-image_gallery-55.jpeg',
    },
    {
        'name': 'Haymishe Bakery',
        'category': 'Restaurants',
        'description': 'Classic kosher bakery on Bathurst. Known for hamantaschen, pastries, and traditional Jewish baked goods. A neighbourhood staple since 1957.',
        'address': '3031 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 781-4212',
        'website': 'https://www.instagram.com/haymishebakeryto/',
        'instagram': 'haymishebakeryto',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
        'image_url': '',
    },
    {
        'name': "Bubby's Bagels",
        'category': 'Restaurants',
        'description': 'COR-certified deli with two locations. NY-style bagels and bialys on Bathurst, plus sandwiches, burgers, tacos, and onion rings at the larger Lawrence Ave diner.',
        'address': '3030 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 862-2435',
        'website': 'https://www.bubbysbagels.com/menu',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': 'https://static.wixstatic.com/media/88e84c_073feaa2390445f79dad02f5c1c7a992~mv2_d_5184_3456_s_4_2.jpg/v1/fill/w_422,h_282,q_90,enc_avif,quality_auto/88e84c_073feaa2390445f79dad02f5c1c7a992~mv2_d_5184_3456_s_4_2.jpg',
    },
    {
        'name': 'Golden Chopsticks',
        'category': 'Caterers',
        'description': 'Glatt kosher Chinese restaurant. Chinese dishes, fried rice, and Asian comfort food. Relocated to Spring Farm Marketplace in Thornhill.',
        'address': '441 Clark Ave W, Unit 15, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 760-2789',
        'website': 'https://goldenchopstick.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
        'image_url': '',
    },
    # Yehudales Falafel and Pizza — removed Mar 2026 (permanently closed per Yelp Dec 2025)
    {
        'name': 'Shalom India',
        'category': 'Caterers',
        'description': "COR-certified kosher Indian restaurant — Toronto's only one. Curries, tandoori, biryani, and vegetarian options — a unique and flavourful choice for shiva meals.",
        'address': '7700 Bathurst St, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 597-3323',
        'website': 'https://shalomindia.ca',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto',
        'image_url': 'https://shalomindia.ca/wp-content/uploads/2023/02/Food.png',
    },
    # Middle Eastern / Mediterranean / Turkish
    {
        'name': 'Sofram Restaurant',
        'category': 'Restaurants',
        'description': 'Turkish and Mediterranean cuisine in North York. Known for generous portions, fresh-baked pide, grilled kebabs, hummus, and mixed grill platters. Reasonably priced and popular for shiva catering orders.',
        'address': '5849 Leslie St, North York, ON',
        'neighborhood': 'North York',
        'phone': '(416) 223-1818',
        'website': 'https://www.sofram.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA',
        'image_url': 'https://sofram.ca/wp-content/uploads/2024/02/S_Home_Desktop.webp',
    },
    # Italian & Pizza
    {
        'name': 'Paese Ristorante',
        'category': 'Restaurants',
        'description': 'Upscale Italian restaurant on Bloor West. Known for housemade pastas, wood-fired pizzas, and refined Italian dishes. A popular choice for shiva catering in the Bloor-Annex neighbourhood.',
        'address': '3827 Bloor St W, Etobicoke, ON',
        'neighborhood': 'Bloor West',
        'phone': '(416) 207-9995',
        'website': 'https://www.paeseristorante.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA',
        'image_url': 'https://farm6.staticflickr.com/5340/30436264196_6456981ebc_b.jpg',
    },
    # New Toronto vendors added Apr 18, 2026 — verified via web research against vendor sites, Yelp, BlogTO, MK/COR directories
    {
        'name': 'Joe Boos Kosher Event Catering',
        'category': 'Caterers',
        'description': 'COR-certified kosher caterer specializing in shiva meals across Toronto, Vaughan, Thornhill, and Richmond Hill. Twenty years of experience, 500+ events per year. Vegetarian, vegan, and gluten-free options. Coordinates delivery and timing so families can focus on what matters.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA',
        'phone': '',
        'website': 'https://joeboos.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': "Levy's Catering",
        'category': 'Caterers',
        'description': 'Family-run kosher caterer with a dedicated shiva tray program. Delivers throughout Toronto and the GTA — including Thornhill, Concord, North York, Vaughan, Markham, Richmond Hill, Newmarket, Scarborough, Etobicoke, and Mississauga.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA',
        'phone': '(416) 256-7886',
        'website': 'https://www.levyskoshercatering.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': 'Pantry by Food Dudes',
        'category': 'Restaurants',
        'description': "The Food Dudes' casual concept. Fresh salads, sandwiches, family-style meals, and platters you can mix and match. Locations in Rosedale, Commerce Court, Richmond-Adelaide, and Yonge & Lawrence. A lighter, more affordable option for shiva meals.",
        'address': '1094 Yonge St, Toronto, ON',
        'neighborhood': 'Rosedale',
        'phone': '',
        'website': 'https://orderpantry.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    {
        'name': 'Limon Restaurant',
        'category': 'Restaurants',
        'description': 'Modern Israeli kitchen with locations in Midtown and the Beaches. Fresh Mediterranean and Middle Eastern flavours — salatim, mains, and sides built for sharing. Full catering menu with reliable delivery throughout Toronto.',
        'address': '1968 Queen St E, Toronto, ON',
        'neighborhood': 'The Beaches',
        'phone': '(416) 901-3440',
        'website': 'https://www.limonbeaches.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
]


# 30 Montreal-area food vendors
MONTREAL_VENDORS = [
    # Caterers (Montreal)
    {
        'name': 'Blossom by La Plaza',
        'category': 'Caterers',
        'description': 'One of Montreal\'s premier kosher caterers, specializing in elegant event planning and gourmet cuisine. Full-service catering for shiva meals, lifecycle events, and community gatherings.',
        'address': '5458 Avenue Westminster, Côte-Saint-Luc, QC',
        'neighborhood': 'Côte-Saint-Luc',
        'phone': '(514) 489-7111',
        'website': 'https://www.blossombylaplaza.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Côte-Saint-Luc,Westmount',
        'image_url': 'https://www.blossombylaplaza.com/cdn/shop/products/5928_sq_300x.jpg?v=1613827994',
    },
    {
        'name': 'Paradise Kosher Catering',
        'category': 'Caterers',
        'description': 'Full-service kosher caterer offering prepared meals, bakery goods, and catering for shiva, Shabbat, and lifecycle events. Provides an à la carte order form for easy meal planning. MK certified.',
        'address': '11608 Boulevard de Salaberry, Dollard-des-Ormeaux, QC',
        'neighborhood': 'Dollard-des-Ormeaux',
        'phone': '(514) 421-0421',
        'website': 'https://www.paradisekosher.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Côte-Saint-Luc,Hampstead,Snowdon',
        'image_url': 'https://www.paradisekosher.com/wp-content/uploads/2018/07/kosher350.png',
    },
    {
        'name': 'Kosher Quality Bakery & Deli',
        'category': 'Caterers',
        'description': 'Iconic Montreal kosher destination offering bakery, butcher, deli, and full catering. Known for challah, prepared Shabbat meals, smoked fish platters, and party sandwiches. MK certified.',
        'address': '5855 Avenue Victoria, Montréal, QC',
        'neighborhood': 'Snowdon',
        'phone': '(514) 731-7883',
        'website': 'https://www.bubbysbagels.com/menu',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Snowdon,Côte-Saint-Luc',
        'image_url': '',
    },
    # Delis & Restaurants
    {
        'name': 'Snowdon Deli',
        'category': 'Restaurants',
        'description': 'A Montreal institution since 1946, beloved for classic smoked meat, deli sandwiches, and homestyle Jewish comfort food. Catering platters ideal for shiva meals.',
        'address': '5265 Boulevard Décarie, Montréal, QC',
        'neighborhood': 'Snowdon',
        'phone': '(514) 488-9129',
        'website': 'https://www.snowdondeli.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'image_url': '',
    },
    {
        'name': 'Deli 365',
        'category': 'Caterers',
        'description': 'MK-certified kosher smoked meat deli on Bernard Street. Take-out sandwiches, burgers, and prepared platters. Reliable for kosher deli trays and comfort food for shiva meals.',
        'address': '365 Rue Bernard Ouest, Montréal, QC',
        'neighborhood': 'Outremont',
        'phone': '(514) 544-3354',
        'website': 'https://deli365.ca',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Outremont,Mile End',
        'image_url': 'https://deli365.ca/wp-content/uploads/2016/06/About-us-pic-2-e1465482294424.jpg',
    },
    {
        'name': 'Schwartz\'s Deli',
        'category': 'Restaurants',
        'description': 'World-famous Montreal smoked meat restaurant since 1928. An iconic Jewish culinary landmark on Boulevard Saint-Laurent.',
        'address': '3895 Boulevard Saint-Laurent, Montréal, QC',
        'neighborhood': 'Plateau Mont-Royal',
        'phone': '(514) 842-4813',
        'website': 'https://schwartzsdeli.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://schwartzsdeli.com/cdn/shop/files/page-catering-services-1.jpg?v=1646472771',
    },
    {
        'name': 'Lester\'s Deli',
        'category': 'Restaurants',
        'description': 'Established in 1951, a beloved Outremont smoked meat institution known for hand-cut fries and community spirit. Catering, take-out, and delivery available.',
        'address': '1057 Avenue Bernard, Outremont, QC',
        'neighborhood': 'Outremont',
        'phone': '(514) 213-1313',
        'website': 'https://lestersdeli.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal,Outremont',
        'image_url': 'https://i0.wp.com/lestersdeli.com/wp-content/uploads/2023/10/DSC02152.jpg',
    },
    # Bagel Shops & Bakeries
    {
        'name': 'Boulangerie Cheskie',
        'category': 'Restaurants',
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
        'category': 'Restaurants',
        'description': 'Legendary wood-fired bagel bakery operating 24/7 since 1957. Hand-rolled Montreal-style bagels baked in a wood-burning oven. A cornerstone of Montreal Jewish food culture.',
        'address': '263 Rue Saint-Viateur Ouest, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 276-8044',
        'website': 'https://stviateurbagel.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal,Canada-wide',
        'image_url': 'https://stviateurbagel.com/cdn/shop/files/StViateurBagel_AdrianoCiampoli_BagelBin-1.jpg?v=1732896354&width=3840',
    },
    {
        'name': 'Fairmount Bagel',
        'category': 'Restaurants',
        'description': 'Montreal\'s original bagel bakery, open 24 hours since 1919. Hand-made, wood-fired bagels. A quintessential Montreal Jewish food experience for bagel platters.',
        'address': '74 Avenue Fairmount Ouest, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 272-0667',
        'website': 'https://fairmountbagel.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'image_url': 'https://fairmountbagel.com/wp-content/uploads/2018/03/hand-bagel-291x300.png',
    },
    {
        'name': 'Montreal Kosher Bakery',
        'category': 'Restaurants',
        'description': 'The largest kosher bakery in Montreal and all of Canada, operating since 1976. Freshly baked muffins, danishes, breads, bagels, and dinner rolls daily. MK certified.',
        'address': '7005 Avenue Victoria, Montréal, QC',
        'neighborhood': 'Côte-des-Neiges',
        'phone': '(514) 739-3651',
        'website': 'https://montrealkosher.ca',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Côte-des-Neiges,Snowdon',
        'image_url': '',
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
        'image_url': 'http://nosherz.com/cdn/shop/collections/platter-2009590_1920_1200x1200.jpg?v=1638390047',
    },
    # Iconic Montreal Restaurants
    {
        'name': "Mandy's",
        'category': 'Restaurants',
        'description': "Montreal's beloved gourmet salad destination with multiple locations. Creative, hearty salads and grain bowls — a fresh, healthy option for feeding a crowd. Catering platters available for groups.",
        'address': '2067 Rue Crescent, Montréal, QC',
        'neighborhood': 'Downtown',
        'phone': '(514) 289-0202',
        'website': 'https://www.mandys.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'image_url': 'https://mandys.ca/wp-content/uploads/2026/01/Mandys-Ordering-Cover.webp',
    },
    {
        'name': "Gibby's",
        'category': 'Restaurants',
        'description': "Iconic Montreal steakhouse in a historic 200-year-old stone building in Old Montreal. Premium steaks, seafood, and classic sides. Private dining and catering for special occasions.",
        'address': "298 Place D'Youville, Montréal, QC",
        'neighborhood': 'Old Montreal',
        'phone': '(514) 282-1837',
        'website': 'https://www.gibbys.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://www.gibbys.com/wp-content/uploads/2025/06/cropped-_GB-Shooting2avril005-2500x1406.jpg',
    },
    {
        'name': "Beauty's Luncheonette",
        'category': 'Restaurants',
        'description': "A Montreal Jewish institution since 1942. Famous for bagels, lox, eggs, and brunch classics. Founded by Hymie Sckolnick — a beloved gathering place for generations of Montreal families.",
        'address': '93 Avenue du Mont-Royal Ouest, Montréal, QC',
        'neighborhood': 'Plateau Mont-Royal',
        'phone': '(514) 849-8883',
        'website': 'https://www.beautys.ca/',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://images.squarespace-cdn.com/content/v1/6633b66c8902e916bd868d86/1fac348b-8b86-4b1c-b531-1646a49d35dd/larry+special.jpg',
    },
    {
        'name': "Wilensky's Light Lunch",
        'category': 'Restaurants',
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
        'category': 'Restaurants',
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
        'category': 'Restaurants',
        'description': "Beloved Outremont French bistro, a neighbourhood favourite for over 20 years. Refined yet accessible cuisine with private dining available for gatherings and celebrations.",
        'address': '1045 Avenue Laurier Ouest, Montréal, QC',
        'neighborhood': 'Outremont',
        'phone': '(514) 270-0999',
        'website': 'https://www.restaurantlemeac.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://images.squarespace-cdn.com/content/v1/5b2bc2a1da02bc3b1c3e2fe9/1662498388633-2TYP8RF6N48NORW9L369/image-asset.jpeg',
    },
    {
        'name': 'Arthurs Nosh Bar',
        'category': 'Restaurants',
        'description': "Jewish-inspired brunch and comfort food. Latkes, smoked fish, shakshuka, and creative deli dishes. A modern take on Montreal's rich Jewish food traditions.",
        'address': '4621 Rue Notre-Dame Ouest, Montréal, QC',
        'neighborhood': 'Saint-Henri',
        'phone': '(514) 757-5190',
        'website': 'https://www.arthursmtl.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://images.tastet.ca/_/rs:fit:1080:720:false:0/plain/https://sesame.tastet.ca/assets/383e3e27-86a5-4704-9b53-279b2d2bbaef.jpg@jpg',
    },
    {
        'name': 'Hof Kelsten',
        'category': 'Restaurants',
        'description': "Award-winning artisan bakery and deli in Mile End. Sourdough breads, croissants, smoked meat sandwiches, and pastries. A modern Montreal bakery with deep respect for tradition.",
        'address': '4524 Boulevard Saint-Laurent, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 277-7700',
        'website': 'https://www.hofkelsten.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://tastet.ca/wp-content/uploads/2017/10/hof-kelsten-boulevard-st-laurent-montreal-jeffrey-finkelstein-15-e1508441445538.jpg',
    },
    {
        'name': 'Olive et Gourmando',
        'category': 'Restaurants',
        'description': "Beloved Old Montreal bakery and café known for artisan breads, gourmet sandwiches, and beautiful pastries. A go-to for high-quality baked goods and catering platters.",
        'address': '351 Rue Saint-Paul Ouest, Montréal, QC',
        'neighborhood': 'Old Montreal',
        'phone': '(514) 350-1083',
        'website': 'https://oliveetgourmando.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'image_url': 'https://oliveetgourmando.com/cdn/shop/files/DO01220577.jpg?v=1773931332&width=1500',
    },
    # ── New verified Montreal vendors — Feb 2026 (Sprint 6) ──
    {
        'name': 'District Bagel',
        'category': 'Restaurants',
        'description': 'The only MK-certified wood-fired Montreal-style bagel bakery. Three locations across Montreal with a 100% kosher menu. Online ordering, catering for corporate events, school lunches, and celebrations.',
        'address': '709 Chemin Lucerne, Mount Royal, QC',
        'neighborhood': 'Mount Royal',
        'phone': '(514) 735-1174',
        'website': 'https://districtbagel.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Mount Royal,Snowdon',
        'image_url': 'https://districtbagel.com/wp-content/uploads/2021/01/bagels.jpeg',
    },
    {
        'name': "JoJo's Pizza",
        'category': 'Restaurants',
        'description': 'New York-style kosher pizza in Mile End under the highest level of MK Mehadrin kosher supervision. Thin-crust pies, dine-in, takeout, and delivery via Uber Eats and DoorDash.',
        'address': '355 Rue Bernard Ouest, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 975-2770',
        'website': 'https://www.umamisushi.ca/',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Mile End,Outremont',
        'image_url': '',
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
        'image_url': 'http://www.lamarguerite.ca/cdn/shop/files/Grilledvegetables_1200x1200.png?v=1770924633',
    },
    {
        'name': "Oineg's Kosher",
        'category': 'Caterers',
        'description': 'A Mile End staple for prepared kosher Shabbat meals. MK-certified meat restaurant known for cholent, sandwiches, dips, and liver. Full Shabbos takeout, dine-in, and catering services.',
        'address': '360 Rue Saint-Viateur Ouest, Montréal, QC',
        'neighborhood': 'Mile End',
        'phone': '(514) 277-3600',
        'website': 'https://www.oinegshabbes.com/',
        'instagram': 'oinegskosher',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Mile End,Outremont',
        'image_url': 'https://static.wixstatic.com/media/9bf085_f157f2f766774660a07c0ff5d1073c58%7Emv2.jpg/v1/fit/w_2500,h_1330,al_c/9bf085_f157f2f766774660a07c0ff5d1073c58%7Emv2.jpg',
    },
    {
        'name': "Chenoy's Deli",
        'category': 'Restaurants',
        'description': 'Legendary Montreal Jewish-style deli open since 1936. Famous for Montreal-style smoked meat sandwiches. The last remaining Chenoy\'s location in Dollard-des-Ormeaux. Open 24/7.',
        'address': '3616 Boulevard Saint-Jean, Dollard-des-Ormeaux, QC',
        'neighborhood': 'Dollard-des-Ormeaux',
        'phone': '(514) 620-2584',
        'website': 'https://chenoys-deli.goto-where.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://static.goto-where.com/7042-albums-7.jpg',
    },
    # ── New Montreal vendors from MK research — Mar 4, 2026 ──
    # Citrus Traiteur — REMOVED Mar 9 (per Jordana)

    {
        'name': 'Mehadrin Meats',
        'category': 'Caterers',
        'description': 'MK-certified kosher butcher, takeout, and full-service caterer in the Mile End area. Prepared Shabbos meals, deli meats, and catering for shiva and lifecycle events.',
        'address': '8600 8e Ave, Montréal, QC',
        'neighborhood': 'Outremont',
        'phone': '(514) 321-8000',
        'website': 'https://mehadrinmeats.ca',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Outremont,Mile End,Côte-Saint-Luc',
        'image_url': '',
    },
    # ── Montreal restaurants (MK-certified, added Mar 4 research) ──
    {
        'name': 'Benny & Fils',
        'category': 'Restaurants',
        'description': 'Family-run kosher grill serving shawarma, falafel, schnitzel, and Mediterranean-style meat dishes on Queen Mary Road.',
        'address': '4944 Queen Mary Rd, Montreal, QC H3W 1X2',
        'neighborhood': 'Snowdon',
        'phone': '(514) 735-5858',
        'website': 'http://www.bennyetfils.com/',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Snowdon,Cote-des-Neiges,Hampstead,Cote-Saint-Luc',
        'image_url': '',
    },
    # Benny & Fils Downtown REMOVED per Jordana Mar 25 — keep Queen Mary only
    {
        'name': "Linny's Luncheonette",
        'category': 'Restaurants',
        'description': "Nostalgic Jewish-style takeout deli on Ossington Ave. Hand-cut pastrami on rye, freshly baked knishes, smoked fish sandwiches, and full-sour pickles. Named after restaurateur David Schwartz's late mother Linda. Catering available.",
        'address': '174 Ossington Avenue, Toronto, ON M6J 2Z7',
        'neighborhood': 'Ossington',
        'phone': '',
        'website': 'https://linnysluncheonette.com',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://linnysluncheonette.com/assets/images/social.png',
    },
    # ── New vendors from Jordana — Mar 25, 2026 ──
    {
        'name': 'Encore Catering',
        'category': 'Caterers',
        'description': 'A trusted name in Toronto catering since 1979. Encore brings warmth and professionalism to meaningful gatherings — from shiva meals to celebrations of life — with generous portions and attentive service.',
        'address': '5000 Dufferin St, Unit P, Toronto, ON M3H 5T5',
        'neighborhood': 'Downsview',
        'phone': '(416) 661-4460',
        'website': 'https://encorecatering.com/',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,North York,GTA-wide',
        'image_url': 'https://encorecatering.com/wp-content/uploads/Encore-Catering-Homepage-Hero-Image.png',
    },
    {
        'name': 'Jerusalem Restaurant',
        'category': 'Restaurants',
        'description': "Toronto's first Middle Eastern restaurant, serving beloved family recipes since 1971. A cornerstone of the Forest Hill Jewish community, offering the kind of comforting, home-style fare that nourishes during times of loss.",
        'address': '955 Eglinton Ave W, Toronto, ON M6C 2C4',
        'neighborhood': 'Forest Hill',
        'phone': '(416) 783-6494',
        'website': 'https://www.jerusalemrestaurant.ca/',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
        'image_url': 'https://eglinton.jerusalemrestaurant.ca/restaurants/jerusalem/gallery/1.jpg',
    },
    {
        'name': 'Tabule',
        'category': 'Restaurants',
        'description': 'A warm and inviting Midtown destination for exceptional Middle Eastern cuisine since 2005. Comforting dishes rooted in tradition — a thoughtful option for bringing nourishing food to families during difficult times.',
        'address': '2009 Yonge St, Toronto, ON',
        'neighborhood': 'Midtown',
        'phone': '(416) 483-3747',
        'website': 'https://tabule.ca/location/tabule-midtown/',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Midtown,Toronto',
        'image_url': 'https://tabule.ca/wp-content/uploads/2025/09/tabule-menu_feat-image-rect.png',
    },
    {
        'name': 'Deli 770',
        'category': 'Restaurants',
        'description': 'Chabad-inspired kosher deli in the Westbury complex specializing in Montreal-style smoked meat sandwiches and gourmet grill fusions.',
        'address': '5193 Avenue de Courtrai, Montreal, QC H3W 2X7',
        'neighborhood': 'Snowdon',
        'phone': '(514) 335-4770',
        'website': 'https://deli770.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Snowdon,Cote-des-Neiges,Cote-Saint-Luc',
        'image_url': 'https://deli770.com/wp-content/uploads/2024/07/Smoked-Meat-.png',
    },
    {
        'name': 'Deli Boyz',
        'category': 'Restaurants',
        'description': 'Kosher deli in Quartier Cavendish Mall serving smoked meat, schnitzel, burgers, wraps, and salads.',
        'address': '5800 Cavendish Blvd, Cote-Saint-Luc, QC H4W 2T5',
        'neighborhood': 'Cote-Saint-Luc',
        'phone': '(514) 303-2699',
        'website': 'https://restaurantdeliboyz.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Cote-Saint-Luc,Hampstead,Snowdon',
        'image_url': 'https://restaurantdeliboyz.com/wp-content/uploads/2023/12/Combo-poulet-BBQ-BBQ-Chicken-Combo-1.png',
    },
    {
        'name': 'Chiyoko',
        'category': 'Restaurants',
        'description': 'Upscale kosher Japanese restaurant in Ville Saint-Laurent serving sushi-grade fish and fine cuts of meat in an elegant setting.',
        'address': '2113 Rue Saint-Louis, Saint-Laurent, QC H4M 1P1',
        'neighborhood': 'Saint-Laurent',
        'phone': '(514) 804-0581',
        'website': 'https://www.chiyokosushi.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Saint-Laurent,Cote-des-Neiges,Town of Mount Royal',
        'image_url': 'https://static.wixstatic.com/media/98cfe8_de8423a9d5634a47871ef721c1a9c0bb~mv2_d_3888_2592_s_4_2.jpg/v1/fit/w_480,h_321,q_90,enc_avif,quality_auto/98cfe8_de8423a9d5634a47871ef721c1a9c0bb~mv2_d_3888_2592_s_4_2.jpg',
    },
    {
        'name': 'LeFalafel Plus',
        'category': 'Restaurants',
        'description': 'Israeli-style MK Mehadrin kosher restaurant on Decarie serving high-quality falafel, shawarma, schnitzel, and Middle Eastern dishes.',
        'address': '6245 Decarie Blvd, Montreal, QC H3W 3E1',
        'neighborhood': 'Snowdon',
        'phone': '(514) 731-1221',
        'website': '',
        'instagram': 'lefalafel_+',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Snowdon,Cote-des-Neiges,Cote-Saint-Luc,Hampstead',
    },
    {
        'name': 'Pizza Gourmetti',
        'category': 'Restaurants',
        'description': 'Authentic New York-style kosher Cholov Yisroel pizza restaurant in Saint-Laurent serving thin-crust pizzas, salads, and sandwiches since 2009.',
        'address': '2075 Rue Saint-Louis, Saint-Laurent, QC H4W 1S5',
        'neighborhood': 'Saint-Laurent',
        'phone': '(514) 739-7707',
        'website': 'https://www.pizzagourmetti.com',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Saint-Laurent,Cote-des-Neiges,Town of Mount Royal',
        'image_url': '',
    },
    {
        'name': 'Pizza Pita Prime',
        'category': 'Restaurants',
        'description': 'Long-standing kosher pizzeria run by the Shpiegelman family for three decades, serving pizza, pasta, and dairy dishes with catering services.',
        'address': '5345 Vezina, Montreal, QC H3X 4A8',
        'neighborhood': 'Snowdon',
        'phone': '(514) 731-7482',
        'website': 'https://pizzapitaprime.order-online.ai/',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Snowdon,Cote-des-Neiges,Cote-Saint-Luc,Hampstead',
        'image_url': '',
    },
    # Gift Baskets
    {
        'name': 'Gifting Kosher Canada',
        'category': 'Gifts & Platters',
        'vendor_type': 'gift',
        'description': 'Canada\'s leading online retailer of kosher shiva gift baskets. Gourmet food, wine, cakes, chocolates, and customizable baskets. Same-day and next-day delivery to Montreal.',
        'address': 'Online — ships Canada-wide',
        'neighborhood': 'Montreal',
        'phone': '1-(800) 548-9624',
        'website': 'https://giftingkosher.ca',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Canada-wide',
        'image_url': 'http://giftingkosher.ca/cdn/shop/files/DecadentFlourlessChocolateCake_600x.png?v=1745435270',
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
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
        'image_url': 'https://mevamekitchenexpress.ca/wp-content/themes/mevamekitchenexpress/assets/img/menu/2022/variety_plates.webp',
    },
    # Orly's Kitchen duplicate removed — original entry at line ~326 with full details
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
        'image_url': 'https://pantryfoods.ca/img/background1.jpg',
    },
]


# 25 gift vendors (local, lead capture, affiliate)
GIFT_VENDORS = [
    {
        'name': 'Baskets n\' Stuf',
        'category': 'Gifts & Platters',
        'description': 'Kosher gift baskets and shiva platters. Beautiful arrangements with fresh fruit, baked goods, and gourmet treats. Experienced in shiva deliveries.',
        'address': '6237 Bathurst St, North York, ON',
        'neighborhood': 'North York',
        'phone': '(416) 250-9116',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
    {
        'name': 'Ely\'s Fine Foods Gift Baskets',
        'category': 'Gifts & Platters',
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
        'category': 'Gifts & Platters',
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
        'category': 'Gifts & Platters',
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
        'category': 'Gifts & Platters',
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
        'category': 'Gifts & Platters',
        'description': 'Beautiful fruit arrangements and displays. Fresh, colourful, and healthy. A thoughtful and refreshing gift for a shiva home.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '(416) 500-5141',
        'website': 'https://fruitate.com/',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
    {
        'name': 'Epic Baskets',
        'category': 'Gifts & Platters',
        'description': 'Fresh fruit baskets and gourmet gift packages. Same-day delivery in GTA. Beautiful presentation for a meaningful gift.',
        'address': '3100 Ridgeway Drive, Unit 39, Mississauga, ON',
        'neighborhood': 'GTA',
        'phone': '(905) 855-0303',
        'website': 'https://www.epicbaskets.com/',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA + same-day',
    },
    {
        'name': 'My Baskets',
        'category': 'Gifts & Platters',
        'description': 'Fruit and gift baskets with free delivery over $100 in the GTA. Wide variety of sympathy and condolence baskets.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA',
        'phone': '',
        'website': 'https://www.mybaskets.ca/',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA (free over $100)',
    },
    # 24-Hour Yahrzeit Memorial Candles — REMOVED Mar 9 (per Jordana)

    # Chocolate & Sweets
    {
        'name': 'Purdys Chocolatier',
        'category': 'Gifts & Platters',
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
        'category': 'Gifts & Platters',
        'description': 'Iconic Canadian chocolate and candy company since 1913. Classic boxed chocolates, fudge, and sweet gift sets. Multiple GTA retail locations plus online ordering.',
        'address': 'Multiple GTA locations',
        'neighborhood': 'GTA',
        'phone': '',
        'website': 'https://www.laurasecord.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Canada-wide',
    },
    {
        'name': 'Boards by Dani',
        'category': 'Gifts & Platters',
        'description': 'Beautiful custom charcuterie and dessert boards. Perfect for bringing to a shiva home — artfully arranged platters that show you care. Toronto-based with local delivery.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://boardsbydani.com',
        'instagram': 'boards_by_dani',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
    },
    # ── New gift basket vendors (Sprint 5 follow-up) ──
    {
        'name': 'Baskets Galore',
        'category': 'Gifts & Platters',
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
        'category': 'Gifts & Platters',
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
        'category': 'Gifts & Platters',
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
        'category': 'Gifts & Platters',
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
        'category': 'Gifts & Platters',
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
        'category': 'Gifts & Platters',
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
        'category': 'Restaurants',
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
        'category': 'Restaurants',
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
        'category': 'Restaurants',
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
        'category': 'Restaurants',
        'description': 'Beautiful custom cookies and sweet treats. Gift boxes perfect for bringing something special to a shiva home.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': '',
        'instagram': 'abcookies.co',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Skye Dough Cookies',
        'category': 'Restaurants',
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
    {
        'name': 'Candy Catchers',
        'category': 'Gifts & Platters',
        'description': 'Creative kosher candy and treat gift boxes. Colourful, fun gift options perfect for bringing to a shiva home or sending condolences.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://candycatchers.com/',
        'kosher_status': 'Kosher',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
    },
    # ── New vendors added Mar 18, 2026 (per Jordana) ──
    {
        'name': 'Box and Board',
        'category': 'Gifts & Platters',
        'description': 'Beautiful charcuterie-style gift boxes featuring chocolates, nuts, dried fruit, and gourmet treats. Thoughtful and elegant gifts for a shiva home.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://www.boxandboard.ca',
        'instagram': '',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto,GTA',
    },
    {
        'name': 'Becked Goods',
        'category': 'Restaurants',
        'description': 'Homemade baked goods and cookie gifts. A warm, personal option for bringing something sweet to a shiva home.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': 'https://beckedgoods.com',
        'instagram': '',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
    },
    # ── New Montreal vendors — Mar 22, 2026 ──
    {
        'name': 'Falafel St. Jacques',
        'category': 'Restaurants',
        'vendor_type': 'food',
        'description': 'Popular Middle Eastern street food restaurant founded by an Israeli-Palestinian duo. Crispy falafel, shawarma, fresh pita, and baked goods including rugelach and babka. Multiple Montreal locations.',
        'address': '345 Rue Saint-Jacques, Lachine, QC',
        'neighborhood': 'Montreal',
        'phone': '(514) 595-7482',
        'website': 'https://falafelstjacques.ca',
        'instagram': 'falafelstjacques',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Fressers',
        'category': 'Restaurants',
        'vendor_type': 'food',
        'description': 'Beloved Montreal deli and bakery on Decarie Boulevard known for kosher-style sandwiches, fresh pastries, and classic comfort food. A neighbourhood staple in Snowdon.',
        'address': '5737 Boulevard Décarie, Montréal, QC H3W 3C8',
        'neighborhood': 'Montreal',
        'phone': '(514) 739-4034',
        'website': 'https://www.restomontreal.ca/resto/fressers-cote-des-neiges/19167/en/',
        'instagram': '',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'David Sacks Catering',
        'category': 'Caterers',
        'vendor_type': 'food',
        'description': 'Montreal caterer specializing in modern cocktail cuisine and artisanal ingredients. Full-service catering for events across the West Island and Greater Montreal. Can accommodate kosher requirements.',
        'address': 'Montreal, QC',
        'neighborhood': 'Montreal',
        'phone': '(514) 887-9799',
        'website': 'https://davidsackscatering.com',
        'instagram': 'davidsackscatering',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Cote St Luc BBQ',
        'category': 'Restaurants',
        'vendor_type': 'food',
        'description': 'Montreal charcoal chicken institution since 1953. Famous rotisserie chicken, fries, and BBQ sauce. Multiple locations including NDG and DDO. Catering and delivery available.',
        'address': '5403 Chemin de la Côte-Saint-Luc, Montréal, QC H3X 2C3',
        'neighborhood': 'Montreal',
        'phone': '(514) 488-4011',
        'website': 'https://cotestlucbbq.com',
        'instagram': 'cotestlucbbqndg',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Beso',
        'category': 'Caterers',
        'vendor_type': 'food',
        'description': 'MK-certified kosher catering, bakery, and takeout in Côte-Saint-Luc. Specializes in Shabbat foods, event catering, and refined kosher cuisine. Meat, dairy, pareve, and fish options.',
        'address': '7018 Côte-Saint-Luc Rd, Montréal, QC H4V 1J3',
        'neighborhood': 'Montreal',
        'phone': '(514) 488-5595',
        'website': 'https://besomontreal.ca',
        'instagram': 'besomtl',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Adar',
        'category': 'Caterers',
        'vendor_type': 'food',
        'description': 'MK-certified kosher bakery, supermarket, and takeout in Côte-Saint-Luc since 1996. Freshly baked goods, pastries, prepared meals, grocery items, fruits and vegetables. Catering available.',
        'address': '5634 Avenue Westminster, Côte-Saint-Luc, QC H4W 2J3',
        'neighborhood': 'Montreal',
        'phone': '(514) 484-1189',
        'website': 'https://www.adar.ca',
        'instagram': '',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Pizza Pita',
        'category': 'Caterers',
        'vendor_type': 'food',
        'description': 'Long-standing Montreal kosher pizzeria and dairy restaurant. Pizza, pita, pasta, and Middle Eastern-style dairy dishes. MK certified. Dine-in, takeout, and delivery.',
        'address': '5345 Avenue Vezina, Montréal, QC H3X 4A8',
        'neighborhood': 'Montreal',
        'phone': '(514) 731-7482',
        'website': 'https://pizzapitaprime.order-online.ai/',
        'instagram': '',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Zera Cafe',
        'category': 'Caterers',
        'vendor_type': 'food',
        'description': 'MK-certified kosher cafe and catering social enterprise employing neurodivergent adults. Creative plant-based menu with modern Israeli and Jewish-inspired foods. Catering and weekly meal delivery.',
        'address': '5151 Chemin de la Côte-Sainte-Catherine, Montréal, QC H3W 1M6',
        'neighborhood': 'Montreal',
        'phone': '(514) 734-1640',
        'website': 'https://zeracafe.ca',
        'instagram': 'zeracafeandcatering',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Yans Deli',
        'category': 'Restaurants',
        'vendor_type': 'food',
        'description': 'Modern Montreal delicatessen from former Joe Beef chef Benji Greenberg. Elevated Jewish deli classics with refined twists — smoked meat, chopped liver, knishes, and house-baked goods.',
        'address': '5345 Rue Ferrier, Montréal, QC H4P 1M1',
        'neighborhood': 'Montreal',
        'phone': '(438) 375-1765',
        'website': 'https://yansdeli.com',
        'instagram': 'yansdeli',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Eatz Chez Vouz',
        'category': 'Caterers',
        'vendor_type': 'food',
        'description': 'West Island gourmet prêt-à-manger and catering in Marché de l\'Ouest. Fresh prepared meals, baked goods, comfort food, and holiday treats. Corporate and private catering available.',
        'address': '11692 Boulevard de Salaberry, Dollard-des-Ormeaux, QC H9B 2R8',
        'neighborhood': 'Montreal',
        'phone': '(514) 683-3289',
        'website': 'https://eatzchezvouz.com',
        'instagram': 'eatzchezvouz',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Cuisine Pronto MTL',
        'category': 'Restaurants',
        'vendor_type': 'food',
        'description': 'Neighbourhood pizzeria in the Plateau-Mont-Royal known for homemade lasagna, pizza, sandwiches, and prepared dishes. Fresh daily cooking with high-quality ingredients. Catering and frozen meal options.',
        'address': '2025 Avenue du Mont-Royal E, Montréal, QC H2H 1J7',
        'neighborhood': 'Montreal',
        'phone': '(514) 903-7499',
        'website': 'https://prontomtl.com',
        'instagram': 'cuisine_pronto_mtl',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Clarke Cafe',
        'category': 'Restaurants',
        'vendor_type': 'food',
        'description': 'Family-run cafe in Pointe-Saint-Charles (est. 2018) carrying on the legacy of Boulangerie Clarke. Italian-style sandwiches, fresh baked goods, and specialty coffee. Two locations: PSC and Kirkland.',
        'address': '1207 Rue Shearer, Montréal, QC H3K 1H8',
        'neighborhood': 'Montreal',
        'phone': '(514) 938-5554',
        'website': 'https://clarkecafe.com',
        'instagram': 'clarkecafe',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': '3 Soeurs',
        'category': 'Caterers',
        'vendor_type': 'food',
        'description': 'West Island catering and restaurant run by the three Bourgault sisters since 1996. Gourmet salads, sandwiches, quiches, and soups. Private event space and full catering services.',
        'address': '3693 Boulevard Saint-Jean, Dollard-des-Ormeaux, QC H9G 1X2',
        'neighborhood': 'Montreal',
        'phone': '(514) 675-3773',
        'website': 'https://www.3soeurs.com',
        'instagram': '3soeursbols',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Solomos',
        'category': 'Restaurants',
        'vendor_type': 'food',
        'description': 'Montreal specialty food shop famous for hand-sliced smoked salmon, bagels, and salmon tartares. A local favourite on Queen Mary Road. Platters and catering available.',
        'address': '5453 Chemin Queen Mary, Montréal, QC H3X 1V4',
        'neighborhood': 'Montreal',
        'phone': '(514) 369-4967',
        'website': 'https://solomos.ca',
        'instagram': 'solomos514',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Bagels on Greene',
        'category': 'Restaurants',
        'vendor_type': 'food',
        'description': 'Westmount bagel shop and cafe serving Montreal-style bagels, sandwiches, salads, and breakfast. Diverse menu with gluten-free and vegan options. Catering platters available.',
        'address': '4160 Rue Sainte-Catherine O, Westmount, QC H3Z 1P4',
        'neighborhood': 'Montreal',
        'phone': '(514) 846-3773',
        'website': 'https://bagelsongreene.com',
        'instagram': 'bagelsongreene',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
    },
    {
        'name': 'Bossa',
        'category': 'Restaurants',
        'vendor_type': 'food',
        'description': 'Montreal Italian deli offering signature gourmet sandwiches, fresh pasta, groceries, and prepared meals. Locations in Verdun, Rosemont, and Downtown. Catering and takeout.',
        'address': '4354 Rue Wellington, Montréal, QC H4G 1W4',
        'neighborhood': 'Montreal',
        'phone': '(438) 387-1211',
        'website': 'https://www.bossa.ca',
        'instagram': 'bossamtl',
        'kosher_status': '',
        'delivery': 1,
        'delivery_area': 'Montreal',
        'featured': 0,
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


def enrich_vendor_images(db_path=None):
    """Apply vendor image/instagram/phone enrichment from outscraper pipeline.
    Safe to run multiple times — all UPDATEs are conditional (only where NULL)."""
    path = db_path or DB_PATH
    enrichment_sql = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outscraper_pipeline', 'vendor_enrichment.sql')
    if not os.path.exists(enrichment_sql):
        logging.info("No vendor_enrichment.sql found. Skipping image enrichment.")
        return 0

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Count images before
    cursor.execute("SELECT COUNT(*) FROM vendors WHERE image_url IS NOT NULL AND image_url != ''")
    before = cursor.fetchone()[0]

    with open(enrichment_sql, 'r') as f:
        sql = f.read()

    for statement in sql.split(';'):
        stmt = statement.strip()
        if stmt and not stmt.startswith('--'):
            try:
                cursor.execute(stmt)
            except Exception as e:
                logging.warning(f"Enrichment SQL error: {e} — statement: {stmt[:80]}")

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM vendors WHERE image_url IS NOT NULL AND image_url != ''")
    after = cursor.fetchone()[0]
    updated = after - before

    conn.close()
    logging.info(f"Image enrichment: {updated} vendor(s) updated ({after} total with images)")
    return updated


def backfill_vendor_logistics(db_path=None):
    """Set per-type defaults for min_order and lead_time on vendors that don't have them.
    Safe to re-run — only updates rows where the field is NULL or empty.
    Manual per-vendor overrides survive future seeds."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Per-type defaults — currently EMPTY by design.
    # Erin's call (Apr 19, 2026): no fake/guessed data on cards. The meta line
    # (min_order · lead_time) renders only when real per-vendor values exist.
    # To populate: UPDATE vendors SET min_order = ?, lead_time = ? WHERE slug = ?
    # Manual per-vendor edits survive future seeds (this function only fills NULLs).
    defaults = {}

    total_updated = 0
    for category, vals in defaults.items():
        for field, value in vals.items():
            if value is None:
                continue
            cursor.execute(
                f"UPDATE vendors SET {field} = ? "
                f"WHERE category = ? AND ({field} IS NULL OR {field} = '')",
                (value, category)
            )
            if cursor.rowcount > 0:
                logging.info(f"Logistics backfill: {cursor.rowcount} {category} rows got {field}='{value}'")
                total_updated += cursor.rowcount

    conn.commit()
    conn.close()
    logging.info(f"Logistics backfill complete: {total_updated} field-level updates")
    return total_updated


def backfill_vendor_cities(db_path=None):
    """Detect and backfill city for vendors with NULL city column."""
    path = db_path or DB_PATH
    sys_dir = os.path.dirname(os.path.abspath(__file__))
    if sys_dir not in sys.path:
        sys.path.insert(0, sys_dir)
    from city_config import detect_city_from_text, CITIES

    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.execute('PRAGMA busy_timeout=30000')
    cursor = conn.cursor()

    cursor.execute('SELECT id, address, neighborhood, delivery_area FROM vendors WHERE city IS NULL')
    rows = cursor.fetchall()
    updated = 0
    for row in rows:
        vid, address, neighborhood, delivery_area = row
        text = ' '.join(filter(None, [address, neighborhood, delivery_area]))
        slug = detect_city_from_text(text)
        if slug and slug in CITIES:
            display_name = CITIES[slug]['display_name']
            cursor.execute('UPDATE vendors SET city = ? WHERE id = ?', (display_name, vid))
            updated += 1
    conn.close()
    if updated:
        logging.info(f" Vendor cities: backfilled {updated} vendors")
    return updated


if __name__ == '__main__':
    seed_vendors()
    backfill_vendor_emails()
    enrich_vendor_images()
    backfill_vendor_cities()
    backfill_vendor_logistics()
