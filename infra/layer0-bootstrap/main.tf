locals {
  required_apis = toset([
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "firestore.googleapis.com",
    "cloudtrace.googleapis.com",
  ])

  github_deployer_roles = toset([
    "roles/artifactregistry.writer",
    "roles/storage.admin",
    "roles/run.admin",
    "roles/aiplatform.admin",
    "roles/datastore.owner",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/resourcemanager.projectIamAdmin",
    "roles/serviceusage.serviceUsageConsumer",
  ])

  state_bucket_name = coalesce(var.tf_state_bucket_name, "${var.project_id}-tfstate-layer1")
  github_repository = "${var.github_owner}/${var.github_repo}"
}

# 1. Required GCP APIs (persist across Layer 1 destroy)
resource "google_project_service" "apis" {
  for_each = local.required_apis

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# 2. GCS Remote State Bucket for Layer 1
resource "google_storage_bucket" "layer1_tfstate" {
  name                        = local.state_bucket_name
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = false
  }

  depends_on = [
    google_project_service.apis["cloudresourcemanager.googleapis.com"],
  ]
}

# 3. Docker Artifact Registry Repository
resource "google_artifact_registry_repository" "docker_repo" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repo_id
  format        = "DOCKER"
  description   = "Docker repository for GCP Enterprise Agent Platform images (agent-core, mcp-pricing-server, showcase-ui)"

  depends_on = [
    google_project_service.apis["artifactregistry.googleapis.com"],
  ]
}

# 4. Workload Identity Federation (WIF) & Service Account for GitHub Actions
resource "google_service_account" "github_actions" {
  project      = var.project_id
  account_id   = "github-actions-deployer"
  display_name = "GitHub Actions Deployer SA"
  description  = "Keyless CI/CD service account used by GitHub Actions via Workload Identity Federation"

  depends_on = [
    google_project_service.apis["iam.googleapis.com"],
  ]
}

resource "google_project_iam_member" "github_actions_roles" {
  for_each = local.github_deployer_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_iam_workload_identity_pool" "github_pool" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions WIF Pool"
  description               = "Workload Identity Pool for GitHub Actions OIDC authentication"

  depends_on = [
    google_project_service.apis["iam.googleapis.com"],
    google_project_service.apis["iamcredentials.googleapis.com"],
    google_project_service.apis["sts.googleapis.com"],
  ]
}

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub Actions OIDC Provider"
  description                        = "OIDC identity pool provider for GitHub Actions"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  attribute_condition = "assertion.repository == '${local.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wif_binding" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${local.github_repository}"
}
