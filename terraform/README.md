# Terraform Infrastructure

This directory contains Terraform configurations for deploying the Jira to Airtable Mirror application to various cloud providers. Currently, we support:

- [AWS Lambda Deployment](aws/README.md) - Deploy as a serverless function on AWS Lambda

## Directory Structure

```
terraform/
├── aws/                    # AWS Lambda deployment
│   ├── main.tf            # Main configuration
│   ├── variables.tf       # Variable definitions
│   ├── outputs.tf         # Output definitions
│   ├── modules/           # Reusable modules
│   │   └── lambda/        # Lambda-specific module
│   └── README.md         # AWS-specific documentation
└── README.md             # This file
```

## General Prerequisites

1. [Terraform CLI](https://www.terraform.io/downloads) (version 1.0+)
2. [Just](https://github.com/casey/just) command runner
3. [Docker](https://www.docker.com/get-started) (for building container images)

## Deployment

We use the `just` command runner for standardized deployment workflows. The main commands are:

```bash
# Deploy the Lambda function (builds and pushes Docker image, applies Terraform)
just lambda-deploy

# Destroy all resources
just lambda-destroy

# View logs
just lambda-logs

# Invoke the function manually
just lambda-invoke

# View other available commands
just --list
```

## Remote State (Optional)

If you want to use remote state storage (recommended for team environments):

1. Create an S3 bucket:
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

3. Configure the backend in your provider's directory:
```bash
cd aws
cp backend.tf.example backend.tf
# Edit backend.tf with your S3 bucket and DynamoDB table
```

## Provider-Specific Documentation

For detailed implementation instructions, refer to:
- [AWS Lambda Deployment Guide](aws/README.md)
