variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for GCS bucket and Firestore Native database"
  type        = string
}

variable "firestore_database_name" {
  description = "Firestore Native database ID"
  type        = string
}

variable "policies_dir" {
  description = "Local directory containing policy source documents (.md, .pdf, .txt)"
  type        = string
}
