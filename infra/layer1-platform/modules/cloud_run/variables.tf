variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "Cloud Run region"
  type        = string
}

variable "artifact_registry_base" {
  description = "Artifact Registry Docker repository base URL"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
}

variable "firestore_database_name" {
  description = "Firestore Native database name"
  type        = string
}

variable "rag_corpus_display_name" {
  description = "Vertex AI RAG Corpus display name"
  type        = string
}

variable "internal_service_ingress" {
  description = "Ingress traffic restriction for internal Cloud Run services"
  type        = string
}

variable "showcase_ui_public" {
  description = "Grant allUsers roles/run.invoker on showcase-ui"
  type        = bool
}

variable "ui_basic_auth_user" {
  description = "Optional Basic Auth username for showcase-ui"
  type        = string
}

variable "ui_basic_auth_password" {
  description = "Optional Basic Auth password for showcase-ui"
  type        = string
  sensitive   = true
}

variable "sa_agent_email" {
  description = "Service account email for agent-core"
  type        = string
}

variable "sa_mcp_email" {
  description = "Service account email for mcp-pricing-server"
  type        = string
}

variable "sa_ui_email" {
  description = "Service account email for showcase-ui"
  type        = string
}

variable "vpc_network_name" {
  description = "VPC network name for Direct VPC Egress"
  type        = string
}

variable "vpc_subnetwork_name" {
  description = "VPC subnetwork name with Private Google Access for Direct VPC Egress"
  type        = string
}
