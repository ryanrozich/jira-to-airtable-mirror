#!/usr/bin/env python3
import os
import sys
import logging
from dotenv import load_dotenv
from pyairtable import Api

logger = logging.getLogger(__name__)


def test_airtable_connection():
    """Test connection to Airtable."""
    try:
        load_dotenv()

        # Initialize Airtable client
        api = Api(os.getenv('AIRTABLE_API_KEY'))
        base_id = os.getenv('AIRTABLE_BASE_ID')
        table_name = os.getenv('AIRTABLE_TABLE_NAME')

        # Get table metadata
        table_info = api.request(
            method="GET",
            url=f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
        )

        # Find our table
        table_meta = None
        for table in table_info["tables"]:
            if table["name"] == table_name:
                table_meta = table
                break

        if not table_meta:
            logger.error(f"❌ Table '{table_name}' not found in Airtable base")
            return False

        logger.info("✅ Successfully connected to Airtable")
        return True

    except Exception as e:
        logger.error(f"❌ Connection test failed: {str(e)}")
        return False


if __name__ == '__main__':
    sys.exit(0 if test_airtable_connection() else 1)
