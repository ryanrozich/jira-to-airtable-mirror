resource "google_service_account" "function_account" {
  account_id   = "${var.name}-sa"
  display_name = "Service Account for ${var.name}"
}

# Grant access to secrets
resource "google_secret_manager_secret_iam_member" "secret_access" {
  for_each  = var.secrets
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.function_account.email}"
}

# Cloud Function
resource "google_cloudfunctions2_function" "function" {
  name        = var.name
  location    = var.region
  description = "Jira to Airtable sync function"

  build_config {
    runtime     = "docker"
    entry_point = "sync.py"
    source {
      storage_source {
        bucket = var.source_bucket
        object = var.source_object
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory     = "512Mi"
    timeout_seconds      = 900
    service_account_email = google_service_account.function_account.email
    
    environment_variables = var.environment_variables
    secret_environment_variables {
      for_each = var.secrets
      key      = each.key
      project_id = var.project_id
      secret    = each.value
      version   = "latest"
    }
  }
}

# Cloud Scheduler job
resource "google_cloud_scheduler_job" "job" {
  name        = "${var.name}-scheduler"
  description = "Triggers the Jira to Airtable sync function"
  schedule    = var.schedule_config.schedule
  time_zone   = var.schedule_config.timezone

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.function.url
    
    oidc_token {
      service_account_email = google_service_account.function_account.email
    }
  }
}
