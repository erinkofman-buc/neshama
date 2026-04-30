-- Neshama photo audit Cycle 3 migration — Apr 30, 2026
-- Run on Render shell AFTER merging the Apr 30 evening deploy.
-- Source: vendor-photo-picks-2026-04-30.csv (Erin's picks via review.html)
--
-- Scope: 41 image_url UPDATEs, 30 clears (→ cream placeholder)

BEGIN TRANSACTION;

SELECT 'vendors before' AS label, COUNT(*) AS n FROM vendors;
SELECT 'with image before' AS label, COUNT(*) AS n FROM vendors WHERE image_url IS NOT NULL AND image_url != '';

-- === Picks: set image_url ===
UPDATE vendors SET image_url = 'https://images.contentstack.io/v3/assets/bltc699f5c4977942f7/blt8afadb9aace1d727/601c6c964b8030688c37b81f/baskets-com.jpg' WHERE slug = '1-800-baskets';  -- 1-800-Baskets
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/15960f_6d54196fd96648d69e62b7cab3c11056~mv2.png/v1/fill/w_317,h_345,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/3SOEURS-enter.png' WHERE slug = '3-soeurs';  -- 3 Soeurs
UPDATE vendors SET image_url = 'https://besomontreal.ca/wp-content/uploads/2025/07/BTrack_portraits-718_NEW-TEAM-NO-CS.png?_t=1753978642' WHERE slug = 'beso';  -- Beso
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/900ec9_4a314822647d459d8c1d2d4bd119e330~mv2.jpg/v1/fill/w_1905,h_934,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/900ec9_4a314822647d459d8c1d2d4bd119e330~mv2.jpg' WHERE slug = 'bossa';  -- Bossa
UPDATE vendors SET image_url = 'https://cdn2.cheryls.com/wcsstore/CherylAndCompany/images/catalog/cco_SPR25_278151x.jpg?height=456&amp;width=418&amp;sharpen=a0.5,r1,t1&amp;auto=webp' WHERE slug = 'cheryls-cookies';  -- Cheryl''s Cookies
UPDATE vendors SET image_url = 'https://images.squarespace-cdn.com/content/v1/5fc2758dc6d96458362bf34f/6c9e740a-1cdd-4147-8804-b6f9a96d464e/9e64bdce-2c14-4712-bbbc-d335dc976c54.jpg' WHERE slug = 'clarke-cafe';  -- Clarke Cafe
UPDATE vendors SET image_url = 'https://cotestlucbbq.com/wp-content/uploads/2021/02/CSL-Badge-Sm-320x266.png' WHERE slug = 'cote-st-luc-bbq';  -- Cote St Luc BBQ
UPDATE vendors SET image_url = 'https://prontomtl.com/wp-content/uploads/2026/02/DSC09854.jpg' WHERE slug = 'cuisine-pronto-mtl';  -- Cuisine Pronto MTL
UPDATE vendors SET image_url = 'https://eatzchezvouz.com/wp-content/uploads/2021/03/catering-services.png' WHERE slug = 'eatz-chez-vouz';  -- Eatz Chez Vouz
UPDATE vendors SET image_url = 'https://falafelstjacques.ca/_astro/falafel.DWYU5N9k_Z23iRtP.jpg' WHERE slug = 'falafel-st-jacques';  -- Falafel St. Jacques
UPDATE vendors SET image_url = 'https://portal.restodata.ca/allo-mon-coco-cnd/gallery/images/SquareSmall/01_all-mon-c_538-2024-12-02.png?315' WHERE slug = 'fressers';  -- Fressers
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/88e84c_62be67e0f9f04131bd551a49e36c01fc~mv2_d_5184_3456_s_4_2.jpg/v1/fill/w_1905,h_993,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/88e84c_62be67e0f9f04131bd551a49e36c01fc~mv2_d_5184_3456_s_4_2.jpg' WHERE slug = 'kosher-quality-bakery-deli';  -- Kosher Quality Bakery & Deli
UPDATE vendors SET image_url = 'https://solomos.ca/wp-content/uploads/2025/02/home-about-solomos.jpg' WHERE slug = 'solomos';  -- Solomos
UPDATE vendors SET image_url = 'http://yansdeli.com/cdn/shop/files/home-yans_796dc25b-2435-4853-81a8-13859fa761c9.jpg?v=1755461841' WHERE slug = 'yans-deli';  -- Yans Deli
UPDATE vendors SET image_url = 'https://bagelsongreene.com/cdn/shop/files/croissantw_egg_300x300.jpg?v=1705285832' WHERE slug = 'bagels-on-greene';  -- Bagels on Greene
UPDATE vendors SET image_url = 'http://www.bennyetfils.com/img/about/about_us.jpg' WHERE slug = 'benny-fils';  -- Benny & Fils
UPDATE vendors SET image_url = 'https://michaeleats.com/wp-content/uploads/2022/10/bc3.jpg?w=760' WHERE slug = 'boulangerie-cheskie';  -- Boulangerie Cheskie
UPDATE vendors SET image_url = 'https://davidsackscatering.com/img/food/breakfast.jpg' WHERE slug = 'david-sacks-catering';  -- David Sacks Catering
UPDATE vendors SET image_url = 'https://portal.restodata.ca/castel-resto/gallery/images/SquareSmall/01_castel-rest_552-2024-09-07.jpg?315' WHERE slug = 'lefalafel-plus';  -- LeFalafel Plus
UPDATE vendors SET image_url = 'https://web.archive.org/web/20120201112004im_/http://www.lauriergordonramsay.com/wp-content/uploads/2011/06/image_accueil_small.jpg' WHERE slug = 'rtisserie-laurier';  -- Rôtisserie Laurier
UPDATE vendors SET image_url = 'http://aishtanoor.com/wp-content/uploads/2019/08/home-pic-2.jpg' WHERE slug = 'aish-tanoor';  -- Aish Tanoor
UPDATE vendors SET image_url = 'https://www.balilaffa.com/restaurants/ba-li-laffa-north/gallery/1.jpg' WHERE slug = 'ba-li-laffa';  -- Ba-Li Laffa
UPDATE vendors SET image_url = 'https://beckedgoods.com/cdn/shop/files/IMG_7675_43aaa3c6-6915-4a6d-8fae-c9941e35d86b.jpg?v=1705426247&amp;width=3840' WHERE slug = 'becked-goods';  -- Becked Goods
UPDATE vendors SET image_url = 'https://boardsbydani.com/cdn/shop/files/IMG_5051.jpg?v=1685626066&amp;width=3840' WHERE slug = 'boards-by-dani';  -- Boards by Dani
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/da0519_4c29705b055d4612bbf88c6f3914ce5f~mv2.jpg/v1/fill/w_1905,h_485,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/da0519_4c29705b055d4612bbf88c6f3914ce5f~mv2.jpg' WHERE slug = 'box-and-board';  -- Box and Board
UPDATE vendors SET image_url = 'https://candycatchers.com/cdn/shop/files/rsz_12adobestock_61464781.jpg?v=1613734341&amp;width=3840' WHERE slug = 'candy-catchers';  -- Candy Catchers
UPDATE vendors SET image_url = 'https://cdn11.bigcommerce.com/s-00kfbby/images/stencil/original/image-manager/rda-photography-905973.jpg?t=1770319078' WHERE slug = 'epic-baskets';  -- Epic Baskets
UPDATE vendors SET image_url = 'https://goldenchopstick.ca/wp-content/uploads/2025/08/steamed-rice.jpg' WHERE slug = 'golden-chopsticks';  -- Golden Chopsticks
UPDATE vendors SET image_url = 'https://images.contentstack.io/v3/assets/blt89dbf1c763ec00a6/bltc724c01a1c03ea6f/67d3211a1aa7755631b1b3c9/20_4202_30E_05.jpg' WHERE slug = 'harry-david';  -- Harry & David
UPDATE vendors SET image_url = 'https://joeboos.com/wp-content/uploads/2025/02/french-roast-kosher-cater.webp' WHERE slug = 'joe-boos-kosher-event-catering';  -- Joe Boos Kosher Event Catering
UPDATE vendors SET image_url = 'https://laurasecord.ca/images/stencil/original/image-manager/sping-summer.png?t' WHERE slug = 'laura-secord';  -- Laura Secord
UPDATE vendors SET image_url = 'https://images.squarespace-cdn.com/content/v1/684a673391b775583ab83321/1749706554435-4QWIGRZ22YMBER15S4FR/limon_shape.png' WHERE slug = 'limon-restaurant';  -- Limon Restaurant
UPDATE vendors SET image_url = 'https://bistrogrande.com/wp-content/uploads/2020/02/mil6127_sm-1024x683.jpg' WHERE slug = 'mattis-kitchen';  -- Matti''s Kitchen
UPDATE vendors SET image_url = 'https://www.mcewangroup.ca/wp-content/uploads/2025/04/04-2-uai-1920x576.jpg' WHERE slug = 'mcewan-fine-foods';  -- McEwan Fine Foods
UPDATE vendors SET image_url = 'https://www.mybaskets.ca/cdn/shop/files/Neutral-Org_1_1600x.jpg?v=1757087299' WHERE slug = 'my-baskets';  -- My Baskets
UPDATE vendors SET image_url = 'https://cdn7.bigcommerce.com/s-v0xtrjmuve/content/webp/webp-all-gifts-345__78030.webp' WHERE slug = 'nutcracker-sweet-baskits';  -- Nutcracker Sweet / Baskits
UPDATE vendors SET image_url = 'https://thepaisanos.ca/images/slider/3.jpg' WHERE slug = 'paisanos';  -- Paisanos
UPDATE vendors SET image_url = 'https://ambassador-media-library-assets.s3.us-east-1.amazonaws.com/d41c6efb-7a09-4e2e-af66-2fe014c41482.jpg' WHERE slug = 'pantry-by-food-dudes';  -- Pantry by Food Dudes
UPDATE vendors SET image_url = 'https://cdn.sanity.io/images/x07rp3eb/production/26e17ca9c79d53e2d548d75d2334c10c29c8384a-1737x1172.jpg' WHERE slug = 'parallel';  -- Parallel
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/e1c23a_0b62a9bdb2b94a908a7a9995e20c72dd~mv2.jpg/v1/fill/w_363,h_395,al_c,q_80,usm_0.66_1.00_0.01,enc_avif,quality_auto/challah%20with%20love.jpg' WHERE slug = 'romis-bakery';  -- Romi''s Bakery
UPDATE vendors SET image_url = 'https://www.thefruitcompany.com/cdn/shop/collections/mountain-blueberries.jpg?v=1776082238&amp;width=1500' WHERE slug = 'the-fruit-company';  -- The Fruit Company

-- === Picks: clear image_url (cream placeholder) ===
UPDATE vendors SET image_url = NULL WHERE slug = 'beyond-delish';  -- Beyond Delish (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'snowdon-deli';  -- Snowdon Deli (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'wolfermans-bakery';  -- Wolferman''s Bakery (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'zera-cafe';  -- Zera Cafe (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'mehadrin-meats';  -- Mehadrin Meats (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'montreal-kosher-bakery';  -- Montreal Kosher Bakery (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'pizza-gourmetti';  -- Pizza Gourmetti (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'baskets-galore';  -- Baskets Galore (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'cheese-boutique';  -- Cheese Boutique (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'dr-laffa';  -- Dr. Laffa (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'edible-arrangements';  -- Edible Arrangements (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'elys-fine-foods-gift-baskets';  -- Ely''s Fine Foods Gift Baskets (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'f-b-kosher-catering';  -- F + B Kosher Catering (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'fruitate';  -- Fruitate (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'hickory-farms';  -- Hickory Farms (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'indigo';  -- Indigo (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'main-event-catering';  -- Main Event Catering (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'nortown-foods';  -- Nortown Foods (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'paramount-fine-foods';  -- Paramount Fine Foods (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'pizza-cafe';  -- Pizza Cafe (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'purdys-chocolatier';  -- Purdys Chocolatier (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'sonny-langers-dairy-vegetarian-caterers';  -- Sonny Langers Dairy & Vegetarian Caterers (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'tov-li-pizza-falafel';  -- Tov-Li Pizza & Falafel (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'adar';  -- Adar (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'pizza-pita';  -- Pizza Pita (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'europea';  -- Europea (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'pizza-pita-prime';  -- Pizza Pita Prime (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'haymishe-bakery';  -- Haymishe Bakery (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'sushi-inn';  -- Sushi Inn (NEEDS NEW SOURCE)
UPDATE vendors SET image_url = NULL WHERE slug = 'zuchter-berk-kosher-caterers';  -- Zuchter Berk Kosher Caterers (NEEDS NEW SOURCE)

SELECT 'vendors after' AS label, COUNT(*) AS n FROM vendors;
SELECT 'with image after' AS label, COUNT(*) AS n FROM vendors WHERE image_url IS NOT NULL AND image_url != '';

COMMIT;

