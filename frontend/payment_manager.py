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
        self.currency = 'cad'
        
        self.setup_database()
    
    def setup_database(self):
        """Add premium columns to subscribers table"""
        conn = sqlite3.connect(self.db_path)
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
