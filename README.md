# Stock Financial Analysis Application

A comprehensive Streamlit-based stock analysis application that fetches real-time financial data from Yahoo Finance and stores it in a PostgreSQL database for efficient caching and historical analysis.

## Features

- 📊 Interactive stock analysis with candlestick charts
- 💰 Real-time financial metrics and ratios
- 📈 5-year earnings per share tracking with bar charts
- 💾 Database caching for improved performance
- 📥 CSV export functionality with complete data sets
- 📊 Advanced volume analysis with 3-month focus and detailed metrics
- 📉 Volume trend analysis and moving averages
- 🏢 Company information and business summaries
- 📋 Income Statement, Balance Sheet, and Cash Flow analysis

## Tech Stack

- **Frontend**: Streamlit
- **Data Source**: Yahoo Finance (yfinance library)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Visualization**: Plotly for interactive charts
- **Data Processing**: Pandas, NumPy

## Prerequisites

Before setting up the project, ensure you have the following installed:

1. **Python 3.11 or higher**
   ```bash
   python --version
   ```

2. **PostgreSQL**
   - macOS: `brew install postgresql@15`
   - Ubuntu/Debian: `sudo apt-get install postgresql postgresql-contrib`
   - Windows: Download from [postgresql.org](https://www.postgresql.org/download/)

3. **uv** (recommended) or pip
   ```bash
   # Install uv (faster package manager)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

## Local Setup Instructions

### 1. Clone and Navigate to Project

```bash
cd /Users/barunshrestha/repo/Agents/ai_stock_analysis
```

### 2. Set Up PostgreSQL Database

#### Start PostgreSQL Service

**macOS (Homebrew):**
```bash
brew services start postgresql@15
```

**Linux:**
```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Windows:**
PostgreSQL service should start automatically after installation.

#### Create Database and User

```bash
# Connect to PostgreSQL
psql postgres

# In psql shell, run:
CREATE DATABASE stock_analysis;
CREATE USER stock_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE stock_analysis TO stock_user;
\q
```

### 3. Configure Environment Variables

Copy the example environment file and update with your credentials:

```bash
cp .env.example .env
```

Edit `.env` file with your PostgreSQL credentials:

```env
DATABASE_URL=postgresql://stock_user:your_secure_password@localhost:5432/stock_analysis

# Or use individual parameters:
PGHOST=localhost
PGPORT=5432
PGUSER=stock_user
PGPASSWORD=your_secure_password
PGDATABASE=stock_analysis
```

### 4. Install Python Dependencies

**Using uv (recommended - faster):**
```bash
uv pip install -e .
```

**Using pip:**
```bash
pip install -e .
```

**Or install from requirements:**
```bash
# If you prefer requirements.txt
pip install numpy>=2.2.6 pandas>=2.2.3 plotly>=6.1.2 psycopg2-binary>=2.9.10 sqlalchemy>=2.0.41 streamlit>=1.45.1 yfinance>=0.2.61
```

### 5. Initialize Database Tables

The application will automatically create database tables on first run. To verify your setup:

```bash
python -c "from database import DatabaseManager; db = DatabaseManager(); print('Database connected successfully!')"
```

### 6. Run the Application

```bash
streamlit run app.py
```

The application will open in your default browser at `http://localhost:8501`

## Usage

1. **Enter a Stock Symbol**: Type any valid stock ticker (e.g., AAPL, GOOGL, MSFT) in the sidebar
2. **Select Time Period**: Choose from 1 month to 5 years of historical data
3. **Choose Analysis Options**:
   - **Comprehensive Financial Overview**: Detailed tabular view with all key metrics
   - **Fundamental Analysis**: Income statement, balance sheet, and cash flow statements
4. **View Analysis**: Explore interactive charts, financial metrics, and company information
5. **Export Data**: Download CSV files with complete stock data
6. **Database Caching**: Check "Use cached data" to load from database instead of API

## Database Schema

The application uses the following PostgreSQL tables:

- **stock_data**: Historical price and volume data
- **stock_info**: Company information and financial metrics
- **earnings_data**: Annual earnings per share records
- **income_statement**: Line-by-line income statement data by date
- **balance_sheet**: Balance sheet items and values by date
- **cash_flow_statement**: Cash flow statement data by date

## Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
pg_isready

# macOS: Check service status
brew services list | grep postgresql

# Linux: Check service status
sudo systemctl status postgresql
```

### Port Already in Use

If port 8501 is in use, specify a different port:
```bash
streamlit run app.py --server.port 8502
```

### Missing Dependencies

```bash
# Reinstall all dependencies
uv pip install --force-reinstall -e .
```

### Database Permission Errors

Grant proper permissions to your database user:
```sql
-- Connect as postgres superuser
psql postgres

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE stock_analysis TO stock_user;
ALTER DATABASE stock_analysis OWNER TO stock_user;
```

## Development

### Project Structure

```
ai_stock_analysis/
├── app.py                  # Main Streamlit application
├── database.py             # PostgreSQL database manager with SQLAlchemy ORM
├── formatting_utils.py     # Global formatting utilities for numbers/currency
├── pyproject.toml          # Python dependencies and project metadata
├── .env                    # Environment variables (not in git)
├── .env.example            # Example environment configuration
└── README.md               # This file
```

### Code Style

This project follows:
- SOLID principles and clean code architecture
- Descriptive variable and function names
- Single responsibility functions
- OWASP security best practices
- Comprehensive error handling

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Full PostgreSQL connection string | `postgresql://user:pass@localhost:5432/stock_analysis` |
| `PGHOST` | PostgreSQL host | `localhost` |
| `PGPORT` | PostgreSQL port | `5432` |
| `PGUSER` | Database user | `stock_user` |
| `PGPASSWORD` | Database password | `your_password` |
| `PGDATABASE` | Database name | `stock_analysis` |

## Contributing

1. Follow the coding guidelines in `.cursorrules`
2. Write unit tests for core logic
3. Keep functions small and focused
4. Document complex logic with comments
5. Use environment variables for configuration

## License

This project is for educational and personal use.

## Acknowledgments

- Data provided by Yahoo Finance via [yfinance](https://github.com/ranaroussi/yfinance)
- Built with [Streamlit](https://streamlit.io/)
- Charts powered by [Plotly](https://plotly.com/)

