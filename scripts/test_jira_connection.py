#!/usr/bin/env python3
import os
import sys
import logging
from dotenv import load_dotenv
from jira import JIRA

logger = logging.getLogger(__name__)


def test_jira_connection():
    """Test connection to Jira."""
    try:
        load_dotenv()

        # Initialize Jira client
        jira = JIRA(
            server=os.getenv('JIRA_SERVER'),
            basic_auth=(os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN'))
        )

        # Test connection by getting server info
        server_info = jira.server_info()
        logger.info(f"✅ Successfully connected to Jira {server_info['version']}")

        # Test JQL query
        jql = os.getenv('JIRA_JQL_FILTER', '')
        issues = jira.search_issues(jql, maxResults=1)

        if issues:
            logger.info(f"✅ Successfully retrieved issue {issues[0].key}")
        else:
            logger.warning("⚠️ No issues found with current JQL filter")

        return True

    except Exception as e:
        logger.error(f"❌ Connection test failed: {str(e)}")
        return False


if __name__ == '__main__':
    sys.exit(0 if test_jira_connection() else 1)
