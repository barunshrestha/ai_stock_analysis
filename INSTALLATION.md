# Installation Guide - Stock Analysis Application

## Quick Start

Follow these steps to get the application running locally on macOS.

## Step 1: Install PostgreSQL

Since you're on macOS, the easiest way is using Homebrew:

### Install Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Install PostgreSQL

```bash
# Install PostgreSQL 15
brew install postgresql@15

# Start PostgreSQL service
brew services start postgresql@15

# Add PostgreSQL to your PATH (add to ~/.zshrc)
echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Verify PostgreSQL Installation

```bash
# Check if PostgreSQL is running
pg_isready

# Expected output: /tmp:5432 - accepting connections
```

## Step 2: Create Database and User

```bash
# Connect to PostgreSQL as default user
psql postgres

# In the psql shell, run these commands:
```

```sql
-- Create database
CREATE DATABASE stock_analysis;

-- Create user with password
CREATE USER stock_user WITH PASSWORD 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE stock_analysis TO stock_user;

-- Grant schema permissions (PostgreSQL 15+)
\c stock_analysis
GRANT ALL ON SCHEMA public TO stock_user;

-- Exit psql
\q
```

## Step 3: Configure Environment Variables

```bash
# Navigate to project directory
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis

# Copy environment template
cp env.example .env

# Edit .env file with your credentials
nano .env  # or use your preferred editor
```

Update `.env` with your PostgreSQL credentials:

```env
DATABASE_URL=postgresql://stock_user:your_secure_password@localhost:5432/stock_analysis

PGHOST=localhost
PGPORT=5432
PGUSER=stock_user
PGPASSWORD=your_secure_password
PGDATABASE=stock_analysis
```

## Step 4: Install Python Dependencies

### Option A: Using uv (Recommended - Faster)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
uv pip install -e .
```

### Option B: Using pip

```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
pip install -e .
```

### Manual Installation (if above fails)

```bash
pip install numpy>=2.2.6 pandas>=2.2.3 plotly>=6.1.2 psycopg2-binary>=2.9.10 sqlalchemy>=2.0.41 streamlit>=1.45.1 yfinance>=0.2.61
```

## Step 5: Test Database Connection

```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis

python3 -c "from database import DatabaseManager; db = DatabaseManager(); print('✅ Database connected successfully!')"
```

## Step 6: Run the Application

```bash
streamlit run app.py
```

The application will automatically:
- Open in your default browser at `http://localhost:8501`
- Create all necessary database tables on first run
- Be ready to analyze stocks!

## Quick Setup Script

Alternatively, use the automated setup script (after installing PostgreSQL):

```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
./setup.sh
```

## Troubleshooting

### PostgreSQL Not Starting

```bash
# Check status
brew services list | grep postgresql

# Restart service
brew services restart postgresql@15

# Check logs
tail -f /opt/homebrew/var/log/postgresql@15.log
```

### Port 5432 Already in Use

```bash
# Find what's using port 5432
lsof -i :5432

# Kill the process if needed
kill -9 <PID>
```

### Permission Denied Errors

```bash
# Connect as postgres superuser
psql postgres

# Grant all permissions
GRANT ALL PRIVILEGES ON DATABASE stock_analysis TO stock_user;
ALTER DATABASE stock_analysis OWNER TO stock_user;
```

### Python Package Installation Fails

```bash
# Upgrade pip
pip install --upgrade pip

# Try installing psycopg2-binary separately
pip install psycopg2-binary

# Then install the rest
pip install -e .
```

### Can't Connect to Database

1. Check if PostgreSQL is running: `pg_isready`
2. Verify credentials in `.env` file
3. Test connection: `psql -U stock_user -d stock_analysis -h localhost`
4. Check PostgreSQL logs for errors

## Alternative: Using Docker (Optional)

If you prefer not to install PostgreSQL directly:

```bash
# Start PostgreSQL in Docker
docker run --name stock-postgres \
  -e POSTGRES_USER=stock_user \
  -e POSTGRES_PASSWORD=changeme \
  -e POSTGRES_DB=stock_analysis \
  -p 5432:5432 \
  -d postgres:15

# Update .env with Docker credentials
DATABASE_URL=postgresql://stock_user:changeme@localhost:5432/stock_analysis
```

## Next Steps

Once the application is running:

1. Enter a stock symbol (e.g., AAPL, GOOGL, MSFT)
2. Select a time period for analysis
3. Explore the interactive charts and financial data
4. Export data to CSV if needed
5. Use database caching for faster subsequent loads

## Getting Help

- Check the main [README.md](README.md) for usage instructions
- Review [replit.md](replit.md) for feature documentation
- Ensure all environment variables are set correctly in `.env`

## System Requirements

- macOS 10.15 or higher (your version: darwin 24.6.0)
- Python 3.11+ (you have: 3.13.1 ✅)
- PostgreSQL 12+ (recommended: 15)
- 4GB RAM minimum
- Internet connection for Yahoo Finance API

