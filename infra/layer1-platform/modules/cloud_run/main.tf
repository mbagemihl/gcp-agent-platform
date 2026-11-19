locals {
  basic_auth_enabled = var.ui_basic_auth_user != "" && var.ui_basic_auth_password != ""
}

# 1. MCP Pricing Server (Internal Only, Invokable ONLY by sa-agent)
resource "google_cloud_run_v2_service" "mcp_pricing_server" {
  project             = var.project_id
  name                = "mcp-pricing-server"
  location            = var.region
  ingress             = var.internal_service_ingress
  deletion_protection = false

  template {
    service_account = var.sa_mcp_email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = "${var.artifact_registry_base}/mcp-pricing-server:${var.image_tag}"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "FIRESTORE_ENABLED"
        value = "true"
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = var.firestore_database_name
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "agent_invokes_mcp" {
  project  = var.project_id
  location = google_cloud_run_v2_service.mcp_pricing_server.location
  name     = google_cloud_run_v2_service.mcp_pricing_server.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.sa_agent_email}"
}

# 2. Agent Core (Internal Only, Invokable ONLY by sa-ui)
resource "google_cloud_run_v2_service" "agent_core" {
  project             = var.project_id
  name                = "agent-core"
  location            = var.region
  ingress             = var.internal_service_ingress
  deletion_protection = false

  template {
    service_account = var.sa_agent_email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    vpc_access {
      network_interfaces {
        network    = var.vpc_network_name
        subnetwork = var.vpc_subnetwork_name
      }
      egress = "ALL_TRAFFIC"
    }

    containers {
      image = "${var.artifact_registry_base}/agent-core:${var.image_tag}"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "MCP_PRICING_SERVER_URL"
        value = google_cloud_run_v2_service.mcp_pricing_server.uri
      }
      env {
        name  = "MCP_USE_ID_TOKEN"
        value = "true"
      }
      env {
        name  = "ENABLE_CLOUD_TRACE"
        value = "true"
      }
      env {
        name  = "VERTEX_LLM_ENABLED"
        value = "true"
      }
      env {
        name  = "VERTEX_LLM_LOCATION"
        value = "global"
      }
      env {
        name  = "VERTEX_RAG_CORPUS_DISPLAY_NAME"
        value = var.rag_corpus_display_name
      }
      env {
        name  = "VERTEX_RAG_REGION"
        value = var.region
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "ui_invokes_agent" {
  project  = var.project_id
  location = google_cloud_run_v2_service.agent_core.location
  name     = google_cloud_run_v2_service.agent_core.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.sa_ui_email}"
}

# 3. Showcase UI (Public Ingress, Proxies to agent-core using sa-ui identity)
resource "google_cloud_run_v2_service" "showcase_ui" {
  project             = var.project_id
  name                = "showcase-ui"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = var.sa_ui_email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    vpc_access {
      network_interfaces {
        network    = var.vpc_network_name
        subnetwork = var.vpc_subnetwork_name
      }
      egress = "ALL_TRAFFIC"
    }

    containers {
      image = "${var.artifact_registry_base}/showcase-ui:${var.image_tag}"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "AGENT_CORE_URL"
        value = google_cloud_run_v2_service.agent_core.uri
      }

      dynamic "env" {
        for_each = local.basic_auth_enabled ? [1] : []
        content {
          name  = "UI_BASIC_AUTH_USER"
          value = var.ui_basic_auth_user
        }
      }

      dynamic "env" {
        for_each = local.basic_auth_enabled ? [1] : []
        content {
          name  = "UI_BASIC_AUTH_PASSWORD"
          value = var.ui_basic_auth_password
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "showcase_ui_public" {
  count = var.showcase_ui_public ? 1 : 0

  project  = var.project_id
  location = google_cloud_run_v2_service.showcase_ui.location
  name     = google_cloud_run_v2_service.showcase_ui.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
