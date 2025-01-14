# Jira to Airtable Sync Integration

## Overview
This tool synchronizes Jira issues with an Airtable base, providing a flexible and configurable way to keep project tracking data in sync.

## Prerequisites
- Python 3.8+
- Jira Cloud account
- Airtable account

## Installation
1. Clone the repository
2. Create a virtual environment:
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in your credentials

## Configuration
Edit the `.env` file to configure:
- Jira credentials and project
- Airtable credentials
- Sync interval
- Field mappings

## Running the Sync
```
python sync.py
# Or for scheduled runs
python sync.py --schedule
```

## Security Notes
- Never commit `.env` file to version control
- Use environment-specific API tokens
- Limit API token permissions

## Supported Features
- One-way sync from Jira to Airtable
- Configurable field mappings
- Scheduled synchronization
- Upsert existing records
- Optional delete synchronization

## Troubleshooting
- Check logs in `sync.log`
- Verify API credentials
- Ensure network connectivity
