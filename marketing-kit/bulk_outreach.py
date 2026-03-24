#!/usr/bin/env python3
"""
#######################################################################
#  WARNING: NOTHING SENDS WITHOUT THE --send FLAG                     #
#                                                                     #
#  By default this script runs in DRY RUN mode.                       #
#  It will print what WOULD be sent but will NOT send any emails.     #
#  You MUST pass --send to actually deliver emails via SendGrid.      #
#                                                                     #
#  Usage:                                                             #
#    python3 bulk_outreach.py --type vendor           # dry run       #
#    python3 bulk_outreach.py --type vendor --send    # actually send #
#    python3 bulk_outreach.py --type synagogue --send                 #
#    python3 bulk_outreach.py --type vendor --send --to test@x.com   #
#######################################################################

Neshama Bulk Outreach Email Sender
Sends personalized vendor/synagogue outreach emails via SendGrid.
"""

import argparse
import csv
import json
import os
import sys
import time
import base64
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONTACTS_CSV = SCRIPT_DIR / "outreach-contacts.csv"
OUTREACH_LOG = SCRIPT_DIR / "outreach-log.json"
PDF_ATTACHMENT = SCRIPT_DIR / "general" / "how-neshama-works-v2.pdf"

FROM_EMAIL = "contact@neshama.ca"
FROM_NAME = "Erin Kofman — Neshama"
REPLY_TO = "contact@neshama.ca"

RATE_LIMIT_SECONDS = 2  # seconds between sends


# ---------------------------------------------------------------------------
# Contact loader
# ---------------------------------------------------------------------------
def load_contacts(csv_path: Path, contact_type: str, single_to: str = None):
    """Load contacts from CSV, filtered by type. If single_to is set, only
    return a synthetic contact for that email address."""
    contacts = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip(): v.strip() for k, v in row.items()}
            if row.get("type", "").lower() == contact_type.lower():
                contacts.append(row)

    if single_to:
        # Find matching contact or create a test one
        for c in contacts:
            if c["email"].lower() == single_to.lower():
                return [c]
        # Not found — create a generic test contact
        return [{
            "name": "Test Recipient",
            "email": single_to,
            "organization": "Test Organization",
            "type": contact_type,
        }]

    return contacts


# ---------------------------------------------------------------------------
# Outreach log (dedup)
# ---------------------------------------------------------------------------
def load_log(log_path: Path) -> dict:
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sent": []}


def save_log(log_path: Path, log_data: dict):
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)


def already_sent(log_data: dict, email: str, contact_type: str) -> bool:
    for entry in log_data.get("sent", []):
        if entry["email"].lower() == email.lower() and entry["type"] == contact_type:
            return True
    return False


def record_sent(log_data: dict, email: str, contact_type: str, org: str, subject: str):
    log_data["sent"].append({
        "email": email,
        "type": contact_type,
        "organization": org,
        "subject": subject,
        "sent_at": datetime.now().isoformat(),
    })


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------

def vendor_subject(org: str) -> str:
    return f"{org} is listed on Neshama \u2014 a resource for Jewish families"


def synagogue_subject(org: str) -> str:
    return f"A community resource for {org} \u2014 Neshama.ca"


def vendor_html(name: str, org: str) -> str:
    greeting = f"Hi {name}," if name else "Hi there,"
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #FFF8F0; -webkit-font-smoothing: antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #FFF8F0;">
<tr><td align="center" style="padding: 40px 20px;">
<table role="presentation" width="580" cellpadding="0" cellspacing="0" style="max-width: 580px; width: 100%; background-color: #ffffff; border-radius: 6px; overflow: hidden;">

    <!-- Header bar -->
    <tr><td style="padding: 28px 36px 24px 36px; border-bottom: 2px solid #D2691E;">
        <span style="font-family: 'Cormorant Garamond', Georgia, 'Times New Roman', serif; font-size: 24px; color: #3E2723; letter-spacing: 0.03em;">Neshama</span>
    </td></tr>

    <!-- Body -->
    <tr><td style="padding: 32px 36px 36px 36px; font-family: 'Crimson Pro', Georgia, 'Times New Roman', serif; font-size: 16px; line-height: 1.75; color: #3E2723;">

        <p style="margin: 0 0 18px 0;">{greeting}</p>

        <p style="margin: 0 0 18px 0;">My name is Erin Kofman. I built <a href="https://neshama.ca" style="color: #D2691E; text-decoration: underline;">Neshama</a> &mdash; a resource for Jewish families in Toronto and Montreal dealing with a loss.</p>

        <p style="margin: 0 0 18px 0;">When someone passes away, the people around them want to help. Send a meal. Bring food for shiva. Find something meaningful to send. Neshama helps them do that &mdash; obituaries from the public funeral home sites, a meal coordination tool, and a directory of local vendors like you.</p>

        <p style="margin: 0 0 18px 0;"><strong style="color: #3E2723;">{org} is already listed on Neshama.</strong> People are using the directory to find vendors for shiva meals, gifts, and other ways to show support.</p>

        <p style="margin: 0 0 18px 0;">Your listing includes your business name, contact information, a link to your website, and your category so families find you when they need you most.</p>

        <p style="margin: 0 0 18px 0;">If anything needs updating &mdash; hours, description, contact details &mdash; just reply and I'll take care of it.</p>

        <p style="margin: 0 0 24px 0;">I've attached a one-page overview of how Neshama works. You can also see the site in action here:</p>

        <!-- CTA Button -->
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 0 0 28px 0;">
        <tr><td style="background-color: #D2691E; border-radius: 4px;">
            <a href="https://neshama.ca/demo" style="display: inline-block; padding: 13px 30px; font-family: 'Crimson Pro', Georgia, serif; font-size: 15px; color: #ffffff; text-decoration: none; letter-spacing: 0.02em;">See Neshama in action</a>
        </td></tr>
        </table>

        <p style="margin: 0 0 18px 0;">Thank you for being part of what families rely on during the hardest moments.</p>

        <p style="margin: 0 0 4px 0;">Warm regards,</p>
        <p style="margin: 0 0 0 0;"><strong>Erin Kofman</strong></p>
        <p style="margin: 0; font-size: 14px; color: #5c534a;">
            <a href="https://neshama.ca" style="color: #D2691E;">neshama.ca</a> &middot;
            <a href="mailto:contact@neshama.ca" style="color: #D2691E;">contact@neshama.ca</a>
        </p>

    </td></tr>

    <!-- Warm footer -->
    <tr><td style="padding: 20px 36px; background-color: #FFF8F0; border-top: 1px solid #e8e0d8;">
        <p style="margin: 0; font-family: 'Crimson Pro', Georgia, serif; font-size: 13px; color: #9e9488; line-height: 1.6;">Neshama &middot; Toronto &amp; Montreal &middot; A community resource for Jewish families</p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def synagogue_html(name: str, org: str) -> str:
    if name:
        greeting = f"Dear {name},"
    else:
        greeting = "Dear Synagogue Office,"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #FFF8F0; -webkit-font-smoothing: antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #FFF8F0;">
<tr><td align="center" style="padding: 40px 20px;">
<table role="presentation" width="580" cellpadding="0" cellspacing="0" style="max-width: 580px; width: 100%; background-color: #ffffff; border-radius: 6px; overflow: hidden;">

    <!-- Header bar -->
    <tr><td style="padding: 28px 36px 24px 36px; border-bottom: 2px solid #D2691E;">
        <span style="font-family: 'Cormorant Garamond', Georgia, 'Times New Roman', serif; font-size: 24px; color: #3E2723; letter-spacing: 0.03em;">Neshama</span>
    </td></tr>

    <!-- Body -->
    <tr><td style="padding: 32px 36px 36px 36px; font-family: 'Crimson Pro', Georgia, 'Times New Roman', serif; font-size: 16px; line-height: 1.75; color: #3E2723;">

        <p style="margin: 0 0 18px 0;">{greeting}</p>

        <p style="margin: 0 0 18px 0;">My name is Erin Kofman. I built a resource for Jewish families in Toronto and Montreal called <a href="https://neshama.ca" style="color: #D2691E; text-decoration: underline;">Neshama</a>, and I wanted to share it with you.</p>

        <p style="margin: 0 0 18px 0;">When someone in our community passes away, the people who want to help always have the same questions. Where's the obituary? Has anyone organized meals? What day should I bring food? Who can I call?</p>

        <p style="margin: 0 0 18px 0;">Neshama puts all of that in one place:</p>

        <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 0 0 20px 0; font-family: 'Crimson Pro', Georgia, serif; font-size: 15px; line-height: 1.7; color: #3E2723;">
            <tr><td style="padding: 4px 0;"><strong>1.</strong> <strong>Obituary feed</strong> &mdash; Pulls directly from funeral home websites (Steeles, Benjamin's, Paperman &amp; Sons) so families don't have to check three different sites.</td></tr>
            <tr><td style="padding: 4px 0;"><strong>2.</strong> <strong>Meal coordination</strong> &mdash; A family sets up a shiva page. Volunteers sign up for specific days. Everyone sees what's covered and what's still needed.</td></tr>
            <tr><td style="padding: 4px 0;"><strong>3.</strong> <strong>"How Can I Help?" hub</strong> &mdash; 120+ local food partners and gift vendors. Browse by category, city, and dietary needs.</td></tr>
            <tr><td style="padding: 4px 0;"><strong>4.</strong> <strong>Yahrzeit reminders</strong> &mdash; Annual email reminders based on the Hebrew calendar, sent before the date so there's time to prepare.</td></tr>
            <tr><td style="padding: 4px 0;"><strong>5.</strong> <strong>Condolence guestbook</strong> &mdash; Each memorial page has a place for community members to leave messages for the family.</td></tr>
        </table>

        <p style="margin: 0 0 18px 0;"><strong style="color: #3E2723;">Free. No accounts. No ads.</strong> Neshama exists to serve the community.</p>

        <p style="margin: 0 0 18px 0;">I think families at {org} would find this useful &mdash; both when they experience a loss and when they want to support someone who is grieving. It's the kind of resource that's most helpful when people know about it before they need it.</p>

        <p style="margin: 0 0 18px 0;">If you think it's valuable, any of these would make a real difference:</p>

        <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 0 0 20px 12px; font-family: 'Crimson Pro', Georgia, serif; font-size: 15px; line-height: 1.8; color: #3E2723;">
            <tr><td style="padding: 2px 0;">&bull; Share the link in your weekly email or newsletter</td></tr>
            <tr><td style="padding: 2px 0;">&bull; Mention it to your chesed or bikur cholim committee</td></tr>
            <tr><td style="padding: 2px 0;">&bull; Add it to your list of community resources</td></tr>
        </table>

        <p style="margin: 0 0 24px 0;">I've attached a one-page overview. You can also see the site here:</p>

        <!-- CTA Button -->
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 0 0 28px 0;">
        <tr><td style="background-color: #D2691E; border-radius: 4px;">
            <a href="https://neshama.ca/demo" style="display: inline-block; padding: 13px 30px; font-family: 'Crimson Pro', Georgia, serif; font-size: 15px; color: #ffffff; text-decoration: none; letter-spacing: 0.02em;">See Neshama in action</a>
        </td></tr>
        </table>

        <p style="margin: 0 0 18px 0;">Happy to answer any questions. I built this because I saw how much families struggle to coordinate during a loss, and I want it to be as useful as possible.</p>

        <p style="margin: 0 0 4px 0;">Warm regards,</p>
        <p style="margin: 0 0 0 0;"><strong>Erin Kofman</strong></p>
        <p style="margin: 0; font-size: 14px; color: #5c534a;">
            <a href="https://neshama.ca" style="color: #D2691E;">neshama.ca</a> &middot;
            <a href="mailto:contact@neshama.ca" style="color: #D2691E;">contact@neshama.ca</a>
        </p>

    </td></tr>

    <!-- Newsletter blurb box -->
    <tr><td style="padding: 0 36px 24px 36px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #FFF8F0; border-radius: 4px; border: 1px solid #e8e0d8;">
        <tr><td style="padding: 18px 22px; font-family: 'Crimson Pro', Georgia, serif; font-size: 14px; line-height: 1.65; color: #5c534a;">
            <p style="margin: 0 0 8px 0;"><strong style="color: #3E2723;">Ready-to-use blurb for your newsletter:</strong></p>
            <p style="margin: 0; font-style: italic;">"When a family in our community experiences a loss, neshama.ca brings together obituaries from local funeral homes, a meal coordination tool for shiva, 120+ local food and gift vendors, and yahrzeit reminders based on the Hebrew calendar. Free &mdash; no sign-up required. Visit neshama.ca to learn more."</p>
        </td></tr>
        </table>
    </td></tr>

    <!-- Warm footer -->
    <tr><td style="padding: 20px 36px; background-color: #FFF8F0; border-top: 1px solid #e8e0d8;">
        <p style="margin: 0; font-family: 'Crimson Pro', Georgia, serif; font-size: 13px; color: #9e9488; line-height: 1.6;">Neshama &middot; Toronto &amp; Montreal &middot; A community resource for Jewish families</p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def html_to_plain(html: str) -> str:
    """Rough HTML-to-plain-text conversion for the plain text part."""
    import re
    text = html
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'</tr>', '\n', text)
    text = re.sub(r'</td>', ' ', text)
    text = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', r'\2 (\1)', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&middot;', '-', text)
    text = re.sub(r'&mdash;|&ndash;', '-', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&bull;', '*', text)
    text = re.sub(r'&[a-z]+;', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ---------------------------------------------------------------------------
# SendGrid sender
# ---------------------------------------------------------------------------
def send_email(to_email: str, subject: str, html_body: str, dry_run: bool = True):
    """Send a single email via SendGrid. Returns True on success."""
    if dry_run:
        return True  # Dry run always "succeeds"

    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        print("  ERROR: SENDGRID_API_KEY environment variable not set.")
        print("  Set it with: export SENDGRID_API_KEY='your-key-here'")
        sys.exit(1)

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Mail, Email, To, Content, MimeType, Attachment,
        FileContent, FileName, FileType, Disposition,
    )

    plain_text = html_to_plain(html_body)

    message = Mail(
        from_email=Email(FROM_EMAIL, FROM_NAME),
        to_emails=To(to_email),
        subject=subject,
        plain_text_content=Content(MimeType.text, plain_text),
        html_content=Content(MimeType.html, html_body),
    )

    # Reply-To header
    from sendgrid.helpers.mail import ReplyTo
    message.reply_to = ReplyTo(REPLY_TO, "Erin Kofman")

    # Attach PDF one-pager if it exists
    if PDF_ATTACHMENT.exists():
        with open(PDF_ATTACHMENT, "rb") as f:
            pdf_data = base64.b64encode(f.read()).decode("utf-8")
        attachment = Attachment(
            FileContent(pdf_data),
            FileName("How-Neshama-Works.pdf"),
            FileType("application/pdf"),
            Disposition("attachment"),
        )
        message.attachment = attachment
    else:
        print(f"  WARNING: PDF not found at {PDF_ATTACHMENT} — sending without attachment")

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        if response.status_code in (200, 201, 202):
            return True
        else:
            print(f"  SendGrid returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"  SendGrid error: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Neshama Bulk Outreach Email Sender",
        epilog="DRY RUN by default. Pass --send to actually deliver emails.",
    )
    parser.add_argument(
        "--type", required=True, choices=["vendor", "synagogue"],
        help="Contact type to email",
    )
    parser.add_argument(
        "--send", action="store_true", default=False,
        help="Actually send emails (default is dry run)",
    )
    parser.add_argument(
        "--to", type=str, default=None,
        help="Send to a single email address only (for testing)",
    )
    parser.add_argument(
        "--csv", type=str, default=None,
        help="Path to contacts CSV (default: outreach-contacts.csv)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv) if args.csv else CONTACTS_CSV
    if not csv_path.exists():
        print(f"ERROR: Contacts file not found: {csv_path}")
        sys.exit(1)

    # Load contacts
    contacts = load_contacts(csv_path, args.type, args.to)
    if not contacts:
        print(f"No {args.type} contacts found in {csv_path}")
        sys.exit(0)

    # Load outreach log
    log_data = load_log(OUTREACH_LOG)

    # Mode banner
    if args.send:
        print("=" * 60)
        print("  LIVE MODE — EMAILS WILL BE SENT VIA SENDGRID")
        print("=" * 60)
        # Safety confirmation
        print(f"\n  Type: {args.type}")
        print(f"  Contacts: {len(contacts)}")
        if args.to:
            print(f"  Single recipient: {args.to}")
        print(f"  From: {FROM_EMAIL}")
        print()
        confirm = input("  Type 'yes' to confirm sending: ").strip().lower()
        if confirm != "yes":
            print("  Aborted.")
            sys.exit(0)
        print()
    else:
        print("=" * 60)
        print("  DRY RUN — nothing will be sent")
        print("  Add --send to actually deliver emails")
        print("=" * 60)
        print()

    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for i, contact in enumerate(contacts, 1):
        email = contact["email"].strip()
        name = contact.get("name", "").strip()
        org = contact.get("organization", "").strip()
        ctype = contact.get("type", args.type).strip()

        # Dedup check
        if already_sent(log_data, email, ctype):
            print(f"  [{i}/{len(contacts)}] SKIP (already sent): {email} ({org})")
            skipped_count += 1
            continue

        # Build email content
        if ctype == "vendor":
            subject = vendor_subject(org)
            html = vendor_html(name, org)
        else:
            subject = synagogue_subject(org)
            html = synagogue_html(name, org)

        if args.send:
            print(f"  [{i}/{len(contacts)}] SENDING: {email} ({org})")
            print(f"           Subject: {subject}")
            success = send_email(email, subject, html, dry_run=False)
            if success:
                record_sent(log_data, email, ctype, org, subject)
                save_log(OUTREACH_LOG, log_data)
                sent_count += 1
                print(f"           Sent successfully.")
            else:
                failed_count += 1
                print(f"           FAILED to send.")

            # Rate limit between sends
            if i < len(contacts):
                time.sleep(RATE_LIMIT_SECONDS)
        else:
            print(f"  [{i}/{len(contacts)}] WOULD SEND: {email} ({org})")
            print(f"           Subject: {subject}")
            sent_count += 1

    # Summary
    print()
    print("-" * 60)
    mode = "SENT" if args.send else "WOULD SEND"
    print(f"  {mode}: {sent_count}")
    print(f"  Skipped (already in log): {skipped_count}")
    if args.send:
        print(f"  Failed: {failed_count}")
    print(f"  Log: {OUTREACH_LOG}")
    print("-" * 60)


if __name__ == "__main__":
    main()
