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
        load_dotenv(override=True)

        # Initialize Jira client
        jira = JIRA(
            server=os.getenv('JIRA_SERVER'),
            basic_auth=(os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN'))
        )

        # Test connection by getting server info and an issue
        jira.server_info()
        jql = os.getenv('JIRA_JQL_FILTER', '')
        # Just check if search works, we don't need the results
        jira.search_issues(jql, maxResults=1)
        
        return True

    except Exception as e:
        logger.error(f"❌ Jira connection failed: {str(e)}")
        return False


def main():
    """Test Jira connection."""
    try:
        return test_jira_connection()
    except Exception as e:
        print(f"Error testing Jira connection: {str(e)}")
        return False

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
