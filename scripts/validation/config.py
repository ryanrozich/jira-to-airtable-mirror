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
    
    # Check if field_map is a dictionary
    if not isinstance(field_map, dict):
        errors.append(f"Field mappings must be a dictionary, got: {type(field_map)}")
        return False, errors

    # Check if field_map is empty
    if not field_map:
        errors.append("Field mappings dictionary is empty")
        return False, errors

    # Required Jira fields that should be mapped
    required_fields = {
        'summary': 'Issue summary/title',
        'description': 'Issue description',
        'status': 'Issue status',
        'issuetype': 'Issue type',
        'created': 'Creation date',
        'updated': 'Last update date'
    }
    
    # Check for missing required fields
    missing_fields = [f"{field} ({desc})" for field, desc in required_fields.items() 
                     if field not in field_map]
    if missing_fields:
        errors.append("Missing required Jira field mappings:\n      - " + 
                     "\n      - ".join(missing_fields))
    
    for jira_field, airtable_info in field_map.items():
        # Check if Jira field name is a string
        if not isinstance(jira_field, str):
            errors.append(f"Jira field must be a string, got: {type(jira_field)}")
            continue
            
        # Check if airtable_info is a dictionary with required structure
        if not isinstance(airtable_info, dict):
            errors.append(f"Mapping for '{jira_field}' must be a dictionary with 'airtable_field_id', got: {type(airtable_info)}")
            continue
            
        # Check for required airtable_field_id key
        if 'airtable_field_id' not in airtable_info:
            errors.append(f"Mapping for '{jira_field}' is missing required 'airtable_field_id' key")
            continue
            
        field_id = airtable_info['airtable_field_id']
        # Check if Airtable field ID is a string
        if not isinstance(field_id, str):
            errors.append(f"Airtable field ID for '{jira_field}' must be a string, got: {type(field_id)}")
            continue
            
        # Validate Airtable field ID format (should start with 'fld')
        if not field_id.startswith('fld'):
            errors.append(f"Invalid Airtable field ID format for '{jira_field}': {field_id} (should start with 'fld')")
    
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
        raw_value = os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP')
        if not raw_value:
            return False, "No field mappings found", """
            To fix:
            1. Add JIRA_TO_AIRTABLE_FIELD_MAP to your .env file
            2. Use this example format (replace fldXXX with your actual Airtable field IDs):
            
               {
                 "summary": {"airtable_field_id": "fldXXX"},
                 "description": {"airtable_field_id": "fldYYY"},
                 "status": {"airtable_field_id": "fldZZZ"},
                 "issuetype": {"airtable_field_id": "fldAAA"},
                 "created": {"airtable_field_id": "fldBBB"},
                 "updated": {"airtable_field_id": "fldCCC"}
               }
               
            To get your Airtable field IDs:
            1. Open your Airtable base in a web browser
            2. Click 'Help' -> 'API Documentation'
            3. Find your table and look for the 'Fields' section
            4. Each field will have an ID starting with 'fld'
            """
        
        try:
            field_map = json.loads(raw_value)
        except json.JSONDecodeError as e:
            return False, "Invalid JSON in field mappings", f"""
            JSON parsing error: {str(e)}
            
            To fix:
            1. Check JIRA_TO_AIRTABLE_FIELD_MAP in your .env file
            2. Ensure it contains valid JSON syntax:
               - Use double quotes for strings
               - No trailing commas
               - Proper nesting of braces
            3. Use a JSON validator (e.g., jsonlint.com) to check your JSON
            
            Example of valid format:
            {{
              "summary": {{"airtable_field_id": "fldXXX"}},
              "description": {{"airtable_field_id": "fldYYY"}}
            }}
            """
        
        # Validate schema
        is_valid, errors = validate_field_mapping_schema(field_map)
        if not is_valid:
            error_list = '\n            '.join(f"- {error}" for error in errors)
            return False, "Invalid field mapping schema", f"""
            Schema validation errors:
            {error_list}
            
            Required format for each field mapping:
            {{
              "jira_field": {{"airtable_field_id": "fldXXX"}},
              ...
            }}
            
            Note:
            - Each Jira field must map to a dictionary containing 'airtable_field_id'
            - All Airtable field IDs must start with 'fld'
            - Required Jira fields: summary, description, status, issuetype, created, updated
            """
        
        return True, f"Field mappings configured ({len(field_map)} fields)", ""
    except Exception as e:
        return False, "Unexpected error in field mappings", f"""
        An unexpected error occurred: {str(e)}
        
        Please check your field mappings configuration and try again.
        If the error persists, please report this issue.
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
