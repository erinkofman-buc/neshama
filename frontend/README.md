# NESHAMA FRONTEND

Warm, respectful web interface for viewing aggregated Jewish funeral home obituaries.

## What's Included

- **index.html** - Main frontend interface (Instagram-style feed)
- **app.js** - JavaScript application logic
- **api_server.py** - Simple Python API server
- **start.sh** - One-command startup script

## Features

✨ **Instagram-Style Feed**
- Scroll through obituaries in a beautiful, respectful interface
- Today / This Week / This Month tabs
- Lazy loading (shows 5 at a time, load more as needed)

🔍 **Search**
- Search by name (English or Hebrew)
- Real-time filtering

📱 **Mobile-Responsive**
- Works perfectly on iPhone, Android, tablets, desktop
- Touch-friendly with large tap targets (56px minimum)

🎨 **Beautiful Design**
- Warm earth tones (sage green, terracotta, beige)
- Elegant serif typography (Crimson Pro, Cormorant Garamond)
- Smooth animations and transitions
- Respectful, calming aesthetic

💬 **Complete Information**
- Deceased name (English + Hebrew)
- Funeral date/time/location
- Shiva details
- Livestream availability
- Link to full obituary and condolences

🔗 **Share Functionality**
- Native share on mobile (WhatsApp, Messages, etc.)
- Copy link on desktop
- Share individual obituaries easily

## Quick Start

### Method 1: One-Command Start (Easiest)

```bash
chmod +x start.sh
./start.sh
```

This will:
1. Start the API server (serves data from database)
2. Open your browser to the Neshama interface

### Method 2: Manual Start

**Terminal 1 - Start API Server:**
```bash
python3 api_server.py
```

**Terminal 2 - Open Frontend:**
```bash
open index.html
```
(Or just double-click `index.html`)

## How It Works

```
┌─────────────────────────────────────────┐
│ BROWSER (index.html)                    │
│ • Beautiful UI                          │
│ • User interactions                     │
└──────────────┬──────────────────────────┘
               │
               │ (HTTP requests)
               ↓
┌─────────────────────────────────────────┐
│ API SERVER (api_server.py)              │
│ • Serves data via /api/obituaries       │
│ • Handles search via /api/search        │
└──────────────┬──────────────────────────┘
               │
               │ (SQLite queries)
               ↓
┌─────────────────────────────────────────┐
│ DATABASE (neshama.db)                   │
│ • All obituary data                     │
│ • Located in backend folder             │
└─────────────────────────────────────────┘
```

## API Endpoints

The API server provides these endpoints:

**GET /api/obituaries**
- Returns all obituaries from database
- Sorted by most recent first

**GET /api/search?q=name**
- Search obituaries by name
- Supports Hebrew and English names

**GET /api/status**
- Database statistics
- Total obituaries, breakdown by source, comment count

## Design Philosophy

Neshama's design is intentionally:

**Warm, Not Clinical**
- Earth tones create a grounding, natural feeling
- Soft shadows and gentle gradients
- No harsh blacks or stark whites

**Elegant, Not Flashy**
- Classic serif typography
- Generous whitespace
- Subtle animations that respect the content

**Respectful, Not Morbid**
- "Every soul remembered" - celebrating lives
- Dove emoji (🕊️) for peace
- Candle emoji (🕯️) for memory
- Beautiful but never decorative at the expense of dignity

**Accessible, Not Simplified**
- Large fonts (18px+ body text, 28px+ names)
- High contrast (WCAG AA compliant)
- Large tap targets (56px minimum)
- Works for ages 35-80+

## Browser Compatibility

✅ **Modern Browsers:**
- Chrome/Edge (last 2 versions)
- Safari (last 2 versions)
- Firefox (last 2 versions)
- iOS Safari (iOS 14+)
- Android Chrome (Android 10+)

❌ **Not Supported:**
- Internet Explorer
- Very old mobile browsers

## Troubleshooting

**"Unable to connect to server"**
- Make sure API server is running (`python3 api_server.py`)
- Check that you're accessing via http://localhost (not file://)
- Verify database exists at ~/Desktop/Neshama/neshama.db

**"No obituaries found"**
- Make sure backend scrapers have run at least once
- Check database has data: `python3 master_scraper.py status`
- Verify API server can find the database

**Search not working**
- API server must be running
- Check browser console (F12) for errors

**Page looks broken on mobile**
- Make sure you're viewing in a modern browser
- Try refreshing the page
- Check that JavaScript is enabled

## File Structure

```
neshama_frontend/
├── index.html         # Main interface
├── app.js            # Application logic
├── api_server.py     # API server
├── start.sh          # Startup script
└── README.md         # This file
```

## Next Steps

After the frontend is working:

1. **Test on real devices** - iPhone, Android, iPad
2. **Get user feedback** - Show to 3-5 community members
3. **Iterate design** - Adjust colors, fonts, spacing based on feedback
4. **Add features:**
   - Email subscription
   - User accounts
   - Payment integration ($18/year)
   - Push notifications

## Development

To modify the design:

**Colors** - Edit CSS variables in `index.html`:
```css
:root {
    --sage: #B2BEB5;
    --terracotta: #D2691E;
    --warm-beige: #F5F5DC;
    /* etc. */
}
```

**Typography** - Change Google Fonts import and CSS:
```css
font-family: 'Crimson Pro', serif;
font-family: 'Cormorant Garamond', serif;
```

**Layout** - Adjust `.feed` max-width, card padding, etc.

## Support

If you encounter issues:
1. Check browser console (F12 → Console tab)
2. Check API server logs in terminal
3. Verify database connection

---

Built with ❤️ for the Toronto Jewish community
