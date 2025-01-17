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
- Runs as a containerized application (locally or in AWS Lambda)
- Uses AWS Secrets Manager for secure credential storage in Lambda
- Infrastructure managed with Terraform
- Automated deployment with Just command runner

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

The `justfile` provides several commands to streamline development and deployment:

### Local Development
- `just run` - Run the sync once locally (auto-creates venv)
- `just run-scheduled` - Run the sync on a schedule locally (auto-creates venv)
- `just validate-all` - Run all validation scripts
- `just clean` - Clean up temporary files

### Docker Commands
- `just docker-build` - Build the Docker image
- `just docker-run` - Run the container locally
- `just docker-stop` - Stop the container
- `just docker-logs` - View container logs
- `just docker-clean` - Clean up Docker resources

### AWS Lambda Commands
- `just terraform-init` - Initialize Terraform
- `just lambda-deploy` - Build and deploy the Lambda function
- `just lambda-invoke` - Manually trigger the Lambda function
- `just lambda-logs` - View Lambda logs
- `just lambda-image` - View Lambda container image details
- `just lambda-update` - Update Lambda configuration

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
