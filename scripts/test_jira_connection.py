#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from jira import JIRA

def test_jira_connection():
    """Test Jira connection and credentials."""
    load_dotenv()
    
    # Required environment variables
    required_vars = ['JIRA_SERVER', 'JIRA_USERNAME', 'JIRA_API_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:", ", ".join(missing_vars))
        sys.exit(1)
    
    try:
        # Initialize Jira client
        jira = JIRA(
            server=os.getenv('JIRA_SERVER'),
            basic_auth=(os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN'))
        )
        
        # Test connection by getting current user
        user = jira.current_user()
        print(f"✅ Successfully connected to Jira as {user}")
        
        # Test project access
        project_key = os.getenv('JIRA_PROJECT_KEY')
        if project_key:
            project = jira.project(project_key)
            print(f"✅ Successfully accessed project {project.name} ({project.key})")
        
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Jira: {str(e)}")
        return False

if __name__ == '__main__':
    sys.exit(0 if test_jira_connection() else 1)
