terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    # Configure your state backend
    # bucket = "your-terraform-state-bucket"
    # key    = "jira-mirror/terraform.tfstate"
    # region = "us-west-2"
  }
}

provider "aws" {
  region = var.aws_region
}

# ECR Repository
resource "aws_ecr_repository" "mirror" {
  name = "jira-to-airtable-mirror"
}

# Lambda Function
module "jira_mirror_lambda" {
  source = "./modules/lambda"

  app_name    = "jira-to-airtable-mirror"
  image_uri   = "${aws_ecr_repository.mirror.repository_url}:latest"
  memory_size = 512
  timeout     = 900  # 15 minutes

  environment_variables = {
    JIRA_SERVER         = var.jira_server
    JIRA_USERNAME       = var.jira_username
    JIRA_PROJECT_KEY    = var.jira_project_key
    JIRA_JQL_FILTER     = var.jira_jql_filter
    SYNC_INTERVAL_MINUTES = "5"
    AIRTABLE_BASE_ID    = var.airtable_base_id
    AIRTABLE_TABLE_NAME = var.airtable_table_name
    TZ                  = "UTC"
  }

  secrets = {
    JIRA_API_TOKEN     = var.jira_api_token_secret_arn
    AIRTABLE_API_KEY   = var.airtable_api_key_secret_arn
  }

  schedule_expression = "rate(5 minutes)"
}
