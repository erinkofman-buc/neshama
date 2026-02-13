// Neshama Frontend Application v2.0
// Handles data loading, filtering, search, share, tributes, and UI interactions

class NeshamaApp {
    constructor() {
        this.apiBase = '/api';
        this.currentTab = 'today';
        this.currentCity = localStorage.getItem('neshama_city') || 'all';
        this.searchQuery = '';
        this.allObituaries = [];
        this.displayedCount = 5;
        this.tributeCounts = {};
        this.scrollObserver = null;
        this.init();
    }

    init() {
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', (e) => this.handleTabChange(e));
        });

        const searchBox = document.getElementById('searchBox');
        if (searchBox) {
            searchBox.addEventListener('input', (e) => this.handleSearch(e));
        }

        // City filter buttons
        document.querySelectorAll('.city-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleCityChange(e));
        });
        // Set active city on load
        this.setCityActive(this.currentCity);

        this.setupScrollObserver();
        this.loadData();
    }

    setupScrollObserver() {
        this.scrollObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    this.scrollObserver.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });
    }

    observeCards() {
        document.querySelectorAll('.obituary-card').forEach(card => {
            this.scrollObserver.observe(card);
        });
    }

    async loadData() {
        const feed = document.getElementById('feed');
        feed.innerHTML = `
            <div class="loading">
                <div class="loading-spinner"></div>
                <p>Loading obituaries...</p>
            </div>
        `;

        try {
            const response = await fetch(this.apiBase + '/obituaries');
            const data = await response.json();

            if (data.status === 'success') {
                this.allObituaries = data.data;
                await this.loadTributeCounts();
                this.render();
            } else {
                this.showError('Failed to load obituaries. Please try again.');
            }
        } catch (error) {
            this.showError('Unable to connect. Please check your internet connection and try again.');
        }
    }

    async loadTributeCounts() {
        try {
            const response = await fetch(this.apiBase + '/tributes/counts');
            const data = await response.json();
            if (data && data.status === 'success' && data.data) {
                this.tributeCounts = data.data;
            }
        } catch (error) {
            // Tribute counts are non-critical; silently continue
        }
    }

    handleCityChange(e) {
        this.currentCity = e.target.dataset.city;
        localStorage.setItem('neshama_city', this.currentCity);
        this.setCityActive(this.currentCity);
        this.displayedCount = 5;
        this.render();
    }

    setCityActive(city) {
        document.querySelectorAll('.city-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.city === city);
        });
    }

    handleTabChange(e) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
        this.currentTab = e.target.dataset.tab;
        this.displayedCount = 5;
        this.render();
    }

    handleSearch(e) {
        this.searchQuery = e.target.value.toLowerCase().trim();
        this.displayedCount = 5;
        this.render();
    }

    filterObituaries() {
        let filtered = [...this.allObituaries];

        // City filter
        if (this.currentCity && this.currentCity !== 'all') {
            filtered = filtered.filter(obit => (obit.city || 'Toronto') === this.currentCity);
        }

        if (this.searchQuery) {
            filtered = filtered.filter(obit => {
                const searchableText = (obit.deceased_name + ' ' + (obit.hebrew_name || '')).toLowerCase();
                return searchableText.includes(this.searchQuery);
            });
        }

        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
        const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

        if (this.currentTab === 'today') {
            filtered = filtered.filter(obit => new Date(obit.last_updated) >= today);
        } else if (this.currentTab === 'week') {
            filtered = filtered.filter(obit => new Date(obit.last_updated) >= weekAgo);
        } else if (this.currentTab === 'month') {
            filtered = filtered.filter(obit => new Date(obit.last_updated) >= monthAgo);
        }

        return filtered;
    }

    highlightText(text, query) {
        if (!query || !text) return text;
        const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp('(' + escaped + ')', 'gi');
        return text.replace(regex, '<mark class="search-highlight">$1</mark>');
    }

    getInitials(name) {
        if (!name) return '';
        const parts = name.trim().split(/\s+/);
        if (parts.length === 1) {
            return parts[0].charAt(0).toUpperCase();
        }
        return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
    }

    getMemorialUrl(obituaryId) {
        return '/memorial/' + obituaryId;
    }

    getShareUrl(obituaryId) {
        return 'https://neshama.ca/memorial/' + obituaryId;
    }

    svgIconFuneral() {
        return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4M12 6c0 0-3 2-3 5v9h6v-9c0-3-3-5-3-5zM6 22h12M9 13h6"/></svg>';
    }

    svgIconShiva() {
        return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M3 10l9-7 9 7M5 10v11M19 10v11M9 21v-6h6v6"/></svg>';
    }

    svgIconLivestream() {
        return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>';
    }

    svgIconHeart() {
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>';
    }

    render() {
        const feed = document.getElementById('feed');
        const loadMoreBtn = document.getElementById('loadMore');
        const filtered = this.filterObituaries();

        if (filtered.length === 0) {
            feed.innerHTML = this.renderEmptyState();
            loadMoreBtn.style.display = 'none';
            return;
        }

        const toDisplay = filtered.slice(0, this.displayedCount);
        feed.innerHTML = toDisplay.map(obit => this.renderCard(obit)).join('');

        if (filtered.length > this.displayedCount) {
            loadMoreBtn.style.display = 'block';
            loadMoreBtn.querySelector('button').textContent =
                'Load More (' + (filtered.length - this.displayedCount) + ' remaining)';
        } else {
            loadMoreBtn.style.display = 'none';
        }

        // Attach event listeners for card clicks
        document.querySelectorAll('.obituary-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (!e.target.closest('.btn') && !e.target.closest('.share-menu') && !e.target.closest('.memorial-link')) {
                    this.handleCardClick(card.dataset.id);
                }
            });
        });

        // Share toggle listeners
        document.querySelectorAll('.share-toggle').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleShareMenu(btn);
            });
        });

        // Share option listeners
        document.querySelectorAll('.share-option').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.closest('.obituary-card').dataset.id;
                this.handleShareAction(id, btn.dataset.action);
            });
        });

        // Observe cards for scroll animation
        this.observeCards();
    }

    renderCard(obit) {
        const timeAgo = this.getTimeAgo(obit.last_updated);
        const preview = this.getPreview(obit.obituary_text);
        const sourceInitial = obit.source ? obit.source.charAt(0).toUpperCase() : '?';
        const initials = this.getInitials(obit.deceased_name);
        const tributeCount = this.tributeCounts[obit.id] || 0;
        const memorialUrl = this.getMemorialUrl(obit.id);

        const name = this.searchQuery
            ? this.highlightText(obit.deceased_name, this.searchQuery)
            : obit.deceased_name;

        const hebrewName = this.searchQuery && obit.hebrew_name
            ? this.highlightText(obit.hebrew_name, this.searchQuery)
            : obit.hebrew_name;

        // Photo area: circular photo if available, otherwise initials circle
        let photoArea = '';
        if (obit.photo_url) {
            photoArea = '<div class="card-photo-circle"><img src="' + this.escapeAttr(obit.photo_url) + '" alt="' + this.escapeAttr(obit.deceased_name) + '" width="140" height="140" loading="lazy" onerror="this.parentElement.innerHTML=\'<span class=card-initials>' + this.escapeHtml(initials) + '</span>\';this.parentElement.classList.add(\'no-photo\')"></div>';
        } else {
            photoArea = '<div class="card-photo-circle no-photo"><span class="card-initials">' + this.escapeHtml(initials) + '</span></div>';
        }

        // Funeral detail row
        let funeralRow = '';
        if (obit.funeral_datetime) {
            funeralRow = '' +
                '<div class="detail-row">' +
                    '<span class="detail-icon">' + this.svgIconFuneral() + '</span>' +
                    '<div class="detail-content">' +
                        '<span class="detail-label">Funeral</span>' +
                        this.escapeHtml(obit.funeral_datetime) +
                        (obit.funeral_location ? '<br>' + this.escapeHtml(obit.funeral_location) : '') +
                    '</div>' +
                '</div>';
        }

        // Shiva detail row
        let shivaRow = '';
        if (obit.shiva_info) {
            shivaRow = '' +
                '<div class="detail-row">' +
                    '<span class="detail-icon">' + this.svgIconShiva() + '</span>' +
                    '<div class="detail-content">' +
                        '<span class="detail-label">Shiva</span>' +
                        this.escapeHtml(obit.shiva_info) +
                    '</div>' +
                '</div>';
        }

        // Livestream detail row
        let livestreamRow = '';
        if (obit.livestream_url || obit.livestream_available) {
            livestreamRow = '' +
                '<div class="detail-row livestream-row">' +
                    '<span class="detail-icon">' + this.svgIconLivestream() + '</span>' +
                    '<div class="detail-content">' +
                        '<span class="detail-label">Livestream</span>' +
                        (obit.livestream_url
                            ? '<a href="' + this.escapeAttr(obit.livestream_url) + '" target="_blank" rel="noopener" onclick="event.stopPropagation()">Watch livestream</a>'
                            : 'Available') +
                    '</div>' +
                '</div>';
        }

        // Obituary preview
        let previewSection = '';
        if (preview) {
            previewSection = '' +
                '<div class="obituary-preview">' +
                    this.escapeHtml(preview) +
                    ' <span class="read-more">Read more \u2192</span>' +
                '</div>';
        }

        // Tribute count badge
        let tributeBadge = '' +
            '<div class="tribute-count" data-id="' + obit.id + '">' +
                this.svgIconHeart() +
                ' <span>' + tributeCount + ' tribute' + (tributeCount !== 1 ? 's' : '') + '</span>' +
            '</div>';

        return '' +
            '<div class="obituary-card" data-id="' + obit.id + '">' +

                '<div class="card-header">' +
                    '<div class="source-icon">' + this.escapeHtml(sourceInitial) + '</div>' +
                    '<span class="source-name">' + this.escapeHtml(obit.source) + '</span>' +
                    '<span class="timestamp">' + timeAgo + '</span>' +
                '</div>' +

                photoArea +

                '<div class="card-body">' +
                    '<p class="in-memory-label">In Loving Memory</p>' +
                    '<h2 class="deceased-name">' + name + '</h2>' +
                    (hebrewName ? '<div class="hebrew-name">' + hebrewName + '</div>' : '') +

                    funeralRow +
                    shivaRow +
                    livestreamRow +
                    previewSection +
                    tributeBadge +
                '</div>' +

                '<div class="card-footer">' +
                    '<a href="' + memorialUrl + '" class="btn btn-primary memorial-link" onclick="event.stopPropagation()">' +
                        'View Memorial' +
                    '</a>' +
                    '<div class="share-wrapper">' +
                        '<button class="btn btn-secondary share-toggle" aria-label="Share">' +
                            'Share \u2197' +
                        '</button>' +
                        '<div class="share-menu">' +
                            '<button class="share-option" data-action="copy" title="Copy link">\ud83d\udd17 Copy Link</button>' +
                            '<button class="share-option" data-action="whatsapp" title="Share via WhatsApp">\ud83d\udcac WhatsApp</button>' +
                            '<button class="share-option" data-action="email" title="Share via email">\u2709\ufe0f Email</button>' +
                        '</div>' +
                    '</div>' +
                '</div>' +

            '</div>';
    }

    renderEmptyState() {
        if (this.searchQuery) {
            return '\
                <div class="empty-state">\
                    <div class="empty-state-icon">\ud83d\udd0d</div>\
                    <p class="empty-state-title">No results for "' + this.escapeHtml(this.searchQuery) + '"</p>\
                    <p class="empty-state-hint">Try a different spelling or check the other time tabs above.</p>\
                </div>';
        }
        if (this.currentTab === 'today') {
            return '\
                <div class="empty-state">\
                    <div class="empty-state-icon">\ud83d\udd4a\ufe0f</div>\
                    <p class="empty-state-title">No services scheduled for today</p>\
                    <p class="empty-state-hint">Check <strong>"This Week"</strong> or <strong>"This Month"</strong> for recent obituaries.</p>\
                </div>';
        }
        return '\
            <div class="empty-state">\
                <div class="empty-state-icon">\ud83d\udd4a\ufe0f</div>\
                <p>No obituaries found for this period.</p>\
            </div>';
    }

    escapeHtml(text) {
        if (!text) return '';
        var d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    escapeAttr(text) {
        if (!text) return '';
        return text
            .replace(/&/g, '&amp;')
            .replace(/'/g, '&#39;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    getPreview(text) {
        if (!text) return '';
        var preview = text.substring(0, 200);
        var lastSpace = preview.lastIndexOf(' ');
        if (lastSpace > 100) {
            return preview.substring(0, lastSpace) + '...';
        }
        return preview + '...';
    }

    getTimeAgo(dateString) {
        var date = new Date(dateString);
        var now = new Date();
        var diffMs = now - date;
        var diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        var diffDays = Math.floor(diffHours / 24);

        if (diffHours < 1) return 'Just now';
        if (diffHours < 24) return diffHours + (diffHours === 1 ? ' hour' : ' hours') + ' ago';
        if (diffDays < 7) return diffDays + (diffDays === 1 ? ' day' : ' days') + ' ago';

        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    handleCardClick(id) {
        // V2.0: navigate to memorial page instead of external condolence URL
        window.location.href = this.getMemorialUrl(id);
    }

    toggleShareMenu(btn) {
        var menu = btn.nextElementSibling;
        var wasVisible = menu.classList.contains('active');

        // Close all share menus
        document.querySelectorAll('.share-menu.active').forEach(function(m) {
            m.classList.remove('active');
        });

        if (!wasVisible) {
            menu.classList.add('active');
        }
    }

    handleShareAction(id, action) {
        var obit = this.allObituaries.find(function(o) { return o.id === id; });
        if (!obit) return;

        // V2.0: share links point to memorial page on neshama.ca
        var url = this.getShareUrl(id);
        var text = 'In memory of ' + obit.deceased_name + ' - neshama.ca';

        if (action === 'copy') {
            navigator.clipboard.writeText(url).then(function() {
                var btn = document.querySelector('.obituary-card[data-id="' + id + '"] .share-option[data-action="copy"]');
                if (btn) {
                    var original = btn.textContent;
                    btn.textContent = '\u2705 Copied!';
                    setTimeout(function() { btn.textContent = original; }, 2000);
                }
            });
        } else if (action === 'whatsapp') {
            window.open('https://wa.me/?text=' + encodeURIComponent(text + '\n' + url), '_blank');
        } else if (action === 'email') {
            window.location.href = 'mailto:?subject=' + encodeURIComponent(text) + '&body=' + encodeURIComponent('I wanted to share this with you:\n\n' + text + '\n' + url + '\n\nFrom Neshama - neshama.ca');
        }

        // Close menu
        document.querySelectorAll('.share-menu.active').forEach(function(m) {
            m.classList.remove('active');
        });
    }

    showError(message) {
        var feed = document.getElementById('feed');
        feed.innerHTML = '\
            <div class="empty-state">\
                <div class="empty-state-icon">\u26a0\ufe0f</div>\
                <p>' + message + '</p>\
                <button onclick="window.app.loadData()" class="btn btn-secondary" style="margin-top:1rem;display:inline-block;">Try Again</button>\
            </div>';
    }
}

// Load more functionality
function loadMore() {
    if (window.app) {
        window.app.displayedCount += 5;
        window.app.render();
    }
}

// Close share menus when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.share-wrapper')) {
        document.querySelectorAll('.share-menu.active').forEach(function(m) {
            m.classList.remove('active');
        });
    }
});

// Initialize app when page loads
document.addEventListener('DOMContentLoaded', function() {
    window.app = new NeshamaApp();
});
