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
                this.loadScraperStatus();
                // Refresh freshness indicator every 60 seconds
                setInterval(() => this.loadScraperStatus(), 60000);
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

    filterByPeriod(list, tab) {
        var now = new Date();
        var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        var weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
        var monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

        if (tab === 'today') {
            return list.filter(function(obit) { return new Date(obit.first_seen) >= today; });
        } else if (tab === 'week') {
            return list.filter(function(obit) { return new Date(obit.first_seen) >= weekAgo; });
        } else if (tab === 'month') {
            return list.filter(function(obit) { return new Date(obit.first_seen) >= monthAgo; });
        }
        return list;
    }

    filterObituaries() {
        var filtered = this.allObituaries.slice();

        // City filter
        if (this.currentCity && this.currentCity !== 'all') {
            filtered = filtered.filter(function(obit) { return (obit.city || 'Toronto') === this.currentCity; }.bind(this));
        }

        if (this.searchQuery) {
            var query = this.searchQuery;
            filtered = filtered.filter(function(obit) {
                var searchableText = (obit.deceased_name + ' ' + (obit.hebrew_name || '')).toLowerCase();
                return searchableText.includes(query);
            });
        }

        // Apply period filter with auto-fallback
        var periodFiltered = this.filterByPeriod(filtered, this.currentTab);

        // Auto-fallback: if current period is empty but broader periods have data, escalate
        if (periodFiltered.length === 0 && filtered.length > 0 && !this.searchQuery) {
            var periods = ['today', 'week', 'month'];
            var currentIdx = periods.indexOf(this.currentTab);
            if (currentIdx >= 0) {
                for (var i = currentIdx + 1; i < periods.length; i++) {
                    periodFiltered = this.filterByPeriod(filtered, periods[i]);
                    if (periodFiltered.length > 0) {
                        this.currentTab = periods[i];
                        document.querySelectorAll('.tab').forEach(function(t) {
                            t.classList.toggle('active', t.dataset.tab === periods[i]);
                        });
                        break;
                    }
                }
                // If all periods empty, show everything
                if (periodFiltered.length === 0) {
                    periodFiltered = filtered;
                    this.currentTab = 'month';
                    document.querySelectorAll('.tab').forEach(function(t) {
                        t.classList.toggle('active', t.dataset.tab === 'month');
                    });
                }
            }
        }

        return periodFiltered;
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
                if (!e.target.closest('.card-link')) {
                    this.handleCardClick(card.dataset.id);
                }
            });
        });

        // Observe cards for scroll animation
        this.observeCards();
    }

    renderCard(obit) {
        const timeAgo = this.getTimeAgo(obit.last_updated);
        const tributeCount = this.tributeCounts[obit.id] || 0;
        const memorialUrl = this.getMemorialUrl(obit.id);

        const name = this.searchQuery
            ? this.highlightText(obit.deceased_name, this.searchQuery)
            : obit.deceased_name;

        const hebrewName = this.searchQuery && obit.hebrew_name
            ? this.highlightText(obit.hebrew_name, this.searchQuery)
            : obit.hebrew_name;

        // Image area: rectangular photo or warm candle placeholder
        let imageArea = '';
        if (obit.photo_url) {
            imageArea = '<div class="card-image"><img src="' + this.escapeAttr(obit.photo_url) + '" alt="' + this.escapeAttr(obit.deceased_name) + '" loading="lazy" decoding="async" onerror="this.parentElement.innerHTML=\'<div class=card-placeholder>\ud83d\udd6f\ufe0f</div>\'"></div>';
        } else {
            imageArea = '<div class="card-image"><div class="card-placeholder">\ud83d\udd6f\ufe0f</div></div>';
        }

        // Funeral info line
        let funeralLine = '';
        if (obit.funeral_datetime) {
            funeralLine = '<p class="card-funeral">\ud83d\udd4a\ufe0f ' + this.escapeHtml(obit.funeral_datetime) +
                (obit.funeral_location ? ' \u00b7 ' + this.escapeHtml(obit.funeral_location) : '') + '</p>';
        }

        // Tribute count
        let tributeText = tributeCount > 0
            ? '<span class="card-tributes">' + this.svgIconHeart() + ' ' + tributeCount + '</span>'
            : '<span class="card-tributes"></span>';

        // Shiva badge
        let shivaBadge = '';
        if (obit.has_shiva) {
            shivaBadge = '<a href="/shiva/' + obit.id + '" class="card-shiva-badge" onclick="event.stopPropagation()" title="Active shiva support page">' + this.svgIconShiva() + ' Shiva</a>';
        }

        return '' +
            '<div class="obituary-card" data-id="' + obit.id + '">' +
                imageArea +
                '<div class="card-body">' +
                    '<div class="card-source">' + this.escapeHtml(obit.source) + ' \u00b7 ' + timeAgo + '</div>' +
                    '<div class="card-updated">Updated ' + this.formatTimestamp(obit.last_updated) + '</div>' +
                    '<h2 class="deceased-name">' + name + '</h2>' +
                    (hebrewName ? '<div class="hebrew-name">' + hebrewName + '</div>' : '') +
                    funeralLine +
                    '<div class="card-meta">' +
                        tributeText +
                        shivaBadge +
                        '<a href="' + memorialUrl + '" class="card-link" onclick="event.stopPropagation()">View Memorial \u2192</a>' +
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
                    <p class="empty-state-title">The community is at rest.</p>\
                    <p class="empty-state-hint">Check back soon, or browse <strong>"This Week"</strong> or <strong>"This Month"</strong> above.</p>\
                </div>';
        }
        return '\
            <div class="empty-state">\
                <div class="empty-state-icon">\ud83d\udd4a\ufe0f</div>\
                <p class="empty-state-title">The community is at rest.</p>\
                <p class="empty-state-hint">Check back soon.</p>\
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

    formatTimestamp(dateString) {
        var date = new Date(dateString);
        var now = new Date();
        var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        var yesterday = new Date(today.getTime() - 86400000);
        var timeStr = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

        if (date >= today) return 'Today at ' + timeStr;
        if (date >= yesterday) return 'Yesterday at ' + timeStr;
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' at ' + timeStr;
    }

    async loadScraperStatus() {
        try {
            var response = await fetch(this.apiBase + '/scraper-status');
            var data = await response.json();
            var bar = document.getElementById('freshnessBar');
            if (!bar || data.status !== 'success') return;

            var freshnessLabel = bar.querySelector('span:first-child');
            var lastChecked = document.getElementById('lastChecked');

            if (data.data.shabbat_mode) {
                if (freshnessLabel) freshnessLabel.textContent = 'Shabbat Shalom \u2014 updates resume Saturday night';
                if (lastChecked) lastChecked.textContent = '';
                bar.style.display = '';
                return;
            }

            if (freshnessLabel) freshnessLabel.textContent = 'Data refreshed every ' + data.data.interval_minutes + ' minutes';
            if (data.data.last_run && lastChecked) {
                var lastRun = new Date(data.data.last_run);
                var diffMin = Math.floor((new Date() - lastRun) / 60000);
                if (diffMin < 1) {
                    lastChecked.textContent = 'Last checked just now';
                } else if (diffMin < 60) {
                    lastChecked.textContent = 'Last checked ' + diffMin + ' min ago';
                } else {
                    var diffHrs = Math.floor(diffMin / 60);
                    lastChecked.textContent = 'Last checked ' + diffHrs + (diffHrs === 1 ? ' hour' : ' hours') + ' ago';
                }
            }
            bar.style.display = '';
        } catch (e) {
            // Non-critical — silently ignore
        }
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
