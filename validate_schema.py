#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from pyairtable import Api
import json

def validate_airtable_schema():
    # Load environment variables
    load_dotenv()
    
    # Get Airtable credentials
    api_key = os.getenv('AIRTABLE_API_KEY')
    base_id = os.getenv('AIRTABLE_BASE_ID')
    table_name = os.getenv('AIRTABLE_TABLE_NAME')
    
    # Required fields from our schema
    required_fields = {
        'JIRA Key': 'singleLineText',
        'Summary': 'singleLineText',
        'Description': 'richText',
        'Assignee': 'singleLineText',
        'Reporter': 'singleLineText',
        'Status': 'singleLineText',
        'Issue Type': 'singleLineText',
        'Parent Issue Key': 'singleLineText',
        'Date Created': 'date',
        'Last Updated': 'date',
        'Date Completed': 'date',
        'Story Points': 'singleLineText'
    }
    
    print("\nValidating Airtable schema...")
    try:
        # Connect to Airtable
        api = Api(api_key)
        table = api.table(base_id, table_name)
        
        # Create a test record with all required fields
        test_record = {
            'JIRA Key': 'TEST-1',
            'Summary': 'Test Issue',
            'Description': 'Test Description',
            'Assignee': 'Test User',
            'Reporter': 'Test Reporter',
            'Status': 'Open',
            'Issue Type': 'Task',
            'Parent Issue Key': 'TEST-0',
            'Date Created': '2025-01-13',
            'Last Updated': '2025-01-13',
            'Date Completed': '2025-01-13',
            'Story Points': '5'
        }
        
        # Try to create the test record
        response = table.create(test_record)
        print("✅ Successfully created test record with all fields")
        
        # Clean up test record
        table.delete(response['id'])
        print("✅ Successfully cleaned up test record")
        
        print("\nAll required fields are present and correctly configured!")
        return True
        
    except Exception as e:
        print(f"\n❌ Schema validation failed: {str(e)}")
        print("\nMake sure the following fields exist in your Airtable with the correct types:")
        for field, field_type in required_fields.items():
            print(f"- {field} ({field_type})")
        return False

if __name__ == '__main__':
    validate_airtable_schema()
