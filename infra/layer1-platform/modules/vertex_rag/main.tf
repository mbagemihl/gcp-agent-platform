# Provision Vertex AI RAG Engine managed database tier (Basic)
resource "google_vertex_ai_rag_engine_config" "rag_config" {
  project = var.project_id
  region  = var.region

  rag_managed_db_config {
    basic {}
  }
}

# Grant the Vertex AI RAG service agent read access to the RAG source documents bucket
resource "google_storage_bucket_iam_member" "vertex_rag_reader" {
  bucket = var.rag_bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${var.project_number}@gcp-sa-vertex-rag.iam.gserviceaccount.com"

  depends_on = [
    google_vertex_ai_rag_engine_config.rag_config,
  ]
}

# Automatically create & seed the Vertex AI RAG Corpus on apply and delete it on destroy
resource "null_resource" "seed_vertex_rag" {
  triggers = {
    project_id          = var.project_id
    region              = var.region
    corpus_display_name = var.corpus_display_name
    embedding_model     = var.embedding_model
    rag_bucket_name     = var.rag_bucket_name
    policy_files_hash   = var.policy_files_hash
    python_executable   = var.python_executable
    script_path         = var.seed_script_path
  }

  provisioner "local-exec" {
    when    = create
    command = "${self.triggers.python_executable} ${self.triggers.script_path} --action seed --project-id ${self.triggers.project_id} --region ${self.triggers.region} --corpus-display-name ${self.triggers.corpus_display_name} --embedding-model ${self.triggers.embedding_model} --gcs-bucket ${self.triggers.rag_bucket_name} --gcs-prefix policies"
  }

  provisioner "local-exec" {
    when    = destroy
    command = "${self.triggers.python_executable} ${self.triggers.script_path} --action destroy --project-id ${self.triggers.project_id} --region ${self.triggers.region} --corpus-display-name ${self.triggers.corpus_display_name}"
  }

  depends_on = [
    google_vertex_ai_rag_engine_config.rag_config,
    google_storage_bucket_iam_member.vertex_rag_reader,
  ]
}
