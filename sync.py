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
        # Jira Connection
        self.jira_client = JIRA(
            server=config['jira_server'], 
            basic_auth=(config['jira_username'], config['jira_api_token'])
        )
        
        # Airtable Connection
        self.airtable_api = Api(config['airtable_api_key'])
        self.airtable_table = self.airtable_api.table(
            config['airtable_base_id'],
            config['airtable_table_name']
        )
        
        self.config = config
        self.field_map = config.get('field_map', {})

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
        Extract value for a specific Jira field
        
        :param issue: Jira issue object
        :param field: Field to extract
        :return: Extracted field value
        """
        try:
            if field == 'key':
                return issue.key
            elif field == 'summary':
                return issue.fields.summary
            elif field == 'description':
                return issue.fields.description
            elif field == 'reporter':
                return issue.fields.reporter.displayName if issue.fields.reporter else None
            elif field == 'assignee':
                return issue.fields.assignee.displayName if issue.fields.assignee else None
            elif field == 'issuetype':
                return issue.fields.issuetype.name
            elif field == 'status':
                return issue.fields.status.name
            elif field == 'parent':
                return issue.fields.parent.key if hasattr(issue.fields, 'parent') else None
            elif field == 'created':
                return str(issue.fields.created)
            elif field == 'updated':
                return str(issue.fields.updated)
            elif field == 'resolutiondate':
                return str(issue.fields.resolutiondate) if issue.fields.resolutiondate else None
            else:
                # Handle custom fields dynamically
                return getattr(issue.fields, field, None)
        except Exception as e:
            logger.error(f"Error extracting {field}: {e}")
            return None

    def sync_issues(self):
        """
        Synchronize Jira issues to Airtable
        """
        try:
            # Fetch Jira issues based on JQL
            issues = self.jira_client.search_issues(
                self.config.get('jira_jql', 'project = ' + self.config['jira_project_key']), 
                maxResults=1000
            )
            
            logger.info(f"Found {len(issues)} Jira issues to sync")
            
            for issue in issues:
                try:
                    record = self._transform_jira_issue(issue)
                    
                    # Search for existing record
                    existing_records = self.airtable_table.first(
                        formula=f"{{Jira Key}}='{issue.key}'"
                    )
                    
                    if existing_records:
                        # Update existing record
                        self.airtable_table.update(existing_records['id'], record)
                        logger.info(f"Updated issue {issue.key}")
                    else:
                        # Create new record
                        self.airtable_table.create(record)
                        logger.info(f"Created issue {issue.key}")
                
                except Exception as issue_sync_error:
                    logger.error(f"Error syncing issue {issue.key}: {issue_sync_error}")
        
        except Exception as sync_error:
            logger.error(f"Sync failed: {sync_error}")

def load_config():
    """
    Load configuration from environment variables
    
    :return: Configuration dictionary
    """
    load_dotenv()
    
    return {
        'jira_server': os.getenv('JIRA_SERVER'),
        'jira_username': os.getenv('JIRA_USERNAME'),
        'jira_api_token': os.getenv('JIRA_API_TOKEN'),
        'jira_project_key': os.getenv('JIRA_PROJECT_KEY'),
        'jira_jql': os.getenv('JIRA_JQL_FILTER'),
        
        'airtable_api_key': os.getenv('AIRTABLE_API_KEY'),
        'airtable_base_id': os.getenv('AIRTABLE_BASE_ID'),
        'airtable_table_name': os.getenv('AIRTABLE_TABLE_NAME'),
        
        'sync_interval': int(os.getenv('SYNC_INTERVAL_MINUTES', 60)),
        
        'field_map': json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}'))
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
