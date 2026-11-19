terraform {
  required_version = ">= 1.5.0"

  backend "gcs" {
    bucket = "gcp-agent-platform-2026-tfstate-layer1"
    prefix = "layer1-platform"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
