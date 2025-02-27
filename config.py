"""Configuration management for Jira to Airtable sync.

This module provides a flexible configuration system that supports multiple environments
(local, Docker, AWS Lambda) through a common interface.
"""

import abc
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class SyncConfig:
    """Data class representing the sync configuration."""
    jira_server: str
    jira_username: str
    jira_api_token: str
    jira_project_key: str
    airtable_api_key: str
    airtable_base_id: str
    airtable_table_name: str
    field_mappings: Dict[str, Any]
    batch_size: int = 50

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary format."""
        return {
            'jira_server': self.jira_server,
            'jira_username': self.jira_username,
            'jira_api_token': self.jira_api_token,
            'jira_project_key': self.jira_project_key,
            'airtable_api_key': self.airtable_api_key,
            'airtable_base_id': self.airtable_base_id,
            'airtable_table_name': self.airtable_table_name,
            'field_mappings': self.field_mappings,
            'batch_size': self.batch_size,
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'SyncConfig':
        """Create config from dictionary."""
        return cls(**config_dict)

    def validate(self) -> None:
        """Validate the configuration."""
        # Check required fields are not empty
        for field, value in self.to_dict().items():
            if field == 'batch_size':
                continue
                
            if isinstance(value, str):
                # For string fields, check they're not empty after stripping whitespace
                if not value.strip():
                    logger.error(f"Configuration validation failed: {field} is empty or whitespace")
                    raise ValueError(f"Empty value for required configuration: {field}")
                logger.debug(f"Validated {field} (length: {len(value)})")
            elif value is None:
                logger.error(f"Configuration validation failed: {field} is None")
                raise ValueError(f"Empty value for required configuration: {field}")
            elif not value and not isinstance(value, bool):  # Allow False as a valid value
                logger.error(f"Configuration validation failed: {field} is empty")
                raise ValueError(f"Empty value for required configuration: {field}")

        # Validate field mappings format
        if not isinstance(self.field_mappings, dict):
            logger.error("Configuration validation failed: field_mappings is not a dictionary")
            raise ValueError("field_mappings must be a dictionary")

        for jira_field, airtable_info in self.field_mappings.items():
            if not isinstance(airtable_info, dict):
                logger.error(f"Configuration validation failed: field mapping for {jira_field} is not a dictionary")
                raise ValueError(f"Field mapping for {jira_field} must be a dictionary with 'airtable_field_id'")
            if 'airtable_field_id' not in airtable_info:
                logger.error(f"Configuration validation failed: field mapping for {jira_field} missing airtable_field_id")
                raise ValueError(f"Field mapping for {jira_field} missing 'airtable_field_id'")
            
        logger.debug("Configuration validation successful")


class ConfigLoader(abc.ABC):
    """Abstract base class for configuration loaders."""

    @abc.abstractmethod
    def load(self) -> SyncConfig:
        """Load and return the sync configuration."""
        pass


class LocalConfigLoader(ConfigLoader):
    """Load configuration from environment variables or .env file."""

    def __init__(self, env_file: Optional[str] = None):
        """Initialize local config loader.
        
        Args:
            env_file: Optional path to .env file
        """
        self.env_file = env_file

    def load(self) -> SyncConfig:
        """Load configuration from environment."""
        if self.env_file:
            load_dotenv(self.env_file, override=True)
        else:
            load_dotenv(override=True)

        config = SyncConfig(
            jira_server=os.getenv('JIRA_SERVER', ''),
            jira_username=os.getenv('JIRA_USERNAME', ''),
            jira_api_token=os.getenv('JIRA_API_TOKEN', ''),
            jira_project_key=os.getenv('JIRA_PROJECT_KEY', ''),
            airtable_api_key=os.getenv('AIRTABLE_API_KEY', ''),
            airtable_base_id=os.getenv('AIRTABLE_BASE_ID', ''),
            airtable_table_name=os.getenv('AIRTABLE_TABLE_NAME', ''),
            field_mappings=json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}')),
            batch_size=int(os.getenv('BATCH_SIZE', '50')),
        )
        
        config.validate()
        return config


class AWSConfigLoader(ConfigLoader):
    """Load configuration from AWS environment and Secrets Manager."""

    def __init__(self, region: Optional[str] = None):
        """Initialize AWS config loader.
        
        Args:
            region: Optional AWS region. If not provided, will be extracted from secret ARNs.
        """
        self.region = region
        self._secrets_client = None

    @property
    def secrets_client(self):
        """Lazy initialization of AWS Secrets Manager client."""
        if self._secrets_client is None:
            session = boto3.session.Session()
            self._secrets_client = session.client(
                service_name='secretsmanager',
                region_name=self.region
            )
        return self._secrets_client

    def get_secret(self, secret_arn: str) -> str:
        """Get secret value from AWS Secrets Manager."""
        try:
            if not self.region:
                self.region = secret_arn.split(':')[3]  # Extract region from ARN
            
            logger.info(f"Fetching secret from ARN: {secret_arn[:8]}...{secret_arn[-8:]}")
            response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            
            if 'SecretString' in response:
                secret_value = response['SecretString']
                if not secret_value:
                    logger.error(f"Secret {secret_arn} exists but contains an empty string")
                    raise ValueError(f"Secret {secret_arn} contains an empty string")
                
                # Ensure proper string encoding and remove any whitespace
                secret_value = secret_value.encode('utf-8').decode('utf-8').strip()
                logger.info(f"Successfully retrieved secret from {secret_arn} (length: {len(secret_value)})")
                
                # Log the first few characters to help with debugging
                if len(secret_value) > 0:
                    logger.debug(f"First few characters of secret: {secret_value[:4]}...")
                
                return secret_value
            
            logger.error(f"Secret {secret_arn} does not contain a SecretString")
            raise ValueError(f"Secret {secret_arn} does not contain a string value")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS Error fetching secret {secret_arn}: {error_code} - {error_message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching secret {secret_arn}: {str(e)}")
            raise

    def load(self) -> SyncConfig:
        """Load configuration from AWS environment and Secrets Manager."""
        # Get secret ARNs
        jira_token_arn = os.getenv('JIRA_API_TOKEN_SECRET_ARN')
        airtable_key_arn = os.getenv('AIRTABLE_API_KEY_SECRET_ARN')

        if not jira_token_arn or not airtable_key_arn:
            raise ValueError("Missing required secret ARNs")

        # Fetch secrets first
        logger.info("Fetching secrets from AWS Secrets Manager...")
        try:
            jira_token = self.get_secret(jira_token_arn)
            airtable_key = self.get_secret(airtable_key_arn)
            logger.info("Successfully retrieved secrets")
        except Exception as e:
            logger.error("Failed to retrieve secrets", exc_info=True)
            raise

        # Create config object
        config = SyncConfig(
            jira_server=os.getenv('JIRA_SERVER', ''),
            jira_username=os.getenv('JIRA_USERNAME', ''),
            jira_api_token=jira_token,
            jira_project_key=os.getenv('JIRA_PROJECT_KEY', ''),
            airtable_api_key=airtable_key,
            airtable_base_id=os.getenv('AIRTABLE_BASE_ID', ''),
            airtable_table_name=os.getenv('AIRTABLE_TABLE_NAME', ''),
            field_mappings=json.loads(os.getenv('JIRA_TO_AIRTABLE_FIELD_MAP', '{}')),
            batch_size=int(os.getenv('BATCH_SIZE', '50')),
        )
        
        # Validate after all values are set
        logger.info("Validating configuration...")
        config.validate()
        logger.info("Configuration validation successful")
        
        return config


class DockerConfigLoader(LocalConfigLoader):
    """Load configuration for Docker environment.
    
    Currently identical to LocalConfigLoader, but can be extended if Docker-specific
    configuration loading is needed in the future.
    """
    pass


def get_config_loader(environment: str = 'local', **kwargs) -> ConfigLoader:
    """Factory function to get the appropriate config loader.
    
    Args:
        environment: The environment to load config for ('local', 'aws', 'docker')
        **kwargs: Additional arguments to pass to the loader
    
    Returns:
        ConfigLoader instance appropriate for the environment
    
    Raises:
        ValueError: If environment is not supported
    """
    logger.info(f"Getting config loader for environment: {environment}")
    loaders = {
        'local': LocalConfigLoader,
        'aws': AWSConfigLoader,
        'docker': DockerConfigLoader,
    }
    
    loader_class = loaders.get(environment.lower())
    if not loader_class:
        raise ValueError(f"Unsupported environment: {environment}")
    
    logger.info(f"Using config loader class: {loader_class.__name__}")
    return loader_class(**kwargs)
