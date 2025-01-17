import os
import logging
from sync import sync_jira_to_airtable

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    AWS Lambda handler function that triggers the Jira to Airtable sync.
    """
    try:
        logger.info("Starting Jira to Airtable sync")
        sync_jira_to_airtable()
        logger.info("Sync completed successfully")
        return {
            'statusCode': 200,
            'body': 'Sync completed successfully'
        }
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}")
        raise
