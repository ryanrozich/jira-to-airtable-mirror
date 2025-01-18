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
        load_dotenv()

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

        logger.info(f"\n✅ Successfully retrieved {len(issues)} issues from Jira")

        # Load field mappings
        field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
        if not field_map:
            logger.error("❌ No field mappings found in JIRA_TO_AIRTABLE_FIELD_MAP")
            return False

        # Test data transformation
        logger.info("\nTesting data transformation (dry run):")
        for issue in issues:
            logger.info(f"\nIssue {issue.key}:")
            record = {}
            for jira_field, airtable_field in field_map.items():
                try:
                    value = getattr(issue.fields, jira_field, None)
                    record[airtable_field] = str(value) if value else None
                    logger.info(f"  {jira_field} -> {airtable_field}: {record[airtable_field]}")
                except AttributeError:
                    logger.warning(f"  ⚠️ Warning: Field '{jira_field}' not found in Jira issue")

        logger.info("\n✅ Data transformation test completed successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Sync test failed: {str(e)}")
        return False


if __name__ == '__main__':
    sys.exit(0 if test_sync() else 1)
