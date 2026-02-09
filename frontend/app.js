// Neshama Frontend Application
// Handles data loading, filtering, search, share, and UI interactions

class NeshamaApp {
    constructor() {
        this.apiBase = '/api';
        this.currentTab = 'today';
        this.searchQuery = '';
        this.allObituaries = [];
        this.displayedCount = 5;
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

        this.loadData();
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
                this.render();
            } else {
                this.showError('Failed to load obituaries. Please try again.');
            }
        } catch (error) {
            this.showError('Unable to connect. Please check your internet connection and try again.');
        }
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

        // Attach event listeners
        document.querySelectorAll('.obituary-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (!e.target.closest('.btn') && !e.target.closest('.share-menu')) {
                    this.handleCardClick(card.dataset.id);
                }
            });
        });

        document.querySelectorAll('.share-toggle').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleShareMenu(btn);
            });
        });

        document.querySelectorAll('.share-option').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.closest('.obituary-card').dataset.id;
                this.handleShareAction(id, btn.dataset.action);
            });
        });
    }

    renderCard(obit) {
        const timeAgo = this.getTimeAgo(obit.last_updated);
        const preview = this.getPreview(obit.obituary_text);
        const sourceInitial = obit.source.charAt(0);
        const name = this.searchQuery
            ? this.highlightText(obit.deceased_name, this.searchQuery)
            : obit.deceased_name;

        return '\
            <div class="obituary-card" data-id="' + obit.id + '">\
                <div class="card-header">\
                    <div class="source-icon">' + sourceInitial + '</div>\
                    <span class="source-name">' + obit.source + '</span>\
                    <span class="timestamp">' + timeAgo + '</span>\
                </div>\
                <div class="card-body">\
                    <h2 class="deceased-name">' + name + '</h2>\
                    ' + (obit.hebrew_name ? '<div class="hebrew-name">' + obit.hebrew_name + '</div>' : '') + '\
                    ' + (obit.funeral_datetime ? '\
                        <div class="detail-row">\
                            <span class="detail-icon">\u{1F56F}\uFE0F</span>\
                            <div class="detail-content">\
                                <span class="detail-label">Funeral</span>\
                                ' + obit.funeral_datetime + '\
                                ' + (obit.funeral_location ? '<br>' + obit.funeral_location : '') + '\
                            </div>\
                        </div>' : '') + '\
                    ' + (obit.shiva_info ? '\
                        <div class="detail-row">\
                            <span class="detail-icon">\u{1F3E0}</span>\
                            <div class="detail-content">\
                                <span class="detail-label">Shiva</span>\
                                ' + obit.shiva_info + '\
                            </div>\
                        </div>' : '') + '\
                    ' + (obit.livestream_url ? '\
                        <div class="livestream-badge">\
                            \u{1F4FA} Livestream Available\
                        </div>' : '') + '\
                    ' + (preview ? '\
                        <div class="obituary-preview">\
                            ' + preview + '\
                            <span class="read-more">Read more \u2192</span>\
                        </div>' : '') + '\
                </div>\
                <div class="card-footer">\
                    <button class="btn btn-primary" onclick="window.open(\'' + obit.condolence_url + '\', \'_blank\')">\
                        View Full Obituary\
                    </button>\
                    <div class="share-wrapper">\
                        <button class="btn btn-secondary share-toggle" aria-label="Share">\
                            Share \u2197\
                        </button>\
                        <div class="share-menu">\
                            <button class="share-option" data-action="copy" title="Copy link">\u{1F517} Copy Link</button>\
                            <button class="share-option" data-action="whatsapp" title="Share via WhatsApp">\u{1F4AC} WhatsApp</button>\
                            <button class="share-option" data-action="email" title="Share via email">\u2709\uFE0F Email</button>\
                        </div>\
                    </div>\
                </div>\
            </div>';
    }

    renderEmptyState() {
        if (this.searchQuery) {
            return '\
                <div class="empty-state">\
                    <div class="empty-state-icon">\u{1F50D}</div>\
                    <p class="empty-state-title">No results for "' + this.escapeHtml(this.searchQuery) + '"</p>\
                    <p class="empty-state-hint">Try a different spelling or check the other time tabs above.</p>\
                </div>';
        }
        if (this.currentTab === 'today') {
            return '\
                <div class="empty-state">\
                    <div class="empty-state-icon">\u{1F54A}\uFE0F</div>\
                    <p class="empty-state-title">No services scheduled for today</p>\
                    <p class="empty-state-hint">Check <strong>"This Week"</strong> or <strong>"This Month"</strong> for recent obituaries.</p>\
                </div>';
        }
        return '\
            <div class="empty-state">\
                <div class="empty-state-icon">\u{1F54A}\uFE0F</div>\
                <p>No obituaries found for this period.</p>\
            </div>';
    }

    escapeHtml(text) {
        var d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
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
        var obit = this.allObituaries.find(function(o) { return o.id === id; });
        if (obit && obit.condolence_url) {
            window.open(obit.condolence_url, '_blank');
        }
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

        var url = obit.condolence_url;
        var text = obit.deceased_name + ' - ' + obit.source;

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
                <div class="empty-state-icon">\u26A0\uFE0F</div>\
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
