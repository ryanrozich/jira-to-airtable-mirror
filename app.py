import os
import logging
from dotenv import load_dotenv
import click
from sync import sync_issues, load_config

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    AWS Lambda handler function that triggers the Jira to Airtable sync.
    """
    try:
        logger.info("Starting Jira to Airtable sync")
        load_dotenv()
        config = load_config()
        sync_issues(config)
        logger.info("Sync completed successfully")
        return {
            'statusCode': 200,
            'body': 'Sync completed successfully'
        }
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}")
        raise

def main():
    load_dotenv()
    config = load_config()
    sync_issues(config)
