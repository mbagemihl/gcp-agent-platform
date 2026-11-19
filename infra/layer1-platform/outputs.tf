output "showcase_ui_url" {
  description = "Public URL of the Showcase UI Cloud Run service"
  value       = module.cloud_run.showcase_ui_url
}

output "agent_core_url" {
  description = "Internal URL of the Agent Core Cloud Run service"
  value       = module.cloud_run.agent_core_url
}

output "mcp_pricing_server_url" {
  description = "Internal URL of the MCP Pricing Server Cloud Run service"
  value       = module.cloud_run.mcp_pricing_server_url
}

output "cloud_trace_dashboard_url" {
  description = "Direct deeplink to the GCP Cloud Trace Explorer for this project"
  value       = "https://console.cloud.google.com/traces/list?project=${var.project_id}"
}

output "rag_documents_bucket_name" {
  description = "GCS bucket storing enterprise policy source documents for Vertex AI RAG"
  value       = module.storage.rag_bucket_name
}

output "firestore_database_name" {
  description = "Firestore Native database name storing compliance reports"
  value       = module.storage.firestore_database_name
}

output "rag_corpus_display_name" {
  description = "Vertex AI RAG Corpus display name"
  value       = var.rag_corpus_display_name
}

output "service_accounts" {
  description = "Least-privilege service account emails for all three Cloud Run services"
  value = {
    agent = module.iam.sa_agent_email
    mcp   = module.iam.sa_mcp_email
    ui    = module.iam.sa_ui_email
  }
}
