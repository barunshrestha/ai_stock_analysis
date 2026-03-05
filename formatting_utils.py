"""
Global formatting utilities for the Stock Financial Analysis application.
These functions provide consistent number formatting throughout the application.
"""

import pandas as pd


def format_number(num, currency=True, decimal_places=2):
    """
    Global function to format numbers with K, M, B, T suffixes
    
    Args:
        num: Number to format
        currency: Whether to include $ symbol (default: True)
        decimal_places: Number of decimal places (default: 2)
    
    Returns:
        Formatted string with appropriate suffix
        
    Examples:
        format_number(1234567) -> "$1.23M"
        format_number(1234567, currency=False) -> "1.23M"
        format_number(1234567, decimal_places=1) -> "$1.2M"
    """
    if pd.isna(num) or num is None:
        return "N/A"
    
    try:
        num = float(num)
        sign = "-" if num < 0 else ""
        abs_num = abs(num)
        currency_symbol = "$" if currency else ""
        
        if abs_num >= 1_000_000_000_000:
            return f"{sign}{currency_symbol}{abs_num/1_000_000_000_000:.{decimal_places}f}T"
        elif abs_num >= 1_000_000_000:
            return f"{sign}{currency_symbol}{abs_num/1_000_000_000:.{decimal_places}f}B"
        elif abs_num >= 1_000_000:
            return f"{sign}{currency_symbol}{abs_num/1_000_000:.{decimal_places}f}M"
        elif abs_num >= 1_000:
            return f"{sign}{currency_symbol}{abs_num/1_000:.{decimal_places}f}K"
        else:
            return f"{sign}{currency_symbol}{abs_num:.{decimal_places}f}"
    except (ValueError, TypeError):
        return "N/A"


def format_percentage(num, decimal_places=2):
    """
    Format numbers as percentage
    
    Args:
        num: Number to format as percentage
        decimal_places: Number of decimal places (default: 2)
    
    Returns:
        Formatted percentage string
        
    Examples:
        format_percentage(25.5) -> "25.50%"
        format_percentage(25.5, 1) -> "25.5%"
    """
    if pd.isna(num) or num is None:
        return "N/A"
    
    try:
        return f"{float(num):.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_volume(num):
    """
    Format volume numbers without currency symbol
    
    Args:
        num: Volume number to format
    
    Returns:
        Formatted volume string
        
    Examples:
        format_volume(1234567) -> "1M"
        format_volume(1234) -> "1K"
    """
    return format_number(num, currency=False, decimal_places=0)


def format_price(num, decimal_places=2):
    """
    Format price with currency symbol and appropriate precision
    
    Args:
        num: Price to format
        decimal_places: Number of decimal places (default: 2)
    
    Returns:
        Formatted price string
        
    Examples:
        format_price(123.456) -> "$123.46"
        format_price(123.456, 3) -> "$123.456"
    """
    if pd.isna(num) or num is None:
        return "N/A"
    
    try:
        num = float(num)
        return f"${num:.{decimal_places}f}"
    except (ValueError, TypeError):
        return "N/A"


def format_ratio(num, decimal_places=2):
    """
    Format financial ratios
    
    Args:
        num: Ratio to format
        decimal_places: Number of decimal places (default: 2)
    
    Returns:
        Formatted ratio string
        
    Examples:
        format_ratio(15.67) -> "15.67"
        format_ratio(15.67, 1) -> "15.7"
    """
    if pd.isna(num) or num is None:
        return "N/A"
    
    try:
        return f"{float(num):.{decimal_places}f}"
    except (ValueError, TypeError):
        return "N/A"


def format_currency_large(num, decimal_places=2):
    """
    Format large currency amounts with appropriate suffixes
    
    Args:
        num: Large currency amount to format
        decimal_places: Number of decimal places (default: 2)
    
    Returns:
        Formatted currency string with suffix
        
    Examples:
        format_currency_large(1500000000) -> "$1.50B"
        format_currency_large(750000) -> "$750.00K"
    """
    return format_number(num, currency=True, decimal_places=decimal_places)


def format_change_percentage(num, decimal_places=2):
    """
    Format percentage change with appropriate sign
    
    Args:
        num: Percentage change to format
        decimal_places: Number of decimal places (default: 2)
    
    Returns:
        Formatted percentage change string with sign
        
    Examples:
        format_change_percentage(5.67) -> "+5.67%"
        format_change_percentage(-3.21) -> "-3.21%"
    """
    if pd.isna(num) or num is None:
        return "N/A"
    
    try:
        num = float(num)
        sign = "+" if num >= 0 else ""
        return f"{sign}{num:.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_financial_statement_value(num, decimal_places=2):
    """
    Format financial statement values with enhanced readability
    Handles negative values appropriately for financial statements
    
    Args:
        num: Financial value to format
        decimal_places: Number of decimal places (default: 2)
    
    Returns:
        Formatted financial value string
        
    Examples:
        format_financial_statement_value(1500000000) -> "$1.50B"
        format_financial_statement_value(-500000000) -> "($500.00M)"
    """
    if pd.isna(num) or num is None:
        return "N/A"
    
    try:
        num = float(num)
        if num < 0:
            # Use parentheses for negative values in financial statements
            abs_num = abs(num)
            formatted = format_number(abs_num, currency=True, decimal_places=decimal_places)
            return f"({formatted[1:]})"  # Remove $ and wrap in parentheses
        else:
            return format_number(num, currency=True, decimal_places=decimal_places)
    except (ValueError, TypeError):
        return "N/A"