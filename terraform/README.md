# Terraform Configurations

This directory contains Terraform configurations for deploying the Jira to Airtable Mirror to AWS Lambda.

## Prerequisites

1. Terraform CLI installed (version 1.0+)
2. AWS CLI configured with appropriate credentials
3. Docker installed and running (for building Lambda container images)
4. Required AWS permissions:
   - Lambda function creation and management
   - ECR repository access
   - CloudWatch Logs
   - EventBridge rules
   - Secrets Manager
   - IAM role and policy management

## Directory Structure

```
terraform/
├── aws/                    # AWS Lambda deployment
│   ├── main.tf            # Main configuration and resources
│   ├── variables.tf       # Variable definitions
│   ├── outputs.tf         # Output definitions
│   ├── backend.tf.example # Example backend configuration
│   └── lambda.tf          # Lambda-specific resources
```

## Configuration Steps

### 1. Set Up Remote State (Optional but Recommended)

1. Create an S3 bucket for Terraform state:
   ```bash
   aws s3 mb s3://your-terraform-state-bucket
   ```

2. Create a DynamoDB table for state locking:
   ```bash
   aws dynamodb create-table \
     --table-name terraform-state-lock \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST
   ```

3. Copy and configure the backend:
   ```bash
   cd aws
   cp backend.tf.example backend.tf
   # Edit backend.tf with your S3 bucket and DynamoDB table
   ```

### 2. Create AWS Secrets

1. Create a secret for the Jira API token:
   ```bash
   aws secretsmanager create-secret \
     --name jira-api-token \
     --description "Jira API token for sync service" \
     --secret-string "your-jira-token"
   ```

2. Create a secret for the Airtable API key:
   ```bash
   aws secretsmanager create-secret \
     --name airtable-api-key \
     --description "Airtable API key for sync service" \
     --secret-string "your-airtable-key"
   ```

### 3. Configure Terraform Variables

Create a `terraform.tfvars` file in the `aws` directory:
```hcl
# AWS Configuration
aws_region = "us-west-2"  # Your preferred AWS region

# Jira Configuration
jira_server = "https://your-domain.atlassian.net"
jira_username = "your-email@example.com"
jira_project_key = "PROJECT"
jira_jql_filter = "project = PROJECT"

# Airtable Configuration
airtable_base_id = "your_base_id"
airtable_table_name = "your_table"

# AWS Secrets Manager ARNs
jira_api_token_secret_arn = "arn:aws:secretsmanager:region:account:secret:jira-api-token-xxx"
airtable_api_key_secret_arn = "arn:aws:secretsmanager:region:account:secret:airtable-api-key-xxx"

# Sync Configuration
sync_interval_minutes = "10"  # How often to run the sync
max_results = "1000"         # Maximum number of Jira issues to fetch

# Field Mappings
jira_to_airtable_field_map = jsonencode({
  key = "fldXXX"
  summary = "fldYYY"
  description = "fldZZZ"
  # Add all your field mappings here
})
```

### 4. Deploy the Infrastructure

1. Initialize Terraform:
   ```bash
   cd aws
   terraform init
   ```

2. Create a workspace (optional):
   ```bash
   terraform workspace new staging  # For staging environment
   # or
   terraform workspace new prod    # For production environment
   ```

3. Review the changes:
   ```bash
   terraform plan
   ```

4. Apply the configuration:
   ```bash
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

# Apply with workspace-specific vars
terraform apply -var-file=staging.tfvars
```

## Important Notes

1. **Security**:
   - Always use AWS Secrets Manager for sensitive values
   - Review IAM roles and policies in `lambda.tf`
   - Consider adding additional security groups or VPC configuration

2. **Monitoring**:
   - CloudWatch Logs are automatically configured
   - Consider setting up CloudWatch Alarms for errors
   - EventBridge rules can be monitored in the AWS Console

3. **Cost Considerations**:
   - Lambda function costs based on execution time and memory
   - CloudWatch Logs costs for log storage
   - Secrets Manager costs per secret
   - Consider adjusting `sync_interval_minutes` for cost control

## Troubleshooting

1. **Terraform State Issues**:
   ```bash
   # Reinitialize backend
   terraform init -reconfigure
   
   # Force unlock state if needed
   terraform force-unlock LOCK_ID
   ```

2. **Deployment Failures**:
   - Check CloudWatch Logs for Lambda errors
   - Verify IAM roles have correct permissions
   - Ensure secrets exist and are accessible

3. **Resource Cleanup**:
   ```bash
   # Remove all resources
   terraform destroy
   
   # Remove specific resource
   terraform destroy -target=aws_lambda_function.sync_function
   ```

## Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)
