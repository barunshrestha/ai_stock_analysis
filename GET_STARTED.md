# Get Started - Stock Analysis Application

## ✅ What's Already Done

- ✅ Python 3.13.1 installed
- ✅ Virtual environment created (`venv/`)
- ✅ All Python dependencies installed successfully
- ✅ Project structure configured

## ⏳ What You Need to Do Now

### Step 1: Install PostgreSQL (5 minutes)

PostgreSQL is the only missing component. Install it using Homebrew:

```bash
# Install PostgreSQL
brew install postgresql@15

# Start PostgreSQL service
brew services start postgresql@15

# Add PostgreSQL to your PATH
echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Verify Installation:**
```bash
# This should show: accepting connections
pg_isready
```

### Step 2: Create Database and User (2 minutes)

```bash
# Connect to PostgreSQL
psql postgres
```

In the PostgreSQL shell, run these commands:

```sql
-- Create database
CREATE DATABASE stock_analysis;

-- Create user
CREATE USER stock_user WITH PASSWORD 'SecurePassword123!';

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE stock_analysis TO stock_user;

-- Switch to the database
\c stock_analysis

-- Grant schema permissions
GRANT ALL ON SCHEMA public TO stock_user;

-- Exit
\q
```

### Step 3: Create .env File (1 minute)

```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis

# Create .env file with your database credentials
cat > .env << 'EOF'
DATABASE_URL=postgresql://stock_user:SecurePassword123!@localhost:5432/stock_analysis

PGHOST=localhost
PGPORT=5432
PGUSER=stock_user
PGPASSWORD=SecurePassword123!
PGDATABASE=stock_analysis
EOF
```

**Important:** Replace `SecurePassword123!` with the password you chose in Step 2.

### Step 4: Test Database Connection (30 seconds)

```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis

# Activate the virtual environment
source venv/bin/activate

# Test database connection
python3 -c "from database import DatabaseManager; db = DatabaseManager(); print('✅ Database connected and tables created!')"
```

### Step 5: Run the Application! (30 seconds)

```bash
# Make sure you're in the project directory with venv activated
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
source venv/bin/activate

# Run the app
streamlit run app.py
```

The application will automatically open in your browser at: **http://localhost:8501**

## 🎉 Using the Application

Once running, you can:

1. **Analyze Stocks**: Enter any ticker symbol (AAPL, GOOGL, MSFT, TSLA, etc.)
2. **View Charts**: Interactive candlestick charts with volume analysis
3. **Financial Metrics**: P/E ratio, market cap, dividend yield, and more
4. **Earnings Data**: 5-year EPS history with visualizations
5. **Financial Statements**: Income statement, balance sheet, and cash flow
6. **Export Data**: Download CSV files with complete stock data
7. **Database Caching**: Toggle to use cached data for faster loading

## 💡 Tips

### Always Activate Virtual Environment

Before running the app or working with the project:
```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
source venv/bin/activate
```

### Running on Different Port

If port 8501 is busy:
```bash
streamlit run app.py --server.port 8502
```

### Check PostgreSQL Status

```bash
# Check if running
pg_isready

# Restart if needed
brew services restart postgresql@15
```

### View Logs

If something goes wrong, check:
```bash
# PostgreSQL logs
tail -f /opt/homebrew/var/log/postgresql@15.log

# Streamlit logs (shown in terminal)
```

## 🔧 Troubleshooting

### "psql: command not found"

Add PostgreSQL to your PATH:
```bash
echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### "Connection refused" Error

PostgreSQL isn't running:
```bash
brew services start postgresql@15
```

### "Authentication failed"

Check your password in `.env` matches what you set in Step 2.

### Dependencies Missing

Reinstall in virtual environment:
```bash
source venv/bin/activate
pip install -e .
```

## 📚 Additional Documentation

- **QUICK_START.md** - Rapid setup guide
- **INSTALLATION.md** - Detailed installation with troubleshooting
- **README.md** - Complete application documentation
- **replit.md** - Feature overview and recent changes

## 🚀 Next Steps After Setup

1. Try analyzing popular stocks (AAPL, GOOGL, MSFT)
2. Export some data to CSV
3. Compare different time periods
4. Explore the financial statement tabs
5. Enable database caching for faster repeated queries

## 📊 Example Stocks to Try

- **AAPL** - Apple Inc.
- **GOOGL** - Alphabet Inc.
- **MSFT** - Microsoft Corporation
- **TSLA** - Tesla Inc.
- **AMZN** - Amazon.com Inc.
- **NVDA** - NVIDIA Corporation
- **META** - Meta Platforms Inc.

---

**Need Help?** Check the troubleshooting sections in INSTALLATION.md or README.md

