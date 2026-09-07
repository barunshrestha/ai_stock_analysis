"""Tests for portfolio CSV import parsing."""

from backend.services.portfolio_import_service import parse_portfolio_csv


class TestParsePortfolioCsv:
    def test_one_column_no_header(self):
        symbols, err = parse_portfolio_csv(b"AAPL\nMSFT\n")
        assert err is None
        assert symbols == ["AAPL", "MSFT"]

    def test_symbol_header(self):
        content = b"symbol\nAAPL\nGOOGL\n"
        symbols, err = parse_portfolio_csv(content)
        assert err is None
        assert symbols == ["AAPL", "GOOGL"]

    def test_ticker_header(self):
        content = b"ticker,notes\nNVDA,chip\n"
        symbols, err = parse_portfolio_csv(content)
        assert err is None
        assert symbols == ["NVDA"]

    def test_deduplicates(self):
        symbols, err = parse_portfolio_csv(b"symbol\nAAPL\naapl\n")
        assert err is None
        assert symbols == ["AAPL"]

    def test_empty_file(self):
        symbols, err = parse_portfolio_csv(b"")
        assert symbols == []
        assert err is not None
