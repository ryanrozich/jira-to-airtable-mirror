#!/usr/bin/env python3
import os
import sys
import json
import logging
from dotenv import load_dotenv
from pyairtable import Api

logger = logging.getLogger(__name__)


def validate_tracking_fields():  # noqa: C901
    """Validate tracking field configuration."""
    try:
        load_dotenv()

        # Initialize Airtable client
        api = Api(os.getenv('AIRTABLE_API_KEY'))
        base_id = os.getenv('AIRTABLE_BASE_ID')
        table_name = os.getenv('AIRTABLE_TABLE_NAME')

        # Get tracking field configuration
        tracking_fields = json.loads(os.getenv('TRACKING_FIELDS', '{}'))
        if not tracking_fields:
            logger.info("No tracking fields configured")
            return True

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
            logger.error(f"Table '{table_name}' not found in Airtable base")
            return False

        # Get field IDs and names
        field_ids = {field["id"] for field in table_meta["fields"]}
        field_names = {field["id"]: field["name"] for field in table_meta["fields"]}

        # Check each tracking field
        invalid_fields = []
        for field_id, config in tracking_fields.items():
            if field_id not in field_ids:
                field_name = field_names.get(field_id, field_id)
                invalid_fields.append(f"{field_name} ({field_id})")
                continue

            # Check if history field exists when tracking changes
            if config.get('track_changes', False):
                history_field_id = f"{field_id}_history"
                if history_field_id not in field_ids:
                    field_name = field_names.get(field_id, field_id)
                    invalid_fields.append(
                        f"{field_name} ({field_id}) - missing history field"
                    )

        if invalid_fields:
            logger.error("The following tracking fields are invalid:")
            for field in invalid_fields:
                logger.error(f"  - {field}")
            logger.info("Available fields in table:")
            for field_id, name in field_names.items():
                logger.info(f"  - {name} ({field_id})")
            return False

        logger.info("All tracking fields are valid")
        return True

    except Exception as e:
        logger.error(f"Failed to validate tracking fields: {str(e)}")
        return False


if __name__ == '__main__':
    sys.exit(0 if validate_tracking_fields() else 1)
