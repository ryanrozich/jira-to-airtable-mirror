#!/usr/bin/env python3
import os
import sys
import json
from dotenv import load_dotenv
from jira import JIRA
from pyairtable import Api
from datetime import datetime

def validate_tracking_fields():
    """Validate comment and status tracking fields by testing with real data."""
    load_dotenv()
    
    try:
        # Load field mappings
        try:
            field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
        except json.JSONDecodeError:
            print("❌ Invalid JSON in JIRA_TO_AIRTABLE_FIELD_MAP")
            return False
        
        if not field_map:
            print("❌ No field mappings found in JIRA_TO_AIRTABLE_FIELD_MAP")
            return False
        
        # Initialize Jira client
        jira = JIRA(
            server=os.getenv('JIRA_SERVER'),
            basic_auth=(os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN'))
        )
        
        # Initialize Airtable client
        api = Api(os.getenv('AIRTABLE_API_KEY'))
        base = api.base(os.getenv('AIRTABLE_BASE_ID'))
        table = base.table(os.getenv('AIRTABLE_TABLE_NAME'))
        
        # Get Airtable schema
        schema = table.schema()
        field_ids = {field.id: field.name for field in schema.fields}
        
        # Validate required status field
        if 'status' not in field_map:
            print("❌ Required 'status' field mapping is missing")
            return False
        
        status_field = field_map['status']
        if status_field not in field_ids:
            print(f"❌ Invalid status field ID: {status_field}")
            return False
        print(f"✅ Valid status field mapping: {field_ids[status_field]} ({status_field})")
        
        # Validate status_updated field if present
        if 'status_updated' in field_map:
            field_id = field_map['status_updated']
            if field_id not in field_ids:
                print(f"❌ Invalid status_updated field ID: {field_id}")
                return False
            print(f"✅ Valid status_updated field mapping: {field_ids[field_id]} ({field_id})")
        
        # Validate comment tracking fields if present
        comment_fields = {
            'latest_comment': 'text',
            'comment_author': 'single line text',
            'comment_updated': 'date'
        }
        
        for field, expected_type in comment_fields.items():
            if field in field_map:
                field_id = field_map[field]
                if field_id not in field_ids:
                    print(f"❌ Invalid {field} field ID: {field_id}")
                    return False
                print(f"✅ Valid {field} field mapping: {field_ids[field_id]} ({field_id})")
                
                # Check field type
                field_type = next((f.type for f in schema.fields if f.id == field_id), None)
                if field_type and field_type.lower() != expected_type:
                    print(f"⚠️ Warning: {field} field is type '{field_type}', expected '{expected_type}'")
        
        # Test with a real issue
        print("\nTesting with a real issue...")
        jql = os.getenv('JIRA_JQL_FILTER', f"project = {os.getenv('JIRA_PROJECT_KEY')}")
        issues = jira.search_issues(jql, maxResults=1, expand='changelog')
        
        if not issues:
            print("⚠️ No issues found to test with")
            return True
        
        issue = issues[0]
        print(f"\nTesting issue {issue.key}:")
        
        # Test status tracking
        print("\nStatus tracking:")
        status = getattr(issue.fields, 'status', None)
        print(f"  Current status: {status}")
        
        # Get status history
        changelog = issue.changelog
        status_changes = []
        for history in changelog.histories:
            for item in history.items:
                if item.field == 'status':
                    status_changes.append({
                        'from': item.fromString,
                        'to': item.toString,
                        'date': history.created
                    })
        
        if status_changes:
            print("  Status changes found:")
            for change in status_changes[-3:]:  # Show last 3 changes
                print(f"    {change['date']}: {change['from']} -> {change['to']}")
        else:
            print("  No status changes found in history")
        
        # Test comment tracking
        print("\nComment tracking:")
        comments = jira.comments(issue)
        if comments:
            latest = comments[-1]
            print(f"  Latest comment found:")
            print(f"    Author: {latest.author.displayName}")
            print(f"    Updated: {latest.updated}")
            print(f"    Text: {latest.body[:100]}...")  # Show first 100 chars
        else:
            print("  No comments found")
        
        print("\n✅ All tracking field validations completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Validation failed: {str(e)}")
        return False

if __name__ == '__main__':
    sys.exit(0 if validate_tracking_fields() else 1)
