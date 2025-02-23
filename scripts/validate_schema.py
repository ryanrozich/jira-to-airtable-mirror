#!/usr/bin/env python3
import os
import sys
import json
import logging
from dotenv import load_dotenv
from pyairtable import Api


logger = logging.getLogger(__name__)


def validate_schema() -> bool:  # noqa: C901
    """Validate that all required fields exist in Airtable with correct IDs."""
    try:
        # Force override of existing environment variables
        load_dotenv(override=True)

        # Debug: Print current working directory and .env loading
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Looking for .env file in: {os.path.abspath('.env')}")

        # Initialize Airtable client
        api = Api(os.getenv('AIRTABLE_API_KEY'))
        base_id = os.getenv('AIRTABLE_BASE_ID')
        table_name = os.getenv('AIRTABLE_TABLE_NAME')
        
        # Debug: Print the actual table name being used
        logger.info(f"Using table name from env: {table_name}")

        # Get field mappings
        field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
        if not field_map:
            logger.error("❌ No field mappings found in JIRA_TO_AIRTABLE_FIELD_MAP")
            return False

        # Get table metadata
        table_info = api.request(
            method="GET",
            url=f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
        )

        # Print available tables
        logger.info("Available tables in base:")
        for table in table_info["tables"]:
            logger.info(f"  - {table['name']}")

        # Find our table
        table_meta = None
        for table in table_info["tables"]:
            if table["name"] == table_name:
                table_meta = table
                break

        if not table_meta:
            logger.error(f"❌ Table '{table_name}' not found in Airtable base")
            return False

        # Get field IDs and names
        field_ids = {field["id"] for field in table_meta["fields"]}
        field_names = {field["id"]: field["name"] for field in table_meta["fields"]}

        # Check for missing fields
        missing_fields = []
        for jira_field, mapping in field_map.items():
            field_id = mapping.get('airtable_field_id')
            if not field_id:
                missing_fields.append(f"{jira_field} -> missing airtable_field_id")
                continue
            if field_id not in field_ids:
                field_name = field_names.get(field_id, field_id)
                missing_fields.append(f"{jira_field} -> {field_name} ({field_id})")

        if missing_fields:
            logger.error("❌ The following field mappings are invalid:")
            for field in missing_fields:
                logger.error(f"  - {field}")
            logger.info("\nAvailable fields in table:")
            for field_id, name in field_names.items():
                logger.info(f"  - {name} ({field_id})")
            return False

        logger.info("✅ All field mappings are valid")
        return True

    except Exception as e:
        logger.error(f"❌ Schema validation failed: {str(e)}")
        return False


if __name__ == '__main__':
    sys.exit(0 if validate_schema() else 1)
