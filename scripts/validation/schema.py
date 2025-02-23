#!/usr/bin/env python3
import os
import sys
import json
import logging
from dotenv import load_dotenv
from pyairtable import Api


logger = logging.getLogger(__name__)


def validate_schema() -> bool:  
    """Validate Airtable schema against field mappings."""
    try:
        load_dotenv(override=True)
        
        # Initialize Airtable client
        base_id = os.getenv('AIRTABLE_BASE_ID')
        table_name = os.getenv('AIRTABLE_TABLE_NAME')
        api_key = os.getenv('AIRTABLE_API_KEY')
        
        if not all([base_id, table_name, api_key]):
            logger.error("❌ Missing required Airtable configuration")
            return False
            
        # Get table metadata
        api = Api(api_key)
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

        # Load and validate field mappings
        field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
        if not field_map:
            logger.error("❌ No field mappings found in JIRA_TO_AIRTABLE_FIELD_MAP")
            return False

        # Check that all mapped fields exist in Airtable
        airtable_fields = {field['name']: field['id'] for field in table_meta['fields']}
        for jira_field, mapping in field_map.items():
            airtable_field = mapping.get('airtable_field_id')
            if airtable_field not in airtable_fields.values():
                logger.error(f"❌ Mapped field '{airtable_field}' not found in Airtable schema")
                return False

        logger.info("   ✅ All field mappings are valid")
        return True

    except Exception as e:
        logger.error(f"❌ Schema validation failed: {str(e)}")
        return False


def main():
    """Run Airtable schema validation."""
    try:
        return validate_schema()
    except Exception as e:
        logger.error(f"Error validating schema: {str(e)}")
        return False

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
