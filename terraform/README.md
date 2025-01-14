# Terraform Configurations

This directory contains Terraform configurations for deploying the Jira to Airtable Mirror to various cloud providers.

## Prerequisites

1. Terraform CLI installed
2. Cloud provider CLI configured:
   - AWS CLI with credentials
   - Google Cloud SDK with authenticated account

## Directory Structure

```
terraform/
├── aws/                 # AWS Lambda deployment
│   ├── main.tf         # Main configuration
│   ├── variables.tf    # Variable definitions
│   └── modules/
│       └── lambda/     # Lambda function module
├── gcp/                 # Google Cloud deployment
│   ├── main.tf         # Main configuration
│   ├── variables.tf    # Variable definitions
│   └── modules/
│       └── cloud-function/ # Cloud Function module
└── README.md
```

## AWS Lambda Deployment

1. Create a `terraform.tfvars` file:
```hcl
aws_region = "us-west-2"
jira_server = "https://your-domain.atlassian.net"
jira_username = "your-email@example.com"
jira_project_key = "PROJECT"
jira_jql_filter = "project = PROJECT"
airtable_base_id = "your_base_id"
airtable_table_name = "your_table"
jira_api_token_secret_arn = "arn:aws:secretsmanager:region:account:secret:jira-token"
airtable_api_key_secret_arn = "arn:aws:secretsmanager:region:account:secret:airtable-key"
```

2. Initialize and apply:
```bash
cd aws
terraform init
terraform workspace new staging  # Optional
terraform apply
```

## Google Cloud Deployment

1. Create a `terraform.tfvars` file:
```hcl
project_id = "your-project-id"
region = "us-west1"
jira_server = "https://your-domain.atlassian.net"
jira_username = "your-email@example.com"
jira_project_key = "PROJECT"
jira_jql_filter = "project = PROJECT"
airtable_base_id = "your_base_id"
airtable_table_name = "your_table"
jira_api_token_secret_id = "projects/123/secrets/jira-token"
airtable_api_key_secret_id = "projects/123/secrets/airtable-key"
```

2. Initialize and apply:
```bash
cd gcp
terraform init
terraform workspace new staging  # Optional
terraform apply
```

## Managing Multiple Environments

Use Terraform workspaces to manage different environments:

```bash
# List workspaces
terraform workspace list

# Create new workspace
terraform workspace new production

# Switch workspace
terraform workspace select staging

# Apply with environment-specific vars
terraform apply -var-file=staging.tfvars
```

## State Management

Both configurations support remote state storage:

- AWS: Using S3 bucket with DynamoDB locking
- GCP: Using Google Cloud Storage bucket

Configure the backend in `main.tf` for each provider.

## Security Notes

1. Never commit `terraform.tfvars` or any files containing sensitive values
2. Use cloud provider secret management services
3. Follow least privilege principle for IAM roles
4. Enable audit logging for all resources
