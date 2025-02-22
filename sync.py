import json
import logging
import os
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from dotenv import load_dotenv
from jira import JIRA
from pyairtable import Api
from pyairtable.formulas import match

# Load environment variables from .env file
load_dotenv()

# Configure logging
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
        if not isinstance(self.tracking_fields, dict):
            logger.warning(f"Invalid tracking_fields configuration. Expected dict, got {type(self.tracking_fields)}. Using empty dict.")
            self.tracking_fields = {}
        
        # Log configuration info
        project_key = os.getenv('JIRA_PROJECT_KEY', '')
        logger.info(f"Initializing sync from Jira project {project_key} to Airtable table {self.table_id}")
        logger.info(f"Jira Server: {config['jira']['server']}")
        logger.info(f"Airtable Base: {self.base_id}")
        
        # Validate and set batch size
        self.batch_size = min(
            int(os.getenv('BATCH_SIZE', '50')), 
            50  # Maximum safe batch size for Airtable
        )
        logger.info(f"Using batch size of {self.batch_size} for Airtable operations")

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

    @retry_with_backoff(retries=3, backoff_in_seconds=1)
    def _get_last_sync_time(self) -> Optional[str]:
        """
        Get the most recent 'updated' timestamp from Airtable records.
        Returns None if no records exist.
        """
        updated_field = self.field_mappings.get('updated')
        if not updated_field:
            raise ValueError("'updated' field mapping is required")
            
        try:
            # Sort by updated field descending (using "-" prefix) and get the first record
            records = self.table.all(
                sort=[f"-{updated_field}"],  # "-" prefix means descending order
                max_records=1
            )
            if records:
                return records[0].get('fields', {}).get(updated_field)
            return None
        except Exception as e:
            logger.error(f"Error getting last sync time: {str(e)}", exc_info=True)
            raise  # Re-raise to trigger retry

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
            failed_keys = [record.get(self.field_mappings['key']) for record in batch]
            return [], [key for key in failed_keys if key]

    @retry_with_backoff(retries=3, backoff_in_seconds=1)
    def _batch_update_with_progress(self, batch: List[Dict], include_keys: bool = False) -> Tuple[int, List[str]]:
        """
        Update a batch of records with progress tracking and error handling.
        
        Args:
            batch: List of records to update
            include_keys: Whether the batch includes Jira keys for error tracking
            
        Returns:
            Tuple of (number of successful updates, list of failed Jira keys)
        """
        try:
            # For batch_update, each record needs id and fields
            formatted_batch = []
            for record in batch:
                if isinstance(record, tuple):
                    # Handle parent update format (record_id, fields, key)
                    formatted_batch.append({
                        "id": record[0],
                        "fields": record[1]
                    })
                else:
                    # Handle regular update format
                    formatted_batch.append({
                        "id": record["id"],
                        "fields": record["fields"] if "fields" in record else record
                    })
            
            self.table.batch_update(formatted_batch)
            return len(batch), []
        except Exception as e:
            logger.error(f"Error in batch update: {str(e)}", exc_info=True)
            # Extract Jira keys from the batch for error tracking
            if include_keys:
                failed_keys = [record[2] for record in batch]  # Key is third element in tuple
            else:
                failed_keys = []
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
            field_name: Name of the field to extract

        Returns:
            Field value, or None if not found
        """
        try:
            logger.debug(f"[{issue.key}] Getting field '{field_name}'")
            
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

            # Try to get the field directly from the issue
            logger.debug(f"[{issue.key}] Getting field '{field_name}' directly from issue fields")
            field = getattr(issue.fields, field_name, None)
            if field is None:
                logger.debug(f"[{issue.key}] Field '{field_name}' not found")
                return None
                
            logger.debug(f"[{issue.key}] Retrieved field value: {field}")

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
            logger.debug(f"[{issue.key}] Error getting field {field_name}: {str(e)}", exc_info=True)
            return None

    def _transform_jira_issue(self, issue: Any) -> Dict[str, Any]:
        """
        Transform Jira issue to Airtable record format.

        This method iterates through the field mappings and extracts the corresponding values from the Jira issue.

        Args:
            issue: Jira issue object

        Returns:
            Dictionary representing the Airtable record
        """
        record = {}
        issue_key = issue.key

        # Iterate through the field mappings (Jira field name -> Airtable field ID)
        for jira_field, airtable_field in self.field_mappings.items():
            logger.debug(f"[{issue_key}] Transforming Jira field '{jira_field}' to Airtable field '{airtable_field}'")
            
            if isinstance(jira_field, dict):
                if 'type' in jira_field and jira_field['type'] == 'formula':
                    logger.debug(f"[{issue_key}] Skipping formula field {airtable_field}")
                    continue
                jira_field = jira_field['field']

            try:
                value = self._get_issue_field_value(issue, jira_field)
                logger.debug(f"[{issue_key}] Got value for {jira_field}: {value}")
                if value is not None:
                    record[airtable_field] = value
            except Exception as e:
                logger.error(f"[{issue_key}] Error transforming field {jira_field} to {airtable_field}: {str(e)}", exc_info=True)
                continue

        # Handle tracking fields
        if self.tracking_fields:
            logger.debug(f"[{issue_key}] Processing tracking fields: {list(self.tracking_fields.keys())}")
            for field, config in self.tracking_fields.items():
                if isinstance(config, dict) and config.get('track_changes', False):
                    logger.debug(f"[{issue_key}] Adding history tracking for field: {field}")
                    record[f"{field}_history"] = []

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
        key_field_id = self.field_mappings['key']
        id_map = {key: None for key in keys}  # Initialize all keys to None
        
        # Process in chunks to avoid Airtable's formula length limits
        CHUNK_SIZE = 50  # Airtable has limits on formula complexity/length
        key_chunks = [list(keys)[i:i + CHUNK_SIZE] for i in range(0, len(keys), CHUNK_SIZE)]
        
        for chunk in key_chunks:
            # Build OR formula to find any records matching the keys in this chunk
            formula_parts = [f"{{{key_field_id}}}='{key}'" for key in chunk]
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
        logger.info(f"Querying Airtable table {self.table_id} to check for existing records matching {len(jira_keys)} Jira keys")
        key_field = self.field_mappings['key']
        
        # Process in chunks to avoid Airtable formula length limits
        chunk_size = 50
        key_chunks = [jira_keys[i:i + chunk_size] for i in range(0, len(jira_keys), chunk_size)]
        key_to_record_id = {}
        
        for chunk in key_chunks:
            # Build OR formula for this chunk of keys
            formula_parts = [f"{{{key_field}}}='{key}'" for key in chunk]
            formula = f"OR({','.join(formula_parts)})"
            
            try:
                records = self.table.all(formula=formula)
                for record in records:
                    jira_key = record['fields'].get(key_field)
                    if jira_key:
                        key_to_record_id[jira_key] = record['id']
            except Exception as e:
                logger.error(f"Error querying Airtable records: {str(e)}", exc_info=True)
        
        found_count = len(key_to_record_id)
        logger.info(f"Found {found_count} existing records in Airtable matching Jira keys")
        return key_to_record_id

    def _fetch_updated_jira_issues(self) -> List[Any]:
        """
        Fetch all Jira issues that have been updated since the last sync.
        Uses pagination to ensure all matching issues are retrieved.
        Orders issues by key to ensure consistent processing order.
        """
        jql = os.getenv('JIRA_JQL_FILTER', f'project = {os.getenv("JIRA_PROJECT_KEY")}')
        max_results = int(os.getenv('MAX_RESULTS', '100'))  # Default to 100 per batch
        
        # Get last sync time and add to JQL if available
        last_sync = self._get_last_sync_time()
        if last_sync:
            # Add updated > last_sync to JQL
            if ' and ' in jql.lower():
                jql += f' AND updated > "{last_sync}"'
            else:
                jql += f' AND updated > "{last_sync}"'
            logger.info(f"Fetching issues updated since {last_sync}")
        else:
            logger.info("No previous sync found - fetching all issues")
        
        # First, get total count
        try:
            total = self.jira.search_issues(jql, maxResults=0).total
            logger.info(f"Total Jira issues to fetch: {total}")
        except Exception as e:
            logger.error(f"Error getting total issue count: {str(e)}", exc_info=True)
            return []
            
        # Then fetch all issues with pagination
        all_issues = []
        start_at = 0
        
        while start_at < total:
            batch_start = start_at + 1
            batch_end = min(start_at + max_results, total)
            logger.info(f"Fetching Jira issues {batch_start} to {batch_end} of {total}")
            
            try:
                batch = self.jira.search_issues(
                    jql,
                    startAt=start_at,
                    maxResults=max_results,
                    expand=['changelog']
                )
                all_issues.extend(batch)
                start_at += len(batch)
                
                if start_at < total:  # Only log progress if not done
                    logger.info(f"Retrieved {start_at} of {total} Jira issues")
                
            except Exception as e:
                logger.error(f"Error fetching issues: {str(e)}", exc_info=True)
                return []
                
        logger.info(f"Completed fetching all {len(all_issues)} Jira issues")
        return all_issues

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
            all_keys = []  # Track all keys for existing record lookup
            transform_errors = []  # Track issues that failed to transform
            
            total_issues = len(issues)
            logger.info(f"Processing {total_issues} issues")
            
            for i, issue in enumerate(issues, 1):
                if i % 100 == 0:  # Log progress every 100 issues
                    logger.info(f"Transforming issues: {i}/{total_issues}")
                    
                try:
                    data = self._transform_jira_issue(issue)
                    parent_key = self._get_issue_field_value(issue, 'parent')
                    
                    # Remove parent field if present - we'll set it in second pass
                    parent_field = self.field_mappings.get('parent')
                    if parent_field and parent_field in data:
                        del data[parent_field]
                    
                    if parent_key:
                        key_to_parent[issue.key] = parent_key
                        
                    transformed_issues.append((issue.key, data))
                    all_keys.append(issue.key)
                except Exception as e:
                    transform_errors.append(issue.key)
                    logger.error(f"[{issue.key}] Error transforming issue: {str(e)}", exc_info=True)
            
            logger.info(f"Successfully transformed {len(transformed_issues)} issues")
            if transform_errors:
                logger.error(f"Failed to transform {len(transform_errors)} issues: {', '.join(transform_errors)}")
            if key_to_parent:
                logger.info(f"Found {len(key_to_parent)} issues with parent relationships")
            
            # Step 3: Get existing record IDs
            key_to_record_id = self._get_existing_record_ids(all_keys)
            existing_count = len(key_to_record_id)
            logger.info(f"Found {existing_count} existing records in Airtable")
            
            # Step 4: Separate records into creates and updates
            records_to_create = []
            records_to_update = {}
            
            for jira_key, data in transformed_issues:
                if jira_key in key_to_record_id:
                    records_to_update[key_to_record_id[jira_key]] = {
                        "id": key_to_record_id[jira_key],
                        "fields": data
                    }
                else:
                    records_to_create.append(data)
            
            create_count = len(records_to_create)
            update_count = len(records_to_update)
            logger.info(f"Processing {create_count} new records and {update_count} updates")
            
            # Step 5: Process creates and updates in batches
            successful_creates = 0
            successful_updates = 0
            failed_creates = []
            failed_updates = []
            
            # Create new records
            for i in range(0, len(records_to_create), self.batch_size):
                batch = records_to_create[i:i + self.batch_size]
                end_idx = min(i + self.batch_size, len(records_to_create))
                logger.info(f"Creating records {i+1} to {end_idx} of {create_count}")
                
                records, failed_keys = self._batch_create_with_progress(batch)
                successful_creates += len(records)
                failed_creates.extend(failed_keys)
                
                # Map new records to their IDs
                for record, (jira_key, _) in zip(records, transformed_issues[i:i + self.batch_size]):
                    if jira_key not in key_to_record_id:  # Only add if not already mapped
                        key_to_record_id[jira_key] = record['id']
            
            # Update existing records
            update_items = list(records_to_update.values())
            for i in range(0, len(update_items), self.batch_size):
                batch = update_items[i:i + self.batch_size]
                end_idx = min(i + self.batch_size, len(update_items))
                logger.info(f"Updating records {i+1} to {end_idx} of {update_count}")
                
                success_count, failed_keys = self._batch_update_with_progress(batch)
                successful_updates += success_count
                failed_updates.extend(failed_keys)
            
            # Step 6: Update parent links
            parent_keys = set(key_to_parent.values())
            parent_id_map = self._get_existing_record_ids(list(parent_keys))
            
            # Prepare parent updates
            parent_updates = []
            failed_parent_links = []  # Track issues where parent link failed
            
            for jira_key, parent_key in key_to_parent.items():
                record_id = key_to_record_id.get(jira_key)
                parent_record_id = parent_id_map.get(parent_key)
                
                if record_id and parent_record_id:
                    parent_updates.append((
                        record_id,
                        {self.field_mappings['parent']: [parent_record_id]},
                        jira_key  # Include Jira key for error tracking
                    ))
                else:
                    failed_parent_links.append(jira_key)
                    if not record_id:
                        logger.debug(f"[{jira_key}] Record ID not found")  # Downgrade to debug
                    if not parent_record_id:
                        logger.debug(f"[{jira_key}] Parent record ID not found for parent {parent_key}")  # Downgrade to debug
            
            # Process parent updates in batches
            successful_parent_updates = 0
            failed_parent_updates = []
            parent_update_count = len(parent_updates)
            
            if parent_update_count > 0:
                logger.info(f"Updating {parent_update_count} parent relationships")
                
                for i in range(0, len(parent_updates), self.batch_size):
                    batch = parent_updates[i:i + self.batch_size]
                    end_idx = min(i + self.batch_size, len(parent_updates))
                    logger.info(f"Updating parent links {i+1} to {end_idx} of {parent_update_count}")
                    
                    update_batch = [(rid, data) for rid, data, _ in batch]
                    success_count, failed_keys = self._batch_update_with_progress(update_batch, include_keys=True)
                    successful_parent_updates += success_count
                    failed_parent_updates.extend(failed_keys)
            
            # Output final summary with error counts
            logger.info("\nSync Summary:")
            logger.info(f"Total Jira issues found: {len(issues)}")
            logger.info(f"Issues failed to transform: {len(transform_errors)}")
            if transform_errors:
                logger.info(f"Failed issue keys: {', '.join(transform_errors)}")
                
            logger.info(f"\nAirtable Operations:")
            logger.info(f"New records created: {successful_creates}/{create_count}")
            if failed_creates:
                logger.error(f"Failed creates: {len(failed_creates)}")
                logger.error(f"Failed issue keys: {', '.join(failed_creates)}")
                
            logger.info(f"Records updated: {successful_updates}/{update_count}")
            if failed_updates:
                logger.error(f"Failed updates: {len(failed_updates)}")
                logger.error(f"Failed issue keys: {', '.join(failed_updates)}")
                
            if parent_update_count > 0:
                logger.info(f"\nParent Relationships:")
                logger.info(f"Successfully updated: {successful_parent_updates}/{parent_update_count}")
                if failed_parent_updates:
                    logger.error(f"Failed parent updates: {len(failed_parent_updates)}")
                    logger.error(f"Failed issue keys: {', '.join(failed_parent_updates)}")
                
            total_errors = (
                len(transform_errors) +
                len(failed_creates) +
                len(failed_updates) +
                len(failed_parent_updates)
            )
            if total_errors > 0:
                logger.info(f"\nTotal errors encountered: {total_errors}")
                
        except Exception as e:
            logger.error(f"Error during sync: {str(e)}", exc_info=True)
            raise

def validate_config(config: Dict[str, Any]) -> None:
    """
    Validate the configuration structure.

    This function checks for the presence of required sections and fields in the configuration.

    Args:
        config: Configuration dictionary

    Raises:
        ValueError: If the configuration is invalid
    """
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
    """
    Load configuration from environment variables.

    This function constructs the configuration dictionary from environment variables.

    Returns:
        Configuration dictionary
    """
    config = {
        'jira': {
            'server': os.getenv('JIRA_SERVER'),
            'username': os.getenv('JIRA_USERNAME'),
            'api_token': os.getenv('JIRA_API_TOKEN')
        },
        'airtable': {
            'api_key': os.getenv('AIRTABLE_API_KEY'),
            'base_id': os.getenv('AIRTABLE_BASE_ID'),
            'table_id': os.getenv('AIRTABLE_TABLE_NAME')  # Using TABLE_NAME instead of TABLE_ID
        },
        'field_mappings': {k: v for k, v in json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}')).items()},
        'tracking_fields': {
            'jira_key': 'Jira Key',
            'jira_id': 'Jira ID',
            'last_sync': 'Last Sync'
        }
    }

    try:
        validate_config(config)
        return config
    except Exception as e:
        raise ValueError(f"Error loading config: {str(e)}")


def sync_issues(config: Dict[str, Any]) -> None:
    """
    Main function to sync issues from Jira to Airtable.

    This function creates a JiraAirtableSync instance and calls its sync_issues method.

    Args:
        config: Configuration dictionary
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
        config = load_config()
        validate_config(config)
        sync_handler = JiraAirtableSync(config)
        sync_handler.sync_issues()
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}", exc_info=True)
        raise
