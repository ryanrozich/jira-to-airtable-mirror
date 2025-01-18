#!/usr/bin/env python3
import os
import json
import logging
from logging.handlers import RotatingFileHandler
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
        RotatingFileHandler(
            '/tmp/sync.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3,
            encoding='utf-8'
        ),
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
        
        # Validate Airtable schema and status field before proceeding
        self._validate_airtable_schema()
        self._validate_status_field()
        
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

    def _validate_status_field(self):
        """
        Validate that status field is properly mapped and exists in Airtable
        
        :raises ValueError: If status field mapping is invalid
        """
        if 'status' not in self.field_map:
            raise ValueError("Status field must be mapped in field_map configuration")
        
        status_field = self.field_map['status']
        try:
            # Check if status field exists in Airtable
            table_info = self.airtable_table.api.request(
                method="GET",
                url=f"https://api.airtable.com/v0/meta/bases/{self.config['airtable_base_id']}/tables"
            )
            
            table_meta = None
            for table in table_info["tables"]:
                if table["name"] == self.config["airtable_table_name"]:
                    table_meta = table
                    break
            
            if not table_meta:
                raise ValueError("Table not found in Airtable base")
            
            field_exists = False
            for field in table_meta["fields"]:
                if field["id"] == status_field:
                    field_exists = True
                    break
            
            if not field_exists:
                raise ValueError(f"Status field '{status_field}' not found in Airtable table")
            
            logger.info("✅ Status field validation successful")
            
        except Exception as e:
            logger.error(f"Status field validation failed: {str(e)}")
            raise ValueError(f"Status field validation failed: {str(e)}")

    def _get_issue_update_times(self, issue) -> Dict[str, Optional[str]]:
        """
        Get all relevant update timestamps from a Jira issue
        
        :param issue: Jira issue object
        :return: Dictionary containing different update timestamps
        """
        try:
            update_times = {
                'status_updated': None,
                'comment_updated': None
            }
            
            # Get status update time from changelog
            changelog = self.jira_client.issue(issue.key, expand='changelog').changelog
            for history in reversed(changelog.histories):
                for item in history.items:
                    if item.field == 'status':
                        update_times['status_updated'] = str(history.created)
                        break
                if update_times['status_updated']:
                    break
            
            # Get latest comment update time
            comments = self.jira_client.comments(issue)
            if comments:
                update_times['comment_updated'] = str(comments[-1].updated)
            
            return update_times
            
        except Exception as e:
            logger.error(f"Failed to get update times for issue {issue.key}: {str(e)}")
            return {
                'status_updated': None,
                'comment_updated': None
            }

    def _get_latest_comment(self, issue) -> Optional[Dict[str, Any]]:
        """
        Get the most recent comment from a Jira issue
        
        :param issue: Jira issue object
        :return: Dictionary containing comment details or None
        """
        try:
            comments = self.jira_client.comments(issue)
            if comments:
                latest = comments[-1]
                return {
                    'text': latest.body,
                    'author': latest.author.displayName,
                    'updated': latest.updated
                }
            return None
        except Exception as e:
            logger.error(f"Failed to fetch comments for issue {issue.key}: {str(e)}")
            return None

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

    def _transform_jira_issue(self, issue) -> Dict[str, Any]:
        """
        Transform Jira issue to Airtable record format
        
        :param issue: Jira issue object
        :return: Transformed record dictionary
        """
        record = {}
        
        # Get all update timestamps
        update_times = self._get_issue_update_times(issue)
        
        # Map update times to Airtable fields if configured
        if 'status_updated' in self.field_map and update_times['status_updated']:
            record[self.field_map['status_updated']] = update_times['status_updated']
        
        # Get the latest comment if configured
        if any(field in self.field_map for field in ['latest_comment', 'comment_author', 'comment_updated']):
            latest_comment = self._get_latest_comment(issue)
            if latest_comment:
                if 'latest_comment' in self.field_map:
                    record[self.field_map['latest_comment']] = latest_comment['text']
                if 'comment_author' in self.field_map:
                    record[self.field_map['comment_author']] = latest_comment['author']
                if 'comment_updated' in self.field_map:
                    record[self.field_map['comment_updated']] = latest_comment['updated']
        
        # Transform other fields
        for jira_field, airtable_field in self.field_map.items():
            if jira_field not in ['latest_comment', 'comment_author', 'comment_updated', 
                                'status_updated']:
                try:
                    value = self._get_issue_field_value(issue, jira_field)
                    if value is not None:
                        record[airtable_field] = value
                        
                        # Log status changes
                        if jira_field == 'status':
                            logger.info(f"Status change for {issue.key}: {value} (Updated: {update_times['status_updated']})")
                except Exception as e:
                    logger.warning(f"Could not map field {jira_field}: {e}")
        
        return record

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

    def add_select_option(self, field_id, new_option):
        """Add a new option to a single select field in Airtable."""
        try:
            logger.debug(f"Getting schema for field {field_id}")
            # Get current schema
            table_info = self.airtable_table.api.request(
                method="GET",
                url=f"https://api.airtable.com/v0/meta/bases/{self.config['airtable_base_id']}/tables"
            )
            logger.debug(f"Got table info: {json.dumps(table_info, indent=2)}")
            
            # Find our table and field
            field_meta = None
            table_id = None
            for table in table_info["tables"]:
                if table["name"] == self.config["airtable_table_name"]:
                    table_id = table["id"]
                    logger.debug(f"Found table {table['name']} with ID {table_id}")
                    for field in table["fields"]:
                        if field["id"] == field_id:
                            field_meta = field
                            logger.debug(f"Found field {field_id}: {json.dumps(field, indent=2)}")
                            break
                    break
            
            if not field_meta:
                logger.error(f"Field {field_id} not found in schema")
                return False
                
            if field_meta["type"] not in ['singleSelect', 'multipleSelects']:
                logger.error(f"Field {field_id} is type {field_meta['type']}, not a select field")
                return False
                
            # Get current choices and add new option if not present
            current_choices = [choice["name"] for choice in field_meta.get("options", {}).get("choices", [])]
            logger.debug(f"Current choices for field {field_id}: {current_choices}")
            
            if new_option not in current_choices:
                current_choices.append(new_option)
                logger.debug(f"Adding new option '{new_option}' to choices")
                
                # Update field options
                update_url = f"https://api.airtable.com/v0/meta/bases/{self.config['airtable_base_id']}/tables/{table_id}/fields/{field_id}"
                update_data = {
                    "options": {
                        "choices": [{"name": choice} for choice in current_choices]
                    }
                }
                logger.debug(f"Updating field options at {update_url}")
                logger.debug(f"Update payload: {json.dumps(update_data, indent=2)}")
                
                try:
                    response = self.airtable_table.api.request(
                        method="PATCH",
                        url=update_url,
                        json=update_data
                    )
                    logger.debug(f"Update response: {json.dumps(response, indent=2)}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to update field options: {str(e)}")
                    if hasattr(e, 'response'):
                        logger.error(f"Response status: {e.response.status_code}")
                        logger.error(f"Response body: {e.response.text}")
                    raise
                
            return True
        except Exception as e:
            logger.error(f"Failed to add select option '{new_option}' to field {field_id}: {str(e)}")
            return False

    def sync_issue(self, issue):
        """Sync a single Jira issue to Airtable."""
        try:
            # Transform Jira issue to Airtable record
            record = self._transform_jira_issue(issue)
            
            # Find existing record
            existing_records = self.airtable_table.all(
                formula=f"{{JIRA Key}} = '{issue.key}'"
            )
            
            try:
                if existing_records:
                    self.airtable_table.update(existing_records[0]['id'], record)
                else:
                    self.airtable_table.create(record)
                    
            except Exception as e:
                if '422 Client Error' in str(e) and 'INVALID_MULTIPLE_CHOICE_OPTIONS' in str(e):
                    # Extract the field and value from the error
                    error_msg = str(e)
                    # Find the value in quotes after "select option"
                    import re
                    match = re.search(r'select option "([^"]+)"', error_msg)
                    if match:
                        value = match.group(1)
                        # Find which field caused the error by checking the record
                        for jira_field, field_id in self.field_map.items():
                            if record.get(field_id) == value:
                                # Try to add the option and retry the update
                                if self.add_select_option(field_id, value):
                                    if existing_records:
                                        self.airtable_table.update(existing_records[0]['id'], record)
                                    else:
                                        self.airtable_table.create(record)
                                break
                else:
                    raise e
                    
            return True
        except Exception as e:
            logger.error(f"Failed to sync issue {issue.key}: {str(e)}")
            return False

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
            
            logger.debug(f"Base JQL: {jql}")
            
            # If we have a latest update time, only fetch issues updated after that time
            if latest_update:
                try:
                    # Parse the ISO datetime and convert to JQL format
                    update_dt = parser.parse(latest_update)
                    jql_date = update_dt.strftime('"%Y-%m-%d %H:%M"')
                    logger.debug(f"Parsed update time: {update_dt}, JQL date: {jql_date}")
                    
                    # Check for any type of update (issue or status changes)
                    jql = f"({jql}) AND (updated > {jql_date})"
                except Exception as e:
                    logger.error(f"Error parsing update time: {str(e)}")
                    raise
            
            # Add sorting by created date in ascending order
            jql = f"{jql} ORDER BY created ASC"
            logger.info(f"Final JQL query: {jql}")
            
            try:
                # Get all issues from Jira with changelog for status updates
                logger.debug("Fetching issues from Jira...")
                issues = self.jira_client.search_issues(
                    jql,
                    maxResults=0,
                    expand='changelog',  # Include changelog for status update tracking
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
                        'customfield_10016',
                        'comment'
                    ]
                )
                logger.info(f"Found {len(issues)} issues to sync")
            except Exception as e:
                logger.error(f"Error fetching issues from Jira: {str(e)}")
                raise
            
            # Process each issue
            for issue in issues:
                try:
                    logger.debug(f"Processing issue {issue.key}...")
                    # Transform the issue to Airtable format
                    record = self._transform_jira_issue(issue)
                    logger.debug(f"Transformed record: {json.dumps(record, indent=2)}")
                    
                    # Find existing record
                    existing_records = self.airtable_table.all(
                        formula=f"{{JIRA Key}} = '{issue.key}'"
                    )
                    
                    try:
                        if existing_records:
                            logger.debug(f"Updating existing record for {issue.key}")
                            self.airtable_table.update(existing_records[0]['id'], record)
                        else:
                            logger.debug(f"Creating new record for {issue.key}")
                            self.airtable_table.create(record)
                            
                    except Exception as e:
                        if '422 Client Error' in str(e) and 'INVALID_MULTIPLE_CHOICE_OPTIONS' in str(e):
                            logger.info(f"Handling invalid choice error for {issue.key}: {str(e)}")
                            # Extract the field and value from the error
                            error_msg = str(e)
                            # Find the value in quotes after "select option"
                            import re
                            match = re.search(r'select option "([^"]+)"', error_msg)
                            if match:
                                value = match.group(1)
                                logger.debug(f"Found invalid choice value: {value}")
                                # Find which field caused the error by checking the record
                                for jira_field, field_id in self.field_map.items():
                                    if record.get(field_id) == value:
                                        logger.info(f"Adding new option '{value}' to field {field_id}")
                                        # Try to add the option and retry the update
                                        if self.add_select_option(field_id, value):
                                            if existing_records:
                                                self.airtable_table.update(existing_records[0]['id'], record)
                                            else:
                                                self.airtable_table.create(record)
                                        break
                        else:
                            raise e
                    
                except Exception as e:
                    logger.error(f"Failed to process issue {issue.key}: {str(e)}")
                    continue
            
            logger.info("✅ Sync completed successfully")
            
        except Exception as sync_error:
            logger.error(f"❌ Sync failed: {str(sync_error)}")
            logger.debug("Full error details:", exc_info=True)

def get_secret_from_aws(secret_arn: str) -> str:
    """
    Get a secret from AWS Secrets Manager
    
    :param secret_arn: ARN of the secret in AWS Secrets Manager
    :return: Secret value or None if retrieval fails
    """
    try:
        import boto3
        client = boto3.client('secretsmanager')
        response = client.get_secret_value(SecretId=secret_arn)
        return response['SecretString']
    except Exception as e:
        logger.error(f"Failed to get secret from AWS: {str(e)}")
        return None

def get_secret(secret_ref: str, cloud_provider: str = None) -> str:
    """
    Get a secret from the appropriate source based on the reference format and environment
    
    :param secret_ref: Secret reference (env var value or AWS secret ARN)
    :param cloud_provider: Cloud provider name ('aws' if specified)
    :return: Secret value
    """
    if not secret_ref:
        return None
        
    # If we're running in AWS Lambda, check for secret ARNs in environment
    if cloud_provider == 'aws':
        # Map of environment variables to their corresponding secret ARN variables
        secret_arn_map = {
            'JIRA_API_TOKEN': 'JIRA_API_TOKEN_SECRET_ARN',
            'AIRTABLE_API_KEY': 'AIRTABLE_API_KEY_SECRET_ARN'
        }
        
        # If this is a secret variable and we have its ARN, get from Secrets Manager
        for secret_var, arn_var in secret_arn_map.items():
            if secret_ref == secret_var:  # If the reference is the name of a secret var
                secret_arn = os.getenv(arn_var)
                if secret_arn:
                    logger.info(f"Getting {secret_var} from AWS Secrets Manager")
                    return get_secret_from_aws(secret_arn)
    
    # If it's a direct AWS secret ARN
    if secret_ref.startswith('arn:aws:secretsmanager:'):
        return get_secret_from_aws(secret_ref)
    
    # Otherwise treat as direct value
    return secret_ref

def load_config():
    """
    Load configuration from environment variables with support for different environments
    
    Supports:
    - Local development with .env file
    - AWS Lambda with environment variables and Secrets Manager
    - Docker containers with environment variables
    
    :return: Configuration dictionary
    :raises ValueError: If any required environment variables are missing
    """
    # Load .env file if it exists (for local development)
    if os.path.exists('.env'):
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
    
    # Detect cloud environment
    cloud_provider = 'aws' if os.getenv('AWS_LAMBDA_FUNCTION_NAME') else None
    
    # Log environment variable status (safely)
    logger.info(f"Loading configuration for environment: {'cloud-' + cloud_provider if cloud_provider else 'local'}")
    logger.info("Checking environment variables...")
    
    # Initialize config dictionary
    config = {}
    missing_vars = []
    
    for var, description in required_vars.items():
        # For sensitive variables in AWS Lambda, use the variable name as a reference
        if cloud_provider == 'aws' and (var.endswith('_API_TOKEN') or var.endswith('_API_KEY')):
            secret_value = get_secret(var, cloud_provider)
            if secret_value:
                config[var.lower()] = secret_value
                logger.info(f"✓ {var}: [SECRET LOADED FROM AWS]")
                continue
        
        # For all other variables, get from environment
        value = os.getenv(var, '')
        is_set = bool(value and value.strip())
        
        # For sensitive variables in non-Lambda environments
        if not cloud_provider and (var.endswith('_API_TOKEN') or var.endswith('_API_KEY')):
            secret_value = get_secret(value, cloud_provider)
            if secret_value:
                config[var.lower()] = secret_value
                logger.info(f"✓ {var}: [SECRET LOADED]")
                continue
            elif not value:
                missing_vars.append(f"{var} ({description})")
                logger.info(f"✗ {var}: [MISSING]")
                continue
        
        # For non-sensitive values or if not a secret reference
        if is_set:
            config[var.lower()] = value
            if not var.endswith('_API_TOKEN') and not var.endswith('_API_KEY'):
                logger.info(f"✓ {var}: {value}")
            else:
                logger.info(f"✓ {var}: [SET]")
        else:
            missing_vars.append(f"{var} ({description})")
            logger.info(f"✗ {var}: [MISSING]")
    
    if missing_vars:
        error_msg = "Missing required environment variables:\n- " + "\n- ".join(missing_vars)
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Parse optional configurations
    try:
        # Field mapping
        if isinstance(config.get('jira_to_airtable_field_map'), str):
            config['field_map'] = json.loads(config['jira_to_airtable_field_map'])
        logger.info(f"✓ Field mapping loaded with {len(config['field_map'])} fields")
        
        # Other optional configs
        config.update({
            'jira_jql': os.getenv('JIRA_JQL_FILTER'),
            'max_results': int(os.getenv('MAX_RESULTS')) if os.getenv('MAX_RESULTS') else None,
            'sync_interval': int(os.getenv('SYNC_INTERVAL_MINUTES', '60').split('#')[0].strip()),
        })
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in JIRA_TO_AIRTABLE_FIELD_MAP: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except ValueError as e:
        error_msg = f"Invalid numeric value in configuration: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info("✓ Configuration loaded successfully")
    return config

def sync_jira_to_airtable():
    """
    Main function to synchronize Jira issues to Airtable.
    This function is called by the Lambda handler.
    """
    config = load_config()
    sync = JiraAirtableSync(config)
    sync.sync_issues()

@click.command()
@click.option('--schedule/--no-schedule', default=False, 
              help='Run as a scheduled job or run once')
def main(schedule):
    """
    Synchronize Jira issues to Airtable
    
    :param schedule: Whether to run as a scheduled job
    """
    if schedule:
        scheduler = BlockingScheduler()
        scheduler.add_job(
            sync_jira_to_airtable, 
            'interval', 
            minutes=int(os.getenv('SYNC_INTERVAL_MINUTES', '60').split('#')[0].strip())
        )
        
        logger.info(f"Starting scheduled sync every {int(os.getenv('SYNC_INTERVAL_MINUTES', '60').split('#')[0].strip())} minutes")
        scheduler.start()
    else:
        sync_jira_to_airtable()

if __name__ == '__main__':
    main()
