-- Neshama directory bundle migration — Apr 21, 2026
-- Run on Render shell AFTER merging fix/directory-bundle-apr21 to main and Render redeploys.
-- Before running: take a backup — see ROLLBACK section at bottom.
--
-- Scope:
--   59 UPDATEs of image_url (Erin's Apr 21 photo picks)
--   25 UPDATEs to clear image_url (triggers cream placeholder fallback)
--   1 DELETEs (Option B drops + cleanup)

BEGIN TRANSACTION;

-- Pre-migration row counts (for your sanity check in Render shell output)
SELECT 'vendors before' AS label, COUNT(*) AS n FROM vendors;

-- === 1. Image URL updates (picked photos) ===
UPDATE vendors SET image_url = 'https://images.tastet.ca/_/rs:fit:1080:720:false:0/plain/https://sesame.tastet.ca/assets/383e3e27-86a5-4704-9b53-279b2d2bbaef.jpg@jpg' WHERE slug = 'arthurs-nosh-bar';  -- Arthurs Nosh Bar
UPDATE vendors SET image_url = 'https://www.blossombylaplaza.com/cdn/shop/products/5928_sq_300x.jpg?v=1613827994' WHERE slug = 'blossom-by-la-plaza';  -- Blossom by La Plaza
UPDATE vendors SET image_url = 'https://static.goto-where.com/7042-albums-7.jpg' WHERE slug = 'chenoys-deli';  -- Chenoy''s Deli
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/98cfe8_de8423a9d5634a47871ef721c1a9c0bb~mv2_d_3888_2592_s_4_2.jpg/v1/fit/w_480,h_321,q_90,enc_avif,quality_auto/98cfe8_de8423a9d5634a47871ef721c1a9c0bb~mv2_d_3888_2592_s_4_2.jpg' WHERE slug = 'chiyoko';  -- Chiyoko
UPDATE vendors SET image_url = 'https://deli365.ca/wp-content/uploads/2016/06/About-us-pic-2-e1465482294424.jpg' WHERE slug = 'deli-365';  -- Deli 365
UPDATE vendors SET image_url = 'https://deli770.com/wp-content/uploads/2024/07/Smoked-Meat-.png' WHERE slug = 'deli-770';  -- Deli 770
UPDATE vendors SET image_url = 'https://restaurantdeliboyz.com/wp-content/uploads/2023/12/Combo-poulet-BBQ-BBQ-Chicken-Combo-1.png' WHERE slug = 'deli-boyz';  -- Deli Boyz
UPDATE vendors SET image_url = 'https://districtbagel.com/wp-content/uploads/2021/01/bagels.jpeg' WHERE slug = 'district-bagel';  -- District Bagel
UPDATE vendors SET image_url = 'https://fairmountbagel.com/wp-content/uploads/2018/03/hand-bagel-291x300.png' WHERE slug = 'fairmount-bagel';  -- Fairmount Bagel
UPDATE vendors SET image_url = 'https://www.gibbys.com/wp-content/uploads/2025/06/cropped-_GB-Shooting2avril005-2500x1406.jpg' WHERE slug = 'gibbys';  -- Gibby''s
UPDATE vendors SET image_url = 'http://giftingkosher.ca/cdn/shop/files/DecadentFlourlessChocolateCake_600x.png?v=1745435270' WHERE slug = 'gifting-kosher-canada';  -- Gifting Kosher Canada
UPDATE vendors SET image_url = 'https://tastet.ca/wp-content/uploads/2017/10/hof-kelsten-boulevard-st-laurent-montreal-jeffrey-finkelstein-15-e1508441445538.jpg' WHERE slug = 'hof-kelsten';  -- Hof Kelsten
UPDATE vendors SET image_url = 'https://eglinton.jerusalemrestaurant.ca/restaurants/jerusalem/gallery/1.jpg' WHERE slug = 'jerusalem-restaurant';  -- Jerusalem Restaurant
UPDATE vendors SET image_url = 'http://www.lamarguerite.ca/cdn/shop/files/Grilledvegetables_1200x1200.png?v=1770924633' WHERE slug = 'la-marguerite-catering';  -- La Marguerite Catering
UPDATE vendors SET image_url = 'https://images.squarespace-cdn.com/content/v1/5b2bc2a1da02bc3b1c3e2fe9/1662498388633-2TYP8RF6N48NORW9L369/image-asset.jpeg' WHERE slug = 'lemeac';  -- Lemeac
UPDATE vendors SET image_url = 'https://i0.wp.com/lestersdeli.com/wp-content/uploads/2023/10/DSC02152.jpg' WHERE slug = 'lesters-deli';  -- Lester''s Deli
UPDATE vendors SET image_url = 'https://mevamekitchenexpress.ca/wp-content/themes/mevamekitchenexpress/assets/img/menu/2022/variety_plates.webp' WHERE slug = 'me-va-mi-kitchen-express';  -- Me Va Mi Kitchen Express
UPDATE vendors SET image_url = 'http://nosherz.com/cdn/shop/collections/platter-2009590_1920_1200x1200.jpg?v=1638390047' WHERE slug = 'nosherz';  -- Nosherz
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/9bf085_f157f2f766774660a07c0ff5d1073c58%7Emv2.jpg/v1/fit/w_2500,h_1330,al_c/9bf085_f157f2f766774660a07c0ff5d1073c58%7Emv2.jpg' WHERE slug = 'oinegs-kosher';  -- Oineg''s Kosher
UPDATE vendors SET image_url = 'https://oliveetgourmando.com/cdn/shop/files/DO01220577.jpg?v=1773931332&width=1500' WHERE slug = 'olive-et-gourmando';  -- Olive et Gourmando
UPDATE vendors SET image_url = 'https://www.paradisekosher.com/wp-content/uploads/2018/07/kosher350.png' WHERE slug = 'paradise-kosher-catering';  -- Paradise Kosher Catering
UPDATE vendors SET image_url = 'https://schwartzsdeli.com/cdn/shop/files/page-catering-services-1.jpg?v=1646472771' WHERE slug = 'schwartzs-deli';  -- Schwartz''s Deli
UPDATE vendors SET image_url = 'https://stviateurbagel.com/cdn/shop/files/StViateurBagel_AdrianoCiampoli_BagelBin-1.jpg?v=1732896354&width=3840' WHERE slug = 'st-viateur-bagel';  -- St-Viateur Bagel
UPDATE vendors SET image_url = 'https://tabule.ca/wp-content/uploads/2025/09/tabule-menu_feat-image-rect.png' WHERE slug = 'tabule';  -- Tabule
UPDATE vendors SET image_url = 'https://img1.wsimg.com/isteam/ip/b9fc4f49-b834-4894-b337-fadb0b8205fa/Aba-0140.jpg/:/cr=t:5.36%25,l:20.23%25,w:59.54%25,h:89.29%25/rs=w:360,h:360,cg:true,m' WHERE slug = 'abas-bagel-company';  -- Aba''s Bagel Company
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/58d4dc_f8ae1ad9eed84dd1980cdaa6f070869f~mv2.jpg/v1/fill/w_247,h_247,q_75,enc_avif,quality_auto/58d4dc_f8ae1ad9eed84dd1980cdaa6f070869f~mv2.jpg' WHERE slug = 'apex-kosher-catering';  -- Apex Kosher Catering
UPDATE vendors SET image_url = 'https://www.aromaespressobar.ca/wp-content/uploads/2024/11/Bowls-x-3-scene.jpg' WHERE slug = 'aroma-espresso-bar';  -- Aroma Espresso Bar
UPDATE vendors SET image_url = 'https://bistrogrande.com/wp-content/uploads/2020/02/mil6277_sm-scaled.jpg' WHERE slug = 'bistro-grande';  -- Bistro Grande
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/88e84c_073feaa2390445f79dad02f5c1c7a992~mv2_d_5184_3456_s_4_2.jpg/v1/fill/w_422,h_282,q_90,enc_avif,quality_auto/88e84c_073feaa2390445f79dad02f5c1c7a992~mv2_d_5184_3456_s_4_2.jpg' WHERE slug = 'bubbys-bagels';  -- Bubby''s Bagels
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/a9a0b8_55595057ce8349c4b65d2b44ccb65580~mv2.jpg/v1/crop/x_126,y_1,w_1201,h_792/fill/w_896,h_591,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/pic14_edited.jpg' WHERE slug = 'centre-street-deli';  -- Centre Street Deli
UPDATE vendors SET image_url = 'https://d24gls5t8gwt4z.cloudfront.net/images/item/86e281b4-3d39-4ff0-8c71-22acbc66ed66' WHERE slug = 'chop-hop';  -- Chop Hop
UPDATE vendors SET image_url = 'https://abc1b6b80c540b51da78.cdn6.editmysite.com/uploads/b/abc1b6b80c540b51da789408a28545b34ec20047c9af1dec09dea835a581d0ec/IG_4.7.2026_69d56d7acbbe64.15870355.jpeg?width=2400&optimize=medium' WHERE slug = 'cumbraes';  -- Cumbrae''s
UPDATE vendors SET image_url = 'https://www.daiterskitchen.ca/media/2020/03/daiters-675x450.jpg' WHERE slug = 'daiters-kitchen';  -- Daiter''s Kitchen
UPDATE vendors SET image_url = 'https://www.harbordbakery.ca/images/cakes.jpg' WHERE slug = 'harbord-bakery';  -- Harbord Bakery
UPDATE vendors SET image_url = 'https://static.wixstatic.com/media/597c20_4c0a53468f474a85b30efaffe597bfab~mv2.png/v1/fill/w_326,h_380,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/IMG_5640.png' WHERE slug = 'jem-salads';  -- Jem Salads
UPDATE vendors SET image_url = 'https://www.restaurantcateringsystems.com/web/documents/kivasbb/images/kiva_home_page.jpg' WHERE slug = 'kivas-bagels';  -- Kiva''s Bagels
UPDATE vendors SET image_url = 'https://cdn11.bigcommerce.com/s-93wuni90xs/images/stencil/390x485/products/176/487/Chicken_Wrap_Box__60284.1686677424.jpg?c=1' WHERE slug = 'kosher-gourmet';  -- Kosher Gourmet
UPDATE vendors SET image_url = 'https://linnysluncheonette.com/assets/images/social.png' WHERE slug = 'linnys-luncheonette';  -- Linny''s Luncheonette
UPDATE vendors SET image_url = 'https://www.marronbistro.com/wp-content/uploads/2016/11/catering_001.jpg' WHERE slug = 'marron-bistro';  -- Marron Bistro
UPDATE vendors SET image_url = 'https://lirp.cdn-website.com/ed3e1e79/dms3rep/multi/opt/BANNER-BOWLS-2304w.jpg' WHERE slug = 'me-va-me';  -- Me-Va-Me
UPDATE vendors SET image_url = 'https://menchens.ca/img/cocktail_reception1.jpg' WHERE slug = 'menchens-glatt-kosher-catering';  -- Menchens Glatt Kosher Catering
UPDATE vendors SET image_url = 'https://milknhoney.ca/wp-content/uploads/2016/12/IMG_3118-Small.jpg' WHERE slug = 'milk-n-honey';  -- Milk ''N Honey
UPDATE vendors SET image_url = 'https://mitzuyankoshercatering.com/wp-content/uploads/2023/02/Pulled-Brisket_Mitzuyan-Kosher_Catering.jpg' WHERE slug = 'mitzuyan-kosher-catering';  -- Mitzuyan Kosher Catering
UPDATE vendors SET image_url = 'https://noah-kosher-sushi.vercel.app/images/og-thumbnail.webp' WHERE slug = 'noah-kosher-sushi';  -- Noah Kosher Sushi
UPDATE vendors SET image_url = 'https://orlyskitchen.com/assets/hero-bg-TNk09rP1.jpg' WHERE slug = 'orlys-kitchen';  -- Orly''s Kitchen
UPDATE vendors SET image_url = 'https://farm6.staticflickr.com/5340/30436264196_6456981ebc_b.jpg' WHERE slug = 'paese-ristorante';  -- Paese Ristorante
UPDATE vendors SET image_url = 'https://pantryfoods.ca/img/background1.jpg' WHERE slug = 'pantry-foods';  -- Pantry Foods
UPDATE vendors SET image_url = 'https://picklebarrelcatering.com/wp-content/uploads/2022/03/breakfast-category-300x300.jpg' WHERE slug = 'pickle-barrel';  -- Pickle Barrel
UPDATE vendors SET image_url = 'https://richmondkosherbakery.com/wp-content/uploads/2023/08/rustic-baguettes-baked-in-bakery-country-kitchen-FLZTJXD-768x512.jpg' WHERE slug = 'richmond-kosher-bakery';  -- Richmond Kosher Bakery
UPDATE vendors SET image_url = 'https://royaldairycafe.com/wp-content/uploads/2025/12/RDC-Salad-800600px-v2-copy.webp' WHERE slug = 'royal-dairy-cafe-catering';  -- Royal Dairy Cafe & Catering
UPDATE vendors SET image_url = 'https://slicenbites.com/wp-content/uploads/2023/01/g02-scaled.jpg' WHERE slug = 'slice-n-bites';  -- Slice n Bites
UPDATE vendors SET image_url = 'https://sofram.ca/wp-content/uploads/2024/02/S_Home_Desktop.webp' WHERE slug = 'sofram-restaurant';  -- Sofram Restaurant
UPDATE vendors SET image_url = 'http://static1.squarespace.com/static/6478a38999812546babb8e36/t/67bf42b0d7ee0406f0c5f769/1724096196631/5.png?format=1500w' WHERE slug = 'summerhill-market';  -- Summerhill Market
UPDATE vendors SET image_url = 'https://labottegaditerroni.com/cdn/shop/files/Catering_Hero_2_300x.jpg?v=1746822618' WHERE slug = 'terroni';  -- Terroni
UPDATE vendors SET image_url = 'https://static3.grubbio.com/10522g-albums-2.jpg' WHERE slug = 'the-chicken-nest';  -- The Chicken Nest
UPDATE vendors SET image_url = 'https://tuttopronto.ca/wp-content/uploads/2019/11/header-platters.jpg' WHERE slug = 'tutto-pronto';  -- Tutto Pronto
UPDATE vendors SET image_url = 'https://unitedbakers.ca/cdn/shop/files/united-bakers-catering-for-30_1200x.jpg?v=1748883399' WHERE slug = 'united-bakers-dairy-restaurant';  -- United Bakers Dairy Restaurant
UPDATE vendors SET image_url = 'https://s3.amazonaws.com/curbngo-menu-items/thumbs/76416CEB-E44C-440C-AB7E-BBDA1195DE5B.jpeg' WHERE slug = 'wok-bowl';  -- Wok & Bowl
UPDATE vendors SET image_url = 'https://yummymarket.com/wp-content/uploads/2020/10/partyplatters-header.jpg' WHERE slug = 'yummy-market';  -- Yummy Market

-- === 2. Image URL NULLs (stock-photo / unpicked → cream placeholder) ===
UPDATE vendors SET image_url = '' WHERE slug = 'ba-li-laffa';  -- Ba-Li Laffa
UPDATE vendors SET image_url = '' WHERE slug = 'benny-fils';  -- Benny & Fils
UPDATE vendors SET image_url = '' WHERE slug = 'beyond-delish';  -- Beyond Delish
UPDATE vendors SET image_url = '' WHERE slug = 'cheese-boutique';  -- Cheese Boutique
UPDATE vendors SET image_url = '' WHERE slug = 'dr-laffa';  -- Dr. Laffa
UPDATE vendors SET image_url = '' WHERE slug = 'f-b-kosher-catering';  -- F + B Kosher Catering
UPDATE vendors SET image_url = '' WHERE slug = 'golden-chopsticks';  -- Golden Chopsticks
UPDATE vendors SET image_url = '' WHERE slug = 'haymishe-bakery';  -- Haymishe Bakery
UPDATE vendors SET image_url = '' WHERE slug = 'howie-ts-burger-bar';  -- Howie T''s Burger Bar
UPDATE vendors SET image_url = '' WHERE slug = 'jojos-pizza';  -- JoJo''s Pizza
UPDATE vendors SET image_url = '' WHERE slug = 'kosher-quality-bakery-deli';  -- Kosher Quality Bakery & Deli
UPDATE vendors SET image_url = '' WHERE slug = 'mehadrin-meats';  -- Mehadrin Meats
UPDATE vendors SET image_url = '' WHERE slug = 'montreal-kosher-bakery';  -- Montreal Kosher Bakery
UPDATE vendors SET image_url = '' WHERE slug = 'nortown-foods';  -- Nortown Foods
UPDATE vendors SET image_url = '' WHERE slug = 'paisanos';  -- Paisanos
UPDATE vendors SET image_url = '' WHERE slug = 'pancers-original-deli';  -- Pancer''s Original Deli
UPDATE vendors SET image_url = '' WHERE slug = 'pizza-cafe';  -- Pizza Cafe
UPDATE vendors SET image_url = '' WHERE slug = 'pizza-gourmetti';  -- Pizza Gourmetti
UPDATE vendors SET image_url = '' WHERE slug = 'pizza-pita-prime';  -- Pizza Pita Prime
UPDATE vendors SET image_url = '' WHERE slug = 'pusateris-fine-foods';  -- Pusateri''s Fine Foods
UPDATE vendors SET image_url = '' WHERE slug = 'snowdon-deli';  -- Snowdon Deli
UPDATE vendors SET image_url = '' WHERE slug = 'sonny-langers-dairy-vegetarian-caterers';  -- Sonny Langers Dairy & Vegetarian Caterers
UPDATE vendors SET image_url = '' WHERE slug = 'sushi-inn';  -- Sushi Inn
UPDATE vendors SET image_url = '' WHERE slug = 'tov-li-pizza-falafel';  -- Tov-Li Pizza & Falafel
UPDATE vendors SET image_url = '' WHERE slug = 'zeldens-deli-and-desserts';  -- Zelden''s Deli and Desserts

-- === 3. Vendor deletions (Option B drops) ===
-- Moishes
DELETE FROM vendor_leads WHERE vendor_id IN (SELECT id FROM vendors WHERE slug = 'moishes');
DELETE FROM vendor_clicks WHERE vendor_slug = 'moishes';
DELETE FROM vendor_views WHERE vendor_slug = 'moishes';
DELETE FROM vendors WHERE slug = 'moishes';

-- Post-migration row counts
SELECT 'vendors after' AS label, COUNT(*) AS n FROM vendors;
SELECT 'with image' AS label, COUNT(*) AS n FROM vendors WHERE image_url IS NOT NULL AND image_url <> '';
SELECT 'placeholder' AS label, COUNT(*) AS n FROM vendors WHERE image_url IS NULL OR image_url = '';

COMMIT;

-- ROLLBACK INSTRUCTIONS
-- If anything looks wrong AFTER COMMIT, restore from the pre-migration dump:
--   sqlite3 neshama.db < pre-bundle-backup.sql
-- Take the backup BEFORE running this script:
--   sqlite3 neshama.db '.dump vendors' > /tmp/vendors-pre-apr21.sql
--   sqlite3 neshama.db '.dump vendor_leads' > /tmp/vendor_leads-pre-apr21.sql
