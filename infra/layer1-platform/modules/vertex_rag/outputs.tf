output "corpus_display_name" {
  description = "Configured Vertex AI RAG Corpus display name"
  value       = var.corpus_display_name
}

output "rag_engine_config_id" {
  description = "Vertex AI RAG Engine Config resource ID"
  value       = google_vertex_ai_rag_engine_config.rag_config.id
}
