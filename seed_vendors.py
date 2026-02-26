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


# 37 Toronto-area food vendors
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
        'kosher_status': 'COR',
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
        'website': '',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Kiva\'s Bagels',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Fresh bagels and baked goods in the heart of the Jewish community. Known for their challah, rugelach, and deli-style platters.',
        'address': '750 Spadina Ave, Toronto, ON',
        'neighborhood': 'Kensington',
        'phone': '(416) 963-5482',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Bagel World',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Popular North York bagel shop offering fresh bagels, cream cheese spreads, lox platters, and catering trays for all occasions.',
        'address': '366 Wilson Ave, Toronto, ON',
        'neighborhood': 'North York',
        'phone': '(416) 636-9011',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Hermes Bakery',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Full-service kosher bakery offering cakes, pastries, challah, and dessert platters. Perfect for shiva dessert trays and Shabbat baking.',
        'address': '3489 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 781-1156',
        'website': '',
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
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Fresh, wholesome platters and prepared meals with generous portions. Extensive experience catering shiva meals with flexible delivery timing. Platters and hot meals for 10-50+ guests.',
        'address': '441 Clark Ave W, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(416) 785-6161',
        'website': 'https://www.jemsalads.com',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York,Toronto',
        'featured': 1,
    },
    {
        'name': 'Bistro Grande',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Upscale kosher dining and catering. Offers elegant plated meals, buffet setups, and family-style dinners suitable for shiva gatherings.',
        'address': '7241 Bathurst St, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 709-4999',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
    },
    {
        'name': 'Miami Grill',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Popular kosher restaurant known for grilled meats, shawarma, and generous portions. Offers catering platters and family meal packages.',
        'address': '3450 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 792-4500',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Tov-Li Pizza & Falafel',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Kosher pizza, falafel, and Israeli favourites. Great for casual shiva meals and feeding a crowd on a budget. Party trays available.',
        'address': '3457 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 782-2522',
        'website': '',
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
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Yummy Market',
        'category': 'Kosher Restaurants & Caterers',
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
        'name': 'Daiter\'s Meat & Deli',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Traditional kosher deli and butcher shop. Deli platters, prepared meats, and classic comfort food. A go-to for shiva deli trays.',
        'address': '3450 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 781-1324',
        'website': '',
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
        'website': '',
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
        'website': '',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
    },
    # Caterers (dedicated catering companies)
    {
        'name': 'Creative Kosher Catering',
        'category': 'Caterers',
        'description': 'Premium kosher catering with creative menus and elegant presentation. Offers customized shiva meal packages from intimate family dinners to large community gatherings.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA-wide',
        'phone': '(416) 792-1234',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': 'Main Event Catering',
        'category': 'Caterers',
        'description': 'Experienced kosher caterer handling events from 20 to 500 guests. Full-service catering including staff, setup, and rentals. Known for reliability and quality.',
        'address': 'Thornhill, ON',
        'neighborhood': 'GTA-wide',
        'phone': '(905) 881-2222',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': 'Taam Hayam Catering',
        'category': 'Caterers',
        'description': 'Kosher fish and dairy catering specialist. Beautiful salmon platters, tuna trays, and dairy buffets perfect for shiva meals and community events.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA-wide',
        'phone': '(416) 789-8888',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    {
        'name': 'Josh\'s Catering',
        'category': 'Caterers',
        'description': 'Affordable kosher catering with generous portions. Specializes in family-style meals that are easy to serve and reheat. Popular choice for multi-day shiva meal coordination.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA-wide',
        'phone': '(416) 792-5678',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA-wide',
    },
    # Italian
    {
        'name': 'Village Pizza Kosher',
        'category': 'Italian',
        'description': 'Kosher pizza and Italian favourites. Offers pizza platters, pasta trays, and garlic bread that are crowd-pleasers at any gathering. Affordable catering options.',
        'address': '3440 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 781-0081',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Pizza Pita',
        'category': 'Italian',
        'description': 'Kosher pizza, calzones, and pasta. A favourite for casual meals. Party-size pizza trays and pasta platters make feeding a crowd easy and affordable.',
        'address': '3495 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 787-0321',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Il Paesano',
        'category': 'Italian',
        'description': 'Authentic Italian restaurant with catering services. Pasta trays, chicken parmigiana, Caesar salads, and tiramisu. Generous portions for family-style meals.',
        'address': '624 College St, Toronto, ON',
        'neighborhood': 'Little Italy',
        'phone': '(416) 534-2801',
        'website': '',
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
    # Middle Eastern / Israeli
    {
        'name': 'Dr. Laffa',
        'category': 'Middle Eastern & Israeli',
        'description': 'Popular Israeli restaurant serving fresh laffa wraps, shawarma, hummus, and Middle Eastern platters. Great for casual, flavourful shiva meals.',
        'address': '3027 Bathurst St, Toronto, ON',
        'neighborhood': 'Lawrence Heights',
        'phone': '(416) 792-8989',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Aish Tanoor',
        'category': 'Middle Eastern & Israeli',
        'description': 'Authentic Iraqi-Jewish cuisine. Homestyle cooking including kubba, t\'beet, and traditional Iraqi dishes. A unique and comforting option for the community.',
        'address': '3453 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 792-4004',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 0,
        'delivery_area': '',
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
    {
        'name': 'Shwarma Express',
        'category': 'Middle Eastern & Israeli',
        'description': 'Quick and affordable shawarma, falafel, and Middle Eastern platters. Catering trays available for groups. A reliable, budget-friendly option.',
        'address': '3434 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 782-0078',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Me-Va-Me',
        'category': 'Middle Eastern & Israeli',
        'description': 'Israeli grill and shawarma with generous portions and bold flavours. Family meal combos and party platters available. Multiple GTA locations.',
        'address': '7241 Bathurst St, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 889-5559',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
    },
    {
        'name': 'Pita Box',
        'category': 'Middle Eastern & Israeli',
        'description': 'Fresh pita sandwiches, shawarma, and Middle Eastern bowls. Quick service and catering trays. Good for informal shiva lunches.',
        'address': '7700 Bathurst St, Thornhill, ON',
        'neighborhood': 'Thornhill',
        'phone': '(905) 731-7482',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Thornhill/Vaughan,North York',
    },
    # More diverse options
    {
        'name': 'Sushi Inn',
        'category': 'Kosher Restaurants & Caterers',
        'description': 'Kosher sushi and Japanese-inspired cuisine. Sushi platters and bento boxes are a refreshing alternative for shiva meals. Party trays available.',
        'address': '3461 Bathurst St, Toronto, ON',
        'neighborhood': 'Bathurst Manor',
        'phone': '(416) 792-0004',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'Toronto,North York',
    },
    {
        'name': 'Noah\'s Natural Foods',
        'category': 'Bagel Shops & Bakeries',
        'description': 'Health-focused grocery with a bakery and prepared foods section. Organic, vegan, and allergy-friendly options. Fruit and veggie platters available.',
        'address': '322 Bloor St W, Toronto, ON',
        'neighborhood': 'Annex',
        'phone': '(416) 968-7930',
        'website': 'https://www.noahsnaturalfoods.ca',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'Toronto',
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
        'website': 'https://www.picklebarrel.com',
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
        'website': '',
        'kosher_status': 'not_certified',
        'delivery': 0,
        'delivery_area': '',
    },
    {
        'name': 'Centre Street Deli',
        'category': 'Kosher Restaurants & Caterers',
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
        'category': 'Kosher Restaurants & Caterers',
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
]


# 13 Montreal-area food vendors
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
        'website': '',
        'kosher_status': 'MK',
        'delivery': 1,
        'delivery_area': 'Montreal,Snowdon,Côte-Saint-Luc',
    },
    # Jewish Delis
    {
        'name': 'Snowdon Deli',
        'category': 'Kosher Restaurants & Caterers',
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
        'category': 'Kosher Restaurants & Caterers',
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
        'category': 'Kosher Restaurants & Caterers',
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
    # Gift Baskets
    {
        'name': 'Gifting Kosher Canada',
        'category': 'Caterers',
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
]


# 11 Toronto-area gift vendors (local, lead capture)
GIFT_VENDORS = [
    {
        'name': 'Baskets n\' Stuf',
        'category': 'Gift Baskets, Shiva Platters',
        'description': 'Kosher gift baskets and shiva platters. Beautiful arrangements with fresh fruit, baked goods, and gourmet treats. Experienced in shiva deliveries.',
        'address': 'Bathurst & Steeles, North York, ON',
        'neighborhood': 'North York',
        'phone': '',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
    {
        'name': 'Dani Gifts',
        'category': 'Gift Baskets, Chocolate',
        'description': 'Kosher gift baskets, chocolate boxes, and treats. Specializes in shiva gifts with tasteful packaging and prompt delivery.',
        'address': '401 Magnetic Dr, North York, ON',
        'neighborhood': 'North York',
        'phone': '',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
    {
        'name': 'Ely\'s Fine Foods',
        'category': 'Shiva Platters, Gift Baskets',
        'description': 'Kosher shiva platters and fine food gift baskets. Prepared meals, deli trays, and curated gift packages for mourning families.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': '',
        'kosher_status': 'COR',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
    {
        'name': 'Nutcracker Sweet / Baskits',
        'category': 'Gift Baskets, Gourmet',
        'description': 'Premium gift baskets and gourmet packages. Known for stunning presentation and high-quality products. Ships Canada-wide. Kosher options available.',
        'address': '3717 Chesswood Dr, Toronto, ON',
        'neighborhood': 'North York',
        'phone': '',
        'website': 'https://www.baskits.com',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA + Canada-wide',
    },
    {
        'name': 'Gifts for Every Reason',
        'category': 'Gift Baskets',
        'description': 'Curated gift baskets for shiva and condolence. Kosher options available. Thoughtful packaging with same-day delivery in GTA.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA',
        'phone': '',
        'website': '',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA',
    },
    {
        'name': 'Romi\'s Bakery',
        'category': 'Baked Goods',
        'description': 'Artisanal baked goods and pastries. Beautiful cookie boxes, cakes, and pastry platters. A warm, personal touch for a shiva home.',
        'address': 'Toronto, ON',
        'neighborhood': 'Toronto',
        'phone': '',
        'website': '',
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
        'category': 'Fruit, Gift Baskets',
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
        'category': 'Fruit, Gift Baskets',
        'description': 'Fruit and gift baskets with free delivery over $100 in the GTA. Wide variety of sympathy and condolence baskets.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA',
        'phone': '',
        'website': '',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA (free over $100)',
    },
    {
        'name': 'Butzi Gift Baskets',
        'category': 'Gift Baskets',
        'description': 'Gourmet gift baskets and sympathy packages. Same-day delivery in Toronto and GTA. Known for generous portions and beautiful wrapping.',
        'address': 'Toronto, ON',
        'neighborhood': 'GTA',
        'phone': '',
        'website': '',
        'kosher_status': 'not_certified',
        'delivery': 1,
        'delivery_area': 'GTA + same-day',
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
        slug = slugify(v['name'])
        # Check if already exists
        cursor.execute('SELECT id FROM vendors WHERE slug = ?', (slug,))
        if cursor.fetchone():
            skipped += 1
            continue

        vendor_type = v.get('vendor_type', 'food')
        cursor.execute('''
            INSERT INTO vendors (name, slug, category, vendor_type, description, address, neighborhood,
                                 phone, website, kosher_status, delivery, delivery_area, image_url, featured, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        slug = slugify(v['name'])
        cursor.execute('SELECT id FROM vendors WHERE slug = ?', (slug,))
        if cursor.fetchone():
            skipped += 1
            continue

        cursor.execute('''
            INSERT INTO vendors (name, slug, category, vendor_type, description, address, neighborhood,
                                 phone, website, kosher_status, delivery, delivery_area, image_url, featured, created_at)
            VALUES (?, ?, ?, 'gift', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            v['name'],
            slug,
            v['category'],
            v.get('description', ''),
            v.get('address', ''),
            v.get('neighborhood', ''),
            v.get('phone', ''),
            v.get('website', ''),
            v.get('kosher_status', 'not_certified'),
            v.get('delivery', 0),
            v.get('delivery_area', ''),
            v.get('image_url'),
            v.get('featured', 0),
            now,
        ))
        gift_inserted += 1
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Vendor seed complete: {inserted} inserted ({gift_inserted} gift), {skipped} skipped (already exist)")
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
            print("No caterer_partners table found. Skipping email backfill.")
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
    print(f"Email backfill: {updated} vendor(s) updated from caterer_partners ({after} total with email)")
    return updated


if __name__ == '__main__':
    seed_vendors()
    backfill_vendor_emails()
