#!/usr/bin/env python3
import os
import sys
import json
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def validate_config():  # noqa: C901
    """Validate configuration from environment variables."""
    try:
        load_dotenv()

        # Validate Jira settings
        required_jira = ['JIRA_SERVER', 'JIRA_USERNAME', 'JIRA_API_TOKEN', 'JIRA_PROJECT_KEY']
        missing_jira = [
            field for field in required_jira
            if not os.getenv(field)
        ]

        if missing_jira:
            logger.error("❌ Missing required Jira settings:")
            for field in missing_jira:
                logger.error(f"  - {field}")
            return False

        # Validate Airtable settings
        required_airtable = ['AIRTABLE_API_KEY', 'AIRTABLE_BASE_ID', 'AIRTABLE_TABLE_NAME']
        missing_airtable = [
            field for field in required_airtable
            if not os.getenv(field)
        ]

        if missing_airtable:
            logger.error("❌ Missing required Airtable settings:")
            for field in missing_airtable:
                logger.error(f"  - {field}")
            return False

        # Validate field mappings
        try:
            field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
        except json.JSONDecodeError:
            logger.error("❌ Invalid JSON in JIRA_TO_AIRTABLE_FIELD_MAP")
            return False

        if not field_map:
            logger.error("❌ No field mappings found in JIRA_TO_AIRTABLE_FIELD_MAP")
            return False

        logger.info("✅ Configuration is valid")
        return True

    except Exception as e:
        logger.error(f"❌ Config validation failed: {str(e)}")
        return False


if __name__ == '__main__':
    sys.exit(0 if validate_config() else 1)
