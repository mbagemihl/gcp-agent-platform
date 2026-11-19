variable "project_id" {
  description = "GCP Project ID for Layer 1 deployment"
  type        = string
  default     = "gcp-agent-platform-2026"
}

variable "region" {
  description = "Default GCP region for Cloud Run, GCS, Firestore, and Vertex AI"
  type        = string
  default     = "europe-west3"
}

variable "artifact_registry_repo_id" {
  description = "Docker Artifact Registry repository ID created in Layer 0"
  type        = string
  default     = "agent-platform"
}

variable "image_tag" {
  description = "Container image tag deployed to Cloud Run services"
  type        = string
  default     = "latest"
}

variable "firestore_database_name" {
  description = "Firestore Native database name"
  type        = string
  default     = "(default)"
}

variable "rag_corpus_display_name" {
  description = "Display name of the Vertex AI RAG Corpus"
  type        = string
  default     = "enterprise-agent-policies"
}

variable "rag_embedding_model" {
  description = "Vertex AI embedding model ID used for the RAG Corpus"
  type        = string
  default     = "text-embedding-005"
}

variable "internal_service_ingress" {
  description = "Ingress setting for internal Cloud Run services (agent-core and mcp-pricing-server)"
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_ONLY"
}

variable "showcase_ui_public" {
  description = "Whether showcase-ui allows unauthenticated public invocations (allUsers)"
  type        = bool
  default     = true
}

variable "ui_basic_auth_user" {
  description = "Optional Basic Auth username for showcase-ui"
  type        = string
  default     = ""
}

variable "ui_basic_auth_password" {
  description = "Optional Basic Auth password for showcase-ui"
  type        = string
  default     = ""
  sensitive   = true
}

variable "python_executable" {
  description = "Python executable used by local-exec for seeding Vertex AI RAG"
  type        = string
  default     = "python3"
}

variable "vpc_network_name" {
  description = "Permanent Layer-0 VPC network name for Cloud Run Direct VPC Egress"
  type        = string
  default     = "agent-platform-vpc"
}

variable "vpc_subnetwork_name" {
  description = "Permanent Layer-0 VPC subnetwork name with Private Google Access"
  type        = string
  default     = "agent-platform-subnet"
}
