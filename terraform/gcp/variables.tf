variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-west1"
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

variable "jira_api_token_secret_id" {
  description = "ID of the Secret Manager secret containing the Jira API token"
  type        = string
}

variable "airtable_api_key_secret_id" {
  description = "ID of the Secret Manager secret containing the Airtable API key"
  type        = string
}
