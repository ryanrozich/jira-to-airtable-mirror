# Validation Scripts

Scripts for validating various aspects of the application configuration and setup.

## Contents

- `aws.py` - Validates AWS CLI installation, credentials, and permissions
- `config.py` - Validates environment variables and field mappings
- `docker.py` - Validates Docker installation and configuration
- `schema.py` - Validates data schema compatibility
- `jira_fields.py` - Validates Jira field configurations
- `tracking_fields.py` - Validates field tracking setup

## Usage

These scripts are typically run through the justfile commands. For example:
```bash
just validate-all  # Runs all validation scripts
just validate-aws  # Runs AWS-specific validation
```
