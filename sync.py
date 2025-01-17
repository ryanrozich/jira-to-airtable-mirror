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
