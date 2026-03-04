#!/bin/bash

# Stock Analysis Application - Local Setup Script
# This script helps set up the application on your local machine

echo "🚀 Stock Analysis Application - Local Setup"
echo "==========================================="
echo ""

# Check if Python is installed
echo "📋 Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python $PYTHON_VERSION found"

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed."
    echo "   macOS: brew install postgresql@15"
    echo "   Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib"
    exit 1
fi

PG_VERSION=$(psql --version | cut -d' ' -f3)
echo "✅ PostgreSQL $PG_VERSION found"

# Check if PostgreSQL is running
if ! pg_isready &> /dev/null; then
    echo "⚠️  PostgreSQL is not running."
    echo "   macOS: brew services start postgresql@15"
    echo "   Linux: sudo systemctl start postgresql"
    exit 1
fi

echo "✅ PostgreSQL is running"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    if [ -f env.example ]; then
        cp env.example .env
        echo "⚠️  Please edit .env file with your PostgreSQL credentials"
        echo "   Default location: $(pwd)/.env"
    else
        echo "⚠️  env.example not found. Creating basic .env file..."
        cat > .env << 'EOF'
# PostgreSQL Database Configuration
DATABASE_URL=postgresql://stock_user:changeme@localhost:5432/stock_analysis

PGHOST=localhost
PGPORT=5432
PGUSER=stock_user
PGPASSWORD=changeme
PGDATABASE=stock_analysis
EOF
        echo "✅ Created .env file - please update with your credentials"
    fi
else
    echo "✅ .env file already exists"
fi

echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "✅ Virtual environment ready"
echo ""

# Install dependencies
echo "📦 Installing Python dependencies..."
source venv/bin/activate

if command -v uv &> /dev/null; then
    echo "   Using uv (fast package manager)..."
    uv pip install -e .
else
    echo "   Using pip..."
    pip install -e .
fi

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo ""

# Test database connection
echo "🔍 Testing database connection..."
python3 -c "
import os
from database import DatabaseManager

try:
    db = DatabaseManager()
    print('✅ Database connected successfully!')
    print('   Tables created and ready to use')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    print('   Please check your .env file and PostgreSQL credentials')
    exit(1)
"

echo ""
echo "✨ Setup complete! You can now run the application:"
echo ""
echo "   Activate virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "   Run the app:"
echo "   streamlit run app.py"
echo ""
echo "📖 For more information, see README.md or GET_STARTED.md"

