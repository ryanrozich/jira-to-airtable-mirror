import logging
from dotenv import load_dotenv
from sync import sync_issues, load_config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    AWS Lambda handler function
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
