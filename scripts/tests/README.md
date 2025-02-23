# Test Scripts

Scripts for testing connections and core functionality.

## Contents

- `airtable_connection.py` - Tests Airtable API connectivity
- `jira_connection.py` - Tests Jira API connectivity
- `sync.py` - Tests the sync functionality between Jira and Airtable

## Usage

These scripts are typically run as part of the validation process:
```bash
just test-connections  # Tests both Jira and Airtable connections
just test-sync        # Tests the sync functionality
```
