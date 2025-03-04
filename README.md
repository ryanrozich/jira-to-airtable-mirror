# Jira to Airtable Mirror

This service synchronizes Jira issues to an Airtable base. It can be run in multiple ways:
- As a local Docker container for development and testing
- As a scheduled AWS Lambda function for production use
- Directly on your local machine for development

The service periodically fetches issues from Jira and updates corresponding records in Airtable, maintaining a one-way sync from Jira to Airtable.

## Features

- Syncs Jira issues to Airtable on a configurable schedule
- Maps Jira fields to Airtable fields with customizable configuration
- Supports filtering Jira issues with JQL
- Syncs latest comments and tracks comment history
- Enhanced status change tracking and validation
- Runs as a containerized application (locally or in AWS Lambda)
- Uses AWS Secrets Manager for secure credential storage in Lambda
- Infrastructure managed with Terraform
- Automated deployment with Just command runner
- Comprehensive metrics monitoring and alerting
- SNS notifications for errors and sync status

## Documentation

- [AWS Lambda Deployment](./terraform/aws/README.md)
  - [Metrics Monitoring](./terraform/aws/docs/metrics.md)
  - [Notifications](./terraform/aws/docs/notifications.md)
- [Development Guide](./scripts/README.md)
- [Schema Documentation](./scripts/schema/README.md)
- [Testing Guide](./scripts/tests/README.md)
- [Utilities](./scripts/utils/README.md)
- [Validation](./scripts/validation/README.md)

## Prerequisites

### For Local Development
- Python 3.9+
- [Just](https://github.com/casey/just) command runner
- Docker (optional, for container-based development)

### For AWS Deployment
- AWS CLI configured with appropriate credentials
- Docker installed and running
- [Just](https://github.com/casey/just) command runner
- Terraform installed
- AWS account with permissions for:
  - Lambda
  - ECR
  - CloudWatch
  - EventBridge
  - Secrets Manager
  - IAM

## Initial Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd jira-to-airtable-mirror
   ```

2. Copy `.env.example` to `.env` and update with your credentials and configuration:
   ```bash
   cp .env.example .env
   ```

3. Update the following variables in `.env`:
   - `JIRA_SERVER`: Your Jira server URL (e.g., https://your-domain.atlassian.net)
   - `JIRA_USERNAME`: Your Jira email
   - `JIRA_API_TOKEN`: Your Jira API token
   - `JIRA_PROJECT_KEY`: The project key to sync (e.g., PROJ)
   - `AIRTABLE_API_KEY`: Your Airtable API key
   - `AIRTABLE_BASE_ID`: Your Airtable base ID
   - `AIRTABLE_TABLE_NAME`: Your Airtable table name
   - `JIRA_TO_AIRTABLE_FIELD_MAP`: JSON mapping of Jira fields to Airtable field IDs

   Required field mappings for Jira to Airtable synchronization:
   ```json
   {
     // Required fields
     "key": "fldXXXXXXXXXXXXXX",      // Jira issue key (e.g., PROJ-123)
     "status": "fldXXXXXXXXXXXXXX",    // Issue status
     "summary": "fldXXXXXXXXXXXXXX",   // Issue title/summary
     "description": "fldXXXXXXXXXXXXXX", // Issue description
     "created": "fldXXXXXXXXXXXXXX",    // Creation timestamp
     "updated": "fldXXXXXXXXXXXXXX",    // Last update timestamp
     
     // Optional fields
     "reporter": "fldXXXXXXXXXXXXXX",   // Issue reporter
     "assignee": "fldXXXXXXXXXXXXXX",   // Assigned user
     "issuetype": "fldXXXXXXXXXXXXXX",  // Type of issue
     "parent": "fldXXXXXXXXXXXXXX",     // Parent issue (for subtasks)
     "resolutiondate": "fldXXXXXXXXXXXXXX", // When the issue was resolved
     
     // Update tracking fields (optional)
     "status_updated": "fldXXXXXXXXXXXXXX",  // Last time status changed
     
     // Comment tracking fields (optional)
     "latest_comment": "fldXXXXXXXXXXXXXX",  // Latest comment text
     "comment_author": "fldXXXXXXXXXXXXXX",  // Latest comment author
     "comment_updated": "fldXXXXXXXXXXXXXX",  // Latest comment timestamp
     
     // Custom fields (optional)
     "customfield_10016": "fldXXXXXXXXXXXXXX"  // Example custom field
   }
   ```

   Notes: 
   - Replace `fldXXXXXXXXXXXXXX` with your actual Airtable field IDs
     - For instructions on finding field IDs, see [Airtable's documentation](https://support.airtable.com/docs/finding-airtable-ids#finding-field-ids)
   - Required fields must be mapped for the sync to work properly
   - Optional fields will be synced if mapped, but can be omitted
   - Custom fields from Jira can be mapped using their field IDs (e.g., customfield_10016)
   - The sync process will fetch issues that have any kind of update (issue fields, status, or comments)
   - The `updated` field tracks all changes to an issue, while `status_updated` and `comment_updated` track specific types of changes

4. Validate your setup by running:
   ```bash
   just validate-all
   ```
   This will:
   - Verify all required environment variables are set
   - Test connections to both Jira and Airtable
   - Validate field mappings against the Airtable schema
   - Test data transformation with sample Jira issues
   
   If successful, you should see all checks pass with ✅ marks. If any checks fail, review the error messages and update your configuration accordingly.

## Configuration System

The application uses a flexible configuration system that supports multiple deployment environments:

### Environment Types

- **Local Development**: Uses `.env` files and environment variables
- **Docker**: Similar to local development, but runs in a container
- **AWS Lambda**: Uses AWS Secrets Manager for sensitive data

### Configuration Loaders

The configuration system is based on a modular design with different loaders for each environment:

```python
# Local development
config_loader = get_config_loader('local')
config = config_loader.load()

# Docker environment
config_loader = get_config_loader('docker')
config = config_loader.load()

# AWS Lambda
config_loader = get_config_loader('aws')
config = config_loader.load()
```

The environment is controlled by the `ENVIRONMENT` environment variable, which defaults to 'local' if not set.

### Required Configuration

The following configuration values are required regardless of environment:

- `JIRA_SERVER`: Jira server URL
- `JIRA_USERNAME`: Jira username
- `JIRA_API_TOKEN`: Jira API token (or secret ARN in AWS)
- `JIRA_PROJECT_KEY`: Jira project key
- `AIRTABLE_API_KEY`: Airtable API key (or secret ARN in AWS)
- `AIRTABLE_BASE_ID`: Airtable base ID
- `AIRTABLE_TABLE_NAME`: Airtable table name
- `JIRA_TO_AIRTABLE_FIELD_MAP`: JSON mapping of Jira fields to Airtable fields

Optional configuration:
- `BATCH_SIZE`: Number of records to process in each batch (default: 50)
- `LOG_LEVEL`: Logging level (default: INFO)

### AWS Specific Configuration

When running in AWS Lambda, the following environment variables are required:

- `JIRA_API_TOKEN_SECRET_ARN`: ARN of the secret containing the Jira API token
- `AIRTABLE_API_KEY_SECRET_ARN`: ARN of the secret containing the Airtable API key

The AWS configuration loader will automatically fetch these secrets from AWS Secrets Manager.

## Sync Strategy

This tool uses an incremental sync approach with timestamp-based tracking to efficiently sync data between Jira and Airtable. Instead of performing full table scans on every sync, it:

1. Tracks the last successful sync time in Airtable
2. Uses Jira's `updated` field to query only for issues modified since the last sync
3. Automatically handles new field options by adding them to Airtable select fields when encountered

This incremental approach provides several benefits:
- Reduced API calls and rate limit usage
- Faster sync times
- Lower computational overhead
- Can be run frequently without performance impact

### How it Works

1. On each sync, the tool queries Airtable for the most recent `updated` timestamp across all records
2. It then queries Jira using JQL: `project = X AND updated > "last_sync_time"`
3. Only issues that have been modified (including field changes, status updates, and new comments) are processed
4. Each issue is upserted to Airtable, with new select field options added automatically if needed

This pattern ensures that syncs are efficient and can be run frequently to keep your Airtable data up to date.

## Just Commands

The project uses [Just](https://github.com/casey/just) as a command runner. Here are the available commands:

### Local Development
- `just install`: Install Python dependencies
- `just test`: Run the test suite
- `just lint`: Run linting checks
- `just format`: Format Python code
- `just run`: Run the sync process locally
- `just docker-build`: Build the Docker image
- `just docker-run`: Run the sync process in Docker

### AWS Lambda Commands
- `just lambda-build`: Build the Lambda container image
- `just lambda-push`: Push the container image to ECR
- `just lambda-deploy`: Deploy the Lambda function
- `just lambda-invoke`: Manually trigger the Lambda function
- `just lambda-logs`: View CloudWatch logs in real-time
- `just lambda-logs-recent [minutes]`: View recent logs
- `just lambda-logs-level [level] [minutes]`: Filter logs by level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- `just lambda-metrics [period]`: View Lambda metrics
  - `period`: `1h` (last hour), `24h` (last day), or `7d` (last week)
  - Shows invocations, errors, duration, memory, network stats
- `just lambda-update`: Update Lambda function code

### Configuration
- `just validate-env`: Validate environment variables
- `just validate-config`: Validate field mappings
- `just generate-schema`: Generate JSON schema for config

For detailed information about AWS deployment and monitoring, see:
- [AWS Lambda Deployment Guide](./terraform/aws/README.md)
- [Metrics Monitoring](./terraform/aws/docs/metrics.md)
- [Notifications](./terraform/aws/docs/notifications.md)

## Local Development

### Option 1: Direct Python Development

1. Run the sync process:
   ```bash
   just run  # Run once
   # or
   just run-scheduled  # Run continuously on a schedule
   ```

   This will automatically:
   - Create a virtual environment if it doesn't exist
   - Install dependencies in the virtual environment
   - Run the sync script

2. Validate your setup:
   ```bash
   just validate-all  # Run all validation scripts
   ```

### Option 2: Local Docker Development

1. Build and run with Docker:
   ```bash
   just docker-build  # Build the image
   just docker-run   # Run the container
   ```

2. View logs:
   ```bash
   just docker-logs  # Follow container logs
   ```

3. Stop the container:
   ```bash
   just docker-stop
   ```

## AWS Lambda Deployment

### 1. Set Up AWS Resources

1. Create AWS Secrets:
   ```bash
   # Create Jira API token secret
   aws secretsmanager create-secret \
     --name jira-api-token \
     --secret-string "your-jira-token"

   # Create Airtable API key secret
   aws secretsmanager create-secret \
     --name airtable-api-key \
     --secret-string "your-airtable-key"
   ```

2. Copy and configure Terraform backend:
   ```bash
   cd terraform/aws
   cp backend.tf.example backend.tf
   # Edit backend.tf with your S3 bucket details
   ```

3. Create `terraform.tfvars`:
   ```hcl
   aws_region = "us-west-2"
   jira_server = "https://your-org.atlassian.net"
   jira_username = "your-email@example.com"
   jira_project_key = "PROJECT"
   jira_jql_filter = "project = PROJECT"
   airtable_base_id = "your-base-id"
   airtable_table_name = "Your Table"
   sync_interval_minutes = "10"
   jira_api_token_secret_arn = "arn:aws:secretsmanager:region:account:secret:jira-api-token-xxx"
   airtable_api_key_secret_arn = "arn:aws:secretsmanager:region:account:secret:airtable-api-key-xxx"
   jira_to_airtable_field_map = jsonencode({
     key = "fldXXX"
     summary = "fldYYY"
     # ... add other field mappings
   })
   ```

### 2. Deploy to AWS

1. Initialize Terraform:
   ```bash
   just terraform-init
   ```

2. Deploy the Lambda function:
   ```bash
   just lambda-deploy
   ```

3. Test the deployment:
   ```bash
   just lambda-invoke  # Trigger the function manually
   just lambda-logs   # View the logs
   ```

## Available Just Commands

The `justfile` provides several commands to streamline development and deployment. Commands are organized by their prefix:

### Local Development (no prefix)
- `just run` - Run the sync once locally (auto-creates venv)
- `just run-scheduled` - Run the sync on a schedule locally (auto-creates venv)
- `just validate-all` - Run all validation scripts
- `just clean` - Clean up local development resources (including Docker)

### Docker Commands (docker- prefix)
- `just docker-build` - Build the Docker image
- `just docker-run` - Run the container locally
- `just docker-stop` - Stop the container
- `just docker-logs` - View container logs
- `just docker-clean` - Clean up Docker resources

### AWS Lambda Commands (lambda- prefix)
- `just lambda-deploy` - Build and deploy the Lambda function
- `just lambda-invoke` - Manually trigger the Lambda function
- `just lambda-logs` - View Lambda logs in real-time
- `just lambda-logs-recent [minutes]` - View recent Lambda logs (default: last 30 minutes)
- `just lambda-logs-level [level] [minutes]` - Filter Lambda logs by level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- `just lambda-image` - View Lambda container image details
- `just lambda-destroy` - Safely destroy all AWS infrastructure

### Master Commands
- `just destroy-all` - Clean up everything (local resources including Docker, and AWS infrastructure)

## Monitoring

### Local Monitoring
- Check logs in the `logs` directory
- View Docker container logs with `just docker-logs`
- Monitor process output in the terminal

### AWS Lambda Monitoring
- View logs in CloudWatch Logs
- Monitor Lambda metrics in CloudWatch Metrics
- Set up CloudWatch Alarms for error conditions
- Check EventBridge for scheduled trigger status

## Troubleshooting

### Common Issues

1. Authentication Errors:
   - Check Jira API token and Airtable API key
   - Verify AWS Secrets Manager values
   - Ensure Lambda has correct IAM permissions

2. Field Mapping Errors:
   - Validate Airtable field IDs with `just validate-schema`
   - Check field types are compatible
   - Ensure required fields are mapped
   - Make sure JSON field map is not wrapped in quotes in .env

3. Environment Issues:
   - Ensure .env file exists for local development
   - Check that JQL filter is properly quoted if it contains spaces
   - Verify virtual environment is working (just run will create if needed)

4. Deployment Issues:
   - Check AWS credentials and permissions
   - Verify Terraform configuration
   - Check Docker build logs

### Debug Steps

1. Run validation scripts:
   ```bash
   just validate-all
   ```

2. Check logs:
   - Local: Check `logs/sync.log`
   - Docker: `just docker-logs`
   - Lambda: `just lambda-logs`

## License

MIT License - See LICENSE file for details
