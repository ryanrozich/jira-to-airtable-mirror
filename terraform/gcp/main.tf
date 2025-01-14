terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    # Configure your state backend
    # bucket = "your-terraform-state-bucket"
    # prefix = "jira-mirror"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Artifact Registry Repository
resource "google_artifact_registry_repository" "mirror" {
  location      = var.region
  repository_id = "jira-mirror"
  description   = "Docker repository for Jira to Airtable mirror"
  format        = "DOCKER"
}

# Cloud Function
module "jira_mirror_function" {
  source = "./modules/cloud-function"

  name          = "jira-to-airtable-mirror"
  project_id    = var.project_id
  region        = var.region
  image_uri     = "${var.region}-docker.pkg.dev/${var.project_id}/jira-mirror/jira-to-airtable-mirror"

  environment_variables = {
    JIRA_SERVER           = var.jira_server
    JIRA_USERNAME         = var.jira_username
    JIRA_PROJECT_KEY      = var.jira_project_key
    JIRA_JQL_FILTER       = var.jira_jql_filter
    SYNC_INTERVAL_MINUTES = "5"
    AIRTABLE_BASE_ID      = var.airtable_base_id
    AIRTABLE_TABLE_NAME   = var.airtable_table_name
    TZ                    = "UTC"
  }

  secrets = {
    JIRA_API_TOKEN     = var.jira_api_token_secret_id
    AIRTABLE_API_KEY   = var.airtable_api_key_secret_id
  }

  schedule_config = {
    schedule = "*/5 * * * *"
    timezone = "UTC"
  }
}
