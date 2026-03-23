/**
 * Footer Subscribe Bar — auto-injects on every page that has a <footer>.
 * Skips pages that already have an inline subscribe form (#inlineSubscribe).
 * Uses the same /api/subscribe endpoint as the popup and inline forms.
 */
(function() {
    'use strict';

    // Don't inject if page already has the full inline subscribe form
    if (document.getElementById('inlineSubscribe')) return;

    // Inject CSS
    var style = document.createElement('style');
    style.textContent =
        '.footer-subscribe { max-width: 600px; margin: 2rem auto 0; padding: 1.5rem 1.5rem 1.25rem; text-align: center; border-top: 1px solid #e8e0d8; }' +
        '.footer-subscribe-text { font-family: "Cormorant Garamond", Georgia, serif; font-size: 1.4rem; font-weight: 500; color: #3E2723; margin: 0 0 0.75rem; }' +
        '.footer-subscribe-form { display: flex; gap: 0.5rem; justify-content: center; align-items: center; flex-wrap: wrap; margin-bottom: 0.5rem; }' +
        '.footer-subscribe-form input[type="email"] { font-family: "Crimson Pro", "Source Serif 4", Georgia, serif; font-size: 1.05rem; padding: 0.6rem 1rem; border: 1px solid #d4c8b8; border-radius: 0.4rem; background: #fff; color: #3E2723; width: 260px; max-width: 100%; outline: none; }' +
        '.footer-subscribe-form input[type="email"]:focus { border-color: #D2691E; }' +
        '.footer-subscribe-form button { font-family: "Crimson Pro", "Source Serif 4", Georgia, serif; font-size: 1.05rem; font-weight: 500; padding: 0.6rem 1.25rem; background: #D2691E; color: #fff; border: none; border-radius: 0.4rem; cursor: pointer; white-space: nowrap; }' +
        '.footer-subscribe-form button:hover { background: #b8571a; }' +
        '.footer-subscribe-form button:disabled { opacity: 0.7; cursor: not-allowed; }' +
        '.footer-subscribe-fine { font-family: "Crimson Pro", "Source Serif 4", Georgia, serif; font-size: 0.9rem; color: #9e9488; margin: 0; }' +
        '.footer-subscribe-error { font-size: 0.9rem; color: #d32f2f; display: none; margin: 0.5rem 0 0; }' +
        '.footer-subscribe-success { font-family: "Crimson Pro", "Source Serif 4", Georgia, serif; font-size: 1rem; color: #3E2723; display: none; margin: 0.5rem 0 0; }' +
        '@media (max-width: 480px) { .footer-subscribe-form input[type="email"] { width: 100%; } .footer-subscribe-form button { width: 100%; } }';
    document.head.appendChild(style);

    // Don't inject on unsubscribe page
    if (window.location.pathname.indexOf('/unsubscribe') !== -1) return;

    var footer = document.querySelector('footer');
    if (!footer) return;

    // Create the subscribe bar
    var bar = document.createElement('section');
    bar.className = 'footer-subscribe';
    bar.setAttribute('aria-label', 'Email subscription');
    bar.innerHTML =
        '<div class="footer-subscribe-inner">' +
            '<p class="footer-subscribe-text">Stay connected to our community</p>' +
            '<form class="footer-subscribe-form" id="footerSubscribeForm" autocomplete="on">' +
                '<input type="email" id="footerEmailInput" placeholder="Your email address" required aria-required="true" aria-label="Email address" autocomplete="email">' +
                '<button type="submit" id="footerSubscribeBtn">Subscribe</button>' +
            '</form>' +
            '<p class="footer-subscribe-fine">Daily obituary updates for Toronto &amp; Montreal. Free. Unsubscribe anytime.</p>' +
            '<p class="footer-subscribe-error" id="footerSubscribeError"></p>' +
            '<p class="footer-subscribe-success" id="footerSubscribeSuccess"></p>' +
        '</div>';

    // Insert before footer
    footer.parentNode.insertBefore(bar, footer);

    // Handle submit
    var form = document.getElementById('footerSubscribeForm');
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var input = document.getElementById('footerEmailInput');
        var btn = document.getElementById('footerSubscribeBtn');
        var errEl = document.getElementById('footerSubscribeError');
        var successEl = document.getElementById('footerSubscribeSuccess');
        var email = input.value.trim();

        if (!email) return;

        btn.disabled = true;
        btn.textContent = 'Subscribing...';
        errEl.textContent = '';
        errEl.style.display = 'none';
        successEl.style.display = 'none';

        fetch('/api/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: email,
                frequency: 'daily',
                locations: 'toronto,montreal',
                consent: true
            })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status === 'success' || data.status === 'already_subscribed' || data.status === 'pending_confirmation') {
                form.style.display = 'none';
                successEl.textContent = 'Thank you. Check your inbox for a confirmation email from updates@neshama.ca.';
                successEl.style.display = 'block';
                document.querySelector('.footer-subscribe-fine').style.display = 'none';
            } else {
                errEl.textContent = data.message || 'Something went wrong. Please try again.';
                errEl.style.display = 'block';
                btn.disabled = false;
                btn.textContent = 'Subscribe';
            }
        })
        .catch(function() {
            errEl.textContent = 'Connection error. Please try again.';
            errEl.style.display = 'block';
            btn.disabled = false;
            btn.textContent = 'Subscribe';
        });
    });
})();
