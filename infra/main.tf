# AgentHarness as a Cloud Run job in the client's own project (REQ-010).
# A job, not a service: each execution is one bounded run that starts, writes its
# evidence to the run bucket and exits. Nothing listens on a port.

locals {
  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com", # the production model route under ADR-002
    "cloudbuild.googleapis.com",
  ]
  image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.harness.repository_id}/agent-harness:${var.image_tag}"
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# Where the image lives.
resource "google_artifact_registry_repository" "harness" {
  repository_id = "agent-harness"
  location      = var.region
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# The job's own identity. It gets exactly three permissions, listed below.
resource "google_service_account" "runner" {
  account_id   = "agent-harness-runner"
  display_name = "AgentHarness Cloud Run job"
}

# REQ-009: every run's result.json, tokens.jsonl and trace.jsonl land here.
resource "google_storage_bucket" "runs" {
  name                        = "${var.project_id}-agent-harness-runs"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  versioning {
    enabled = true
  }
}

resource "google_storage_bucket_iam_member" "runner_writes_runs" {
  bucket = google_storage_bucket.runs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runner.email}"
}

# The model provider key for the POC route. Terraform creates the empty secret; a person
# adds the value with gcloud so the key never appears in Terraform state.
resource "google_secret_manager_secret" "anthropic_key" {
  secret_id = "anthropic-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "runner_reads_key" {
  secret_id = google_secret_manager_secret.anthropic_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runner.email}"
}

# Ready for the production route (Claude on Vertex AI) once security answers Q2.
resource "google_project_iam_member" "runner_calls_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runner.email}"
}

resource "google_cloud_run_v2_job" "harness" {
  name                = "agent-harness"
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account = google_service_account.runner.email
      max_retries     = 0 # a failed run is evidence; never re-spend the budget silently
      timeout         = "900s"

      containers {
        image = local.image
        args  = concat(["-m", "simulation.run_engagement"], var.live ? ["--live"] : [])

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        dynamic "env" {
          for_each = var.live ? [1] : []
          content {
            name = "ANTHROPIC_API_KEY"
            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.anthropic_key.secret_id
                version = "latest"
              }
            }
          }
        }

        volume_mounts {
          name       = "runs"
          mount_path = "/app/runs"
        }
      }

      volumes {
        name = "runs"
        gcs {
          bucket    = google_storage_bucket.runs.name
          read_only = false
        }
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_storage_bucket_iam_member.runner_writes_runs,
    google_secret_manager_secret_iam_member.runner_reads_key,
  ]
}
