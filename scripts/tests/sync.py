#!/usr/bin/env python3
import os
import sys
import json
import logging
from dotenv import load_dotenv
from jira import JIRA

logger = logging.getLogger(__name__)

def test_sync():
    """Test sync process without writing to Airtable."""
    try:
        load_dotenv(override=True)

        # Initialize Jira client
        jira = JIRA(
            server=os.getenv('JIRA_SERVER'),
            basic_auth=(os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN'))
        )

        # Test Jira query
        jql = os.getenv('JIRA_JQL_FILTER', '')
        issues = jira.search_issues(jql, maxResults=5)

        if not issues:
            logger.warning("⚠️ No issues found with current JQL filter")
            return True

        # Load field mappings
        field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
        if not field_map:
            logger.error("❌ No field mappings found in JIRA_TO_AIRTABLE_FIELD_MAP")
            return False

        # Test data transformation
        for issue in issues:
            record = {}
            for jira_field, mapping in field_map.items():
                try:
                    value = getattr(issue.fields, jira_field, None)
                    airtable_field = mapping.get('airtable_field_id')
                    record[airtable_field] = str(value) if value else None
                except AttributeError:
                    logger.debug(f"Field '{jira_field}' not found in Jira issue {issue.key}")

        return True

    except Exception as e:
        logger.error(f"❌ Sync test failed: {str(e)}")
        return False


def main():
    """Test sync functionality."""
    try:
        return test_sync()
    except Exception as e:
        logger.error(f"Error testing sync functionality: {str(e)}")
        return False


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
