#!/usr/bin/env python3
import os
import sys
import json
from dotenv import load_dotenv
from jira import JIRA
from pyairtable import Api

def test_sync():
    """Test sync process without writing to Airtable."""
    load_dotenv()
    
    try:
        # Initialize Jira client
        jira = JIRA(
            server=os.getenv('JIRA_SERVER'),
            basic_auth=(os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN'))
        )
        
        # Get Jira issues
        jql = os.getenv('JIRA_JQL_FILTER', f"project = {os.getenv('JIRA_PROJECT_KEY')}")
        issues = jira.search_issues(jql, maxResults=5)
        
        if not issues:
            print("⚠️ No issues found with current JQL filter")
            return True
        
        print(f"\n✅ Successfully retrieved {len(issues)} issues from Jira")
        
        # Initialize Airtable client
        api = Api(os.getenv('AIRTABLE_API_KEY'))
        base = api.base(os.getenv('AIRTABLE_BASE_ID'))
        table = base.table(os.getenv('AIRTABLE_TABLE_NAME'))
        
        # Load field mappings
        field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
        if not field_map:
            print("❌ No field mappings found in JIRA_TO_AIRTABLE_FIELD_MAP")
            return False
        
        # Test data transformation
        print("\nTesting data transformation (dry run):")
        for issue in issues:
            print(f"\nIssue {issue.key}:")
            record = {}
            for jira_field, airtable_field in field_map.items():
                try:
                    value = getattr(issue.fields, jira_field, None)
                    record[airtable_field] = str(value) if value else None
                    print(f"  {jira_field} -> {airtable_field}: {record[airtable_field]}")
                except AttributeError:
                    print(f"  ⚠️ Warning: Field '{jira_field}' not found in Jira issue")
        
        print("\n✅ Data transformation test completed successfully")
        return True
    except Exception as e:
        print(f"❌ Sync test failed: {str(e)}")
        return False

if __name__ == '__main__':
    sys.exit(0 if test_sync() else 1)
