output "showcase_ui_url" {
  description = "URL of showcase-ui Cloud Run service"
  value       = google_cloud_run_v2_service.showcase_ui.uri
}

output "agent_core_url" {
  description = "URL of agent-core Cloud Run service"
  value       = google_cloud_run_v2_service.agent_core.uri
}

output "mcp_pricing_server_url" {
  description = "URL of mcp-pricing-server Cloud Run service"
  value       = google_cloud_run_v2_service.mcp_pricing_server.uri
}
