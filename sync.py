import json
import logging
import os
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Optional, Callable, Tuple, TypeVar, Union

from dotenv import load_dotenv
from jira import JIRA
from pyairtable import Api
from pyairtable.formulas import match

from config import SyncConfig, get_config_loader

# Configure logging
logger = logging.getLogger(__name__)

class JiraAirtableSync:
    """Handles synchronization between Jira and Airtable."""

    def __init__(self, config: SyncConfig) -> None:
        """Initialize the sync class with configuration."""
        self.jira = JIRA(
            server=config.jira_server,
            basic_auth=(config.jira_username, config.jira_api_token)
        )
        self.api = Api(config.airtable_api_key)
        self.table = self.api.table(config.airtable_base_id, config.airtable_table_name)
        self.project_key = config.jira_project_key
        self.batch_size = config.batch_size
        self.field_mappings = config.field_mappings
        
        # Get Jira timezone
        self.timezone = self._get_jira_timezone()
        logger.info(f"Initializing sync from Jira project {self.project_key} to Airtable table {config.airtable_table_name}")
        logger.info(f"Jira Server: {config.jira_server}")
        logger.info(f"Airtable Base: {config.airtable_base_id}")
        logger.info(f"Using batch size of {self.batch_size} for Airtable operations")
        logger.info(f"Using Jira instance timezone: {self.timezone}")
        
        # Fetch and populate Airtable field names
        self._populate_field_names()

    def _get_jira_timezone(self) -> str:
        """Get the timezone setting from Jira instance."""
        try:
            # For Jira Cloud, we can get the timezone from the current user using API v3
            myself = self.jira._session.get(f"{self.jira._options['server']}/rest/api/3/myself").json()
            user_tz = myself.get('timeZone')
            if user_tz:
                try:
                    import pytz
                    pytz.timezone(user_tz)  # Validate the timezone
                    logger.info(f"Using Jira Cloud user timezone: {user_tz}")
                    return user_tz
                except pytz.exceptions.UnknownTimeZoneError:
                    logger.warning(f"Invalid timezone {user_tz} from Jira Cloud user, falling back to UTC")
            
            logger.warning("Could not determine Jira timezone from user settings, falling back to UTC")
            return 'UTC'
        except Exception as e:
            logger.warning(f"Error getting Jira timezone, falling back to UTC: {str(e)}")
            return 'UTC'

    def _populate_field_names(self) -> None:
        """
        Fetch field names from Airtable and populate them in field_mappings.
        This ensures we have the current field names even if they change in Airtable.
        """
        try:
            logger.info("Starting to map Airtable field IDs to field names...")
            # Get table metadata which includes field information
            table_schema = self.table.schema()
            logger.debug(f"Retrieved schema for table with {len(table_schema.fields)} fields")
            
            # Create mapping of field IDs to names
            field_map = {}
            for field in table_schema.fields:
                field_map[field.id] = field.name
                logger.debug(f"Found field: {field.name} (Type: {field.type})")
            
            # Update field mappings with current field names
            field_mapping_results = []
            for jira_field, airtable_info in self.field_mappings.items():
                field_id = airtable_info.get('airtable_field_id')
                if field_id in field_map:
                    airtable_info['airtable_field_name'] = field_map[field_id]
                    field_mapping_results.append(f"'{jira_field}' -> {field_id} ({field_map[field_id]})")
                    logger.debug(f"Mapped Airtable field ID {field_id} to name: {field_map[field_id]}")
                else:
                    logger.warning(f"Could not find Airtable field name for ID: {field_id}")
                    airtable_info['airtable_field_name'] = None
            
            logger.info("Field mapping complete. Final mappings:")
            for mapping in sorted(field_mapping_results):
                logger.info(f"  {mapping}")
        except Exception as e:
            logger.error(f"Error fetching Airtable field names: {str(e)}", exc_info=True)
            raise

    def _get_airtable_field_name(self, jira_field: str) -> Optional[str]:
        """Get the Airtable field name for a given Jira field."""
        if jira_field in self.field_mappings:
            return self.field_mappings[jira_field]['airtable_field_name']
        return None

    def _get_airtable_field_id(self, jira_field: str) -> Optional[str]:
        """Get the Airtable field ID for a given Jira field."""
        if jira_field in self.field_mappings:
            return self.field_mappings[jira_field]['airtable_field_id']
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
                # Convert method args to function args if this is a method
                method_args = args[1:] if len(args) > 0 and isinstance(args[0], JiraAirtableSync) else args
                
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

    def _format_jira_timestamp(self, timestamp: str) -> str:
        """Convert ISO timestamp to Jira-compatible format in configured timezone."""
        from datetime import datetime
        import pytz
        try:
            # Parse ISO format timestamp (which is in UTC)
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            # Convert to configured timezone
            target_tz = pytz.timezone(self.timezone)
            local_dt = dt.astimezone(target_tz)
            
            # Format to Jira's supported minute precision
            formatted = local_dt.strftime('%Y-%m-%d %H:%M')
            logger.debug(f"Converting timestamp from UTC ({timestamp}) to Jira instance timezone {self.timezone} ({formatted})")
            return formatted
        except Exception as e:
            logger.error(f"Error formatting timestamp {timestamp}: {str(e)}")
            return timestamp

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
    def _get_last_sync_time(self) -> Optional[str]:
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
        last_sync = self._get_last_sync_time()
        jql_filter = os.getenv('JIRA_JQL_FILTER', '')
        
        # Build JQL query
        jql_parts = [f"project = {self.project_key}"]
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
                expand=['changelog']  # Include changelog for additional fields
            )
            batch_size = sum(len(str(issue.raw)) for issue in batch)
            total_bytes += batch_size
            logger.info(f"Retrieved {len(batch)} issues ({self._format_bytes(batch_size)})")
            
            all_issues.extend(batch)
            start_at += len(batch)  # Use actual batch size for pagination
            
        logger.info(f"Successfully retrieved {len(all_issues)} issues (Total size: {self._format_bytes(total_bytes)})")
        return all_issues

    @retry_with_backoff(retries=3, backoff_in_seconds=1)
    def _batch_create_with_progress(self, batch: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """
        Create a batch of records with progress tracking and error handling.
        
        Args:
            batch: List of records to create
            
        Returns:
            Tuple of (successful records, failed Jira keys)
        """
        try:
            # For batch_create, we just pass the fields directly
            records = self.table.batch_create(batch)
            return records, []
        except Exception as e:
            logger.error(f"Error in batch create: {str(e)}", exc_info=True)
            # Extract Jira keys from the batch for error tracking
            failed_keys = [record.get(self._get_airtable_field_id('key')) for record in batch]
            return [], [key for key in failed_keys if key]

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

    def _get_issue_field_value(self, issue: Any, field_name: str) -> Any:  # noqa: C901
        """
        Extract field value from Jira issue.

        This method handles various field types and edge cases, including:
        - Direct field access
        - Special handling for 'key', 'parent', 'latest_comment', 'comment_author', 'comment_updated', and 'status_updated' fields
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
                logger.debug(f"[{issue.key}] Processing comment field '{field_name}'")
                # Comments should be pre-fetched in the issue object
                if not hasattr(issue, 'fields') or not hasattr(issue.fields, 'comment'):
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
                    return latest_comment.author.displayName if hasattr(latest_comment.author, 'displayName') else str(latest_comment.author)
                elif field_name == 'comment_updated':
                    return latest_comment.updated

            # Special handling for status_updated field
            if field_name == 'status_updated':
                logger.debug(f"[{issue.key}] Processing status_updated field")
                # Changelog should be pre-fetched in the issue object
                if not hasattr(issue, 'changelog'):
                    logger.debug(f"[{issue.key}] No changelog found")
                    return None
                    
                status_changes = [
                    item for history in issue.changelog.histories
                    for item in history.items if item.field == 'status'
                ]
                logger.debug(f"[{issue.key}] Found {len(status_changes)} status changes")
                if status_changes:
                    latest_status = status_changes[-1]
                    logger.debug(f"[{issue.key}] Latest status change: {latest_status.to}")
                    return latest_status.to
                return None

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

            # Handle different field value types
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
            logger.warning(f"[{issue.key}] Error getting Jira field {field_name}: {str(e)}")
            return None

    def _transform_jira_issue(self, issue: Any) -> Dict[str, Any]:
        """
        Transform Jira issue to Airtable record format.

        This method iterates through the field mappings and extracts the corresponding values from the Jira issue.
        The field_mappings dictionary has Jira field names as keys and Airtable field IDs as values.

        Args:
            issue: Jira issue object

        Returns:
            Dictionary representing the Airtable record
        """
        record = {}
        issue_key = issue.key

        # Iterate through the field mappings (Jira field name -> Airtable field ID)
        for jira_field, airtable_info in self.field_mappings.items():
            logger.debug(f"[{issue_key}] Transforming Jira field '{jira_field}' to Airtable field ID '{airtable_info['airtable_field_id']}'")
            
            try:
                value = self._get_issue_field_value(issue, jira_field)
                logger.debug(f"[{issue_key}] Got value for {jira_field}: {value}")
                if value is not None:
                    record[airtable_info['airtable_field_id']] = value
            except Exception as e:
                logger.warning(f"[{issue_key}] Error transforming field {jira_field}: {str(e)}")
                continue

        return record

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
            formula_parts = [f"{key_field_id}='{key}'" for key in chunk]
            formula = f"OR({','.join(formula_parts)})"
            logger.debug(f"Querying Airtable for {len(chunk)} keys with formula: {formula}")
            
            try:
                records = self.table.all(formula=formula)
                for record in records:
                    jira_key = record['fields'].get(key_field_id)
                    if jira_key:
                        id_map[jira_key] = record['id']
            except Exception as e:
                logger.error(f"Error querying records: {str(e)}", exc_info=True)
        
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
            
        key_field = self._get_airtable_field_name('key')
        if not key_field:
            logger.error("No 'key' field mapping found in field_mappings")
            return {}
            
        logger.debug(f"Looking up existing records for {len(jira_keys)} Jira keys")
        logger.debug(f"Using Airtable field '{key_field}' for Jira key lookup")
        
        # Get records in chunks to avoid formula length limits
        chunk_size = 100  # Adjust if needed based on key lengths
        key_to_record_id = {}
        
        for i in range(0, len(jira_keys), chunk_size):
            chunk = jira_keys[i:i + chunk_size]
            # Build OR condition for each key - wrap field names with spaces in curly braces
            conditions = [f"{{{key_field}}} = '{key}'" for key in chunk]
            formula = f"OR({','.join(conditions)})"
            
            try:
                logger.debug(f"Querying Airtable with formula: {formula}")
                records = self.table.all(formula=formula)
                logger.debug(f"Found {len(records)} matching records")
                
                # Map each record's key to its ID
                for record in records:
                    jira_key = record['fields'].get(key_field)
                    if jira_key:
                        if jira_key in key_to_record_id:
                            logger.warning(f"Found duplicate record for Jira key {jira_key}. "
                                         f"Previous record ID: {key_to_record_id[jira_key]}, "
                                         f"New record ID: {record['id']}")
                        key_to_record_id[jira_key] = record['id']
                        
            except Exception as e:
                logger.error(f"Error looking up records for keys {chunk}: {str(e)}", exc_info=True)
                
        logger.info(f"Found {len(key_to_record_id)} existing records in Airtable")
        return key_to_record_id

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
                    data = self._transform_jira_issue(issue)
                    parent_key = self._get_issue_field_value(issue, 'parent')
                    
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
                logger.error(f"Failed to transform {len(transform_errors)} issues: {', '.join(transform_errors)}")
            if key_to_parent:
                logger.info(f"Found {len(key_to_parent)} issues with parent relationships")
            
            # Step 3: First pass - get existing record IDs
            key_to_record_id = self._get_existing_record_ids(list(all_keys))
            existing_count = len(key_to_record_id)
            logger.info(f"Found {existing_count} existing records in Airtable")
            
            # Step 4: Process all records without parent links first
            records_to_create = []
            records_to_update = []
            
            for jira_key, data in transformed_issues:
                # Remove parent field for now - we'll update it in the second pass
                parent_field = self._get_airtable_field_id('parent')
                if parent_field in data:
                    del data[parent_field]
                
                if jira_key in key_to_record_id:
                    records_to_update.append({
                        'id': key_to_record_id[jira_key],
                        'fields': data
                    })
                else:
                    records_to_create.append(data)
            
            # Step 5: First pass - create/update all records
            create_success = []
            create_errors = []
            update_success = 0
            update_errors = []
            
            # Process creates
            if records_to_create:
                logger.info(f"Creating {len(records_to_create)} new records")
                for i in range(0, len(records_to_create), self.batch_size):
                    batch = records_to_create[i:i + self.batch_size]
                    success, errors = self._batch_create_with_progress(batch)
                    create_success.extend(success)
                    create_errors.extend(errors)
                    logger.info(f"Created batch of {len(success)} records")
                    
                    # Map newly created records to their IDs
                    for record in success:
                        key = record['fields'].get(self._get_airtable_field_id('key'))
                        if key:
                            key_to_record_id[key] = record['id']
            
            # Process updates
            if records_to_update:
                logger.info(f"Updating {len(records_to_update)} existing records")
                for i in range(0, len(records_to_update), self.batch_size):
                    batch = records_to_update[i:i + self.batch_size]
                    success_count, errors = self._batch_update_with_progress(batch, include_keys=True)
                    update_success += success_count
                    update_errors.extend(errors)
                    logger.info(f"Updated batch of {success_count} records")
            
            # Log first pass results
            logger.info(f"First Pass Results:")
            logger.info(f"  Created: {len(create_success)} records")
            logger.info(f"  Updated: {update_success} records")
            if create_errors or update_errors:
                logger.error(f"  Errors: {len(create_errors)} creates, {len(update_errors)} updates")
            
            # Step 6: Second pass - update parent relationships
            if key_to_parent:
                logger.info("Starting second pass - updating parent relationships")
                parent_field = self._get_airtable_field_id('parent')
                
                # Do another lookup to catch any newly created records
                logger.info("Refreshing record IDs after first pass")
                key_to_record_id = self._get_existing_record_ids(list(all_keys))
                logger.info(f"Found {len(key_to_record_id)} total records after refresh")
                
                # Build parent relationship updates
                parent_updates = []
                missing_parents = []
                
                for child_key, parent_key in key_to_parent.items():
                    child_record_id = key_to_record_id.get(child_key)
                    parent_record_id = key_to_record_id.get(parent_key)
                    
                    if child_record_id and parent_record_id:
                        parent_updates.append({
                            'id': child_record_id,
                            'fields': {parent_field: [parent_record_id]}
                        })
                    else:
                        missing_parents.append((child_key, parent_key))
                        if not child_record_id:
                            logger.error(f"Missing child record ID for {child_key}")
                        if not parent_record_id:
                            logger.error(f"Missing parent record ID for {parent_key}")
                
                # Process parent updates in batches
                if parent_updates:
                    logger.info(f"Updating {len(parent_updates)} parent relationships")
                    parent_success = 0
                    parent_errors = []
                    
                    for i in range(0, len(parent_updates), self.batch_size):
                        batch = parent_updates[i:i + self.batch_size]
                        success_count, errors = self._batch_update_with_progress(batch)
                        parent_success += success_count
                        parent_errors.extend(errors)
                        logger.info(f"Updated batch of {success_count} parent relationships")
                    
                    # Log second pass results
                    logger.info(f"Second Pass Results:")
                    logger.info(f"  Updated: {parent_success} parent relationships")
                    if parent_errors:
                        logger.error(f"  Errors: {len(parent_errors)} updates")
                    if missing_parents:
                        logger.error(f"  Missing parents: {len(missing_parents)} relationships")
                        for child, parent in missing_parents:
                            logger.error(f"  Could not link {child} -> {parent}")
            
        except Exception as e:
            logger.error(f"Error during sync: {str(e)}", exc_info=True)
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
        logger.error(f"Error during sync: {str(e)}", exc_info=True)
        raise
