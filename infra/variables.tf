variable "project_id" {
  description = "The client's Google Cloud project (REQ-010)."
  type        = string
}

variable "region" {
  description = "Region for the job, the image registry and the run bucket."
  type        = string
  default     = "us-central1"
}

variable "image_tag" {
  description = "Tag of the agent-harness image in Artifact Registry."
  type        = string
  default     = "latest"
}

variable "live" {
  description = "false: scripted replies, no model calls, no key needed. true: real calls, reads the API key secret."
  type        = bool
  default     = false
}
