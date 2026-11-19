output "sa_agent_email" {
  description = "Email of sa-agent"
  value       = google_service_account.sa_agent.email
}

output "sa_mcp_email" {
  description = "Email of sa-mcp"
  value       = google_service_account.sa_mcp.email
}

output "sa_ui_email" {
  description = "Email of sa-ui"
  value       = google_service_account.sa_ui.email
}
