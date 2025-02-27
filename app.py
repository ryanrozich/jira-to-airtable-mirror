"""AWS Lambda handler for Jira to Airtable sync."""

import json
import logging
import os
from typing import Any, Dict

from config import get_config_loader
from sync import sync_issues

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO').upper())

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler function.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    try:
        # Load configuration using AWS config loader
        config_loader = get_config_loader('aws')
        config = config_loader.load()
        
        # Run sync
        sync_issues(config)
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Sync completed successfully'})
        }
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def main():
    # Load configuration using AWS config loader
    config_loader = get_config_loader('aws')
    config = config_loader.load()
    
    # Run sync
    sync_issues(config)
