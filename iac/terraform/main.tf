terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "4.80.0" // Provider version
    }
  }
  required_version = ">=1.5.6" // Terraform version
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# -----------------------------------------------------------
# 1) Enable required Google APIs BEFORE creating resources
# -----------------------------------------------------------
resource "google_project_service" "required" {
  for_each = toset([
    "container.googleapis.com",       # GKE
    "compute.googleapis.com",         # VMs, networks
    "iam.googleapis.com",             # IAM
    "logging.googleapis.com",         # Cloud Logging
    "monitoring.googleapis.com",      # Cloud Monitoring
    "serviceusage.googleapis.com",    # Service Usage
    "servicemanagement.googleapis.com",
    "storage.googleapis.com"          # GCS
  ])
  project = var.project_id
  service = each.value

  # không disable API khi destroy (tránh ảnh hưởng project)
  disable_on_destroy = false
}

# -----------------------------------------------------------
# 2) GKE Standard Cluster (tạo sau khi API đã bật)
# -----------------------------------------------------------
resource "google_container_cluster" "gke_cluster" {
  name                     = "${var.project_id}-gke"
  location                 = var.region
  remove_default_node_pool = true
  initial_node_count       = 1
  node_locations           = [var.zone]

  depends_on = [google_project_service.required]
}

# -----------------------------------------------------------
# 3) Custom Node Pool
# -----------------------------------------------------------
resource "google_container_node_pool" "node_pool" {
  name       = "node-pool-gke"
  cluster    = google_container_cluster.gke_cluster.name
  location   = var.region
  node_count = 1

  node_config {
    machine_type  = "e2-standard-4"
    preemptible   = false
    disk_size_gb  = 40
    # service_account = var.node_service_account   # (tuỳ chọn)
    # oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  depends_on = [google_container_cluster.gke_cluster]
}

# -----------------------------------------------------------
# 4) GCS Bucket
# -----------------------------------------------------------
resource "google_storage_bucket" "my-bucket" {
  name                        = var.bucket
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  depends_on = [google_project_service.required]
}
