#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from jira import JIRA

def get_jira_schema():
    """Get and print the schema of Jira fields."""
    load_dotenv()
    
    # Get configuration from environment variables
    server = os.getenv('JIRA_SERVER')
    username = os.getenv('JIRA_USERNAME')
    api_token = os.getenv('JIRA_API_TOKEN')
    
    if not all([server, username, api_token]):
        print("Error: Missing required environment variables.")
        print("Please ensure JIRA_SERVER, JIRA_USERNAME, and JIRA_API_TOKEN are set.")
        return
    
    try:
        # Initialize Jira client
        jira = JIRA(server=server, basic_auth=(username, api_token))
        
        # Get all fields
        fields = jira.fields()
        
        # Core fields we commonly use
        core_fields = {
            'key',
            'summary',
            'description',
            'issuetype',
            'status',
            'assignee',
            'reporter',
            'parent',
            'created',
            'updated',
            'resolutiondate',
            'customfield_10016',  # Story Points
            'comment'
        }
        
        # Print field information
        print("\nJira Field Information:")
        name_width = 35
        id_width = 25
        jql_width = 35
        
        header = (
            f"{'Display Name':<{name_width}} "
            f"{'Field ID':<{id_width}} "
            f"{'JQL Name':<{jql_width}}"
        )
        print("\nCore Fields:")
        print(header)
        print("-" * (name_width + id_width + jql_width + 2))
        
        # First print core fields
        core_field_objects = [f for f in fields if f['id'] in core_fields or f['key'] in core_fields]
        for field in sorted(core_field_objects, key=lambda x: x['name']):
            row = (
                f"{field['name']:<{name_width}} "
                f"{field['id']:<{id_width}} "
                f"{field['key']:<{jql_width}}"
            )
            print(row)
        
        # Then print all other fields
        print("\nAll Other Fields:")
        print(header)
        print("-" * (name_width + id_width + jql_width + 2))
        
        other_fields = [f for f in fields if f['id'] not in core_fields and f['key'] not in core_fields]
        for field in sorted(other_fields, key=lambda x: x['name']):
            row = (
                f"{field['name']:<{name_width}} "
                f"{field['id']:<{id_width}} "
                f"{field['key']:<{jql_width}}"
            )
            print(row)
            
    except Exception as e:
        print(f"Error getting schema: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    get_jira_schema()
