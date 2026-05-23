#!/usr/bin/env python3
"""
Neshama Payment Integration
Handles Stripe subscriptions for Premium ($18/year)
"""

import sqlite3
import os
from datetime import datetime
import json

# Stripe imports (install with: pip3 install stripe)
import stripe
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class PaymentManager:
    def __init__(self, db_path='neshama.db', stripe_api_key=None):
        """Initialize payment manager"""
        self.db_path = db_path
        self.stripe_api_key = stripe_api_key or os.environ.get('STRIPE_SECRET_KEY')
        
        if not self.stripe_api_key:
            logging.warning(" Warning: STRIPE_SECRET_KEY not set")
        else:
            stripe.api_key = self.stripe_api_key
        
        # Product configuration
        self.premium_price_id = os.environ.get('STRIPE_PRICE_ID')  # Set this in production
        self.premium_annual_price = 1800  # $18.00 in cents
        # Featured Vendor (vendor-side only; families never pay)
        self.featured_monthly_price = 4900  # $49.00/mo in cents
        self.featured_trial_days = 90       # 3-month free trial, no charge during trial
        self.currency = 'cad'

        self.setup_database()
        self.setup_vendor_featured_schema()
    
    def setup_database(self):
        """Add premium columns to subscribers table"""
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.execute('PRAGMA busy_timeout=30000')
        cursor = conn.cursor()
        
        # Add premium tracking columns if they don't exist
        try:
            cursor.execute('''
                ALTER TABLE subscribers ADD COLUMN premium BOOLEAN DEFAULT FALSE
            ''')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('''
                ALTER TABLE subscribers ADD COLUMN premium_since TEXT
            ''')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('''
                ALTER TABLE subscribers ADD COLUMN stripe_customer_id TEXT
            ''')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('''
                ALTER TABLE subscribers ADD COLUMN stripe_subscription_id TEXT
            ''')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('''
                ALTER TABLE subscribers ADD COLUMN premium_expires_at TEXT
            ''')
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        conn.close()

    # ── Featured Vendor ($49/mo subscription). Vendor-side only ──────────
    # Families never pay. This block governs the vendors table only and never
    # touches the subscribers/sustainer flow above.

    def setup_vendor_featured_schema(self):
        """Additive migration: add Featured Vendor columns to the vendors table.
        Idempotent (guarded). The editorial-featured set is intentionally EMPTY
        (decided 2026-05-22): "featured" means a vendor who paid. featured_source
        is set to 'paid' only by the webhook below; there is no editorial backfill.
        The featured_source='paid' guard on defeature stays as a defensive measure
        against ever defeaturing a manually-set future row."""
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.execute('PRAGMA busy_timeout=30000')
        cursor = conn.cursor()

        for ddl in (
            "ALTER TABLE vendors ADD COLUMN stripe_customer_id TEXT",
            "ALTER TABLE vendors ADD COLUMN stripe_subscription_id TEXT",
            "ALTER TABLE vendors ADD COLUMN featured_status TEXT",       # trialing|active|past_due|canceled|unpaid
            "ALTER TABLE vendors ADD COLUMN featured_since TEXT",
            "ALTER TABLE vendors ADD COLUMN trial_ends_at TEXT",
            "ALTER TABLE vendors ADD COLUMN featured_source TEXT",       # 'paid' only (no editorial set)
        ):
            try:
                cursor.execute(ddl)
            except sqlite3.OperationalError:
                pass  # column already exists

        conn.commit()
        conn.close()

    def create_vendor_featured_checkout(self, vendor_slug, email, success_url, cancel_url):
        """Create a Stripe Checkout session for the $49/mo Featured Vendor
        subscription with a 90-day free trial (no charge during the trial).
        vendor_slug is carried in metadata on BOTH the session and the
        subscription so webhooks can identify the vendor on later events."""
        if not self.stripe_api_key:
            return {'error': 'Payment system not configured', 'test_mode': True}
        if not vendor_slug:
            return {'error': 'vendor_slug required'}

        try:
            customer = self.get_or_create_stripe_customer(email) if email else None
            session_kwargs = {
                'payment_method_types': ['card'],
                'line_items': [{
                    'price_data': {
                        'currency': self.currency,
                        'product_data': {
                            'name': 'Neshama Featured Vendor',
                            'description': 'Monthly featured placement in the Neshama vendor directory',
                        },
                        'unit_amount': self.featured_monthly_price,
                        'recurring': {'interval': 'month'},
                    },
                    'quantity': 1,
                }],
                'mode': 'subscription',
                'subscription_data': {
                    'trial_period_days': self.featured_trial_days,
                    'metadata': {
                        'product': 'neshama_featured_vendor',
                        'vendor_slug': vendor_slug,
                    },
                },
                'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}',
                'cancel_url': cancel_url,
                'billing_address_collection': 'required',
                'metadata': {
                    'product': 'neshama_featured_vendor',
                    'vendor_slug': vendor_slug,
                    'email': email or '',
                },
            }
            if customer:
                session_kwargs['customer'] = customer.id
                session_kwargs['customer_update'] = {'address': 'auto'}
            else:
                session_kwargs['customer_email'] = email or None

            session = stripe.checkout.Session.create(**session_kwargs)
            return {'url': session.url, 'session_id': session.id}

        except stripe.error.StripeError as e:
            logging.error(f"Vendor featured checkout error: {str(e)}")
            return {'error': str(e)}

    def set_vendor_featured(self, vendor_slug, status, customer_id=None,
                            subscription_id=None, trial_ends_at=None):
        """Turn ON paid featured placement for a vendor (trialing or active).
        Marks the row featured_source='paid' so editorial seeds are never
        affected. Idempotent."""
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.execute('PRAGMA busy_timeout=30000')
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE vendors SET
                featured = 1,
                featured_source = 'paid',
                featured_status = ?,
                featured_since = COALESCE(featured_since, ?),
                trial_ends_at = COALESCE(?, trial_ends_at),
                stripe_customer_id = COALESCE(?, stripe_customer_id),
                stripe_subscription_id = COALESCE(?, stripe_subscription_id)
            WHERE slug = ?
            """,
            (status, datetime.now().isoformat(), trial_ends_at,
             customer_id, subscription_id, vendor_slug)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        logging.info(f" Featured ON ({status}) for vendor '{vendor_slug}' (rows={affected})")
        return affected

    def set_vendor_featured_status(self, subscription_id, status):
        """Update only the status text for a paid vendor without changing the
        featured flag. Used for grace states like past_due, where the vendor STAYS
        featured during Stripe dunning."""
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.execute('PRAGMA busy_timeout=30000')
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE vendors SET featured_status = ? "
            "WHERE stripe_subscription_id = ? AND featured_source = 'paid'",
            (status, subscription_id)
        )
        conn.commit()
        conn.close()

    def defeature_vendor(self, subscription_id, status='canceled'):
        """Turn OFF featured placement for a PAID vendor identified by Stripe
        subscription id. The featured_source='paid' guard means an editorial
        seed can never be defeatured by payment events. Only called when a
        subscription reaches a terminal/unpaid state (after dunning), never on
        a single failed invoice."""
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.execute('PRAGMA busy_timeout=30000')
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE vendors SET featured = 0, featured_status = ? "
            "WHERE stripe_subscription_id = ? AND featured_source = 'paid'",
            (status, subscription_id)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        logging.info(f" Featured OFF ({status}) for subscription '{subscription_id}' (rows={affected})")
        return affected

    def create_vendor_portal_session(self, vendor_slug, return_url):
        """Stripe Customer Portal session for a vendor to manage/cancel their
        Featured subscription. Cancellation flows back through the webhook."""
        if not self.stripe_api_key:
            return {'error': 'Payment system not configured'}
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT stripe_customer_id FROM vendors WHERE slug = ?", (vendor_slug,))
        row = cursor.fetchone()
        conn.close()
        if not row or not row[0]:
            return {'error': 'No featured subscription found for this vendor'}
        try:
            session = stripe.billing_portal.Session.create(
                customer=row[0], return_url=return_url,
            )
            return {'url': session.url}
        except stripe.error.StripeError as e:
            logging.error(f"Vendor portal error: {str(e)}")
            return {'error': str(e)}

    def create_checkout_session(self, email, success_url, cancel_url, amount=18):
        """
        Create Stripe Checkout session for community sustainer contribution
        Returns: {'url': 'checkout.stripe.com/...', 'session_id': '...'}
        """
        if not self.stripe_api_key:
            return {
                'error': 'Payment system not configured',
                'test_mode': True
            }
        
        try:
            # Create or retrieve Stripe customer
            customer = self.get_or_create_stripe_customer(email)
            
            # Validate and convert amount to cents
            try:
                amount_cents = int(amount) * 100
                if amount_cents < 100:
                    amount_cents = 1800  # fallback to $18
            except (ValueError, TypeError):
                amount_cents = 1800

            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': self.currency,
                        'product_data': {
                            'name': 'Sustain Neshama',
                            'description': 'Annual community sustainer contribution',
                        },
                        'unit_amount': amount_cents,
                        'recurring': {
                            'interval': 'year',
                        }
                    },
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
                customer_update={
                    'address': 'auto',
                },
                # Tax - enable after configuring business address in Stripe dashboard
                # tax_id_collection={'enabled': True},
                # automatic_tax={'enabled': True},
                billing_address_collection='required',
                metadata={
                    'email': email,
                    'product': 'neshama_sustainer_annual'
                }
            )
            
            return {
                'url': session.url,
                'session_id': session.id
            }
            
        except stripe.error.StripeError as e:
            logging.error(f"Stripe error: {str(e)}")
            return {
                'error': str(e)
            }
    
    def get_or_create_stripe_customer(self, email):
        """Get existing Stripe customer or create new one"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if customer exists in database
        cursor.execute('''
            SELECT stripe_customer_id FROM subscribers WHERE email = ?
        ''', (email,))
        
        result = cursor.fetchone()
        
        if result and result[0]:
            # Customer exists, retrieve from Stripe
            try:
                customer = stripe.Customer.retrieve(result[0])
                conn.close()
                return customer
            except stripe.error.StripeError:
                pass  # Customer not found, create new one
        
        # Create new customer
        customer = stripe.Customer.create(
            email=email,
            metadata={
                'source': 'neshama_app'
            }
        )
        
        # Store customer ID
        cursor.execute('''
            UPDATE subscribers SET stripe_customer_id = ? WHERE email = ?
        ''', (customer.id, email))
        
        conn.commit()
        conn.close()
        
        return customer
    
    def activate_premium(self, email, stripe_subscription_id=None):
        """Activate premium for email address"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE subscribers SET
                premium = TRUE,
                premium_since = ?,
                stripe_subscription_id = ?
            WHERE email = ?
        ''', (datetime.now().isoformat(), stripe_subscription_id, email))
        
        conn.commit()
        conn.close()
        
        logging.info(f" Premium activated for {email}")
    
    def deactivate_premium(self, email):
        """Deactivate premium for email address"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE subscribers SET
                premium = FALSE,
                premium_expires_at = ?
            WHERE email = ?
        ''', (datetime.now().isoformat(), email))
        
        conn.commit()
        conn.close()
        
        logging.info(f" Premium deactivated for {email}")
    
    def is_premium(self, email):
        """Check if email has active premium subscription"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT premium FROM subscribers WHERE email = ?
        ''', (email,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result and result[0]
    
    def get_premium_info(self, email):
        """Get premium subscription details for email"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT premium, premium_since, stripe_customer_id, 
                   stripe_subscription_id, premium_expires_at
            FROM subscribers 
            WHERE email = ?
        ''', (email,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return dict(result)
        return None
    
    def create_customer_portal_session(self, email, return_url):
        """
        Create Stripe Customer Portal session for subscription management
        Returns: {'url': 'billing.stripe.com/...'}
        """
        if not self.stripe_api_key:
            return {'error': 'Payment system not configured'}
        
        try:
            # Get customer ID
            info = self.get_premium_info(email)
            if not info or not info.get('stripe_customer_id'):
                return {'error': 'No subscription found'}
            
            # Create portal session
            session = stripe.billing_portal.Session.create(
                customer=info['stripe_customer_id'],
                return_url=return_url,
            )
            
            return {'url': session.url}
            
        except stripe.error.StripeError as e:
            logging.error(f"Portal error: {str(e)}")
            return {'error': str(e)}
    
    def handle_webhook(self, payload, signature, webhook_secret):
        """
        Handle Stripe webhook events
        Returns: {'status': 'success'/'error', 'message': '...'}
        """
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
        except ValueError:
            return {'status': 'error', 'message': 'Invalid payload'}
        except stripe.error.SignatureVerificationError:
            return {'status': 'error', 'message': 'Invalid signature'}
        
        event_type = event['type']
        obj = event['data']['object']

        # ── Featured Vendor routing (vendor-side; intercept before sustainer) ──
        # Vendor events are identified by metadata.product on the checkout
        # session or the subscription. Grace rule: a single failed invoice never
        # defeatures; only a subscription reaching canceled/unpaid does.
        def _is_vendor(meta):
            return bool(meta) and meta.get('product') == 'neshama_featured_vendor'

        if event_type == 'checkout.session.completed' and _is_vendor(obj.get('metadata')):
            vendor_slug = obj['metadata'].get('vendor_slug')
            subscription_id = obj.get('subscription')
            customer_id = obj.get('customer')
            status, trial_ends_at = 'trialing', None
            try:
                if subscription_id:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    status = sub.get('status', 'trialing')
                    if sub.get('trial_end'):
                        trial_ends_at = datetime.utcfromtimestamp(sub['trial_end']).isoformat()
            except stripe.error.StripeError:
                pass
            self.set_vendor_featured(vendor_slug, status, customer_id, subscription_id, trial_ends_at)
            return {'status': 'success', 'message': f'Featured vendor activated: {vendor_slug} ({status})'}

        if event_type in ('customer.subscription.updated', 'customer.subscription.deleted') and _is_vendor(obj.get('metadata')):
            subscription_id = obj.get('id')
            status = obj.get('status', 'canceled')
            if event_type == 'customer.subscription.deleted':
                self.defeature_vendor(subscription_id, status='canceled')
                return {'status': 'success', 'message': f'Featured vendor cancelled: {subscription_id}'}
            if status in ('active', 'trialing'):
                self.set_vendor_featured(obj['metadata'].get('vendor_slug'), status, subscription_id=subscription_id)
                return {'status': 'success', 'message': f'Featured vendor active: {subscription_id} ({status})'}
            if status in ('canceled', 'unpaid'):
                # Terminal/unpaid after Stripe dunning exhausts → defeature now.
                self.defeature_vendor(subscription_id, status=status)
                return {'status': 'success', 'message': f'Featured vendor defeatured: {subscription_id} ({status})'}
            # past_due / incomplete / etc → GRACE: stay featured, record status.
            self.set_vendor_featured_status(subscription_id, status)
            return {'status': 'success', 'message': f'Featured vendor grace state: {subscription_id} ({status})'}

        if event_type == 'invoice.payment_failed' and obj.get('subscription'):
            try:
                sub = stripe.Subscription.retrieve(obj['subscription'])
                if _is_vendor(sub.get('metadata')):
                    logging.warning(f" Featured vendor invoice failed (grace window, NOT defeaturing): {obj['subscription']}")
                    return {'status': 'success', 'message': 'Featured vendor payment failed; grace window, not defeatured'}
            except stripe.error.StripeError:
                pass
        # ── end Featured Vendor routing; sustainer ($18 annual) logic below ──

        # Handle different event types
        if event_type == 'checkout.session.completed':
            session = event['data']['object']
            email = session['customer_details']['email']
            subscription_id = session.get('subscription')
            
            self.activate_premium(email, subscription_id)
            
            return {
                'status': 'success',
                'message': f'Premium activated for {email}'
            }
        
        elif event_type == 'customer.subscription.deleted':
            subscription = event['data']['object']
            customer_id = subscription['customer']
            
            # Find email by customer ID
            email = self.get_email_by_customer_id(customer_id)
            if email:
                self.deactivate_premium(email)
            
            return {
                'status': 'success',
                'message': f'Premium cancelled for {email}'
            }
        
        elif event_type == 'invoice.payment_failed':
            invoice = event['data']['object']
            customer_id = invoice['customer']
            email = self.get_email_by_customer_id(customer_id)
            
            # TODO: Send email notification about failed payment
            logging.error(f" Payment failed for {email}")
            
            return {
                'status': 'success',
                'message': f'Payment failure logged for {email}'
            }
        
        elif event_type == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            customer_id = invoice['customer']
            email = self.get_email_by_customer_id(customer_id)
            
            # Renewal successful
            logging.info(f" Renewal successful for {email}")
            
            return {
                'status': 'success',
                'message': f'Renewal processed for {email}'
            }
        
        else:
            # Unhandled event type
            return {
                'status': 'success',
                'message': f'Unhandled event type: {event_type}'
            }
    
    def get_email_by_customer_id(self, customer_id):
        """Get email address by Stripe customer ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT email FROM subscribers WHERE stripe_customer_id = ?
        ''', (customer_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def get_stats(self):
        """Get premium subscription statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM subscribers WHERE premium = TRUE')
        premium_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM subscribers WHERE confirmed = TRUE')
        total_subscribers = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'premium_subscribers': premium_count,
            'free_subscribers': total_subscribers - premium_count,
            'total_subscribers': total_subscribers,
            'conversion_rate': round(premium_count / total_subscribers * 100, 1) if total_subscribers > 0 else 0,
            'annual_recurring_revenue': premium_count * 18  # $18/year
        }

if __name__ == '__main__':
    # Test the payment system
    manager = PaymentManager()
    
    logging.info("\n" + "="*60)
    logging.info(" NESHAMA PAYMENT SYSTEM")
    logging.info("="*60 + "\n")
    
    stats = manager.get_stats()
    logging.info(f"Premium subscribers: {stats['premium_subscribers']}")
    logging.info(f"Free subscribers: {stats['free_subscribers']}")
    logging.info(f"Total subscribers: {stats['total_subscribers']}")
    logging.info(f"Conversion rate: {stats['conversion_rate']}%")
    logging.info(f"Annual recurring revenue: ${stats['annual_recurring_revenue']} CAD")
    
    logging.info("\n" + "="*60 + "\n")
