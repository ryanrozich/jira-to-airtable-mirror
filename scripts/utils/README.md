# Utility Scripts

Helper scripts for common tasks in the Jira to Airtable Mirror application.

## Contents

- `list_projects.py` - Lists all accessible Jira projects with their keys and names

## Usage

List all accessible Jira projects:
```bash
python -m scripts.utils.list_projects
```

This will display:
- Project keys (e.g., PROJ)
- Project names
- Project URLs (if applicable)
