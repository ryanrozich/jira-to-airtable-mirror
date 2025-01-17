#!/usr/bin/env python3
import os
import sys
import json
from dotenv import load_dotenv
from pyairtable import Api

def validate_schema():
    """Validate field mappings against Airtable schema."""
    load_dotenv()
    
    # Load field mappings
    try:
        field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
    except json.JSONDecodeError:
        print("❌ Invalid JSON in JIRA_TO_AIRTABLE_FIELD_MAP")
        return False
    
    if not field_map:
        print("❌ No field mappings found in JIRA_TO_AIRTABLE_FIELD_MAP")
        return False
    
    try:
        # Get Airtable schema
        api = Api(os.getenv('AIRTABLE_API_KEY'))
        base = api.base(os.getenv('AIRTABLE_BASE_ID'))
        table = base.table(os.getenv('AIRTABLE_TABLE_NAME'))
        
        # Get field IDs by making a minimal request
        schema = table.schema()
        field_ids = {}
        
        # Extract field information from schema
        for field in schema.fields:
            field_ids[field.id] = field.name
        
        # Validate each mapped field
        invalid_fields = []
        for jira_field, airtable_id in field_map.items():
            if airtable_id not in field_ids:
                invalid_fields.append(f"{jira_field} -> {airtable_id}")
            else:
                print(f"✅ Valid mapping: {jira_field} -> {field_ids[airtable_id]} ({airtable_id})")
        
        if invalid_fields:
            print("\n❌ Invalid field mappings found:")
            for mapping in invalid_fields:
                print(f"  - {mapping}")
            print("\nAvailable Airtable fields:")
            for field_id, field_name in field_ids.items():
                print(f"  - {field_name}: {field_id}")
            return False
        
        print("\n✅ All field mappings are valid!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to validate schema: {str(e)}")
        return False

if __name__ == '__main__':
    sys.exit(0 if validate_schema() else 1)
