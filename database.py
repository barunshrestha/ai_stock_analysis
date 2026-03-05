import os
import pandas as pd
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class StockData(Base):
    __tablename__ = 'stock_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False)
    date = Column(DateTime, nullable=False)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    volume = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class StockInfo(Base):
    __tablename__ = 'stock_info'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, unique=True)
    company_name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    dividend_yield = Column(Float)
    country = Column(String(50))
    currency = Column(String(10))
    exchange = Column(String(50))
    website = Column(String(255))
    business_summary = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)

class EarningsData(Base):
    __tablename__ = 'earnings_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False)
    year = Column(Integer, nullable=False)
    earnings_per_share = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class IncomeStatement(Base):
    __tablename__ = 'income_statement'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False)
    date = Column(DateTime, nullable=False)
    line_item = Column(String(255), nullable=False)
    value = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class BalanceSheet(Base):
    __tablename__ = 'balance_sheet'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False)
    date = Column(DateTime, nullable=False)
    line_item = Column(String(255), nullable=False)
    value = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class CashFlowStatement(Base):
    __tablename__ = 'cash_flow_statement'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False)
    date = Column(DateTime, nullable=False)
    line_item = Column(String(255), nullable=False)
    value = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class Portfolio(Base):
    __tablename__ = 'portfolio'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, unique=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StockIndustry(Base):
    """Admin-managed stock-to-industry assignments. A stock can belong to multiple industries."""
    __tablename__ = 'stock_industry'
    __table_args__ = (UniqueConstraint('symbol', 'industry', name='uq_stock_industry'),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    industry = Column(String(150), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not found")
        
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create tables
        self.create_tables()
    
    def create_tables(self):
        """Create all database tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def get_session(self):
        """Get a database session"""
        return self.SessionLocal()
    
    def save_stock_data(self, symbol, hist_data):
        """Save historical stock data to database"""
        session = self.get_session()
        try:
            # Clear existing data for this symbol
            session.query(StockData).filter(StockData.symbol == symbol).delete()
            
            # Prepare batch insert data
            batch_data = []
            for date, row in hist_data.iterrows():
                batch_data.append({
                    'symbol': symbol,
                    'date': date,
                    'open_price': float(row['Open']),
                    'high_price': float(row['High']),
                    'low_price': float(row['Low']),
                    'close_price': float(row['Close']),
                    'volume': int(row['Volume']),
                    'created_at': datetime.utcnow()
                })
            
            # Insert in batches of 100 to avoid parameter limit
            batch_size = 100
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i + batch_size]
                session.bulk_insert_mappings(StockData, batch)
            
            session.commit()
            logger.info(f"Saved {len(hist_data)} records for {symbol}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving stock data: {e}")
            return False
        finally:
            session.close()
    
    def save_stock_info(self, symbol, info):
        """Save stock company information to database"""
        session = self.get_session()
        try:
            # Check if record exists
            existing = session.query(StockInfo).filter(StockInfo.symbol == symbol).first()
            
            if existing:
                # Delete and recreate to avoid column assignment issues
                session.delete(existing)
                session.flush()
            
            # Create new record
            stock_info = StockInfo(
                symbol=symbol,
                company_name=info.get('longName', ''),
                sector=info.get('sector', ''),
                industry=info.get('industry', ''),
                market_cap=info.get('marketCap'),
                pe_ratio=info.get('trailingPE'),
                dividend_yield=info.get('dividendYield'),
                country=info.get('country', ''),
                currency=info.get('currency', ''),
                exchange=info.get('exchange', ''),
                website=info.get('website', ''),
                business_summary=info.get('longBusinessSummary', '')
            )
            session.add(stock_info)
            
            session.commit()
            logger.info(f"Saved stock info for {symbol}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving stock info: {e}")
            return False
        finally:
            session.close()
    
    def save_earnings_data(self, symbol, earnings_data):
        """Save earnings data to database"""
        if earnings_data is None or earnings_data.empty:
            return True
            
        session = self.get_session()
        try:
            # Clear existing earnings data for this symbol
            session.query(EarningsData).filter(EarningsData.symbol == symbol).delete()
            
            # Insert new earnings data
            for year, row in earnings_data.iterrows():
                earnings = EarningsData(
                    symbol=symbol,
                    year=year,
                    earnings_per_share=row['Earnings']
                )
                session.add(earnings)
            
            session.commit()
            logger.info(f"Saved earnings data for {symbol}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving earnings data: {e}")
            return False
        finally:
            session.close()
    
    def get_stock_data(self, symbol, limit=None):
        """Retrieve historical stock data from database"""
        session = self.get_session()
        try:
            query = session.query(StockData).filter(StockData.symbol == symbol).order_by(StockData.date.desc())
            if limit:
                query = query.limit(limit)
            
            records = query.all()
            
            if not records:
                return None
            
            # Convert to DataFrame
            data = []
            for record in records:
                data.append({
                    'Date': record.date,
                    'Open': record.open_price,
                    'High': record.high_price,
                    'Low': record.low_price,
                    'Close': record.close_price,
                    'Volume': record.volume
                })
            
            df = pd.DataFrame(data)
            df.set_index('Date', inplace=True)
            df.sort_index(inplace=True)
            return df
        except Exception as e:
            logger.error(f"Error retrieving stock data: {e}")
            return None
        finally:
            session.close()
    
    def get_stock_info(self, symbol):
        """Retrieve stock company information from database"""
        session = self.get_session()
        try:
            record = session.query(StockInfo).filter(StockInfo.symbol == symbol).first()
            if not record:
                return None
            
            return {
                'longName': record.company_name,
                'sector': record.sector,
                'industry': record.industry,
                'marketCap': record.market_cap,
                'trailingPE': record.pe_ratio,
                'dividendYield': record.dividend_yield,
                'country': record.country,
                'currency': record.currency,
                'exchange': record.exchange,
                'website': record.website,
                'longBusinessSummary': record.business_summary
            }
        except Exception as e:
            logger.error(f"Error retrieving stock info: {e}")
            return None
        finally:
            session.close()
    
    def get_earnings_data(self, symbol):
        """Retrieve earnings data from database"""
        session = self.get_session()
        try:
            records = session.query(EarningsData).filter(EarningsData.symbol == symbol).order_by(EarningsData.year).all()
            
            if not records:
                return None
            
            data = []
            for record in records:
                data.append({
                    'Year': record.year,
                    'Earnings': record.earnings_per_share
                })
            
            df = pd.DataFrame(data)
            df.set_index('Year', inplace=True)
            return df
        except Exception as e:
            logger.error(f"Error retrieving earnings data: {e}")
            return None
        finally:
            session.close()
    
    def get_all_symbols(self):
        """Get all stock symbols stored in database"""
        session = self.get_session()
        try:
            symbols = session.query(StockInfo.symbol).distinct().all()
            return [symbol[0] for symbol in symbols]
        except Exception as e:
            logger.error(f"Error retrieving symbols: {e}")
            return []
        finally:
            session.close()

    def get_all_industries(self):
        """Get distinct industry names from stock_info (non-null, non-empty)."""
        session = self.get_session()
        try:
            rows = (
                session.query(StockInfo.industry)
                .filter(StockInfo.industry.isnot(None), StockInfo.industry != "")
                .distinct()
                .order_by(StockInfo.industry)
                .all()
            )
            return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"Error retrieving industries: {e}")
            return []
        finally:
            session.close()

    def get_stocks_by_industry(self, industry):
        """Get list of (symbol, company_name, sector) for a given industry."""
        session = self.get_session()
        try:
            rows = (
                session.query(StockInfo.symbol, StockInfo.company_name, StockInfo.sector)
                .filter(StockInfo.industry == industry)
                .order_by(StockInfo.symbol)
                .all()
            )
            return [{"symbol": r[0], "company_name": r[1] or r[0], "sector": r[2] or "N/A"} for r in rows]
        except Exception as e:
            logger.error(f"Error retrieving stocks by industry: {e}")
            return []
        finally:
            session.close()

    def get_industries_with_stocks(self):
        """Get dict mapping industry -> list of {symbol, company_name, sector} for all industries."""
        session = self.get_session()
        try:
            rows = (
                session.query(StockInfo.industry, StockInfo.symbol, StockInfo.company_name, StockInfo.sector)
                .filter(StockInfo.industry.isnot(None), StockInfo.industry != "")
                .order_by(StockInfo.industry, StockInfo.symbol)
                .all()
            )
            result = {}
            for industry, symbol, company_name, sector in rows:
                if industry not in result:
                    result[industry] = []
                result[industry].append({
                    "symbol": symbol,
                    "company_name": company_name or symbol,
                    "sector": sector or "N/A",
                })
            return result
        except Exception as e:
            logger.error(f"Error retrieving industries with stocks: {e}")
            return {}
        finally:
            session.close()

    # ---------- Admin: stock_industry (By Industry page) ----------
    def admin_get_all_industries(self):
        """Distinct industry names from stock_industry table (admin-managed)."""
        session = self.get_session()
        try:
            rows = (
                session.query(StockIndustry.industry)
                .distinct()
                .order_by(StockIndustry.industry)
                .all()
            )
            return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"Error retrieving admin industries: {e}")
            return []
        finally:
            session.close()

    def admin_get_industries_with_stocks(self):
        """Dict industry -> list of {symbol, company_name} from stock_industry. company_name from stock_info if available."""
        session = self.get_session()
        try:
            rows = (
                session.query(StockIndustry.symbol, StockIndustry.industry)
                .order_by(StockIndustry.industry, StockIndustry.symbol)
                .all()
            )
            result = {}
            for symbol, industry in rows:
                if industry not in result:
                    result[industry] = []
                # Resolve display name from stock_info if present
                info = session.query(StockInfo.company_name).filter(StockInfo.symbol == symbol).first()
                name = (info[0] or symbol) if info else symbol
                result[industry].append({"symbol": symbol, "company_name": name})
            return result
        except Exception as e:
            logger.error(f"Error retrieving admin industries with stocks: {e}")
            return {}
        finally:
            session.close()

    def admin_get_stocks_by_industry(self, industry):
        """List of {symbol, company_name} for an industry from admin table (for sidebar filter)."""
        session = self.get_session()
        try:
            rows = (
                session.query(StockIndustry.symbol)
                .filter(StockIndustry.industry == industry)
                .order_by(StockIndustry.symbol)
                .all()
            )
            out = []
            for (symbol,) in rows:
                info = session.query(StockInfo.company_name).filter(StockInfo.symbol == symbol).first()
                name = (info[0] or symbol) if info else symbol
                out.append({"symbol": symbol, "company_name": name})
            return out
        except Exception as e:
            logger.error(f"Error in admin_get_stocks_by_industry: {e}")
            return []
        finally:
            session.close()

    def admin_get_industries_for_stock(self, symbol):
        """List of industries this symbol is assigned to (admin table)."""
        session = self.get_session()
        try:
            rows = (
                session.query(StockIndustry.industry)
                .filter(StockIndustry.symbol == symbol)
                .order_by(StockIndustry.industry)
                .all()
            )
            return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"Error retrieving industries for stock: {e}")
            return []
        finally:
            session.close()

    def admin_add_stock_to_industry(self, symbol, industry):
        """Add (symbol, industry). Idempotent if already present. Returns (True, None) or (False, error_msg)."""
        symbol = (symbol or "").strip().upper()
        industry = (industry or "").strip()
        if not symbol or not industry:
            return False, "Symbol and industry are required."
        session = self.get_session()
        try:
            existing = (
                session.query(StockIndustry)
                .filter(StockIndustry.symbol == symbol, StockIndustry.industry == industry)
                .first()
            )
            if existing:
                return True, None
            rec = StockIndustry(symbol=symbol, industry=industry)
            session.add(rec)
            session.commit()
            logger.info(f"Admin: added {symbol} to industry {industry}")
            return True, None
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding stock to industry: {e}")
            return False, str(e)
        finally:
            session.close()

    def admin_remove_stock_from_industry(self, symbol, industry):
        """Remove one (symbol, industry) assignment. Returns (True, None) or (False, error_msg)."""
        session = self.get_session()
        try:
            session.query(StockIndustry).filter(
                StockIndustry.symbol == symbol,
                StockIndustry.industry == industry,
            ).delete()
            session.commit()
            logger.info(f"Admin: removed {symbol} from industry {industry}")
            return True, None
        except Exception as e:
            session.rollback()
            logger.error(f"Error removing stock from industry: {e}")
            return False, str(e)
        finally:
            session.close()

    def admin_remove_stock_from_all_industries(self, symbol):
        """Remove symbol from all industries in admin table. Returns (True, None) or (False, error_msg)."""
        session = self.get_session()
        try:
            session.query(StockIndustry).filter(StockIndustry.symbol == symbol).delete()
            session.commit()
            logger.info(f"Admin: removed {symbol} from all industries")
            return True, None
        except Exception as e:
            session.rollback()
            logger.error(f"Error removing stock from all industries: {e}")
            return False, str(e)
        finally:
            session.close()

    def admin_set_stock_industries(self, symbol, industry_list):
        """Set industries for symbol: replace all current assignments with the given list. Returns (True, None) or (False, error_msg)."""
        symbol = (symbol or "").strip().upper()
        industries = [(i or "").strip() for i in (industry_list or []) if (i or "").strip()]
        session = self.get_session()
        try:
            session.query(StockIndustry).filter(StockIndustry.symbol == symbol).delete()
            for ind in industries:
                session.add(StockIndustry(symbol=symbol, industry=ind))
            session.commit()
            logger.info(f"Admin: set industries for {symbol} to {industries}")
            return True, None
        except Exception as e:
            session.rollback()
            logger.error(f"Error setting stock industries: {e}")
            return False, str(e)
        finally:
            session.close()

    def save_financial_statements(self, symbol, financials):
        """Save financial statements data to database"""
        if not financials:
            return True
            
        session = self.get_session()
        try:
            # Clear existing financial data for this symbol
            session.query(IncomeStatement).filter(IncomeStatement.symbol == symbol).delete()
            session.query(BalanceSheet).filter(BalanceSheet.symbol == symbol).delete()
            session.query(CashFlowStatement).filter(CashFlowStatement.symbol == symbol).delete()
            
            # Save Income Statement
            if financials.get('income_stmt') is not None and not financials['income_stmt'].empty:
                income_data = []
                for line_item in financials['income_stmt'].index:
                    for date_col in financials['income_stmt'].columns:
                        value = financials['income_stmt'].loc[line_item, date_col]
                        if pd.notna(value):
                            income_data.append({
                                'symbol': symbol,
                                'date': date_col,
                                'line_item': str(line_item),
                                'value': float(value),
                                'created_at': datetime.utcnow()
                            })
                
                if income_data:
                    session.bulk_insert_mappings(IncomeStatement, income_data)
            
            # Save Balance Sheet
            if financials.get('balance_sheet') is not None and not financials['balance_sheet'].empty:
                balance_data = []
                for line_item in financials['balance_sheet'].index:
                    for date_col in financials['balance_sheet'].columns:
                        value = financials['balance_sheet'].loc[line_item, date_col]
                        if pd.notna(value):
                            balance_data.append({
                                'symbol': symbol,
                                'date': date_col,
                                'line_item': str(line_item),
                                'value': float(value),
                                'created_at': datetime.utcnow()
                            })
                
                if balance_data:
                    session.bulk_insert_mappings(BalanceSheet, balance_data)
            
            # Save Cash Flow Statement
            if financials.get('cash_flow') is not None and not financials['cash_flow'].empty:
                cashflow_data = []
                for line_item in financials['cash_flow'].index:
                    for date_col in financials['cash_flow'].columns:
                        value = financials['cash_flow'].loc[line_item, date_col]
                        if pd.notna(value):
                            cashflow_data.append({
                                'symbol': symbol,
                                'date': date_col,
                                'line_item': str(line_item),
                                'value': float(value),
                                'created_at': datetime.utcnow()
                            })
                
                if cashflow_data:
                    session.bulk_insert_mappings(CashFlowStatement, cashflow_data)
            
            session.commit()
            logger.info(f"Saved financial statements for {symbol}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving financial statements: {e}")
            return False
        finally:
            session.close()
    
    def get_financial_statements(self, symbol):
        """Retrieve financial statements from database"""
        session = self.get_session()
        try:
            financials = {
                'income_stmt': None,
                'balance_sheet': None,
                'cash_flow': None
            }
            
            logger.info(f"Retrieving financial statements for {symbol}")
            
            # Get Income Statement
            income_records = session.query(IncomeStatement).filter(IncomeStatement.symbol == symbol).all()
            logger.info(f"Found {len(income_records)} income statement records for {symbol}")
            if income_records:
                income_df = self._build_financial_dataframe(income_records)
                if income_df is not None and not income_df.empty:
                    financials['income_stmt'] = income_df
                    logger.info(f"Built income statement DataFrame with shape {income_df.shape}")
                else:
                    logger.warning(f"Failed to build income statement DataFrame for {symbol}")
            
            # Get Balance Sheet
            balance_records = session.query(BalanceSheet).filter(BalanceSheet.symbol == symbol).all()
            logger.info(f"Found {len(balance_records)} balance sheet records for {symbol}")
            if balance_records:
                balance_df = self._build_financial_dataframe(balance_records)
                if balance_df is not None and not balance_df.empty:
                    financials['balance_sheet'] = balance_df
                    logger.info(f"Built balance sheet DataFrame with shape {balance_df.shape}")
                else:
                    logger.warning(f"Failed to build balance sheet DataFrame for {symbol}")
            
            # Get Cash Flow Statement
            cashflow_records = session.query(CashFlowStatement).filter(CashFlowStatement.symbol == symbol).all()
            logger.info(f"Found {len(cashflow_records)} cash flow records for {symbol}")
            if cashflow_records:
                cashflow_df = self._build_financial_dataframe(cashflow_records)
                if cashflow_df is not None and not cashflow_df.empty:
                    financials['cash_flow'] = cashflow_df
                    logger.info(f"Built cash flow DataFrame with shape {cashflow_df.shape}")
                else:
                    logger.warning(f"Failed to build cash flow DataFrame for {symbol}")
            
            # Return financials if at least one statement was retrieved
            if any(v is not None for v in financials.values()):
                logger.info(f"Successfully retrieved financial statements for {symbol}")
                return financials
            else:
                logger.warning(f"No financial statements found for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving financial statements for {symbol}: {e}")
            return None
        finally:
            session.close()
    
    def _build_financial_dataframe(self, records):
        """Helper method to build DataFrame from financial records"""
        if not records:
            return None
        
        try:
            data = {}
            for record in records:
                if record.line_item not in data:
                    data[record.line_item] = {}
                data[record.line_item][record.date] = record.value
            
            if not data:
                return None
                
            df = pd.DataFrame(data).T  # Transpose to have line items as rows
            # Sort columns by date descending and ensure proper data types
            df = df.sort_index(axis=1, ascending=False)
            
            # Convert numeric columns to float where possible
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors='ignore')
                except:
                    pass
                    
            return df
        except Exception as e:
            logger.error(f"Error building financial dataframe: {e}")
            return None
    
    def delete_stock_data(self, symbol):
        """Delete all data for a specific stock symbol"""
        session = self.get_session()
        try:
            session.query(StockData).filter(StockData.symbol == symbol).delete()
            session.query(StockInfo).filter(StockInfo.symbol == symbol).delete()
            session.query(EarningsData).filter(EarningsData.symbol == symbol).delete()
            session.query(IncomeStatement).filter(IncomeStatement.symbol == symbol).delete()
            session.query(BalanceSheet).filter(BalanceSheet.symbol == symbol).delete()
            session.query(CashFlowStatement).filter(CashFlowStatement.symbol == symbol).delete()
            session.commit()
            logger.info(f"Deleted all data for {symbol}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting stock data: {e}")
            return False
        finally:
            session.close()
    
    def add_to_portfolio(self, symbol):
        """Add a stock symbol to the portfolio"""
        session = self.get_session()
        try:
            # Check if symbol already exists
            existing = session.query(Portfolio).filter(Portfolio.symbol == symbol).first()
            if existing:
                logger.info(f"{symbol} already exists in portfolio")
                return True
            
            # Add new symbol
            portfolio_item = Portfolio(symbol=symbol)
            session.add(portfolio_item)
            session.commit()
            logger.info(f"Added {symbol} to portfolio")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding {symbol} to portfolio: {e}")
            return False
        finally:
            session.close()
    
    def remove_from_portfolio(self, symbol):
        """Remove a stock symbol from the portfolio"""
        session = self.get_session()
        try:
            session.query(Portfolio).filter(Portfolio.symbol == symbol).delete()
            session.commit()
            logger.info(f"Removed {symbol} from portfolio")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error removing {symbol} from portfolio: {e}")
            return False
        finally:
            session.close()
    
    def get_portfolio(self):
        """Retrieve all stock symbols in the portfolio"""
        session = self.get_session()
        try:
            records = session.query(Portfolio).order_by(Portfolio.added_at).all()
            symbols = [record.symbol for record in records]
            logger.info(f"Retrieved {len(symbols)} symbols from portfolio")
            return symbols
        except Exception as e:
            logger.error(f"Error retrieving portfolio: {e}")
            return []
        finally:
            session.close()
    
    def save_portfolio(self, symbols):
        """Replace entire portfolio with new list of symbols"""
        session = self.get_session()
        try:
            # Clear existing portfolio
            session.query(Portfolio).delete()
            
            # Add all symbols
            for symbol in symbols:
                portfolio_item = Portfolio(symbol=symbol)
                session.add(portfolio_item)
            
            session.commit()
            logger.info(f"Saved portfolio with {len(symbols)} symbols")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving portfolio: {e}")
            return False
        finally:
            session.close()