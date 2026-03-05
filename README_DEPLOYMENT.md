# 📊 Stock Analysis App - Local Deployment Guide

## 🚀 Quick Start

### Option 1: Simple Terminal Launch (Recommended)

1. Open Terminal
2. Navigate to the app directory:
   ```bash
   cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
   ```
3. Run the startup script:
   ```bash
   ./start_app.sh
   ```
4. Bookmark in your browser: `http://localhost:8501`

---

## 🔖 Creating a Permanent Bookmark

Once the app is running:

1. **Open your browser** and go to: `http://localhost:8501`
2. **Bookmark the page** (⌘+D on Mac)
3. **Name it**: "Stock Analysis Dashboard"
4. The bookmark will work whenever the app is running

---

## 🖥️ Creating a Desktop Launcher (macOS)

### Method 1: Create an Application Shortcut

1. Open **Automator** (Applications → Automator)
2. Choose **Application**
3. Search for "Run Shell Script" and drag it to the workflow
4. Paste this script:
   ```bash
   cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
   source venv/bin/activate
   streamlit run app.py --server.port=8501 --server.address=localhost &
   sleep 3
   open http://localhost:8501
   ```
5. Save as "Stock Analysis App" in your Applications folder
6. **Drag to Dock** for easy access

### Method 2: Terminal Alias (Quick Access)

Add this to your `~/.zshrc` or `~/.bash_profile`:

```bash
alias stock-app='cd /Users/barunshrestha/repo/Agents/ai_stock_analysis && ./start_app.sh'
```

Then reload your terminal:
```bash
source ~/.zshrc  # or source ~/.bash_profile
```

Now you can start the app by typing: `stock-app`

---

## 🔄 Auto-Start on Login (Optional)

### Using macOS LaunchAgent

1. Create a launch agent file:
   ```bash
   nano ~/Library/LaunchAgents/com.stockanalysis.app.plist
   ```

2. Add this content:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.stockanalysis.app</string>
       <key>ProgramArguments</key>
       <array>
           <string>/Users/barunshrestha/repo/Agents/ai_stock_analysis/start_app.sh</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <false/>
       <key>StandardOutPath</key>
       <string>/tmp/stockanalysis.log</string>
       <key>StandardErrorPath</key>
       <string>/tmp/stockanalysis.error.log</string>
   </dict>
   </plist>
   ```

3. Load the launch agent:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.stockanalysis.app.plist
   ```

4. To disable auto-start:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.stockanalysis.app.plist
   ```

---

## 📱 Mobile Access (Same Network)

To access from your phone/tablet on the same WiFi:

1. Find your Mac's IP address:
   ```bash
   ifconfig | grep "inet " | grep -v 127.0.0.1
   ```

2. Update `.streamlit/config.toml`:
   ```toml
   [server]
   address = "0.0.0.0"  # Change from "localhost"
   ```

3. Access from mobile: `http://YOUR_MAC_IP:8501`

---

## 🛑 Stopping the App

- **If running in terminal**: Press `Ctrl+C`
- **If running in background**:
  ```bash
  pkill -f "streamlit run"
  ```

---

## 🔧 Troubleshooting

### Port Already in Use
```bash
lsof -ti:8501 | xargs kill -9
```

### App Won't Start
1. Check if virtual environment is activated
2. Verify database connection in `.env`
3. Check logs: `tail -f /tmp/stockanalysis.log`

### Dependencies Missing
```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
source venv/bin/activate
pip install -r requirements.txt  # or uv pip install -r requirements.txt
```

---

## 📊 App URL

**Local Access**: http://localhost:8501
**Network Access**: http://YOUR_IP:8501

---

## ✨ Tips

1. **Keep Terminal Open**: Don't close the terminal window while using the app
2. **Bookmark It**: Save `http://localhost:8501` in your browser favorites
3. **Use Dock**: Add the Automator app to your Dock for one-click launch
4. **Background Mode**: Use `nohup` to run in background (see below)

### Running in Background
```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
source venv/bin/activate
nohup streamlit run app.py --server.port=8501 > /tmp/stockanalysis.log 2>&1 &
```

---

## 🆘 Support

For issues, check:
- Database connection in `.env`
- Virtual environment activation
- Port availability (8501)
- Python dependencies installed

