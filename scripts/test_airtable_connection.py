#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from pyairtable import Api

def test_airtable_connection():
    """Test Airtable connection and table access."""
    load_dotenv()
    
    # Required environment variables
    required_vars = ['AIRTABLE_API_KEY', 'AIRTABLE_BASE_ID', 'AIRTABLE_TABLE_NAME']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:", ", ".join(missing_vars))
        sys.exit(1)
    
    try:
        # Initialize Airtable client
        api = Api(os.getenv('AIRTABLE_API_KEY'))
        base = api.base(os.getenv('AIRTABLE_BASE_ID'))
        table = base.table(os.getenv('AIRTABLE_TABLE_NAME'))
        
        # Test connection by getting table schema
        schema = table.schema
        print(f"✅ Successfully connected to Airtable table {os.getenv('AIRTABLE_TABLE_NAME')}")
        print(f"✅ Found {len(schema['fields'])} fields in table")
        
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Airtable: {str(e)}")
        return False

if __name__ == '__main__':
    sys.exit(0 if test_airtable_connection() else 1)
