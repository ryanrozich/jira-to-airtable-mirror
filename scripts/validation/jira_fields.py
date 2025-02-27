#!/usr/bin/env python3
import os
import sys
import json
import logging
from dotenv import load_dotenv
from jira import JIRA
from sync import JiraAirtableSync

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
logger.addHandler(handler)


def validate_jira_fields() -> bool:
    """Validate that all JIRA fields in our mapping can be retrieved."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize JIRA client for schema lookup
        jira = JIRA(
            server=os.getenv('JIRA_SERVER'),
            basic_auth=(os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN'))
        )
        
        # Get all JIRA fields for reference
        all_fields = jira.fields()
        logger.info("Available JIRA fields:")
        for field in sorted(all_fields, key=lambda x: x['name']):
            logger.info(f"  - {field['name']} (id: {field['id']})")
        logger.info("---")
        
        # Load field mappings
        field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
        if not field_map:
            logger.error("❌ JIRA_TO_AIRTABLE_FIELD_MAP not found in environment")
            return False
            
        # Build maps of field IDs to names
        jira_fields = {}
        for field in all_fields:
            jira_fields[field['id']] = field['id']
        custom_field_ids = {field['id']: field['name'] for field in all_fields}
        
        # Initialize the sync handler to use its methods
        config = {
            'jira': {
                'server': os.getenv('JIRA_SERVER'),
                'username': os.getenv('JIRA_USERNAME'),
                'api_token': os.getenv('JIRA_API_TOKEN'),
                'project_key': os.getenv('JIRA_PROJECT_KEY')
            },
            'airtable': {
                'api_key': os.getenv('AIRTABLE_API_KEY'),
                'base_id': os.getenv('AIRTABLE_BASE_ID'),
                'table_id': os.getenv('AIRTABLE_TABLE_NAME')
            },
            'field_mappings': field_map
        }
        sync_handler = JiraAirtableSync(config)
        
        # Get test issues using the sync handler
        max_results = 20
        logger.info(f"Fetching up to {max_results} issues for testing")
        
        try:
            issues = sync_handler.get_jira_issues(max_results=max_results)
        except Exception as e:
            logger.error(f"❌ Error fetching JIRA issues: {str(e)}")
            return False
            
        if not issues:
            logger.error("❌ No JIRA issues found to validate fields against")
            return False
        
        if len(issues) < max_results:
            logger.warning(f"⚠️  Only found {len(issues)} issues to test against")
            
        logger.info("Testing against the following issues:")
        for issue in issues:
            logger.info(f"  - {issue.key}")
        logger.info("---")
        
        # Track field statistics across all test issues
        field_stats = {}  # field_name -> {'present': count, 'non_null': count}
        
        # Special computed fields that we handle in the sync code
        computed_fields = {
            'latest_comment': 'Comment field - handled by sync code',
            'comment_author': 'Comment field - handled by sync code',
            'comment_updated': 'Comment field - handled by sync code',
            'status_updated': 'Status field - handled by sync code'
        }
        
        # Special fields that are accessed directly on the issue object
        special_fields = {
            'key': 'Issue key field - accessed directly on issue'
        }
        
        # Check each mapped JIRA field
        success = True
        for jira_field, airtable_field in field_map.items():
            # Skip special fields that aren't direct JIRA fields
            if jira_field.startswith('_'):
                continue
                
            # Handle computed fields
            if jira_field in computed_fields:
                logger.info(f"✅ Found computed field '{jira_field}' ({computed_fields[jira_field]})")
                continue
                
            # Handle special fields
            if jira_field in special_fields:
                logger.info(f"✅ Found special field '{jira_field}' ({special_fields[jira_field]})")
                continue
                
            # Handle custom fields
            if jira_field.startswith('customfield_'):
                if jira_field not in custom_field_ids:
                    logger.error(f"❌ Custom JIRA field '{jira_field}' (mapped to Airtable '{airtable_field}') does not exist")
                    success = False
                    continue
                logger.info(f"✅ Found custom field '{jira_field}' ({custom_field_ids[jira_field]})")
            
            # For standard fields, check if they exist
            elif jira_field not in jira_fields:
                logger.error(f"❌ JIRA field '{jira_field}' (mapped to Airtable '{airtable_field}') does not exist")
                success = False
                continue
            
            # Initialize stats for this field
            field_stats[jira_field] = {'present': 0, 'non_null': 0}
            
            # Try to access the field in all test issues
            for issue in issues:
                try:
                    # Special handling for 'key' field which is accessed directly on the issue
                    if jira_field == 'key':
                        field_value = issue.key
                    else:
                        field_value = getattr(issue.fields, jira_field, None)
                    
                    field_stats[jira_field]['present'] += 1
                    if field_value is not None:
                        field_stats[jira_field]['non_null'] += 1
                except Exception as e:
                    logger.error(f"❌ Error accessing JIRA field '{jira_field}' in issue {issue.key}: {str(e)}")
                    success = False
            
            # Report field statistics
            stats = field_stats[jira_field]
            total_issues = len(issues)
            
            if stats['present'] == 0:
                logger.error(f"❌ JIRA field '{jira_field}' not found in any test issues")
                success = False
            elif stats['non_null'] == 0:
                logger.warning(f"⚠️  JIRA field '{jira_field}' exists but is null in all {total_issues} test issues")
            else:
                logger.info(f"✅ Successfully accessed JIRA field '{jira_field}' (non-null in {stats['non_null']}/{total_issues} issues)")

        return success

    except Exception as e:
        logger.error(f"❌ Error validating JIRA fields: {str(e)}")
        return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    sys.exit(0 if validate_jira_fields() else 1)
