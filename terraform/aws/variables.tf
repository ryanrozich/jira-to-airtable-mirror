variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository"
  type        = string
  default     = "jira-to-airtable-mirror"
}

variable "jira_server" {
  description = "Jira server URL"
  type        = string
}

variable "jira_username" {
  description = "Jira username (email)"
  type        = string
}

variable "jira_project_key" {
  description = "Jira project key"
  type        = string
}

variable "jira_jql_filter" {
  description = "Jira JQL filter"
  type        = string
}

variable "airtable_base_id" {
  description = "Airtable base ID"
  type        = string
}

variable "airtable_table_name" {
  description = "Airtable table name"
  type        = string
}

variable "jira_api_token_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the Jira API token"
  type        = string
}

variable "airtable_api_key_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the Airtable API key"
  type        = string
}

variable "sync_interval_minutes" {
  description = "Interval in minutes between syncs"
  type        = string
  default     = "60"
}

variable "jira_to_airtable_field_map" {
  description = "JSON mapping of Jira fields to Airtable field IDs"
  type        = string
}

variable "max_results" {
  description = "Maximum number of Jira issues to sync"
  type        = string
  default     = "1000"
}

variable "batch_size" {
  description = "Number of records to process in each batch"
  type        = string
  default     = "50"
}

variable "log_level" {
  description = "Log level for the Lambda function (DEBUG, INFO, WARNING, ERROR)"
  type        = string
  default     = "INFO"
}
