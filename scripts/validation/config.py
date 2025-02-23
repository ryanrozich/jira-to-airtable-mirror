#!/usr/bin/env python3
import os
import sys
import json
from typing import List, Tuple, Dict, Any
import shutil
from dotenv import load_dotenv

def validate_field_mapping_schema(field_map: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate the schema of field mappings."""
    errors = []
    
    for jira_field, airtable_field_id in field_map.items():
        # Check if Jira field name is a string
        if not isinstance(jira_field, str):
            errors.append(f"Jira field must be a string, got: {type(jira_field)}")
            continue
            
        # Check if Airtable field ID is a string
        if not isinstance(airtable_field_id, str):
            errors.append(f"Airtable field ID for '{jira_field}' must be a string, got: {type(airtable_field_id)}")
            continue
            
        # Optional: validate Airtable field ID format (should start with 'fld')
        if not airtable_field_id.startswith('fld'):
            errors.append(f"Invalid Airtable field ID format for '{jira_field}': {airtable_field_id} (should start with 'fld')")
    
    return len(errors) == 0, errors

def check_env_file() -> Tuple[bool, str, str]:
    """Check if .env file exists and create it from example if not."""
    if os.path.exists('.env'):
        return True, "Environment file exists", ""
    
    if os.path.exists('.env.example'):
        shutil.copy('.env.example', '.env')
        return False, "Created .env from .env.example", """
        Action required:
        1. A new .env file has been created from .env.example
        2. Please edit .env and fill in your configuration values
        3. Run validation again after updating the file
        """
    
    return False, ".env and .env.example files not found", """
    To fix:
    1. Ensure .env.example exists in the project root
    2. Copy .env.example to .env:
       cp .env.example .env
    3. Edit .env with your configuration
    """

def check_jira_config() -> Tuple[bool, str, List[str]]:
    """Validate Jira configuration."""
    required_vars = {
        'JIRA_SERVER': 'Your Jira server URL',
        'JIRA_USERNAME': 'Your Jira username/email',
        'JIRA_API_TOKEN': 'Your Jira API token',
        'JIRA_PROJECT_KEY': 'Your Jira project key'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var}: {description}")
    
    if missing_vars:
        return False, "Missing Jira configuration", missing_vars
    return True, "Jira configuration complete", []

def check_airtable_config() -> Tuple[bool, str, List[str]]:
    """Validate Airtable configuration."""
    required_vars = {
        'AIRTABLE_API_KEY': 'Your Airtable API key',
        'AIRTABLE_BASE_ID': 'Your Airtable base ID',
        'AIRTABLE_TABLE_NAME': 'Your Airtable table name'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var}: {description}")
    
    if missing_vars:
        return False, "Missing Airtable configuration", missing_vars
    return True, "Airtable configuration complete", []

def check_field_mappings() -> Tuple[bool, str, str]:
    """Validate field mappings configuration."""
    try:
        field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
        if not field_map:
            return False, "No field mappings found", """
            To fix:
            1. Add JIRA_TO_AIRTABLE_FIELD_MAP to your .env file
            2. Ensure it contains valid JSON mapping Jira fields to Airtable fields
            3. Example format:
               {
                 "summary": "fldXXX",
                 "description": "fldYYY",
                 "status": "fldZZZ"
               }
            """
        
        # Validate schema
        is_valid, errors = validate_field_mapping_schema(field_map)
        if not is_valid:
            error_list = '\n            '.join(f"- {error}" for error in errors)
            return False, "Invalid field mapping schema", f"""
            Schema validation errors:
            {error_list}
            
            Expected format:
            {{
              "jira_field": "fldXXX",
              ...
            }}
            """
        
        return True, f"Field mappings configured ({len(field_map)} fields)", ""
    except json.JSONDecodeError:
        return False, "Invalid JSON in field mappings", """
        To fix:
        1. Check JIRA_TO_AIRTABLE_FIELD_MAP in your .env file
        2. Ensure it contains valid JSON syntax
        3. Use a JSON validator if needed
        """

def main():
    """Run all configuration validation checks."""
    load_dotenv()
    
    checks = [
        ("Environment File", check_env_file()),
        ("Jira Configuration", check_jira_config()),
        ("Airtable Configuration", check_airtable_config()),
        ("Field Mappings", check_field_mappings())
    ]
    
    all_passed = True
    first = True
    
    for name, (passed, message, _) in checks:
        status = "✅" if passed else "❌"
        if first:
            print(f"\n   {status} {name}:")
            first = False
        else:
            print(f"\n   {status} {name}:")
        print(f"      {message}")
        if not passed:
            all_passed = False
    
    print()  # Add blank line at the end
    return all_passed

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
