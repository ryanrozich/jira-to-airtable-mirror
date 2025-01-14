#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from jira import JIRA
from pyairtable import Api
import sys

def test_jira_connection(config):
    print("\nTesting Jira connection...")
    try:
        jira = JIRA(
            server=config['jira_server'],
            basic_auth=(config['jira_username'], config['jira_api_token'])
        )
        
        # Test by fetching project
        project = jira.project(config['jira_project_key'])
        print(f"✅ Successfully connected to Jira")
        print(f"Project details: {project.key} - {project.name}")
        
        # Test JQL query
        issues = jira.search_issues(config['jira_jql_filter'], maxResults=1)
        print(f"✅ JQL query successful")
        print(f"Found {len(issues)} issues")
        if issues:
            print(f"Sample issue: {issues[0].key} - {issues[0].fields.summary}")
        
        return True
    except Exception as e:
        print(f"❌ Jira connection failed: {str(e)}")
        return False

def test_airtable_connection(config):
    print("\nTesting Airtable connection...")
    try:
        api = Api(config['airtable_api_key'])
        table = api.table(config['airtable_base_id'], config['airtable_table_name'])
        
        # Test by getting first page of records
        records = table.all(max_records=1)
        print(f"✅ Successfully connected to Airtable")
        print(f"Base ID: {config['airtable_base_id']}")
        print(f"Table: {config['airtable_table_name']}")
        print(f"Found {len(records)} records in table")
        
        return True
    except Exception as e:
        print(f"❌ Airtable connection failed: {str(e)}")
        return False

def main():
    # Load environment variables
    load_dotenv()
    
    config = {
        'jira_server': os.getenv('JIRA_SERVER'),
        'jira_username': os.getenv('JIRA_USERNAME'),
        'jira_api_token': os.getenv('JIRA_API_TOKEN'),
        'jira_project_key': os.getenv('JIRA_PROJECT_KEY'),
        'jira_jql_filter': os.getenv('JIRA_JQL_FILTER'),
        'airtable_api_key': os.getenv('AIRTABLE_API_KEY'),
        'airtable_base_id': os.getenv('AIRTABLE_BASE_ID'),
        'airtable_table_name': os.getenv('AIRTABLE_TABLE_NAME'),
    }
    
    # Check if all required environment variables are set
    missing_vars = [k for k, v in config.items() if not v]
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        sys.exit(1)
    
    jira_success = test_jira_connection(config)
    airtable_success = test_airtable_connection(config)
    
    if jira_success and airtable_success:
        print("\n✅ All connections successful! You're ready to start syncing.")
    else:
        print("\n❌ Some connections failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
