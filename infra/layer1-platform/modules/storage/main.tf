locals {
  policy_files = setunion(
    fileset(var.policies_dir, "*.md"),
    fileset(var.policies_dir, "*.pdf"),
    fileset(var.policies_dir, "*.txt"),
  )
}

# Ephemeral GCS bucket for RAG source documents (destroyed cleanly on Layer 1 destroy)
resource "google_storage_bucket" "rag_documents" {
  name                        = "${var.project_id}-rag-documents"
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

# Auto-upload policy documents from seed-data/policies/
resource "google_storage_bucket_object" "policy_documents" {
  for_each = local.policy_files

  name   = "policies/${each.value}"
  bucket = google_storage_bucket.rag_documents.name
  source = "${var.policies_dir}/${each.value}"
}

# Ephemeral Firestore database (Native Mode) for compliance assessment reports
resource "google_firestore_database" "compliance_db" {
  project                 = var.project_id
  name                    = var.firestore_database_name
  location_id             = var.region
  type                    = "FIRESTORE_NATIVE"
  delete_protection_state = "DELETE_PROTECTION_DISABLED"
  deletion_policy         = "DELETE"
}
