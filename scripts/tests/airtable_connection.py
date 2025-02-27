#!/usr/bin/env python3
import os
import sys
import logging
from dotenv import load_dotenv
from pyairtable import Table

logger = logging.getLogger(__name__)


def test_airtable_connection():
    """Test connection to Airtable."""
    try:
        load_dotenv(override=True)
        
        # Get Airtable configuration
        base_id = os.getenv('AIRTABLE_BASE_ID')
        table_name = os.getenv('AIRTABLE_TABLE_NAME')
        api_key = os.getenv('AIRTABLE_API_KEY')
        
        if not all([base_id, table_name, api_key]):
            logger.error("❌ Missing required Airtable configuration")
            return False
        
        # Initialize Airtable client and test connection
        table = Table(api_key, base_id, table_name)
        table.first()
        return True
        
    except Exception as e:
        logger.error(f"❌ Airtable connection failed: {str(e)}")
        return False


def main():
    """Test Airtable connection."""
    try:
        return test_airtable_connection()
    except Exception as e:
        print(f"Error testing Airtable connection: {str(e)}")
        return False


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
