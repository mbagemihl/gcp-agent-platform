resource "google_service_account" "sa_agent" {
  project      = var.project_id
  account_id   = "sa-agent"
  display_name = "Agent Core Runtime Service Account"
  description  = "Least-privilege SA for agent-core (Vertex AI user + Cloud Trace agent)"
}

resource "google_service_account" "sa_mcp" {
  project      = var.project_id
  account_id   = "sa-mcp"
  display_name = "MCP Pricing Server Service Account"
  description  = "Least-privilege SA for mcp-pricing-server (Firestore user only)"
}

resource "google_service_account" "sa_ui" {
  project      = var.project_id
  account_id   = "sa-showcase-ui"
  display_name = "Showcase UI Service Account"
  description  = "Least-privilege SA for showcase-ui (permitted only to invoke agent-core)"
}

# Only sa-agent may call Vertex AI and emit Cloud Trace spans
resource "google_project_iam_member" "agent_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.sa_agent.email}"
}

resource "google_project_iam_member" "agent_cloudtrace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.sa_agent.email}"
}

# Only sa-mcp reads/writes Firestore compliance reports
resource "google_project_iam_member" "mcp_datastore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.sa_mcp.email}"
}
