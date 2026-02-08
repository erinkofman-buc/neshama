// Neshama Frontend Application
// Handles data loading, filtering, search, and UI interactions

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
        // Set up event listeners
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', (e) => this.handleTabChange(e));
        });
        
        const searchBox = document.getElementById('searchBox');
        searchBox.addEventListener('input', (e) => this.handleSearch(e));
        
        // Load initial data
        this.loadData();
    }
    
    async loadData() {
        try {
            const response = await fetch(`${this.apiBase}/obituaries`);
            const data = await response.json();
            
            if (data.status === 'success') {
                this.allObituaries = data.data;
                this.render();
            } else {
                this.showError('Failed to load obituaries');
            }
        } catch (error) {
            console.error('Error loading data:', error);
            this.showError('Unable to connect to server. Please ensure the API server is running.');
        }
    }
    
    handleTabChange(e) {
        // Update active tab
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
        
        this.currentTab = e.target.dataset.tab;
        this.displayedCount = 5; // Reset count
        this.render();
    }
    
    handleSearch(e) {
        this.searchQuery = e.target.value.toLowerCase();
        this.displayedCount = 5; // Reset count
        this.render();
    }
    
    filterObituaries() {
        let filtered = [...this.allObituaries];
        
        // Apply search filter
        if (this.searchQuery) {
            filtered = filtered.filter(obit => {
                const searchableText = `${obit.deceased_name} ${obit.hebrew_name || ''}`.toLowerCase();
                return searchableText.includes(this.searchQuery);
            });
        }
        
        // Apply time filter
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
        const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
        
        if (this.currentTab === 'today') {
            filtered = filtered.filter(obit => {
                const updated = new Date(obit.last_updated);
                return updated >= today;
            });
        } else if (this.currentTab === 'week') {
            filtered = filtered.filter(obit => {
                const updated = new Date(obit.last_updated);
                return updated >= weekAgo;
            });
        } else if (this.currentTab === 'month') {
            filtered = filtered.filter(obit => {
                const updated = new Date(obit.last_updated);
                return updated >= monthAgo;
            });
        }
        
        return filtered;
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
        
        // Show/hide load more button
        if (filtered.length > this.displayedCount) {
            loadMoreBtn.style.display = 'block';
        } else {
            loadMoreBtn.style.display = 'none';
        }
        
        // Attach event listeners to cards
        document.querySelectorAll('.obituary-card').forEach(card => {
            card.addEventListener('click', (e) => {
                // Don't trigger if clicking buttons
                if (!e.target.closest('.btn')) {
                    this.handleCardClick(card.dataset.id);
                }
            });
        });
        
        // Attach share button listeners
        document.querySelectorAll('.share-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.handleShare(btn.dataset.id);
            });
        });
    }
    
    renderCard(obit) {
        const timeAgo = this.getTimeAgo(obit.last_updated);
        const preview = this.getPreview(obit.obituary_text);
        const sourceInitial = obit.source.charAt(0);
        
        return `
            <div class="obituary-card" data-id="${obit.id}">
                <div class="card-header">
                    <div class="source-icon">${sourceInitial}</div>
                    <span class="source-name">${obit.source}</span>
                    <span class="timestamp">${timeAgo}</span>
                </div>
                
                <div class="card-body">
                    <h2 class="deceased-name">${obit.deceased_name}</h2>
                    ${obit.hebrew_name ? `<div class="hebrew-name">${obit.hebrew_name}</div>` : ''}
                    
                    ${obit.funeral_datetime ? `
                        <div class="detail-row">
                            <span class="detail-icon">🕯️</span>
                            <div class="detail-content">
                                <span class="detail-label">Funeral</span>
                                ${obit.funeral_datetime}
                                ${obit.funeral_location ? `<br>${obit.funeral_location}` : ''}
                            </div>
                        </div>
                    ` : ''}
                    
                    ${obit.shiva_info ? `
                        <div class="detail-row">
                            <span class="detail-icon">🏠</span>
                            <div class="detail-content">
                                <span class="detail-label">Shiva</span>
                                ${obit.shiva_info}
                            </div>
                        </div>
                    ` : ''}
                    
                    ${obit.livestream_url ? `
                        <div class="livestream-badge">
                            📺 Livestream Available
                        </div>
                    ` : ''}
                    
                    ${preview ? `
                        <div class="obituary-preview">
                            ${preview}
                            <span class="read-more">Read more →</span>
                        </div>
                    ` : ''}
                    
                    <div class="comments-indicator">
                        💬 View condolences
                    </div>
                </div>
                
                <div class="card-footer">
                    <button class="btn btn-primary" onclick="window.open('${obit.condolence_url}', '_blank')">
                        View Full Obituary
                    </button>
                    <button class="btn btn-secondary share-btn" data-id="${obit.id}">
                        Share ↗
                    </button>
                </div>
            </div>
        `;
    }
    
    renderEmptyState() {
        let message = 'No obituaries found';
        
        if (this.searchQuery) {
            message = `No results for "${this.searchQuery}"`;
        } else if (this.currentTab === 'today') {
            message = 'No services scheduled for today. Check "This Week" for recent obituaries.';
        }
        
        return `
            <div class="empty-state">
                <div class="empty-state-icon">🕊️</div>
                <p>${message}</p>
            </div>
        `;
    }
    
    getPreview(text) {
        if (!text) return '';
        
        // Get first 200 characters
        const preview = text.substring(0, 200);
        
        // Cut at last complete word
        const lastSpace = preview.lastIndexOf(' ');
        return preview.substring(0, lastSpace) + '...';
    }
    
    getTimeAgo(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffHours < 1) return 'Just now';
        if (diffHours < 24) return `${diffHours} ${diffHours === 1 ? 'hour' : 'hours'} ago`;
        if (diffDays < 7) return `${diffDays} ${diffDays === 1 ? 'day' : 'days'} ago`;
        
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }
    
    handleCardClick(id) {
        const obit = this.allObituaries.find(o => o.id === id);
        if (obit && obit.condolence_url) {
            window.open(obit.condolence_url, '_blank');
        }
    }
    
    handleShare(id) {
        const obit = this.allObituaries.find(o => o.id === id);
        if (!obit) return;
        
        const shareUrl = obit.condolence_url;
        const shareText = `${obit.deceased_name} - ${obit.source}`;
        
        // Check if Web Share API is available (mobile)
        if (navigator.share) {
            navigator.share({
                title: shareText,
                url: shareUrl
            }).catch(err => console.log('Share cancelled'));
        } else {
            // Fallback: Copy to clipboard
            navigator.clipboard.writeText(shareUrl).then(() => {
                alert('Link copied to clipboard!');
            });
        }
    }
    
    showError(message) {
        const feed = document.getElementById('feed');
        feed.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <p>${message}</p>
            </div>
        `;
    }
}

// Load more functionality
function loadMore() {
    if (window.app) {
        window.app.displayedCount += 5;
        window.app.render();
    }
}

// Initialize app when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.app = new NeshamaApp();
});
