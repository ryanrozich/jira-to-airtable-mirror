# Scripts Directory

This directory contains utility scripts for managing, validating, and testing the Jira to Airtable Mirror application.

## Directory Structure

- `validation/` - Scripts for validating configuration, infrastructure, and data schemas
- `tests/` - Connection and functionality test scripts
- `schema/` - Scripts for retrieving and managing Jira and Airtable schemas
- `utils/` - Utility scripts for common tasks

## Key Files

- `run_validation.py` - Main script for running all validation checks

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
