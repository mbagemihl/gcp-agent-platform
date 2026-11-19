variable "project_id" {
  description = "GCP Project ID for the Enterprise Agent Platform"
  type        = string
  default     = "gcp-agent-platform-2026"
}

variable "region" {
  description = "Default GCP region for Artifact Registry and GCS State Bucket"
  type        = string
  default     = "europe-west3"
}

variable "github_owner" {
  description = "GitHub repository owner (user or organization) allowed to authenticate via WIF"
  type        = string
  default     = "mbagemihl"
}

variable "github_repo" {
  description = "GitHub repository name allowed to authenticate via WIF"
  type        = string
  default     = "gcp-agent-platform"
}

variable "artifact_registry_repo_id" {
  description = "Repository ID for the Docker Artifact Registry"
  type        = string
  default     = "agent-platform"
}

variable "tf_state_bucket_name" {
  description = "Optional custom name for the Layer 1 Terraform remote state GCS bucket"
  type        = string
  default     = ""
}

variable "billing_account_id" {
  description = "GCP Billing Account ID for FinOps Budget Alerts"
  type        = string
  default     = "01A44C-EB29CE-4771C9"
}

variable "monthly_budget_eur" {
  description = "Monthly project budget cap in EUR (thresholds at 25%=5 EUR, 50%=10 EUR, 100%=20 EUR)"
  type        = number
  default     = 20
}
