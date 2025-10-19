#!/usr/bin/env python3
"""
Utility functions for Stock Screener
Includes validation, API helpers, and common functions
"""

from flask import jsonify
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union
import re
import logging
from constants import SETTINGS_VALIDATION, VALID_SETTINGS_KEYS

logger = logging.getLogger(__name__)


# ========================================
# API Response Helpers
# ========================================

def api_response(
    success: bool,
    data: Any = None,
    error: Optional[str] = None,
    status: int = 200
) -> Tuple[Dict, int]:
    """
    Standardized API response format

    Args:
        success: Whether the operation was successful
        data: Response data (optional)
        error: Error message if success=False (optional)
        status: HTTP status code

    Returns:
        Tuple of (response_dict, status_code)
    """
    response = {
        'success': success,
        'data': data,
        'error': error,
        'timestamp': datetime.utcnow().isoformat()
    }

    return jsonify(response), status


def api_error(error_message: str, status: int = 500) -> Tuple[Dict, int]:
    """
    Shorthand for error responses

    Args:
        error_message: Error message to return
        status: HTTP status code

    Returns:
        Tuple of (response_dict, status_code)
    """
    return api_response(False, error=error_message, status=status)


def api_success(data: Any = None, status: int = 200) -> Tuple[Dict, int]:
    """
    Shorthand for success responses

    Args:
        data: Response data
        status: HTTP status code

    Returns:
        Tuple of (response_dict, status_code)
    """
    return api_response(True, data=data, status=status)


# ========================================
# Input Validation
# ========================================

def validate_setting(key: str, value: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a single setting key-value pair

    Args:
        key: Setting key
        value: Setting value

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if key is in whitelist
    if key not in VALID_SETTINGS_KEYS:
        return False, f"Invalid setting key: {key}"

    # Get validation rules
    if key not in SETTINGS_VALIDATION:
        return True, None  # No specific validation rules

    rules = SETTINGS_VALIDATION[key]

    # Type validation
    if 'type' in rules:
        expected_type = rules['type']

        # Handle multiple allowed types
        if isinstance(expected_type, tuple):
            try:
                # Try converting to int/float
                if int in expected_type or float in expected_type:
                    value_converted = float(value) if '.' in str(value) else int(value)
                    if not isinstance(value_converted, expected_type):
                        return False, f"{key} must be of type {expected_type}"
            except (ValueError, TypeError):
                return False, f"{key} must be a number"
        elif expected_type == str:
            if not isinstance(value, str):
                return False, f"{key} must be a string"

    # Pattern validation (regex)
    if 'pattern' in rules:
        pattern = rules['pattern']
        if not re.match(pattern, str(value)):
            return False, f"{key} has invalid format"

    # Allowed values validation
    if 'allowed_values' in rules:
        if str(value).lower() not in rules['allowed_values']:
            return False, f"{key} must be one of: {', '.join(rules['allowed_values'])}"

    # Min/Max validation for numbers
    if 'min' in rules or 'max' in rules:
        try:
            num_value = float(value)

            if 'min' in rules and num_value < rules['min']:
                return False, f"{key} must be >= {rules['min']}"

            if 'max' in rules and num_value > rules['max']:
                return False, f"{key} must be <= {rules['max']}"

        except (ValueError, TypeError):
            return False, f"{key} must be a valid number"

    return True, None


def validate_settings(settings: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, str]]:
    """
    Validate multiple settings at once

    Args:
        settings: Dictionary of settings to validate

    Returns:
        Tuple of (all_valid, first_error_message, sanitized_settings)
    """
    sanitized = {}

    for key, value in settings.items():
        is_valid, error = validate_setting(key, value)

        if not is_valid:
            return False, error, {}

        # Sanitize the value
        sanitized[key] = sanitize_string(str(value))

    return True, None, sanitized


def sanitize_string(value: str, max_length: int = 255) -> str:
    """
    Sanitize a string value

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        value = str(value)

    # Remove potentially dangerous characters
    # Keep alphanumeric, spaces, and common punctuation
    sanitized = re.sub(r'[^\w\s:.,/\-]', '', value)

    # Trim to max length
    sanitized = sanitized[:max_length]

    # Remove leading/trailing whitespace
    sanitized = sanitized.strip()

    return sanitized


# ========================================
# Data Validation
# ========================================

def validate_ticker(ticker: str) -> bool:
    """
    Validate a stock ticker symbol

    Args:
        ticker: Stock ticker symbol

    Returns:
        True if valid, False otherwise
    """
    if not ticker or not isinstance(ticker, str):
        return False

    # Ticker should be 1-5 uppercase letters, optionally with . or -
    pattern = r'^[A-Z]{1,5}(\.[A-Z]{1,2})?(-[A-Z]{1,2})?$'
    return bool(re.match(pattern, ticker.upper()))


def validate_portfolio_basket(basket: Dict[str, list]) -> Tuple[bool, Optional[str]]:
    """
    Validate a portfolio basket structure

    Args:
        basket: Portfolio basket dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_keys = ['take_profit', 'hold', 'buffer']

    # Check required keys
    for key in required_keys:
        if key not in basket:
            return False, f"Missing required key: {key}"

        if not isinstance(basket[key], list):
            return False, f"{key} must be a list"

    # Validate tickers
    all_tickers = basket['take_profit'] + basket['hold'] + basket['buffer']

    for ticker in all_tickers:
        if not validate_ticker(ticker):
            return False, f"Invalid ticker: {ticker}"

    # Check for duplicates
    if len(all_tickers) != len(set(all_tickers)):
        return False, "Duplicate tickers found in basket"

    return True, None


# ========================================
# Retry Logic
# ========================================

def retry_on_failure(func, max_retries: int = 3, delay: float = 1.0):
    """
    Decorator for retrying failed operations

    Args:
        func: Function to retry
        max_retries: Maximum number of retries
        delay: Delay between retries in seconds

    Returns:
        Decorated function
    """
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        last_exception = None

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")

                if attempt < max_retries - 1:
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed")

        raise last_exception

    return wrapper


# ========================================
# Environment Variable Helpers
# ========================================

def get_env_var(key: str, default: Any = None, cast_type: type = str) -> Any:
    """
    Get environment variable with type casting

    Args:
        key: Environment variable key
        default: Default value if not found
        cast_type: Type to cast the value to

    Returns:
        Environment variable value or default
    """
    import os

    value = os.getenv(key)

    if value is None:
        return default

    try:
        if cast_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        elif cast_type == int:
            return int(value)
        elif cast_type == float:
            return float(value)
        else:
            return cast_type(value)
    except (ValueError, TypeError):
        logger.warning(f"Failed to cast {key}={value} to {cast_type}, using default")
        return default


# ========================================
# Time Formatting
# ========================================

def format_time_ago(timestamp: Union[str, datetime]) -> str:
    """
    Format a timestamp as 'time ago' string

    Args:
        timestamp: Timestamp to format

    Returns:
        Formatted string like "5 min ago"
    """
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return timestamp

    now = datetime.utcnow()

    # Ensure timestamp is timezone-naive for comparison
    if timestamp.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=None)

    delta = now - timestamp
    seconds = delta.total_seconds()

    if seconds < 60:
        return 'Just now'
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f'{minutes} min ago'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours} hr ago'
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f'{days} day{"s" if days > 1 else ""} ago'
    else:
        return timestamp.strftime('%Y-%m-%d')
