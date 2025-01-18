import json
import logging
import os
from typing import Any, Dict

from jira import JIRA
from pyairtable import Api
from pyairtable.formulas import match


logger = logging.getLogger(__name__)


class JiraAirtableSync:
    """Handles synchronization between Jira and Airtable."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the sync handler with configuration."""
        self.config = config
        self.jira = JIRA(
            server=config['jira']['server'],
            basic_auth=(config['jira']['username'], config['jira']['api_token'])
        )
        self.airtable = Api(config['airtable']['api_key'])
        self.base_id = config['airtable']['base_id']
        self.table_id = config['airtable']['table_id']
        self.table = self.airtable.table(self.base_id, self.table_id)
        self.field_mappings = config['field_mappings']
        self.tracking_fields = config.get('tracking_fields', {})

    def _get_issue_field_value(self, issue: Any, field_name: str) -> Any:
        """Extract field value from Jira issue."""
        try:
            field = getattr(issue.fields, field_name)
            if field is None:
                return None

            if isinstance(field, (str, int, float, bool)):
                return field

            if hasattr(field, 'value'):
                return field.value

            if hasattr(field, 'name'):
                return field.name

            if isinstance(field, list):
                if not field:
                    return None
                if hasattr(field[0], 'value'):
                    return [item.value for item in field]
                if hasattr(field[0], 'name'):
                    return [item.name for item in field]
                return field

            if hasattr(field, 'displayName'):
                return field.displayName

            return str(field)
        except Exception as e:
            logger.warning(f"Error getting field {field_name}: {str(e)}")
            return None

    def _transform_jira_issue(self, issue: Any) -> Dict[str, Any]:
        """Transform Jira issue to Airtable record format."""
        record = {}

        for airtable_field, jira_field in self.field_mappings.items():
            if isinstance(jira_field, dict):
                if 'type' in jira_field and jira_field['type'] == 'formula':
                    continue
                jira_field = jira_field['field']

            value = self._get_issue_field_value(issue, jira_field)
            if value is not None:
                record[airtable_field] = value

        for field, config in self.tracking_fields.items():
            if config.get('track_changes', False):
                record[f"{field}_history"] = []

        return record

    def add_select_option(self, field_name: str, option: str) -> None:
        """Add a new select option to an Airtable field."""
        try:
            schema = self.table.schema()
            field = next(
                (f for f in schema['fields'] if f['name'] == field_name),
                None
            )

            if not field:
                logger.warning(f"Field {field_name} not found in schema")
                return

            if field['type'] not in ['singleSelect', 'multipleSelects']:
                logger.warning(
                    f"Field {field_name} is not a select field"
                )
                return

            options = field.get('options', {}).get('choices', [])
            option_names = [opt.get('name') for opt in options]

            if option not in option_names:
                new_option = {'name': option}
                options.append(new_option)
                field['options']['choices'] = options

                self.table.update_schema([field])
                logger.info(f"Added option '{option}' to field '{field_name}'")

        except Exception as e:
            logger.error(
                f"Error adding select option '{option}' to field '{field_name}': {str(e)}"
            )

    def sync_issue(self, issue: Any) -> None:
        """Synchronize a single Jira issue to Airtable."""
        try:
            issue_key = issue.key
            logger.info(f"Syncing issue {issue_key}")

            transformed_data = self._transform_jira_issue(issue)
            formula = match({'Issue Key': issue_key})
            existing_records = self.table.all(formula=formula)

            if existing_records:
                record_id = existing_records[0]['id']
                self.table.update(record_id, transformed_data)
                logger.info(f"Updated record for issue {issue_key}")
            else:
                transformed_data['Issue Key'] = issue_key
                self.table.create(transformed_data)
                logger.info(f"Created record for issue {issue_key}")

        except Exception as e:
            logger.error(f"Error syncing issue {issue_key}: {str(e)}")

    def sync_issues(self) -> None:
        """Synchronize all matching Jira issues to Airtable."""
        try:
            jql = self.config['jira'].get('jql', '')
            batch_size = self.config['jira'].get('batch_size', 50)
            start_at = 0

            while True:
                issues = self.jira.search_issues(
                    jql,
                    startAt=start_at,
                    maxResults=batch_size
                )

                if not issues:
                    break

                for issue in issues:
                    self.sync_issue(issue)

                if len(issues) < batch_size:
                    break

                start_at += batch_size

        except Exception as e:
            logger.error(f"Error during sync: {str(e)}")
            raise


def validate_config(config: Dict[str, Any]) -> None:
    """Validate the configuration structure."""
    required_sections = ['jira', 'airtable', 'field_mappings']
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required section: {section}")

    if 'server' not in config['jira']:
        raise ValueError("Missing Jira server URL")

    if 'username' not in config['jira']:
        raise ValueError("Missing Jira username")

    if 'api_token' not in config['jira']:
        raise ValueError("Missing Jira API token")

    if 'api_key' not in config['airtable']:
        raise ValueError("Missing Airtable API key")

    if 'base_id' not in config['airtable']:
        raise ValueError("Missing Airtable base ID")

    if 'table_id' not in config['airtable']:
        raise ValueError("Missing Airtable table ID")


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables and config file."""
    try:
        config_path = os.getenv('CONFIG_PATH', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Override with environment variables if present
        if os.getenv('JIRA_SERVER'):
            config['jira']['server'] = os.getenv('JIRA_SERVER')

        if os.getenv('JIRA_USERNAME'):
            config['jira']['username'] = os.getenv('JIRA_USERNAME')

        if os.getenv('JIRA_API_TOKEN'):
            config['jira']['api_token'] = os.getenv('JIRA_API_TOKEN')

        if os.getenv('AIRTABLE_API_KEY'):
            config['airtable']['api_key'] = os.getenv('AIRTABLE_API_KEY')

        if os.getenv('AIRTABLE_BASE_ID'):
            config['airtable']['base_id'] = os.getenv('AIRTABLE_BASE_ID')

        if os.getenv('AIRTABLE_TABLE_ID'):
            config['airtable']['table_id'] = os.getenv('AIRTABLE_TABLE_ID')

        validate_config(config)
        return config

    except FileNotFoundError:
        raise ValueError(f"Config file not found at {config_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in config file {config_path}")
    except Exception as e:
        raise ValueError(f"Error loading config: {str(e)}")


def sync_issues(config: Dict[str, Any]) -> None:
    """Main function to sync issues from Jira to Airtable."""
    sync_handler = JiraAirtableSync(config)
    sync_handler.sync_issues()
