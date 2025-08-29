variable "project_id" {
  description = "The project ID to host the cluster in"
  type        = string
  default     = "iee-project-2025-470505"
}

variable "region" {
  description = "The region the cluster in"
  type        = string
  default     = "asia-southeast1"
}

variable "zone" {
  description = "Zone to deploy GKE nodes"
  type        = string
  default     = "asia-southeast1-a"
}

variable "bucket" {
  description = "GCS bucket name"
  type        = string
  default     = "iee-project-2025-bucket"
}
