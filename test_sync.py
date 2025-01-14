#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from jira import JIRA
from pyairtable import Api
import json
from datetime import datetime

def format_field_value(value):
    """Format field value for display"""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize Jira client
    jira = JIRA(
        server=os.getenv('JIRA_SERVER'),
        basic_auth=(os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN'))
    )
    
    # Initialize Airtable client
    airtable = Api(os.getenv('AIRTABLE_API_KEY')).table(
        os.getenv('AIRTABLE_BASE_ID'),
        os.getenv('AIRTABLE_TABLE_NAME')
    )
    
    # Default field mappings if not specified in .env
    default_field_map = {
        "key": "Jira Key",
        "summary": "Summary",
        "description": "Description",
        "reporter": "Reporter",
        "assignee": "Assignee",
        "issuetype": "Issue Type",
        "status": "Status",
        "parent": "Parent Issue Key",
        "created": "Date Created",
        "updated": "Last Updated",
        "resolutiondate": "Date Completed"
    }
    
    # Get field mappings from env or use defaults
    field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', json.dumps(default_field_map)))
    
    # Get JQL filter from env or use default
    jql = os.getenv('JIRA_JQL_FILTER', f"project = {os.getenv('JIRA_PROJECT_KEY')}")
    
    print(f"\nFetching Jira issues using JQL: {jql}")
    issues = jira.search_issues(jql, maxResults=50)  # Limiting to 50 for test
    print(f"Found {len(issues)} issues")
    
    # Get existing records from Airtable
    existing_records = {
        record['fields'].get(field_map['key']): record 
        for record in airtable.all()
        if field_map['key'] in record['fields']
    }
    
    print(f"\nFound {len(existing_records)} existing records in Airtable")
    print("\nProcessing issues:")
    print("-" * 80)
    
    for issue in issues:
        record = {}
        for jira_field, airtable_field in field_map.items():
            try:
                if jira_field == 'key':
                    value = issue.key
                elif jira_field == 'parent':
                    value = issue.fields.parent.key if hasattr(issue.fields, 'parent') else None
                elif jira_field in ['reporter', 'assignee']:
                    field_value = getattr(issue.fields, jira_field)
                    value = field_value.displayName if field_value else None
                elif jira_field in ['issuetype', 'status']:
                    value = getattr(getattr(issue.fields, jira_field), 'name')
                else:
                    value = getattr(issue.fields, jira_field)
                
                if value is not None:
                    record[airtable_field] = format_field_value(value)
            
            except Exception as e:
                print(f"Warning: Could not process field {jira_field} for issue {issue.key}: {str(e)}")
        
        # Check if record exists
        if issue.key in existing_records:
            print(f"Would UPDATE {issue.key} - {issue.fields.summary}")
            print("New values:")
            for field, value in record.items():
                current = existing_records[issue.key]['fields'].get(field)
                if current != value:
                    print(f"  {field}: {current} -> {value}")
        else:
            print(f"Would CREATE {issue.key} - {issue.fields.summary}")
            print("Values:")
            for field, value in record.items():
                print(f"  {field}: {value}")
        print("-" * 80)

if __name__ == "__main__":
    main()
