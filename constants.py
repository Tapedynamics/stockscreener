#!/usr/bin/env python3
"""
Constants and configuration values for Stock Screener
"""

# Portfolio Configuration
TAKE_PROFIT_SIZE = 3
HOLD_SIZE = 10
BUFFER_SIZE = 2
TOTAL_PORTFOLIO_SIZE = 15

# Financial Defaults
DEFAULT_INITIAL_VALUE = 150000
DEFAULT_PERFORMANCE_DAYS = 7

# Scheduler Defaults
DEFAULT_SCHEDULER_DAY = 'mon'
DEFAULT_SCHEDULER_TIME = '19:00'
DEFAULT_SCHEDULER_TIMEZONE = 'Europe/Rome'

# HTTP Configuration
HTTP_REQUEST_TIMEOUT = 10  # seconds
HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# API Rate Limiting
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Database Configuration
DB_PATH = 'portfolio.db'
DB_BATCH_SIZE = 100

# Settings Keys (Whitelist)
VALID_SETTINGS_KEYS = {
    'scheduler_day',
    'scheduler_time',
    'scheduler_timezone',
    'initial_value',
    'take_profit_count',
    'hold_count',
    'buffer_count',
    'notify_rebalance',
    'notify_changes'
}

# Settings Validation Rules
SETTINGS_VALIDATION = {
    'scheduler_day': {
        'type': str,
        'allowed_values': ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    },
    'scheduler_time': {
        'type': str,
        'pattern': r'^\d{2}:\d{2}$'  # HH:MM format
    },
    'scheduler_timezone': {
        'type': str,
        'allowed_values': ['Europe/Rome', 'America/New_York', 'America/Los_Angeles', 'Asia/Tokyo', 'UTC']
    },
    'initial_value': {
        'type': (int, float),
        'min': 1000,
        'max': 10000000
    },
    'take_profit_count': {
        'type': int,
        'min': 1,
        'max': 10
    },
    'hold_count': {
        'type': int,
        'min': 5,
        'max': 20
    },
    'buffer_count': {
        'type': int,
        'min': 1,
        'max': 5
    },
    'notify_rebalance': {
        'type': str,
        'allowed_values': ['true', 'false']
    },
    'notify_changes': {
        'type': str,
        'allowed_values': ['true', 'false']
    }
}

# Logging Configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'

# Cache Configuration
CACHE_TTL = 3600  # 1 hour in seconds
PRICE_CACHE_ENABLED = True
