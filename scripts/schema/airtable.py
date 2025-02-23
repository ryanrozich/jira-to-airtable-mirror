#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from pyairtable import Api

def get_table_schema():
    """Get and print the schema of the Airtable table."""
    load_dotenv()
    
    # Get configuration from environment variables
    api_key = os.getenv('AIRTABLE_API_KEY')
    base_id = os.getenv('AIRTABLE_BASE_ID')
    table_name = os.getenv('AIRTABLE_TABLE_NAME')
    
    if not all([api_key, base_id, table_name]):
        print("Error: Missing required environment variables.")
        print("Please ensure AIRTABLE_API_KEY, AIRTABLE_BASE_ID, and AIRTABLE_TABLE_NAME are set.")
        return
    
    try:
        # Initialize Airtable API
        api = Api(api_key)
        table = api.table(base_id, table_name)
        
        # Get schema - note: schema() is a method, not a property
        schema = table.schema()
        
        # Print table info
        print("\nAirtable Table Information:")
        print(f"Name: {schema.name}")
        print(f"ID: {schema.id}")
        
        # Print field information
        print("\nFields:")
        # Adjust column widths for better readability
        name_width = 35
        type_width = 25
        id_width = 35
        
        header = (
            f"{'Field Name':<{name_width}} "
            f"{'Field Type':<{type_width}} "
            f"{'Field ID':<{id_width}}"
        )
        print(header)
        print("-" * (name_width + type_width + id_width + 2))  # +2 for spaces
        
        for field in schema.fields:
            row = (
                f"{field.name:<{name_width}} "
                f"{field.type:<{type_width}} "
                f"{field.id:<{id_width}}"
            )
            print(row)
            
    except Exception as e:
        print(f"Error getting schema: {str(e)}")
        # Print more detailed error info for debugging
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    get_table_schema()
