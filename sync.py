#!/usr/bin/env python3
import os
import json
import logging
import click
from dotenv import load_dotenv
from jira import JIRA
from pyairtable import Api
from apscheduler.schedulers.blocking import BlockingScheduler
from typing import Dict, Any, Optional
from datetime import datetime
from dateutil import parser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class JiraAirtableSync:
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize sync configuration and connections
        
        :param config: Dictionary containing sync configuration
        """
        self.config = config
        
        # Initialize Airtable client
        self.airtable_api = Api(config['airtable_api_key'])
        base = self.airtable_api.base(config['airtable_base_id'])
        self.airtable_table = base.table(config['airtable_table_name'])
        
        # Initialize field mapping
        self.field_map = config.get('field_map', {})
        
        # Validate Airtable schema before proceeding
        self._validate_airtable_schema()
        
        # Initialize JIRA client
        self.jira_client = JIRA(
            server=config['jira_server'], 
            basic_auth=(config['jira_username'], config['jira_api_token'])
        )

    def _validate_airtable_schema(self):
        """
        Validate that all required fields exist in Airtable with correct IDs
        
        :raises ValueError: If any required fields are missing
        """
        try:
            # First get the table metadata to check fields
            table_info = self.airtable_table.api.request(
                method="GET",
                url=f"https://api.airtable.com/v0/meta/bases/{self.config['airtable_base_id']}/tables"
            )
            
            # Find our table
            table_meta = None
            for table in table_info["tables"]:
                if table["name"] == self.config["airtable_table_name"]:
                    table_meta = table
                    break
            
            if not table_meta:
                raise ValueError(
                    f"Table '{self.config['airtable_table_name']}' not found in Airtable base. "
                    "Please verify the table name is correct."
                )
            
            # Get field IDs from metadata
            field_ids = {field["id"] for field in table_meta["fields"]}
            field_names = {field["id"]: field["name"] for field in table_meta["fields"]}
            
            # Check for missing fields
            missing_fields = []
            for jira_field, airtable_field_id in self.field_map.items():
                if airtable_field_id not in field_ids:
                    field_name = field_names.get(airtable_field_id, airtable_field_id)
                    missing_fields.append(f"{jira_field} -> {field_name} ({airtable_field_id})")
            
            if missing_fields:
                raise ValueError(
                    f"The following field mappings are invalid in your Airtable:\n"
                    f"{', '.join(missing_fields)}\n\n"
                    f"Available fields in table '{self.config['airtable_table_name']}':\n"
                    f"{', '.join(f'{name} ({id})' for id, name in field_names.items())}\n\n"
                    "Please update the field mappings to use valid field IDs."
                )
            
            logger.info("Successfully validated all field IDs exist")
                
        except Exception as e:
            logger.error(f"Airtable schema validation failed: {str(e)}")
            raise ValueError(f"Airtable schema validation failed: {str(e)}")

    def _transform_jira_issue(self, issue) -> Dict[str, Any]:
        """
        Transform Jira issue to Airtable record format
        
        :param issue: Jira issue object
        :return: Transformed record dictionary
        """
        record = {}
        for jira_field, airtable_field in self.field_map.items():
            try:
                value = self._get_issue_field_value(issue, jira_field)
                if value is not None:
                    record[airtable_field] = value
            except Exception as e:
                logger.warning(f"Could not map field {jira_field}: {e}")
        
        return record

    def _get_issue_field_value(self, issue, field):
        """
        Get a field value from a Jira issue, with special handling for certain field types
        """
        try:
            # Special handling for key field
            if field == 'key':
                return issue.key
                
            # Special handling for parent field - convert to linked record
            if field == 'parent':
                parent_key = getattr(issue.fields, 'parent', None)
                if parent_key:
                    parent_key = parent_key.key
                    # Look up the parent record in Airtable
                    parent_records = self.airtable_table.all(
                        formula=f"{{JIRA Key}} = '{parent_key}'"
                    )
                    if parent_records:
                        # Return array of record IDs for linked record field
                        return [parent_records[0]['id']]
                return None
            
            # Handle date fields
            elif field in ['created', 'updated', 'resolutiondate']:
                date_str = str(getattr(issue.fields, field, None))
                if date_str and date_str != 'None':
                    # Insert colon in timezone offset (if any)
                    if date_str[-5:-2].isdigit():  # Check if we have a timezone offset
                        date_str = f"{date_str[:-2]}:{date_str[-2:]}"
                    logger.debug(f"Formatted {field} date: {date_str}")
                    return date_str
                else:
                    logger.debug(f"Formatted {field} date: None")
                    return None
            else:
                # Handle custom fields dynamically
                if field.startswith('customfield_'):
                    value = getattr(issue.fields, field, None)
                    if value is not None:
                        if hasattr(value, 'value'):  # Handle custom field objects
                            return value.value
                        return value
                    return None
                
                # Handle standard fields
                value = getattr(issue.fields, field, None)
                if value is not None:
                    if hasattr(value, 'key'):  # Handle objects with key attribute
                        return value.key
                    elif hasattr(value, 'value'):  # Handle objects with value attribute
                        return value.value
                    elif hasattr(value, 'name'):  # Handle objects with name attribute
                        return value.name
                    return str(value)
                return None
                
        except Exception as e:
            logger.error(f"Error getting field {field} from issue: {str(e)}")
            return None

    def _get_latest_update_time(self):
        """
        Get the latest update time from Airtable
        
        :return: Latest update time as ISO string
        """
        try:
            # Get the latest record sorted by Last Updated in descending order
            latest_records = self.airtable_table.all(
                sort=["-Last Updated"],  # Sort by Last Updated in descending order
                max_records=1  # We only need the most recent record
            )
            
            if latest_records:
                latest_record = latest_records[0]
                latest_update = latest_record['fields'].get('Last Updated')
                logger.debug(f"Found latest update time: {latest_update}")
                return latest_update
            
            logger.warning("No update time found in Airtable")
            return None
        
        except Exception as e:
            logger.error(f"Failed to get latest update time: {str(e)}")
            return None

    def sync_issues(self):
        """
        Synchronize Jira issues to Airtable
        """
        try:
            # Get the latest update time from Airtable
            latest_update = self._get_latest_update_time()
            logger.info(f"Latest update time from Airtable: {latest_update}")
            
            # Base JQL
            jql = self.config.get('jira_jql')
            if not jql:
                jql = f"project = {self.config['jira_project_key']}"
            
            # If we have a latest update time, only fetch issues updated after that time
            if latest_update:
                # Parse the ISO datetime and convert to JQL format
                update_dt = parser.parse(latest_update)
                jql_date = update_dt.strftime('"%Y-%m-%d %H:%M"')
                jql = f"({jql}) AND updated > {jql_date}"
            
            # Add sorting by created date in ascending order
            jql = f"{jql} ORDER BY created ASC"
            
            logger.debug(f"Using JQL query: {jql}")
            
            # Get all issues from Jira
            issues = self.jira_client.search_issues(
                jql,
                maxResults=0,
                fields=[
                    'summary',
                    'description',
                    'reporter',
                    'assignee',
                    'issuetype',
                    'status',
                    'parent',
                    'created',
                    'updated',
                    'resolutiondate',
                    'customfield_10016'
                ]
            )
            logger.info(f"Found {len(issues)} issues to sync")
            
            # Process each issue
            for issue in issues:
                try:
                    # Transform the issue to Airtable format
                    record = self._transform_jira_issue(issue)
                    
                    # Look for existing record with matching key
                    existing_records = self.airtable_table.all(
                        formula=f"{{{self.field_map['key']}}} = '{issue.key}'"
                    )
                    
                    if existing_records:
                        # Update existing record
                        record_id = existing_records[0]['id']
                        logger.info(f"Updating existing record for {issue.key}")
                        self.airtable_table.update(record_id, record)
                    else:
                        # Create new record
                        logger.info(f"Creating new record for {issue.key}")
                        self.airtable_table.create(record)
                    
                except Exception as e:
                    logger.error(f"Failed to sync issue {issue.key}: {str(e)}")
                    continue
            
            logger.info("✅ Sync completed successfully")
            
        except Exception as sync_error:
            logger.error(f"❌ Sync failed: {str(sync_error)}")
            logger.debug("Full error details:", exc_info=True)

def load_config():
    """
    Load configuration from environment variables
    
    :return: Configuration dictionary
    :raises ValueError: If any required environment variables are missing
    """
    load_dotenv()
    
    # Required environment variables
    required_vars = {
        'JIRA_SERVER': 'Jira server URL',
        'JIRA_USERNAME': 'Jira username/email',
        'JIRA_API_TOKEN': 'Jira API token',
        'JIRA_PROJECT_KEY': 'Jira project key',
        'AIRTABLE_API_KEY': 'Airtable API key',
        'AIRTABLE_BASE_ID': 'Airtable base ID',
        'AIRTABLE_TABLE_NAME': 'Airtable table name',
        'JIRA_TO_AIRTABLE_FIELD_MAP': 'Field mapping JSON'
    }
    
    # Check for missing or empty required variables
    missing_vars = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value or value.strip() == '':
            missing_vars.append(f"{var} ({description})")
    
    if missing_vars:
        error_msg = "Missing required environment variables:\n- " + "\n- ".join(missing_vars)
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Get max_results as integer or None
    max_results_str = os.getenv('MAX_RESULTS')
    max_results = int(max_results_str) if max_results_str else None
    
    try:
        field_map = json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in JIRA_TO_AIRTABLE_FIELD_MAP: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return {
        'jira_server': os.getenv('JIRA_SERVER'),
        'jira_username': os.getenv('JIRA_USERNAME'),
        'jira_api_token': os.getenv('JIRA_API_TOKEN'),
        'jira_project_key': os.getenv('JIRA_PROJECT_KEY'),
        'jira_jql': os.getenv('JIRA_JQL_FILTER'),
        'max_results': max_results,
        
        'airtable_api_key': os.getenv('AIRTABLE_API_KEY'),
        'airtable_base_id': os.getenv('AIRTABLE_BASE_ID'),
        'airtable_table_name': os.getenv('AIRTABLE_TABLE_NAME'),
        
        'sync_interval': int(os.getenv('SYNC_INTERVAL_MINUTES', '60').split('#')[0].strip()),
        
        'field_map': field_map
    }

@click.command()
@click.option('--schedule/--no-schedule', default=False, 
              help='Run as a scheduled job or run once')
def main(schedule):
    """
    Synchronize Jira issues to Airtable
    
    :param schedule: Whether to run as a scheduled job
    """
    config = load_config()
    sync_manager = JiraAirtableSync(config)
    
    if schedule:
        scheduler = BlockingScheduler()
        scheduler.add_job(
            sync_manager.sync_issues, 
            'interval', 
            minutes=config['sync_interval']
        )
        
        logger.info(f"Starting scheduled sync every {config['sync_interval']} minutes")
        scheduler.start()
    else:
        sync_manager.sync_issues()

if __name__ == '__main__':
    main()
