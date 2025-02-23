import os
from jira import JIRA
from dotenv import load_dotenv

load_dotenv()

def main():
    print("Connecting to Jira...")
    jira = JIRA(
        server=os.getenv('JIRA_SERVER'),
        basic_auth=(os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN'))
    )
    
    print("\nJira connection successful")
    print(f"Server: {os.getenv('JIRA_SERVER')}")
    print(f"Username: {os.getenv('JIRA_USERNAME')}")
    
    print("\nListing all accessible projects:")
    projects = jira.projects()
    
    if not projects:
        print("No projects accessible to this user")
        print("\nThis could be due to:")
        print("1. The user doesn't have any project permissions")
        print("2. The API token doesn't have sufficient permissions")
        print("3. The projects exist but are not visible to this user")
        return
    
    for project in projects:
        print(f"\nProject: {project.key}")
        print(f"  Name: {project.name}")
        print(f"  ID: {project.id}")
        try:
            roles = jira.project_roles(project.key)
            print(f"  Roles: {', '.join(roles.keys())}")
        except Exception as e:
            print(f"  Couldn't fetch roles: {str(e)}")

if __name__ == '__main__':
    main()
