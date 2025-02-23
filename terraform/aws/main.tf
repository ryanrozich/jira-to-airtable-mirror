terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Import existing ECR Repository if it exists
data "aws_ecr_repository" "existing" {
  name = var.ecr_repository_name
}

# Create ECR Repository if it doesn't exist
resource "aws_ecr_repository" "mirror" {
  count = var.ecr_repository_name != data.aws_ecr_repository.existing.name ? 1 : 0
  name = var.ecr_repository_name
  force_delete = true
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = {
    Name        = var.ecr_repository_name
    Environment = terraform.workspace
    ManagedBy   = "terraform"
  }

  lifecycle {
    prevent_destroy = false
  }
}

# Use either existing or new repository
locals {
  ecr_repository_url = var.ecr_repository_name == data.aws_ecr_repository.existing.name ? data.aws_ecr_repository.existing.repository_url : aws_ecr_repository.mirror[0].repository_url
}

# ECR Lifecycle Policy
resource "aws_ecr_lifecycle_policy" "mirror" {
  repository = data.aws_ecr_repository.existing.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Lambda Function
module "jira_mirror_lambda" {
  source = "./modules/lambda"

  app_name    = "jira-to-airtable-mirror"
  image_uri   = "${local.ecr_repository_url}:latest"
  memory_size = 256
  timeout     = 900  # 15 minutes

  environment_variables = {
    JIRA_SERVER            = var.jira_server
    JIRA_USERNAME          = var.jira_username
    JIRA_PROJECT_KEY       = var.jira_project_key
    JIRA_JQL_FILTER        = var.jira_jql_filter
    SYNC_INTERVAL_MINUTES  = var.sync_interval_minutes
    AIRTABLE_BASE_ID       = var.airtable_base_id
    AIRTABLE_TABLE_NAME    = var.airtable_table_name
    JIRA_TO_AIRTABLE_FIELD_MAP = var.jira_to_airtable_field_map
    MAX_RESULTS            = var.max_results
    BATCH_SIZE             = var.batch_size
    TZ                     = "UTC"
    JIRA_API_TOKEN_SECRET_ARN     = var.jira_api_token_secret_arn
    AIRTABLE_API_KEY_SECRET_ARN   = var.airtable_api_key_secret_arn
  }

  secrets = {
    JIRA_API_TOKEN     = var.jira_api_token_secret_arn
    AIRTABLE_API_KEY   = var.airtable_api_key_secret_arn
  }

  schedule_expression = "rate(${var.sync_interval_minutes} minutes)"
  
  tags = {
    Environment = terraform.workspace
    ManagedBy   = "terraform"
    Project     = var.jira_project_key
  }
}

# Outputs
output "lambda_function_name" {
  description = "Name of the created Lambda function"
  value       = module.jira_mirror_lambda.function_name
}

output "lambda_function_arn" {
  description = "ARN of the created Lambda function"
  value       = module.jira_mirror_lambda.function_arn
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic"
  value       = module.jira_mirror_lambda.sns_topic_arn
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = local.ecr_repository_url
}

output "cloudwatch_log_group" {
  description = "Name of the CloudWatch log group"
  value       = module.jira_mirror_lambda.cloudwatch_log_group_name
}
