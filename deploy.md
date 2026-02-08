# Deploying Neshama to Render.com

## Prerequisites

- A [Render.com](https://render.com) account (free tier works)
- A GitHub repository with the Neshama code pushed to it
- Your API keys ready:
  - SendGrid API key
  - Stripe secret key
  - Stripe publishable key

---

## Step 1: Push Code to GitHub

```bash
cd ~/Desktop/Neshama
git init
git add -A
git commit -m "Initial commit - Neshama obituary service"
```

Create a new repository on GitHub (https://github.com/new), then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/neshama.git
git branch -M main
git push -u origin main
```

---

## Step 2: Create Web Service on Render

### Option A: Blueprint (Automatic)

1. Go to https://dashboard.render.com
2. Click **New** > **Blueprint**
3. Connect your GitHub repository
4. Render will detect `render.yaml` and configure everything automatically
5. You will be prompted to enter environment variable values (see Step 3)

### Option B: Manual Setup

1. Go to https://dashboard.render.com
2. Click **New** > **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Name:** `neshama`
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt && python database_setup.py`
   - **Start Command:** `python frontend/api_server.py`
5. Add a **Disk:**
   - **Name:** `neshama-data`
   - **Mount Path:** `/data`
   - **Size:** 1 GB
6. Set environment variables (see Step 3)
7. Click **Create Web Service**

---

## Step 3: Set Environment Variables

In the Render dashboard, go to your service > **Environment** and add:

| Key | Value | Notes |
|-----|-------|-------|
| `DATABASE_PATH` | `/data/neshama.db` | Points to persistent disk |
| `SENDGRID_API_KEY` | `SG.xxxxx...` | Your SendGrid API key |
| `STRIPE_SECRET_KEY` | `sk_live_xxxxx...` | Use `sk_test_...` for testing |
| `STRIPE_PUBLISHABLE_KEY` | `pk_live_xxxxx...` | Use `pk_test_...` for testing |
| `STRIPE_WEBHOOK_SECRET` | `whsec_xxxxx...` | Set after Step 5 |

---

## Step 4: Point neshama.ca DNS to Render

### In Render Dashboard:

1. Go to your web service > **Settings** > **Custom Domains**
2. Click **Add Custom Domain**
3. Enter `neshama.ca`
4. Also add `www.neshama.ca`
5. Render will show you the DNS records to create

### At Your Domain Registrar (where you bought neshama.ca):

Add these DNS records:

| Type | Name | Value |
|------|------|-------|
| CNAME | `www` | `neshama.onrender.com` |
| A | `@` | *(Render will provide the IP)* |

Or if your registrar supports CNAME flattening (like Cloudflare):

| Type | Name | Value |
|------|------|-------|
| CNAME | `@` | `neshama.onrender.com` |
| CNAME | `www` | `neshama.onrender.com` |

**SSL/HTTPS:** Render provides free SSL certificates automatically. After DNS propagates (5-30 minutes), https://neshama.ca will work.

---

## Step 5: Set Up Stripe Webhook

After your service is live:

1. Go to [Stripe Dashboard](https://dashboard.stripe.com) > **Developers** > **Webhooks**
2. Click **Add endpoint**
3. Set endpoint URL: `https://neshama.ca/webhook`
4. Select these events:
   - `checkout.session.completed`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
   - `invoice.payment_succeeded`
5. Click **Add endpoint**
6. Copy the **Signing secret** (`whsec_...`)
7. Go back to Render dashboard > **Environment**
8. Set `STRIPE_WEBHOOK_SECRET` to the signing secret value

---

## Step 6: Initialize the Database

The first deploy runs `python database_setup.py` as part of the build command, which creates the SQLite database tables on the persistent disk.

To populate it with obituaries, you have two options:

### Option A: Upload Existing Database

1. SSH or use Render Shell to copy your local `neshama.db` to `/data/neshama.db`

### Option B: Run Scrapers on Render

Add a **Cron Job** in Render:

1. Go to **New** > **Cron Job**
2. Connect same GitHub repo
3. **Command:** `python master_scraper.py`
4. **Schedule:** `0 */4 * * *` (every 4 hours)
5. Add same `DATABASE_PATH` environment variable

---

## Step 7: Set Up Daily Digest Cron

To send daily email digests:

1. Go to Render dashboard > **New** > **Cron Job**
2. Connect same GitHub repo
3. **Command:** `cd frontend && python daily_digest.py`
4. **Schedule:** `0 12 * * *` (every day at 7 AM ET / 12 PM UTC)
5. Set environment variables:
   - `DATABASE_PATH` = `/data/neshama.db`
   - `SENDGRID_API_KEY` = your key

---

## Step 8: Verify Deployment

After deploying, test these URLs:

- https://neshama.ca - Landing page
- https://neshama.ca/feed - Obituary feed
- https://neshama.ca/about - About page
- https://neshama.ca/api/status - API health check
- https://neshama.ca/api/obituaries - API data

Test the email flow:
1. Subscribe on the feed page
2. Check email for confirmation
3. Click confirmation link

Test the payment flow (in test mode):
1. Click a premium feature
2. Use test card `4242 4242 4242 4242`
3. Verify redirect to success page

---

## Going Live with Stripe

When ready to accept real payments:

1. In Stripe Dashboard, toggle from **Test mode** to **Live mode**
2. Get your live API keys (`sk_live_...`, `pk_live_...`)
3. Update environment variables in Render:
   - `STRIPE_SECRET_KEY` = live secret key
   - `STRIPE_PUBLISHABLE_KEY` = live publishable key
4. Create a new webhook endpoint for live mode and update `STRIPE_WEBHOOK_SECRET`
5. Complete Stripe account activation (business details, bank account)

---

## Monitoring

- **Render Dashboard:** View logs, restarts, deploy history
- **Stripe Dashboard:** Monitor payments, subscriptions, webhook logs
- **SendGrid Dashboard:** Track email delivery, bounces, opens

---

## Troubleshooting

**Site shows "Not Found":**
- Check Render deploy logs for errors
- Verify build and start commands are correct

**Database empty after deploy:**
- Run scrapers manually or upload existing database
- Verify `DATABASE_PATH` points to `/data/neshama.db`

**Emails not sending:**
- Check `SENDGRID_API_KEY` is set correctly
- Verify sender identity is verified in SendGrid

**Payments not working:**
- Check `STRIPE_SECRET_KEY` is set
- Verify webhook endpoint URL and secret
- Check Stripe webhook logs for delivery failures

**DNS not resolving:**
- Allow 5-30 minutes for DNS propagation
- Verify records with `dig neshama.ca` or `nslookup neshama.ca`
- Check for typos in CNAME/A record values
