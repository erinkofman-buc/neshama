"""
Seed data for care provider directory.
Sources: Web searches conducted 2026-03-29.
Only includes providers verified from live search results.
"""

CARE_PROVIDERS = [
    # ============================================================
    # DEATH DOULAS — TORONTO
    # ============================================================
    {
        'name': 'Good Death Doula — Kayla Moryoussef',
        'provider_type': 'death_doula',
        'city': 'Toronto',
        'neighbourhood': '',
        'website': 'https://www.gooddeath.ca',
        'phone': '',
        'description': 'Registered social worker and certified death doula offering death planning, legacy work, vigil sitting, caregiver respite, and mortality coaching.',
        'services': 'death planning, legacy work, vigil sitting, caregiver respite, mortality coaching, grief counselling',
        'price_range': '',
    },
    {
        'name': 'Dragonfly Collective — Community Deathcare',
        'provider_type': 'death_doula',
        'city': 'Toronto',
        'neighbourhood': '',
        'website': 'https://dragonflycollective.ca',
        'phone': '',
        'description': 'Death midwife practice helping individuals and families clarify end-of-life wishes and receive person-directed support.',
        'services': 'end-of-life planning, family support, death midwifery, resource navigation',
        'price_range': '',
    },
    {
        'name': 'Death Coach Corinne — Corinne Alstrom-Sonne',
        'provider_type': 'death_doula',
        'city': 'Toronto',
        'neighbourhood': '',
        'website': 'https://www.deathcoachcorinne.com',
        'phone': '',
        'description': 'Trained death doula and hospice volunteer with a BSW from Toronto Metropolitan University providing emotional, social, and spiritual end-of-life support.',
        'services': 'emotional support, spiritual support, family guidance, hospice companionship',
        'price_range': '',
    },
    {
        'name': 'Adrianna Prosser — Lady Death Doula',
        'provider_type': 'death_doula',
        'city': 'Toronto',
        'neighbourhood': 'Danforth',
        'website': 'https://www.adrianna-prosser.com',
        'phone': '',
        'description': 'Death doula and grief educator known for community grief events, advance care planning workshops, and end-of-life support.',
        'services': 'death doula support, grief education, advance care planning, grief walks, community workshops',
        'price_range': '',
    },
    {
        'name': 'Wishstone',
        'provider_type': 'death_doula',
        'city': 'Toronto',
        'neighbourhood': '',
        'website': 'https://wishstone.ca',
        'phone': '',
        'description': 'End-of-life doula organization researching and expanding the role of death doulas with ground-breaking practitioners.',
        'services': 'end-of-life doula services, research, practitioner engagement',
        'price_range': '',
    },

    # ============================================================
    # DEATH DOULAS — MONTREAL
    # ============================================================
    {
        'name': 'End-of-Life Doula Catherine',
        'provider_type': 'death_doula',
        'city': 'Montreal',
        'neighbourhood': '',
        'website': 'https://www.deathdoulamontreal.com',
        'phone': '',
        'description': 'Montreal-based end-of-life doula offering services to individuals and families experiencing death and grief.',
        'services': 'end-of-life support, grief care, death planning, family guidance',
        'price_range': '',
    },
    {
        'name': 'Thanadoula Denise Lefebvre',
        'provider_type': 'death_doula',
        'city': 'Montreal',
        'neighbourhood': '',
        'website': 'https://www.thanadouladenise.com',
        'phone': '514-777-2219',
        'description': 'Certified thanadoula serving greater Montreal, South Shore, and Laval with end-of-life accompaniment and funeral planning guidance.',
        'services': 'end-of-life accompaniment, funeral planning advice, death preparation, family support',
        'price_range': '',
    },
    {
        'name': 'Montréal Death Care',
        'provider_type': 'death_doula',
        'city': 'Montreal',
        'neighbourhood': '',
        'website': 'https://www.montrealdeathcare.com',
        'phone': '',
        'description': 'Death care practice founded in 2018 offering compassionate, holistic support including grief care, legacy work, vigil companionship, and funeral planning.',
        'services': 'grief care, legacy work, vigil companionship, funeral planning, comfort measures, family communication support',
        'price_range': '',
    },

    # ============================================================
    # HOME CARE AGENCIES — TORONTO
    # ============================================================
    {
        'name': 'Closing the Gap Healthcare',
        'provider_type': 'home_care',
        'city': 'Toronto',
        'neighbourhood': 'North York',
        'website': 'https://www.closingthegap.ca',
        'phone': '416-226-6141',
        'description': 'National home and community care provider offering holistic, team-based care including nursing, personal support, therapy, and social work.',
        'services': 'nursing, personal support, physiotherapy, occupational therapy, speech language pathology, social work, dietetics, home support',
        'price_range': '',
    },
    {
        'name': 'Bayshore Home Health',
        'provider_type': 'home_care',
        'city': 'Toronto',
        'neighbourhood': '',
        'website': 'https://www.bayshore.ca',
        'phone': '1-877-289-3997',
        'description': 'One of Canada\'s largest home health care providers with over 55 years of experience delivering personalized care including palliative and respite support.',
        'services': 'personal care, companionship, meal preparation, dementia care, nursing, hospice palliative care, respite care, home safety assessments, 24/7 service',
        'price_range': '',
    },
    {
        'name': 'SE Health',
        'provider_type': 'home_care',
        'city': 'Toronto',
        'neighbourhood': '',
        'website': 'https://sehc.com',
        'phone': '',
        'description': 'Not-for-profit social enterprise established in 1908, serving 20,000+ Canadians daily with home health care, rehab therapy, and caregiver resources.',
        'services': 'personal support, homemaking, nursing, medicine management, rehab therapy, grooming assistance',
        'price_range': '',
    },
    {
        'name': 'Spectrum Health Care',
        'provider_type': 'home_care',
        'city': 'Toronto',
        'neighbourhood': 'Midtown',
        'website': 'https://spectrumhealthcare.com',
        'phone': '416-964-0322',
        'description': 'Ontario\'s leading home health care provider since 1977, offering 24/7 nursing, personal support, and specialized care across the GTA.',
        'services': 'nursing, personal support, homemaking, foot care, wound care, palliative care, physiotherapy, overnight care',
        'price_range': '$160/10hr overnight, $200/12hr overnight',
    },
    {
        'name': 'C-Care Health Services',
        'provider_type': 'home_care',
        'city': 'Toronto',
        'neighbourhood': 'North York',
        'website': 'https://c-care.ca',
        'phone': '416-724-2273',
        'description': 'Trusted private home care agency with 20+ years of experience providing caregivers, PSWs, and nurses for seniors and individuals with medical needs.',
        'services': 'companionship, personal care, palliative nursing, post-surgery recovery, overnight care, medical escorts, 24/7 service',
        'price_range': '',
    },
    {
        'name': 'CareHop Nursing & Home Care',
        'provider_type': 'home_care',
        'city': 'Toronto',
        'neighbourhood': 'Etobicoke',
        'website': 'https://carehop.ca',
        'phone': '',
        'description': 'Accredited home care agency since 2012 offering nursing, personal support, and cleaning services with flexible scheduling from respite to 24/7 live-in care.',
        'services': 'nursing, personal support, medication management, wound care, mobility assistance, meal preparation, companionship, respite care, live-in care',
        'price_range': '',
    },
    {
        'name': 'Right at Home Toronto',
        'provider_type': 'home_care',
        'city': 'Toronto',
        'neighbourhood': 'Lakeshore',
        'website': 'https://www.rightathomecanada.com/toronto',
        'phone': '647-994-1812',
        'description': 'Award-winning home care provider with 25 years of experience offering personalized senior care and support for physical, medical, and memory impairment.',
        'services': 'personal care, companionship, dementia care, Alzheimer\'s care, respite care, hospital-to-home transition',
        'price_range': '',
    },
    {
        'name': 'Integracare Home Care',
        'provider_type': 'home_care',
        'city': 'Toronto',
        'neighbourhood': 'Midtown',
        'website': 'https://integracarehomecare.ca',
        'phone': '416-421-4243',
        'description': 'Three-decade veteran of Toronto home care providing high-quality senior services in Toronto and Mississauga.',
        'services': 'personal support, nursing, companionship, dementia care, palliative care, post-surgery care',
        'price_range': '',
    },
    {
        'name': 'The Care Company',
        'provider_type': 'home_care',
        'city': 'Toronto',
        'neighbourhood': '',
        'website': 'https://www.carecompany.com',
        'phone': '',
        'description': 'GTA home care provider with experienced nurses and PSWs offering services from daily housekeeping to palliative, post-op, and dementia care.',
        'services': 'nursing, personal support, palliative care, dementia care, post-op care, housekeeping, meal preparation',
        'price_range': '',
    },
    {
        'name': 'VHA Home HealthCare',
        'provider_type': 'home_care',
        'city': 'Toronto',
        'neighbourhood': '',
        'website': 'https://www.vha.ca',
        'phone': '',
        'description': 'Major not-for-profit home care provider serving the GTA and Durham Region with personal support, nursing, and community programs.',
        'services': 'personal support, homemaking, nursing, community programs',
        'price_range': '',
    },

    # ============================================================
    # HOME CARE AGENCIES — MONTREAL
    # ============================================================
    {
        'name': 'Golden Home Care',
        'provider_type': 'home_care',
        'city': 'Montreal',
        'neighbourhood': 'West Island',
        'website': 'https://www.goldenhomecare.ca',
        'phone': '514-685-8889',
        'description': 'Personalized in-home support and personal care for seniors across Montreal, NDG, Westmount, Côte-Saint-Luc, and the West Island.',
        'services': 'companionship, housekeeping, daily routine assistance, nutritional planning, emergency response, memory workshops, incontinence care',
        'price_range': '',
    },
    {
        'name': 'Home Care Assistance Montreal',
        'provider_type': 'home_care',
        'city': 'Montreal',
        'neighbourhood': '',
        'website': 'https://www.homecareassistancemontreal.ca',
        'phone': '514-907-5065',
        'description': 'Specialized in around-the-clock care with care managers on call 24/7 including nights and weekends.',
        'services': 'bathing, dressing, meal preparation, transportation, companionship, fall prevention, live-in care, 24/7 care',
        'price_range': '',
    },
    {
        'name': 'A+ Solutions Home Health Care',
        'provider_type': 'home_care',
        'city': 'Montreal',
        'neighbourhood': 'NDG',
        'website': 'https://www.aplushomecare.ca',
        'phone': '514-999-8009',
        'description': 'Full-spectrum private home health care in Montreal, Laval, and West Island with licensed nursing and personal support.',
        'services': 'nursing, personal support, hourly care, long-term care, 24/7 availability',
        'price_range': '',
    },
    {
        'name': 'TheKey Montreal',
        'provider_type': 'home_care',
        'city': 'Montreal',
        'neighbourhood': '',
        'website': 'https://thekey.ca/locations/canada/montreal',
        'phone': '',
        'description': 'National home care provider with 20+ years of experience supporting older adults with a wide range of age-related conditions in the Montreal area.',
        'services': 'personal care, companionship, dementia care, respite care, live-in care',
        'price_range': '',
    },
    {
        'name': 'Premier Home Care Montreal',
        'provider_type': 'home_care',
        'city': 'Montreal',
        'neighbourhood': '',
        'website': 'https://premierhomecare.ca',
        'phone': '514-781-6553',
        'description': 'Locally owned personal care and companion caregiver agency bringing a concierge experience to seniors and their families.',
        'services': 'personal care, companionship, caregiver support',
        'price_range': '',
    },
]


def slugify(name):
    """Generate a URL-safe slug from a provider name."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug.strip('-')[:100]


def seed_providers(db_path='neshama.db'):
    """Seed care providers into the database."""
    import sqlite3
    from datetime import datetime

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute('PRAGMA busy_timeout=30000')
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS care_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            provider_type TEXT NOT NULL,
            description TEXT,
            city TEXT,
            neighbourhood TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            instagram TEXT,
            services TEXT,
            price_range TEXT,
            image_url TEXT,
            featured INTEGER DEFAULT 0,
            virtual_available INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    ''')

    now = datetime.now().isoformat()
    inserted = 0
    skipped = 0

    for p in CARE_PROVIDERS:
        slug = slugify(p['name'])
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO care_providers
                (name, slug, provider_type, description, city, neighbourhood,
                 phone, email, website, instagram, services, price_range,
                 image_url, featured, virtual_available, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                p['name'], slug, p['provider_type'],
                p.get('description', ''), p.get('city', ''),
                p.get('neighbourhood', ''), p.get('phone', ''),
                p.get('email', ''), p.get('website', ''),
                p.get('instagram', ''), p.get('services', ''),
                p.get('price_range', ''), p.get('image_url', ''),
                0, 1 if p.get('virtual_available') else 0, now
            ))
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  Error seeding {p['name']}: {e}")
            skipped += 1

    conn.commit()
    conn.close()
    print(f"Seeded {inserted} providers ({skipped} skipped/existing)")


if __name__ == '__main__':
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'neshama.db'
    print(f"Seeding care providers into {db_path}...")
    seed_providers(db_path)

    toronto_doulas = [p for p in CARE_PROVIDERS if p['city'] == 'Toronto' and p['provider_type'] == 'death_doula']
    montreal_doulas = [p for p in CARE_PROVIDERS if p['city'] == 'Montreal' and p['provider_type'] == 'death_doula']
    toronto_hc = [p for p in CARE_PROVIDERS if p['city'] == 'Toronto' and p['provider_type'] == 'home_care']
    montreal_hc = [p for p in CARE_PROVIDERS if p['city'] == 'Montreal' and p['provider_type'] == 'home_care']

    print(f"\nTotal providers: {len(CARE_PROVIDERS)}")
    print(f"  Toronto death doulas:  {len(toronto_doulas)}")
    print(f"  Montreal death doulas: {len(montreal_doulas)}")
    print(f"  Toronto home care:     {len(toronto_hc)}")
    print(f"  Montreal home care:    {len(montreal_hc)}")
