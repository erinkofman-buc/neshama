-- Neshama photo audit Cycle 4 migration — May 1, 2026
-- Run on Render shell AFTER tonight's Render memory fix deploy lands.
-- Source: /Users/erinkofman/Desktop/Tax 2025/vendor-photo-picks-2026-05-01.csv (Erin's picks via review-cycle4.html)
--
-- Scope: 4 image_url UPDATEs from Cycle 4 picks.
-- The other 34 vendors in Cycle 4 returned junk Firecrawl candidates (cookie banners,
-- accessibility widgets, site headers — not food photos). They get a fresh fallback
-- pipeline run with WebSearch-sourced URLs in Cycle 5 (queued separately).
--
-- Pizza Pita (Montreal) duplicate of Pizza Pita Prime — NOT touched here.
-- Logged to data-quality-backlog.md for surgical cleanup with vendor_clicks migration first.

BEGIN TRANSACTION;

SELECT 'vendors before' AS label, COUNT(*) AS n FROM vendors;
SELECT 'with image before' AS label, COUNT(*) AS n FROM vendors WHERE image_url IS NOT NULL AND image_url != '';

-- Pancer's Original Deli (Erin: Option 2)
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/ccc15e_52ab9209516d44c295dd9fbe4c09621b.jpg/v1/crop/x_4,y_20,w_154,h_166/fill/w_214,h_232,al_c,lg_1,q_80,enc_avif,quality_auto/ccc15e_52ab9209516d44c295dd9fbe4c09621b.jpg'
WHERE slug = 'pancers-original-deli';

-- Nortown Foods (Erin: Option 1, with note "not a great picture, weird focused chicken")
-- Flagged for re-pick in Cycle 5 if a better candidate surfaces.
UPDATE vendors SET image_url = 'https://www.nortownfoods.com/pictures/banners/image14.jpg'
WHERE slug = 'nortown-foods';

-- Pusateri's Fine Foods (Erin: Option 2)
UPDATE vendors SET image_url = 'https://www.pusateris.com/web/image/2169-dfc6850c/Catering_Events_4.webp'
WHERE slug = 'pusateris-fine-foods';

-- Zelden's Deli and Desserts (Erin: Option 3)
UPDATE vendors SET image_url = 'http://zeldensdelianddesserts.com/wp-content/uploads/2020/01/platter.jpg'
WHERE slug = 'zeldens-deli-and-desserts';

SELECT 'vendors after' AS label, COUNT(*) AS n FROM vendors;
SELECT 'with image after' AS label, COUNT(*) AS n FROM vendors WHERE image_url IS NOT NULL AND image_url != '';
SELECT 'expected delta' AS label, '+4' AS value;

-- Verification: confirm each pick landed.
SELECT slug, name, image_url FROM vendors WHERE slug IN (
    'pancers-original-deli', 'nortown-foods', 'pusateris-fine-foods', 'zeldens-deli-and-desserts'
);

COMMIT;
