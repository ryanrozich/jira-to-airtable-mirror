variable "name" {
  description = "Name of the function"
  type        = string
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "image_uri" {
  description = "URI of the container image"
  type        = string
}

variable "environment_variables" {
  description = "Environment variables for the function"
  type        = map(string)
}

variable "secrets" {
  description = "Map of secret names to their IDs in Secret Manager"
  type        = map(string)
}

variable "schedule_config" {
  description = "Configuration for Cloud Scheduler"
  type = object({
    schedule = string
    timezone = string
  })
}

variable "source_bucket" {
  description = "GCS bucket containing the function source"
  type        = string
}

variable "source_object" {
  description = "Path to the function source in GCS"
  type        = string
}
