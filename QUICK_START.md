# 🚀 Quick Start Guide - Stock Analysis App

## 📋 Prerequisites
- Python environment is already set up ✅
- Virtual environment exists at `venv/` ✅
- All dependencies installed ✅

---

## 🎯 How to Run the App

### **Option 1: Quick Launch (Terminal stays open)**

```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
./start_app.sh
```

- Terminal window must stay open
- Press `Ctrl+C` to stop
- Best for development/testing

### **Option 2: Background Mode (Recommended for Daily Use)**

```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
./start_background.sh
```

- Runs in background
- Can close terminal
- App stays running
- Auto-opens in browser

### **Option 3: Direct Streamlit Command**

```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
source venv/bin/activate
streamlit run app.py
```

---

## 🔗 Access the App

Once running, open your browser to:

**http://localhost:8501**

⭐ **Bookmark this URL for easy access!**

---

## 🛑 Stopping the App

```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
./stop_app.sh
```

Or manually:
```bash
pkill -f "streamlit run"
```

---

## 🔍 Check if App is Running

```bash
lsof -i:8501
```

---

## 📱 Create Desktop Shortcut (macOS)

1. Open **Script Editor** (Applications → Utilities → Script Editor)
2. Paste this code:
   ```applescript
   do shell script "cd /Users/barunshrestha/repo/Agents/ai_stock_analysis && ./start_background.sh"
   ```
3. Save as **Application** → Name it "Stock Analysis"
4. Drag to **Dock** or **Desktop**

---

## ⚡ Create Terminal Alias (Super Fast Access)

Add to `~/.zshrc`:

```bash
# Stock Analysis App Shortcuts
alias stock='cd /Users/barunshrestha/repo/Agents/ai_stock_analysis && ./start_background.sh'
alias stock-stop='cd /Users/barunshrestha/repo/Agents/ai_stock_analysis && ./stop_app.sh'
alias stock-logs='tail -f /tmp/stockanalysis.log'
```

Then reload:
```bash
source ~/.zshrc
```

Now just type `stock` to launch the app!

---

## 🔧 Troubleshooting

### App won't start?
```bash
# Check port availability
lsof -i:8501

# Kill existing processes
lsof -ti:8501 | xargs kill -9
```

### Check logs
```bash
tail -f /tmp/stockanalysis.log
```

### Database issues?
Verify `.env` file has correct `DATABASE_URL`

---

## ✨ Daily Workflow

1. **Morning**: `./start_background.sh`
2. **Open browser**: Go to bookmarked URL `http://localhost:8501`
3. **Work all day**: App stays running
4. **Evening**: `./stop_app.sh` (or leave running)

---

## 🎉 You're All Set!

The app is now ready to use. Just run the start script and bookmark the URL!
