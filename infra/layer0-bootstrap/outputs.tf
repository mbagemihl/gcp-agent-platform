output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "region" {
  description = "Default GCP region"
  value       = var.region
}

output "tf_state_bucket_name" {
  description = "GCS bucket name for Layer 1 Terraform remote state"
  value       = google_storage_bucket.layer1_tfstate.name
}

output "artifact_registry_repository_url" {
  description = "Docker repository URL in Artifact Registry"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}"
}

output "workload_identity_provider" {
  description = "Full resource name of the Workload Identity Pool Provider for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "github_actions_service_account_email" {
  description = "Email of the GitHub Actions deployer Service Account"
  value       = google_service_account.github_actions.email
}

output "vpc_network_name" {
  description = "VPC network name for Cloud Run Direct VPC Egress"
  value       = google_compute_network.agent_vpc.name
}

output "vpc_subnetwork_name" {
  description = "VPC subnetwork name with Private Google Access"
  value       = google_compute_subnetwork.agent_subnet.name
}
