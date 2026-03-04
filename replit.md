# Stock Financial Analysis Application

## Overview
A comprehensive Streamlit-based stock analysis application that fetches real-time financial data from Yahoo Finance and stores it in a PostgreSQL database for efficient caching and historical analysis.

## Project Architecture

### Core Components
- **app.py**: Main Streamlit application with interactive UI
- **database.py**: PostgreSQL database manager with SQLAlchemy ORM
- **formatting_utils.py**: Global formatting utilities for consistent number display
- **Database**: PostgreSQL for data persistence and caching

### Key Features
- Interactive stock analysis with candlestick charts
- Real-time financial metrics and ratios
- 5-year earnings per share tracking with bar charts
- Database caching for improved performance
- CSV export functionality with complete data sets
- Advanced volume analysis with 3-month focus and detailed metrics
- Volume trend analysis and moving averages
- Company information and business summaries

### Database Schema
- **stock_data**: Historical price and volume data
- **stock_info**: Company information and financial metrics
- **earnings_data**: Annual earnings per share records
- **income_statement**: Line-by-line income statement data by date
- **balance_sheet**: Balance sheet items and values by date
- **cash_flow_statement**: Cash flow statement data by date

## Recent Changes
**Date: 2025-06-26**
- Added PostgreSQL database integration with SQLAlchemy
- Implemented data caching to reduce API calls
- Added database management interface in sidebar
- Enhanced CSV export to include earnings data
- Created comprehensive database schema for stock analytics
- Added fundamental analysis with income statement, balance sheet, and cash flow
- Implemented K, M, B, T number formatting for all financial data
- Enhanced readability with proper currency formatting throughout application
- Created dedicated database tables for financial statements storage
- Integrated automatic saving/loading of financial statements data
- Fixed batch processing issues for large datasets
- Added 3-month trading volume analysis with detailed metrics and trends
- Enhanced volume charts with moving averages and enhanced visualization
- Strict database checkbox control - only uses cached data when checked
- Created global formatting utilities with comprehensive number formatting functions
- Consistent K, M, B, T suffixes and currency formatting across entire application
- Enhanced financial statement formatting with proper negative value display (parentheses)
- Applied professional accounting standards to Income Statement, Balance Sheet, and Cash Flow displays

## User Preferences
- Focus on real data from Yahoo Finance API
- Clean, professional interface without excessive styling
- Database-first approach for performance optimization

## Technical Stack
- **Frontend**: Streamlit
- **Data Source**: Yahoo Finance (yfinance library)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Visualization**: Plotly for interactive charts
- **Data Processing**: Pandas, NumPy

## Environment Variables
- DATABASE_URL: PostgreSQL connection string
- PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE: Database credentials

## Deployment
- Application runs on port 5000
- Configured for Replit deployment with proper server settings