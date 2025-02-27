import logging
import os
import time
from datetime import datetime
from functools import wraps
from logging import getLogger
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pytz
from jira import JIRA
from pyairtable import Api, Table

from config import SyncConfig, get_config_loader


# Configure logging
logger = getLogger(__name__)


class JiraAirtableSync:
    """Handles synchronization between Jira and Airtable."""

    def __init__(self, config: SyncConfig):
        """
        Initialize the sync handler with configuration.

        Args:
            config: Configuration object containing Jira and Airtable settings
        """
        self.config = config
        self.jira = JIRA(
            server=config.jira_server,
            basic_auth=(config.jira_username, config.jira_api_token)
        )
        self.airtable = Api(config.airtable_api_key)
        self.table = Table(
            api_key=config.airtable_api_key,
            base_id=config.airtable_base_id,
            table_name=config.airtable_table_name
        )
        self.field_mappings = self._init_field_mappings()
        self.reverse_field_mappings = {v['airtable_field_id']: k for k, v in self.field_mappings.items()}
        
        try:
            logger.info(f"Attempting to connect to JIRA server at {config.jira_server}")
            logger.info(f"Successfully authenticated to JIRA as {config.jira_username}")
        except Exception as e:
            logger.error(f"Failed to connect to JIRA: {str(e)}")
            raise
            
        # Initialize sync state
        self.jira_issue_buffer = []
        self.current_batch = []
        
        # Fetch and populate Airtable field names
        self._populate_field_names()
        
        # Log initialization details
        logger.info(f"Initializing sync from Jira project {self.config.jira_project_key} to Airtable table {config.airtable_table_name}")
        logger.info(f"Jira Server: {config.jira_server}")
        logger.info(f"Airtable Base: {config.airtable_base_id}")
        logger.info(f"Using batch size of {config.batch_size} for Airtable operations")
        
        # Add debug logging for environment variables
        logger.debug(f"Environment variables: {dict(os.environ)}")

    def _init_field_mappings(self) -> Dict[str, Dict[str, str]]:
        """Initialize field mappings from configuration."""
        logger.debug("Initializing field mappings")
        return self.config.field_mappings

    def _get_jira_timezone(self) -> str:
        """Get the timezone setting from Jira instance."""
        try:
            # For Jira Cloud, get the timezone from the current user
            myself = self.jira.myself()
            user_tz = myself.get('timeZone')
            if user_tz:
                return user_tz
            
            # Fall back to UTC if no timezone is found
            logger.warning("No timezone found in Jira user profile, falling back to UTC")
            return "UTC"
        except Exception as e:
            logger.warning(f"Error getting Jira timezone, falling back to UTC: {str(e)}")
            return "UTC"

    def _populate_field_names(self) -> None:
        """
        Fetch field names from Airtable and populate them in field_mappings.
        This ensures we have the current field names even if they change in Airtable.
        """
        try:
            # Get field metadata from Airtable
            schema = self.table.schema()
            field_map = {field.id: field.name for field in schema.fields}
            logger.debug(f"Retrieved {len(field_map)} field names from Airtable")

            # Update field mappings with names
            for jira_field, airtable_info in self.field_mappings.items():
                field_id = airtable_info.get('airtable_field_id')
                # Only fetch and populate field name if it's not already provided
                if field_id and not airtable_info.get('airtable_field_name'):
                    airtable_info['airtable_field_name'] = None
                    # Only populate if this is the 'updated' field which needs the name for sorting
                    if jira_field == 'updated':
                        airtable_info['airtable_field_name'] = field_map.get(field_id)
                        if not airtable_info['airtable_field_name']:
                            logger.warning(f"Could not find field name for Jira field '{jira_field}' (ID: {field_id})")

        except Exception as e:
            logger.error(f"Error fetching Airtable field names: {str(e)}", exc_info=True)
        
    def _get_airtable_field_name(self, jira_field: str) -> Optional[str]:
        """Get the Airtable field name for a given Jira field."""
        if jira_field in self.field_mappings:
            return self.field_mappings[jira_field].get('airtable_field_name')
        return None

    def _get_airtable_field_id(self, jira_field: str) -> Optional[str]:
        """
        Get the Airtable field ID for a given Jira field.
        
        Args:
            jira_field: Jira field name
            
        Returns:
            Airtable field ID or None if not found
        """
        if jira_field in self.field_mappings:
            mapping = self.field_mappings[jira_field]
            if isinstance(mapping, dict) and 'airtable_field_id' in mapping:
                return mapping['airtable_field_id']
            elif isinstance(mapping, str):
                # For backward compatibility with old format
                return mapping
        
        logger.warning(f"No Airtable field mapping found for Jira field: {jira_field}")
        return None

    def retry_with_backoff(retries: int = 3, backoff_in_seconds: int = 1) -> Callable:
        """
        Retry decorator with exponential backoff.
        
        Args:
            retries: Maximum number of retries
            backoff_in_seconds: Initial backoff time in seconds
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                
                for i in range(retries):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if i == retries - 1:  # Last attempt
                            logger.error(f"Final retry attempt failed for {func.__name__}: {str(e)}")
                            raise  # Re-raise the last exception
                        
                        wait_time = (backoff_in_seconds * 2 ** i)  # Exponential backoff
                        logger.warning(f"Attempt {i + 1} failed for {func.__name__}: {str(e)}. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                return None  # Should never reach here
            return wrapper
        return decorator

    def _format_jira_timestamp(self, timestamp: str) -> Optional[str]:
        """Format a timestamp for use in Jira JQL queries."""
        try:
            # Parse ISO format timestamp
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            # Convert to configured timezone
            target_tz = pytz.timezone(self._get_jira_timezone())
            local_dt = dt.astimezone(target_tz)
            
            # Format to Jira's supported minute precision
            formatted = local_dt.strftime('%Y-%m-%d %H:%M')
            logger.debug(f"Converting timestamp from UTC ({timestamp}) to "
                        f"Jira instance timezone {self._get_jira_timezone()} ({formatted})")
            return formatted
        except Exception as e:
            logger.error(f"Error formatting timestamp {timestamp}: {e}")
            return None

    def _format_bytes(self, num_bytes: int) -> str:
        """
        Format bytes into human readable string (e.g., KB, MB, GB).

        Args:
            num_bytes: Number of bytes to format

        Returns:
            Formatted string with appropriate unit
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if num_bytes < 1024.0:
                return f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} TB"

    @retry_with_backoff(retries=3, backoff_in_seconds=1)
    def _get_most_recent_jira_update_time(self) -> Optional[str]:
        """
        Get the most recent Jira update timestamp from Airtable records.
        This timestamp represents the last time any Jira issue was updated
        that we have stored in Airtable.
        """
        try:
            # Get the updated field ID from field mappings
            updated_field = self._get_airtable_field_name('updated')
            if not updated_field:
                logger.warning("No 'updated' field mapping found in JIRA_TO_AIRTABLE_FIELD_MAP")
                return None

            logger.info(f"Looking for most recent Jira update timestamp in Airtable field: {updated_field}")
            
            # Sort by the updated field in descending order to get most recent first
            records = self.table.all(
                sort=['-' + updated_field],  # Changed sort format to match pyairtable's expectations
                max_records=1,
                fields=[updated_field]
            )
            
            if records:
                if records[0]['fields'].get(updated_field):
                    last_update = records[0]['fields'][updated_field]
                    logger.info(f"Most recent Jira update timestamp in Airtable: {last_update}")
                    return last_update
                else:
                    logger.info(f"Most recent record has no value in {updated_field} field")
            else:
                logger.info("No records found in Airtable")
                    
            logger.info("No Jira update timestamp found in Airtable")
            return None
        except Exception as e:
            logger.error(f"Error getting last Jira update time: {str(e)}", exc_info=True)
            return None

    @retry_with_backoff(retries=3, backoff_in_seconds=1)
    def _fetch_updated_jira_issues(self) -> List[Any]:
        """
        Fetch all Jira issues that have been updated since the last sync.
        Uses pagination to ensure all matching issues are retrieved.
        Orders issues by key to ensure consistent processing order.
        """
        last_sync = self._get_most_recent_jira_update_time()
        jql_filter = os.getenv('JIRA_JQL_FILTER', '')
        
        # Build JQL query
        jql_parts = [f"project = {self.config.jira_project_key}"]
        if last_sync:
            formatted_time = self._format_jira_timestamp(last_sync)
            jql_parts.append(f"updated > '{formatted_time}'")
        if jql_filter:
            jql_parts.append(f"({jql_filter})")
        
        jql = " AND ".join(jql_parts)
        jql += " ORDER BY key ASC"  # Ensure consistent ordering
        
        logger.debug(f"Fetching Jira issues with JQL: {jql}")
        
        # Get total issue count first
        total_issues = self.jira.search_issues(jql, maxResults=0).total
        logger.info(f"Total Jira issues to fetch: {total_issues}")
        
        # Fetch issues in batches
        all_issues = []
        total_bytes = 0
        start_at = 0
        max_results = int(os.getenv('MAX_RESULTS', '100'))
        
        while start_at < total_issues:
            end_at = min(start_at + max_results, total_issues)
            logger.info(f"Fetching Jira issues {start_at + 1} to {end_at} of {total_issues}")
            
            batch = self.jira.search_issues(
                jql,
                startAt=start_at,
                maxResults=max_results,
                expand=['changelog'],  # Include changelog for additional fields
                fields='*all,comment'  # Include all fields and comments
            )
            batch_size = sum(len(str(issue.raw)) for issue in batch)
            total_bytes += batch_size
            logger.info(f"Retrieved {len(batch)} issues ({self._format_bytes(batch_size)})")
            
            all_issues.extend(batch)
            start_at += len(batch)  # Use actual batch size for pagination
            
        logger.info(f"Successfully retrieved {len(all_issues)} issues (Total size: {self._format_bytes(total_bytes)})")
        return all_issues

    @retry_with_backoff(retries=3, backoff_in_seconds=1)
    def _batch_create_with_progress(self, records: List[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Create records in batches with progress tracking and error handling.
        
        Args:
            records: List of records to create
            
        Returns:
            Tuple containing count of created records and list of failed records
        """
        created_count = 0
        failed_records = []
        
        try:
            created = self.table.batch_create(records)
            created_count = len(created)
        except Exception as e:
            logger.error(f"Error in batch creation: {str(e)}")
            # If the batch fails, try creating records one by one to identify problematic records
            for record in records:
                try:
                    self.table.create(record)
                    created_count += 1
                except Exception as record_error:
                    logger.warning(f"Failed to create record: {str(record_error)}")
                    failed_records.append(record)
        
        return created_count, failed_records

    @retry_with_backoff(retries=3, backoff_in_seconds=1)
    def _batch_update_with_progress(self, batch: List[Union[Dict, Tuple]], include_keys: bool = False) -> Tuple[int, List[str]]:
        """
        Update a batch of records with progress tracking and error handling.
        
        Args:
            batch: List of records to update. Each record can be either:
                  - A dict with 'id' and 'fields' keys
                  - A tuple of (record_id, fields_dict)
            include_keys: Whether the batch includes Jira keys for error tracking
            
        Returns:
            Tuple of (number of successful updates, list of failed Jira keys)
        """
        try:
            logger.debug(f"Updating batch of {len(batch)} records")
            
            # Convert records to the format expected by Airtable
            formatted_batch = []
            for record in batch:
                if isinstance(record, tuple):
                    # Handle tuple format (record_id, fields_dict)
                    record_id, fields = record
                    formatted_record = {"id": record_id, "fields": fields}
                else:
                    # Handle dictionary format
                    formatted_record = record
                    
                logger.debug(f"Updating record {formatted_record['id']} with fields: {formatted_record['fields']}")
                formatted_batch.append(formatted_record)
            
            # Perform the batch update
            updated_records = self.table.batch_update(formatted_batch)
            return len(updated_records), []
            
        except Exception as e:
            logger.error(f"Error in batch update: {str(e)}", exc_info=True)
            # Extract Jira keys from the batch for error tracking if available
            failed_keys = []
            if include_keys:
                key_field = self._get_airtable_field_id('key')
                for record in batch:
                    if isinstance(record, tuple):
                        fields = record[1]
                    else:
                        fields = record.get('fields', {})
                    
                    if key_field in fields:
                        failed_keys.append(fields[key_field])
            
            return 0, failed_keys

    def _get_issue_field_value(self, issue: Any, field_name: str) -> Any:
        """
        Extract field value from Jira issue.

        This method handles various field types and edge cases, including:
        - Direct field access
        - Special handling for 'key', 'parent', 'latest_comment', 'comment_author',
          'comment_updated', and 'status_updated' fields
        - Handling for fields with 'value', 'name', or 'displayName' attributes
        - Handling for list fields

        Args:
            issue: Jira issue object
            field_name: Name of the field to extract (Jira field name)

        Returns:
            Field value, or None if not found
        """
        try:
            logger.debug(f"[{issue.key}] Getting Jira field '{field_name}'")

            # Special case for 'key' field which is accessed directly from issue
            if field_name == 'key':
                return issue.key

            # Special handling for parent field
            if field_name == 'parent':
                logger.debug(f"[{issue.key}] Processing parent field")
                if hasattr(issue.fields, 'parent'):
                    parent = issue.fields.parent
                    logger.debug(f"[{issue.key}] Parent field found: {parent}")
                    return parent.key if parent else None
                logger.debug(f"[{issue.key}] No parent field found")
                return None

            # Special handling for comment-related fields
            if field_name in ['latest_comment', 'comment_author', 'comment_updated']:
                return self._get_comment_field_value(issue, field_name)

            # Special handling for status_updated field
            if field_name == 'status_updated':
                return self._get_status_updated_value(issue)

            # Try to get the field from issue.fields
            if not hasattr(issue, 'fields'):
                logger.warning(f"[{issue.key}] Issue has no fields attribute")
                return None

            # Handle both standard fields and custom fields
            field = None
            try:
                field = getattr(issue.fields, field_name)
            except AttributeError:
                logger.debug(f"[{issue.key}] Field '{field_name}' not found in issue fields")
                return None

            if field is None:
                return None

            logger.debug(f"[{issue.key}] Retrieved field value: {field}")
            return self._process_field_value(field)

        except Exception as e:
            logger.warning(f"[{issue.key}] Error getting Jira field {field_name}: {str(e)}")
            return None

    def _get_comment_field_value(self, issue: Any, field_name: str) -> Optional[str]:
        """Extract value from comment-related fields."""
        logger.debug(f"[{issue.key}] Processing comment field '{field_name}'")
        if not hasattr(issue.fields, 'comment'):
            logger.debug(f"[{issue.key}] No comments field found")
            return None

        comments = issue.fields.comment.comments
        if not comments:
            return None

        latest_comment = comments[-1]  # Get the most recent comment
        logger.debug(f"[{issue.key}] Latest comment: {latest_comment}")

        if field_name == 'latest_comment':
            return latest_comment.body
        elif field_name == 'comment_author':
            return (latest_comment.author.displayName 
                   if hasattr(latest_comment.author, 'displayName') 
                   else str(latest_comment.author))
        elif field_name == 'comment_updated':
            return latest_comment.updated
        return None

    def _get_status_updated_value(self, issue: Any) -> Optional[str]:
        """Extract the latest status update time."""
        logger.debug(f"[{issue.key}] Processing status_updated field")
        if not hasattr(issue, 'changelog'):
            logger.debug(f"[{issue.key}] No changelog found")
            return None

        status_changes = [
            (history.created, item)
            for history in issue.changelog.histories
            for item in history.items if item.field == 'status'
        ]
        logger.debug(f"[{issue.key}] Found {len(status_changes)} status changes")
        if status_changes:
            # Sort by created date to get the most recent
            status_changes.sort(key=lambda x: x[0])
            latest_update_time = status_changes[-1][0]
            logger.debug(f"[{issue.key}] Latest status change time: {latest_update_time}")
            return latest_update_time
        return None

    def _process_field_value(self, field: Any) -> Any:
        """Process field value based on its type."""
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

    def _convert_issue_to_record(self, issue: Any) -> Dict[str, Any]:
        """
        Convert a Jira issue to an Airtable record format.

        Args:
            issue: Jira issue to convert (object or dictionary)

        Returns:
            Dictionary containing the Airtable record data
        """
        record_data = {}
        
        # If the issue is already in dictionary format with field IDs, just return it
        if isinstance(issue, dict):
            # Check if this is already formatted for Airtable (has field IDs as keys)
            # We'll check if at least one key matches our expected Airtable field IDs pattern
            has_field_ids = any(key.startswith('fld') for key in issue.keys())
            if has_field_ids:
                return issue
                
            # Otherwise, we need to convert from a Jira dictionary to Airtable format
            # This would happen if we have a dict with Jira field names instead of Airtable field IDs
            for jira_field, airtable_field in self.field_mappings.items():
                airtable_field_id = airtable_field['airtable_field_id']
                
                # Skip parent field - we'll handle parent relationships separately
                if jira_field == 'parent':
                    continue
                    
                if jira_field in issue:
                    value = issue[jira_field]
                    record_data[airtable_field_id] = value
            return record_data
            
        # For object format (standard Jira issue object)
        for jira_field, airtable_field in self.field_mappings.items():
            airtable_field_id = airtable_field['airtable_field_id']
            
            # Skip parent field - we'll handle parent relationships separately
            if jira_field == 'parent':
                continue
                
            field_value = self._get_issue_field_value(issue, jira_field)
            if field_value is not None:
                record_data[airtable_field_id] = field_value
                
        return record_data

    def add_select_option(self, field_name: str, option: str) -> None:
        """
        Add a new select option to an Airtable field.

        This method updates the Airtable field schema to include the new option.

        Args:
            field_name: Name of the Airtable field
            option: New option to add
        """
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

    def _get_airtable_ids_for_keys(self, keys: set[str]) -> Dict[str, Optional[str]]:
        """
        Query Airtable to get record IDs for a set of Jira issue keys.

        This method handles the complexity of querying Airtable with potentially large sets of keys
        by breaking them into smaller chunks to avoid hitting Airtable's formula length limits.

        Args:
            keys: Set of Jira issue keys to look up in Airtable

        Returns:
            Dictionary mapping Jira keys to their corresponding Airtable record IDs.
            If a key is not found, its value will be None.
        """
        key_field_id = self._get_airtable_field_id('key')
        id_map = {key: None for key in keys}  # Initialize all keys to None

        # Process in chunks to avoid Airtable's formula length limits
        CHUNK_SIZE = 50  # Airtable has limits on formula complexity/length
        key_chunks = [list(keys)[i:i + CHUNK_SIZE] for i in range(0, len(keys), CHUNK_SIZE)]

        for chunk in key_chunks:
            # Build OR formula to find any records matching the keys in this chunk
            formula_parts = [f"{{'{key_field_id}'}} = '{key}'" for key in chunk]
            formula = f"OR({','.join(formula_parts)})"
            logger.debug(f"Querying Airtable for {len(chunk)} keys with formula: {formula}")

            try:
                records = self.table.all(formula=formula)
                for record in records:
                    jira_key = record['fields'].get(key_field_id)
                    if jira_key:
                        id_map[jira_key] = record['id']
            except Exception as e:
                logger.error(f"Error querying records: {e}", exc_info=True)

        return id_map


    def _get_existing_record_ids(self, jira_keys: List[str]) -> Dict[str, str]:
        """
        Get Airtable record IDs for existing Jira issues.

        Args:
            jira_keys: List of Jira issue keys to look up

        Returns:
            Dictionary mapping Jira keys to their Airtable record IDs
        """
        if not jira_keys:
            return {}

        key_field_id = self._get_airtable_field_id('key')
        key_field_name = self._get_airtable_field_name('key')
        logger.debug(f"Field mappings in _get_existing_record_ids: {self.field_mappings}")
        logger.debug(f"Key field ID: {key_field_id}, field name: {key_field_name}")
        if not key_field_id or not key_field_name:
            logger.error("No 'key' field mapping found in field_mappings")
            return {}

        logger.debug(f"Looking up existing records for {len(jira_keys)} Jira keys: {jira_keys}")
        logger.debug(f"Using Airtable field '{key_field_name}' for Jira key lookup")

        # Get records in chunks to avoid formula length limits
        chunk_size = 100  # Adjust if needed based on key lengths
        key_to_record_id = {}

        for i in range(0, len(jira_keys), chunk_size):
            chunk = jira_keys[i:i + chunk_size]
            # Build OR condition for each key - wrap field names with spaces in curly braces
            conditions = [f"{{{key_field_name}}} = '{key}'" for key in chunk]
            formula = f"OR({','.join(conditions)})"

            try:
                logger.debug(f"Querying Airtable with formula: {formula}")
                records = self.table.all(formula=formula)
                logger.debug(f"Found {len(records)} matching records")

                # Map each record's key to its ID
                for record in records:
                    logger.debug(f"Processing record: {record}")
                    jira_key = record['fields'].get(key_field_name)
                    if jira_key:
                        if jira_key in key_to_record_id:
                            logger.warning(
                                f"Found duplicate record for Jira key {jira_key}. "
                                f"Previous record ID: {key_to_record_id[jira_key]}, "
                                f"New record ID: {record['id']}"
                            )
                        key_to_record_id[jira_key] = record['id']

            except Exception as e:
                logger.error(f"Error looking up records for keys {chunk}: {e}", exc_info=True)

        logger.info(f"Found {len(key_to_record_id)} existing records in Airtable")
        return key_to_record_id

    def _process_issue_batch(self, issues: List[Any], existing_record_ids: Dict[str, str]) -> None:
        """
        Process a batch of Jira issues and sync them to Airtable.

        Args:
            issues: List of Jira issues to process
            existing_record_ids: Dictionary mapping Jira keys to Airtable record IDs
        """
        records_to_create = []
        records_to_update = []
        keys_to_process = set()

        for issue in issues:
            # Handle both dictionary and object formats
            if isinstance(issue, dict):
                # For dictionary format, get the key from the field ID that corresponds to "key"
                key_field_id = self._get_airtable_field_id('key')
                key = issue.get(key_field_id)
                if not key:
                    logger.warning(f"Could not find Jira key in issue dictionary using field ID {key_field_id}")
                    continue
            else:
                # For object format, get the key directly
                key = issue.key
                
            keys_to_process.add(key)
            record_data = self._convert_issue_to_record(issue)

            # Check if this issue already exists in Airtable
            if key in existing_record_ids and existing_record_ids[key]:
                # Update existing record
                record_id = existing_record_ids[key]
                records_to_update.append({"id": record_id, "fields": record_data})
                logger.debug(f"Updating existing record for {key} (Airtable ID: {record_id})")
            else:
                # Create new record
                records_to_create.append(record_data)
                logger.debug(f"Creating new record for {key}")
        
        if records_to_create:
            logger.info(f"Creating {len(records_to_create)} new records")
            try:
                created, failed = self._batch_create_with_progress(records_to_create)
                logger.info(f"Created {created} new records")
                if failed:
                    logger.warning(f"Failed to create {len(failed)} records: {failed}")
            except Exception as e:
                logger.error(f"Error creating records: {str(e)}")
                raise

        if records_to_update:
            logger.info(f"Updating {len(records_to_update)} existing records")
            try:
                # The records_to_update is now in the format expected by batch_update
                self.table.batch_update(records_to_update)
                logger.info(f"Updated {len(records_to_update)} records")
            except Exception as e:
                logger.error(f"Error updating records: {str(e)}")
                raise

        # Update parent relationships after all records are created/updated
        self._update_parent_relationships(issues, existing_record_ids)

    def _extract_parent_key(self, issue: Any) -> Optional[str]:
        """
        Extract the parent key from a Jira issue.
        
        Args:
            issue: Jira issue (object or dictionary)
            
        Returns:
            Parent key or None if no parent
        """
        if isinstance(issue, dict):
            # For dictionary format, check if parent exists
            parent_field = None
            for jira_field, airtable_field in self.field_mappings.items():
                if jira_field == 'parent':
                    parent_field = jira_field
                    break
            
            if parent_field and parent_field in issue:
                return issue[parent_field]
        else:
            # For object format
            if hasattr(issue, 'fields') and hasattr(issue.fields, 'parent'):
                return issue.fields.parent.key
                
        return None

    def _update_parent_relationships(self, issues: List[Any], 
                                  existing_record_ids: Dict[str, str]) -> None:
        """
        Update parent-child relationships in Airtable.

        Args:
            issues: List of Jira issues to process
            existing_record_ids: Dictionary mapping Jira keys to Airtable record IDs
        """
        parent_updates = []
        
        for issue in issues:
            # Get the issue key based on the type
            if isinstance(issue, dict):
                key_field_id = self._get_airtable_field_id('key')
                if not key_field_id or key_field_id not in issue:
                    logger.warning(f"Could not find key field in issue: {issue}")
                    continue
                issue_key = issue[key_field_id]
            else:
                issue_key = issue.key
                
            parent_key = self._extract_parent_key(issue)
            if parent_key:
                logger.debug(f"Processing parent relationship: {issue_key} -> {parent_key}")
                
                # Skip if either child or parent is not in Airtable
                if issue_key not in existing_record_ids:
                    logger.warning(f"Child issue {issue_key} not found in Airtable")
                    continue
                if parent_key not in existing_record_ids:
                    logger.warning(f"Parent issue {parent_key} not found in Airtable")
                    continue
                        
                child_record_id = existing_record_ids[issue_key]
                parent_record_id = existing_record_ids[parent_key]
                
                # Get the field ID for parent
                parent_field_id = self._get_airtable_field_id('parent')
                if not parent_field_id:
                    logger.warning("Missing parent field ID in field mappings")
                    continue
                    
                # Add to batch updates
                parent_updates.append({
                    "id": child_record_id,
                    "fields": {
                        parent_field_id: [parent_record_id]  # Must be an array of record IDs
                    }
                })
        
        # Process all parent updates in a single batch
        if parent_updates:
            try:
                logger.info(f"Updating {len(parent_updates)} parent relationships")
                self.table.batch_update(parent_updates)
                logger.info(f"Successfully updated parent relationships")
            except Exception as e:
                logger.error(f"Error updating parent relationships: {str(e)}")

    def sync_issues(self) -> None:
        """
        Synchronize Jira issues to Airtable using an incremental approach.

        This implementation:
        1. Gets the last sync time from Airtable
        2. Fetches only Jira issues updated since then
        3. First Pass: Creates/updates all records (without parent links)
        4. Second Pass: Updates parent links

        This approach ensures efficient syncing by:
        - Only processing recently updated issues
        - Handling both new and existing records
        - Maintaining parent relationships correctly
        - Implementing retry logic for API calls
        - Providing detailed progress and error tracking
        """
        try:
            logger.info("Starting Jira to Airtable sync")

            # Step 1: Fetch updated Jira issues
            issues = self._fetch_updated_jira_issues()

            if not issues:
                logger.info("No issues found to sync")
                return

            # Step 2: Transform issues and prepare for sync
            transformed_issues = []
            key_to_parent = {}  # Store parent relationships for second pass
            all_keys = set()  # Track all keys for existing record lookup
            transform_errors = []  # Track issues that failed to transform

            total_issues = len(issues)
            logger.info(f"Processing {total_issues} issues")

            for i, issue in enumerate(issues, 1):
                if i % 100 == 0:  # Log progress every 100 issues
                    logger.info(f"Transforming issues: {i}/{total_issues}")

                try:
                    data = self._convert_issue_to_record(issue)
                    parent_key = self._extract_parent_key(issue)

                    # Store parent relationship for second pass
                    if parent_key:
                        key_to_parent[issue.key] = parent_key
                        all_keys.add(parent_key)  # Add parent key to lookup set

                    transformed_issues.append((issue.key, data))
                    all_keys.add(issue.key)
                except Exception as e:
                    transform_errors.append(issue.key)
                    logger.error(f"[{issue.key}] Error transforming issue: {str(e)}", exc_info=True)

            logger.info(f"Successfully transformed {len(transformed_issues)} issues")
            if transform_errors:
                logger.error(
                    f"Failed to transform {len(transform_errors)} issues: {', '.join(transform_errors)}"
                )
            if key_to_parent:
                logger.info(f"Found {len(key_to_parent)} issues with parent relationships")

            # Step 3: First pass - get existing record IDs
            key_to_record_id = self._get_existing_record_ids(list(all_keys))
            existing_count = len(key_to_record_id)
            logger.info(f"Found {existing_count} existing records in Airtable")

            # Step 4: Process all records without parent links first
            for i in range(0, len(transformed_issues), self.config.batch_size):
                batch = transformed_issues[i:i + self.config.batch_size]
                issues_in_batch = [issue for key, issue in batch]
                self._process_issue_batch(issues_in_batch, key_to_record_id)

        except Exception as e:
            logger.error(f"Error during sync: {e}", exc_info=True)
            raise

def sync_issues(config: SyncConfig) -> None:
    """
    Main function to sync issues from Jira to Airtable.

    This function creates a JiraAirtableSync instance and calls its sync_issues method.

    Args:
        config: Configuration object
    """
    sync_handler = JiraAirtableSync(config)
    sync_handler.sync_issues()

if __name__ == '__main__':
    # Set up logging based on environment variable
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    try:
        # Get configuration based on environment
        environment = os.getenv('ENVIRONMENT', 'local')
        config_loader = get_config_loader(environment)
        config = config_loader.load()
        
        # Run sync
        sync_handler = JiraAirtableSync(config)
        sync_handler.sync_issues()
    except Exception as e:
        logger.error(f"Error during sync: {e}", exc_info=True)
        raise
