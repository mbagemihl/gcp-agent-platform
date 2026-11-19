variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "project_number" {
  description = "GCP Project Number (used to construct gcp-sa-vertex-rag service agent email)"
  type        = string
}

variable "region" {
  description = "Vertex AI RAG Engine region"
  type        = string
}

variable "corpus_display_name" {
  description = "Display name of the Vertex AI RAG Corpus"
  type        = string
}

variable "embedding_model" {
  description = "Vertex AI embedding model ID"
  type        = string
}

variable "rag_bucket_name" {
  description = "GCS bucket name holding uploaded policy files"
  type        = string
}

variable "policy_files_hash" {
  description = "Hash of policy files in GCS to trigger re-seeding on updates"
  type        = string
}

variable "python_executable" {
  description = "Python executable used to invoke seed_vertex_rag.py"
  type        = string
}

variable "seed_script_path" {
  description = "Path to scripts/seed_vertex_rag.py"
  type        = string
}
