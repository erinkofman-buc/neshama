"""
Neshama City Configuration — Single Source of Truth

Adding a new city = adding one entry to CITIES dict below.
Everything else (filters, scrapers, vendors, SEO) reads from this config.
"""

CITIES = {
    'toronto': {
        'display_name': 'Toronto',
        'country': 'CA',
        'region': 'ON',
        'timezone': 'America/Toronto',
        'neighborhoods': [
            'Annex', 'Bathurst Manor', 'Bayview Village', 'Bloor West',
            'Don Mills', 'Downsview', 'Forest Hill', 'Lawrence Park',
            'Midtown', 'North York', 'Richmond Hill', 'Summerhill',
            'Thornhill', 'Toronto', 'Yorkville', 'Vaughan',
        ],
        'detection_keywords': [
            'toronto', 'north york', 'thornhill', 'vaughan', 'bathurst manor',
            'forest hill', 'lawrence park', 'richmond hill', ', on',
            'downsview', 'don mills', 'scarborough', 'etobicoke',
            'bayview', 'bloor', 'yorkville', 'midtown',
        ],
        'scrapers': ['steeles', 'benjamins', 'misaskim'],
        'funeral_homes': {
            'steeles': 'Steeles Memorial Chapel',
            'benjamins': "Benjamin's Park Memorial Chapel",
            'misaskim': 'Misaskim',
        },
        'outscraper_keywords': {
            'caterers': ['kosher catering Toronto', 'shiva catering Toronto', 'kosher restaurant North York'],
            'gifts': ['gift basket Toronto', 'kosher gift basket Toronto'],
        },
        'seo': {
            'title': 'Toronto Jewish Obituaries & Shiva Support',
            'description': 'Obituaries from Toronto Jewish funeral homes — Steeles, Benjamin\'s, Misaskim. Free shiva meal coordination and community support.',
        },
    },
    'montreal': {
        'display_name': 'Montreal',
        'country': 'CA',
        'region': 'QC',
        'timezone': 'America/Montreal',
        'neighborhoods': [
            'Côte-des-Neiges', 'Côte-Saint-Luc', 'Dollard-des-Ormeaux',
            'Downtown', 'Mile End', 'Mount Royal', 'Old Montreal',
            'Outremont', 'Plateau', 'Saint-Henri', 'Snowdon',
            'Hampstead', 'Westmount',
        ],
        'detection_keywords': [
            'montreal', 'montréal', 'côte-saint-luc', 'cote-saint-luc',
            'outremont', 'mile end', 'snowdon', 'hampstead', 'westmount',
            'dollard', 'mount royal', 'plateau', 'saint-henri', ', qc',
        ],
        'scrapers': ['paperman', 'misaskim'],
        'funeral_homes': {
            'paperman': 'Paperman & Sons',
        },
        'outscraper_keywords': {
            'caterers': ['kosher catering Montreal', 'shiva catering Montreal', 'kosher restaurant Montreal'],
            'gifts': ['gift basket Montreal', 'kosher gift basket Montreal'],
        },
        'seo': {
            'title': 'Montreal Jewish Obituaries & Shiva Support',
            'description': 'Obituaries from Montreal Jewish funeral homes — Paperman & Sons. Free shiva meal coordination and community support.',
        },
    },
    # ── EXPANSION CITIES (uncomment when ready to launch) ──
    #
    # 'south-florida': {
    #     'display_name': 'South Florida',
    #     'country': 'US',
    #     'region': 'FL',
    #     'timezone': 'America/New_York',
    #     'neighborhoods': [
    #         'Aventura', 'Bal Harbour', 'Boca Raton', 'Boynton Beach',
    #         'Coconut Creek', 'Coral Springs', 'Davie', 'Deerfield Beach',
    #         'Delray Beach', 'Fort Lauderdale', 'Hollywood', 'Miami Beach',
    #         'North Miami Beach', 'Palm Beach Gardens', 'Parkland',
    #         'Pompano Beach', 'Sunny Isles', 'Surfside', 'Tamarac',
    #         'West Palm Beach', 'Weston',
    #     ],
    #     'detection_keywords': [
    #         'boca raton', 'aventura', 'fort lauderdale', 'hollywood, fl',
    #         'miami beach', 'sunny isles', 'surfside', 'bal harbour',
    #         'deerfield beach', 'delray beach', 'parkland', 'weston',
    #         'coral springs', 'tamarac', 'boynton beach', ', fl',
    #         'north miami beach', 'palm beach', 'pompano beach', 'davie',
    #     ],
    #     'scrapers': ['dignity_memorial'],
    #     'funeral_homes': {
    #         'star-of-david': 'Star of David Memorial Gardens',
    #         'riverside-gordon': 'Riverside Gordon Memorial Chapels',
    #         'menorah-gardens': 'Menorah Gardens Funeral Chapels',
    #         'ij-morris-fl': 'IJ Morris at Star of David',
    #         'riverside-stanetsky': 'Riverside-Stanetsky Memorial Chapel',
    #         'levitt-weinstein': 'Levitt-Weinstein Memorial Chapel',
    #         'gutterman-warheit': 'Gutterman Warheit Memorial Chapel',
    #         'kronish': 'Kronish Funeral Services',
    #     },
    #     'outscraper_keywords': {
    #         'caterers': [
    #             'kosher catering Boca Raton', 'shiva catering Fort Lauderdale',
    #             'kosher restaurant Aventura', 'kosher catering Hollywood FL',
    #         ],
    #         'gifts': ['gift basket Boca Raton', 'kosher gift basket Miami'],
    #     },
    #     'seo': {
    #         'title': 'South Florida Jewish Obituaries & Shiva Support',
    #         'description': 'Obituaries from South Florida Jewish funeral homes. Free shiva meal coordination for Boca Raton, Aventura, Fort Lauderdale, and beyond.',
    #     },
    # },
    #
    # 'chicago': {
    #     'display_name': 'Chicago',
    #     'country': 'US',
    #     'region': 'IL',
    #     'timezone': 'America/Chicago',
    #     'neighborhoods': [
    #         'Skokie', 'Highland Park', 'Deerfield', 'Northbrook',
    #         'Buffalo Grove', 'Glencoe', 'Wilmette', 'Winnetka',
    #         'Lakeview', 'Lincoln Park', 'West Rogers Park', 'Vernon Hills',
    #     ],
    #     'detection_keywords': [
    #         'skokie', 'highland park, il', 'deerfield, il', 'northbrook',
    #         'buffalo grove', 'glencoe', 'wilmette', 'winnetka',
    #         'lakeview', 'lincoln park', 'west rogers park', ', il',
    #     ],
    #     'scrapers': ['chicago_jewish_funerals', 'shalom_memorial', 'goldman'],
    #     'funeral_homes': {
    #         'chicago-jewish-funerals': 'Chicago Jewish Funerals',
    #         'shalom-memorial': 'Shalom Memorial Funeral Home',
    #         'goldman': 'Goldman Funeral Group',
    #     },
    #     'outscraper_keywords': {
    #         'caterers': ['kosher catering Chicago', 'shiva catering Skokie', 'kosher restaurant Highland Park IL'],
    #         'gifts': ['gift basket Chicago', 'kosher gift basket Skokie'],
    #     },
    #     'seo': {
    #         'title': 'Chicago Jewish Obituaries & Shiva Support',
    #         'description': 'Obituaries from Chicago Jewish funeral homes. Free shiva meal coordination for Skokie, Highland Park, and the North Shore.',
    #     },
    # },
    #
    # 'nyc': {
    #     'display_name': 'New York',
    #     'country': 'US',
    #     'region': 'NY',
    #     'timezone': 'America/New_York',
    #     'neighborhoods': [
    #         'Upper West Side', 'Borough Park', 'Crown Heights',
    #         'Flatbush', 'Forest Hills', 'Great Neck', 'Five Towns',
    #         'Teaneck', 'Williamsburg', 'Park Slope', 'Kew Gardens Hills',
    #         'Scarsdale', 'White Plains', 'Englewood',
    #     ],
    #     'detection_keywords': [
    #         'new york', 'manhattan', 'brooklyn', 'queens', 'bronx',
    #         'long island', 'great neck', 'five towns', 'hewlett',
    #         'teaneck', 'forest hills', 'borough park', 'flatbush',
    #         'scarsdale', 'white plains', ', ny', ', nj',
    #     ],
    #     'scrapers': ['dignity_memorial', 'plaza', 'guttermans', 'shermans', 'shomrei_hadas'],
    #     'funeral_homes': {
    #         'plaza': 'Plaza Jewish Community Chapel',
    #         'guttermans': "Gutterman's",
    #         'shermans': "Sherman's Flatbush Memorial Chapel",
    #         'riverside-memorial': 'Riverside Memorial Chapel',
    #         'ij-morris-nyc': 'IJ Morris',
    #         'shomrei-hadas': 'Shomrei Hadas Chapels',
    #     },
    #     'outscraper_keywords': {
    #         'caterers': ['kosher catering Brooklyn', 'shiva catering Manhattan', 'kosher restaurant Great Neck'],
    #         'gifts': ['gift basket New York', 'kosher gift basket Brooklyn'],
    #     },
    #     'seo': {
    #         'title': 'New York Jewish Obituaries & Shiva Support',
    #         'description': 'Obituaries from New York Jewish funeral homes. Free shiva meal coordination for Manhattan, Brooklyn, Queens, Long Island, and NJ.',
    #     },
    # },
    #
    # 'la': {
    #     'display_name': 'Los Angeles',
    #     'country': 'US',
    #     'region': 'CA',
    #     'timezone': 'America/Los_Angeles',
    #     'neighborhoods': [
    #         'Beverly Hills', 'Pico-Robertson', 'Encino', 'Tarzana',
    #         'Calabasas', 'Santa Monica', 'Brentwood', 'Hollywood Hills',
    #         'Culver City', 'Westwood', 'Irvine', 'Newport Beach',
    #     ],
    #     'detection_keywords': [
    #         'los angeles', 'beverly hills', 'pico-robertson', 'encino',
    #         'tarzana', 'calabasas', 'culver city', 'santa monica',
    #         'brentwood', 'hollywood', 'westwood', ', ca',
    #     ],
    #     'scrapers': ['hillside', 'mount_sinai_la', 'dignity_memorial'],
    #     'funeral_homes': {
    #         'hillside': 'Hillside Memorial Park & Mortuary',
    #         'mount-sinai-la': 'Mount Sinai Memorial Parks & Mortuaries',
    #         'groman-eden': 'Groman Eden Mortuary',
    #     },
    #     'outscraper_keywords': {
    #         'caterers': ['kosher catering Los Angeles', 'shiva catering Beverly Hills', 'kosher restaurant Pico Robertson'],
    #         'gifts': ['gift basket Los Angeles', 'kosher gift basket Beverly Hills'],
    #     },
    #     'seo': {
    #         'title': 'Los Angeles Jewish Obituaries & Shiva Support',
    #         'description': 'Obituaries from Los Angeles Jewish funeral homes. Free shiva meal coordination for Beverly Hills, Pico-Robertson, the Valley, and beyond.',
    #     },
    # },
}


# ── Helper Functions ──

def get_city_slugs():
    """Return list of active city slugs."""
    return list(CITIES.keys())


def get_city_by_slug(slug):
    """Get city config by slug, or None."""
    return CITIES.get(slug)


def detect_city_from_text(text):
    """Given address/neighborhood/delivery_area text, return matching city slug."""
    if not text:
        return None
    text_lower = text.lower()
    for slug, cfg in CITIES.items():
        if any(kw in text_lower for kw in cfg['detection_keywords']):
            return slug
    return None


def get_all_neighborhoods():
    """Return {city_slug: [neighborhoods]} for frontend dropdowns."""
    return {slug: cfg['neighborhoods'] for slug, cfg in CITIES.items()}


def get_valid_location_set():
    """For subscription location validation."""
    return set(CITIES.keys())


def get_cities_for_api():
    """Return serializable city data for /api/cities endpoint."""
    return {
        slug: {
            'display_name': cfg['display_name'],
            'country': cfg['country'],
            'region': cfg['region'],
            'neighborhoods': cfg['neighborhoods'],
            'funeral_homes': cfg['funeral_homes'],
            'seo': cfg['seo'],
        }
        for slug, cfg in CITIES.items()
    }
