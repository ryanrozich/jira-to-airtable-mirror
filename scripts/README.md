# Scripts Directory

This directory contains utility scripts for managing, validating, and testing the Jira to Airtable Mirror application.

## Directory Structure

- `validation/` - Scripts for validating configuration, infrastructure, and data schemas
- `tests/` - Connection and functionality test scripts
- `schema/` - Scripts for retrieving and managing Jira and Airtable schemas
- `utils/` - Utility scripts for common tasks
- `metrics/` - Package for collecting and formatting AWS Lambda metrics

## Key Files

- `run_validation.py` - Main script for running all validation checks
- `get_metrics.py` - Script for retrieving and displaying Lambda metrics

Each subdirectory contains its own README with more detailed information.

## Usage

Run all validations:
```bash
just validate-all
```

List available Jira projects:
```bash
python -m scripts.utils.list_projects
```

Get Lambda metrics:
```bash
# Using just recipe (recommended)
just lambda-metrics

# Or directly using the script
./get_metrics.py -f jira-to-airtable-mirror -H 24  # Last 24 hours
