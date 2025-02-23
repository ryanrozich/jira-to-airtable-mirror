import os
from jira import JIRA
from dotenv import load_dotenv

load_dotenv()

# Print environment variables (with API token partially masked)
jira_server = os.getenv('JIRA_SERVER')
jira_username = os.getenv('JIRA_USERNAME')
jira_token = os.getenv('JIRA_API_TOKEN')
if jira_token:
    masked_token = jira_token[:4] + '*' * (len(jira_token) - 8) + jira_token[-4:]
else:
    masked_token = None

print(f"JIRA_SERVER: {jira_server}")
print(f"JIRA_USERNAME: {jira_username}")
print(f"JIRA_API_TOKEN: {masked_token}")

# Try to connect to Jira
try:
    jira = JIRA(server=jira_server, basic_auth=(jira_username, jira_token))
    print("\nSuccessfully connected to Jira")
    
    # Try to get server info
    try:
        server_info = jira.server_info()
        print(f"Server info: {server_info}")
    except Exception as e:
        print(f"Error getting server info: {str(e)}")
    
    # Try to get projects
    try:
        projects = jira.projects()
        print(f"\nProjects: {[p.key for p in projects]}")
    except Exception as e:
        print(f"Error getting projects: {str(e)}")
        
    # Try to get issues with the current JQL
    try:
        jql = os.getenv('JIRA_JQL_FILTER', f'project = {os.getenv("JIRA_PROJECT_KEY")}')
        print(f"\nTrying JQL query: {jql}")
        issues = jira.search_issues(jql)
        print(f"Found {len(issues)} issues")
    except Exception as e:
        print(f"Error searching issues: {str(e)}")
        
except Exception as e:
    print(f"Error connecting to Jira: {str(e)}")
