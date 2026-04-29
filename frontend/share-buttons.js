/**
 * share-buttons.js — single source of truth for share UI across Neshama.
 *
 * Renders 4 share buttons (Copy, WhatsApp, Email, Text) into any element with
 * `data-share-target="true"`. Reads share content from data attributes.
 *
 * Usage:
 *   <div data-share-target="true"
 *        data-share-url="https://neshama.ca/shiva/abc"
 *        data-share-family="The Cohen Family"></div>
 *   <script src="/share-buttons.js"></script>
 *
 * Optional data attributes:
 *   data-share-short-text  — used for SMS + WhatsApp (defaults to a short
 *                            "{family} sitting shiva — meal coordination" message)
 *   data-share-email-subject — used for email subject line
 *   data-share-email-body   — used for email body (longer message)
 *
 * The component is intentionally framework-free, vanilla JS, no build step.
 * Each surface that needs share buttons just drops in the target div + script.
 */
(function () {
    'use strict';

    // Render all share targets on the page on DOMContentLoaded.
    function init() {
        var targets = document.querySelectorAll('[data-share-target="true"]');
        targets.forEach(renderShareBar);
    }

    function addUtm(url, source) {
        var sep = url.indexOf('?') >= 0 ? '&' : '?';
        return url + sep + 'utm_source=' + encodeURIComponent(source) + '&utm_medium=share';
    }

    function defaultShortText(family, url) {
        var f = family ? ('The ' + family.replace(/^The\s+/i, '') + ' family') : 'The family';
        return f + ' is sitting shiva. Friends are organizing meals — sign up to bring one: ' + url;
    }

    function defaultEmailSubject(family) {
        var f = family ? family.replace(/^The\s+/i, '') : 'family';
        return 'Shiva meals for the ' + f + ' family — sign up to help';
    }

    function defaultEmailBody(family, url) {
        var f = family ? ('The ' + family.replace(/^The\s+/i, '') + ' family') : 'The family';
        return f + ' is sitting shiva. Friends are organizing meals so the family is taken care of.\n\n' +
               'If you can sign up to bring a meal, you can do so here:\n' + url + '\n\n' +
               'Every meal makes a difference. Thank you for being part of this community.';
    }

    function renderShareBar(target) {
        // Don't double-render if already initialized
        if (target.dataset.shareInitialized === 'true') return;
        target.dataset.shareInitialized = 'true';

        var url = target.getAttribute('data-share-url') || window.location.href;
        var family = target.getAttribute('data-share-family') || '';
        var customShort = target.getAttribute('data-share-short-text');
        var shortText = customShort || defaultShortText(family, url);                       // SMS keeps current behavior
        var waText    = customShort || defaultShortText(family, addUtm(url, 'whatsapp'));   // WhatsApp gets UTM
        var emailSubject = target.getAttribute('data-share-email-subject') || defaultEmailSubject(family);
        var emailBody = target.getAttribute('data-share-email-body') || defaultEmailBody(family, url);

        var waUrl = 'https://wa.me/?text=' + encodeURIComponent(waText);
        var emailUrl = 'mailto:?subject=' + encodeURIComponent(emailSubject) + '&body=' + encodeURIComponent(emailBody);
        var smsUrl = 'sms:?&body=' + encodeURIComponent(shortText);

        // Inject styles once per page
        ensureStyles();

        target.classList.add('neshama-share-bar');
        target.innerHTML = '' +
            // 1. Copy
            '<button type="button" class="neshama-share-btn neshama-share-copy" data-action="copy" aria-label="Copy link">' +
                iconCopy() +
                '<span class="neshama-share-label">Copy link</span>' +
            '</button>' +
            // 2. WhatsApp
            '<a class="neshama-share-btn neshama-share-whatsapp" href="' + escapeAttr(waUrl) + '" target="_blank" rel="noopener noreferrer" aria-label="Share via WhatsApp">' +
                iconWhatsapp() +
                '<span class="neshama-share-label">WhatsApp</span>' +
            '</a>' +
            // 3. Email
            '<a class="neshama-share-btn neshama-share-email" href="' + escapeAttr(emailUrl) + '" aria-label="Share via Email">' +
                iconEmail() +
                '<span class="neshama-share-label">Email</span>' +
            '</a>' +
            // 4. Text / SMS
            '<a class="neshama-share-btn neshama-share-sms" href="' + escapeAttr(smsUrl) + '" aria-label="Share via Text">' +
                iconSms() +
                '<span class="neshama-share-label">Text</span>' +
            '</a>';

        // Wire up the Copy button
        var copyBtn = target.querySelector('[data-action="copy"]');
        copyBtn.addEventListener('click', function () {
            copyToClipboard(url, copyBtn);
        });
    }

    function copyToClipboard(text, btn) {
        function showCopied() {
            var label = btn.querySelector('.neshama-share-label');
            if (!label) return;
            var orig = label.textContent;
            label.textContent = 'Copied!';
            btn.classList.add('neshama-share-copied');
            setTimeout(function () {
                label.textContent = orig;
                btn.classList.remove('neshama-share-copied');
            }, 2000);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(showCopied).catch(fallbackCopy);
        } else {
            fallbackCopy();
        }

        function fallbackCopy() {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand('copy'); } catch (e) {}
            document.body.removeChild(ta);
            showCopied();
        }
    }

    function escapeAttr(s) {
        return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function ensureStyles() {
        if (document.getElementById('neshama-share-buttons-styles')) return;
        var style = document.createElement('style');
        style.id = 'neshama-share-buttons-styles';
        style.textContent = '' +
            '.neshama-share-bar {' +
                'display: flex;' +
                'gap: 0.6rem;' +
                'flex-wrap: wrap;' +
                'justify-content: center;' +
                'align-items: center;' +
                'margin: 0;' +
            '}' +
            '.neshama-share-btn {' +
                'display: inline-flex;' +
                'align-items: center;' +
                'gap: 0.5rem;' +
                'padding: 0.65rem 1.15rem;' +
                'border-radius: 2rem;' +
                'border: none;' +
                'font-family: \'Source Serif 4\', Georgia, serif;' +
                'font-size: 0.95rem;' +
                'font-weight: 600;' +
                'cursor: pointer;' +
                'text-decoration: none;' +
                'transition: transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;' +
                'min-height: 44px;' +
                'box-sizing: border-box;' +
                'white-space: nowrap;' +
            '}' +
            '.neshama-share-btn:hover {' +
                'transform: translateY(-1px);' +
                'box-shadow: 0 4px 10px rgba(62, 39, 35, 0.12);' +
                'text-decoration: none;' +
            '}' +
            '.neshama-share-btn:focus-visible {' +
                'outline: 3px solid #C2621A;' +
                'outline-offset: 2px;' +
            '}' +
            '.neshama-share-btn svg {' +
                'width: 18px;' +
                'height: 18px;' +
                'flex-shrink: 0;' +
            '}' +
            // Copy — terracotta primary
            '.neshama-share-copy {' +
                'background: #C2621A;' +
                'color: white;' +
            '}' +
            '.neshama-share-copy:hover { background: #A8541A; color: white; }' +
            '.neshama-share-copied { background: #3D6B40 !important; color: white !important; }' +
            // WhatsApp — brand green
            '.neshama-share-whatsapp {' +
                'background: #25D366;' +
                'color: white;' +
            '}' +
            '.neshama-share-whatsapp:hover { background: #1FB855; color: white; }' +
            // Email — warm dark
            '.neshama-share-email {' +
                'background: #3E2723;' +
                'color: white;' +
            '}' +
            '.neshama-share-email:hover { background: #2C1B17; color: white; }' +
            // Text / SMS — sage
            '.neshama-share-sms {' +
                'background: #4A5E4D;' +
                'color: white;' +
            '}' +
            '.neshama-share-sms:hover { background: #3A4D3D; color: white; }' +
            '@media (max-width: 480px) {' +
                '.neshama-share-btn { padding: 0.6rem 1rem; font-size: 0.9rem; }' +
                '.neshama-share-label { display: inline; }' +
            '}';
        document.head.appendChild(style);
    }

    // Inline SVG icons (vanilla strings to avoid template literal issues)
    function iconCopy() {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>' +
            '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>' +
        '</svg>';
    }
    function iconWhatsapp() {
        return '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">' +
            '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413"/>' +
        '</svg>';
    }
    function iconEmail() {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<rect x="2" y="4" width="20" height="16" rx="2"/>' +
            '<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>' +
        '</svg>';
    }
    function iconSms() {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>' +
        '</svg>';
    }

    // Public API: re-render share targets (e.g., after dynamic data updates)
    window.NeshamaShare = {
        render: init,
        renderInto: function (selector) {
            document.querySelectorAll(selector).forEach(function (el) {
                if (el.matches('[data-share-target="true"]')) {
                    el.dataset.shareInitialized = 'false';
                    renderShareBar(el);
                }
            });
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
