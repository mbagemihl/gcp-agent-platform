locals {
  platform_apis = toset([
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "firestore.googleapis.com",
    "cloudtrace.googleapis.com",
  ])

  artifact_registry_base = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo_id}"
  policies_dir           = "${path.module}/../../seed-data/policies"
  seed_script_path       = "${path.module}/../../scripts/seed_vertex_rag.py"
}

data "google_project" "current" {
  project_id = var.project_id
}

# Safeguard platform APIs so destroying Layer 1 never disables shared project APIs
resource "google_project_service" "platform_apis" {
  for_each = local.platform_apis

  project                    = var.project_id
  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false
}

module "iam" {
  source = "./modules/iam"

  project_id = var.project_id
}

module "storage" {
  source = "./modules/storage"

  project_id              = var.project_id
  region                  = var.region
  firestore_database_name = var.firestore_database_name
  policies_dir            = local.policies_dir

  depends_on = [
    google_project_service.platform_apis["firestore.googleapis.com"],
  ]
}

module "vertex_rag" {
  source = "./modules/vertex_rag"

  project_id          = var.project_id
  project_number      = data.google_project.current.number
  region              = var.region
  corpus_display_name = var.rag_corpus_display_name
  embedding_model     = var.rag_embedding_model
  rag_bucket_name     = module.storage.rag_bucket_name
  policy_files_hash   = module.storage.policy_files_hash
  python_executable   = var.python_executable
  seed_script_path    = local.seed_script_path

  depends_on = [
    google_project_service.platform_apis["aiplatform.googleapis.com"],
    module.storage,
  ]
}

module "cloud_run" {
  source = "./modules/cloud_run"

  project_id               = var.project_id
  region                   = var.region
  artifact_registry_base   = local.artifact_registry_base
  image_tag                = var.image_tag
  firestore_database_name  = module.storage.firestore_database_name
  rag_corpus_display_name  = var.rag_corpus_display_name
  internal_service_ingress = var.internal_service_ingress
  showcase_ui_public       = var.showcase_ui_public
  ui_basic_auth_user       = var.ui_basic_auth_user
  ui_basic_auth_password   = var.ui_basic_auth_password
  sa_agent_email           = module.iam.sa_agent_email
  sa_mcp_email             = module.iam.sa_mcp_email
  sa_ui_email              = module.iam.sa_ui_email
  vpc_network_name         = var.vpc_network_name
  vpc_subnetwork_name      = var.vpc_subnetwork_name

  depends_on = [
    google_project_service.platform_apis["run.googleapis.com"],
    google_project_service.platform_apis["cloudtrace.googleapis.com"],
    module.iam,
    module.storage,
    module.vertex_rag,
  ]
}
