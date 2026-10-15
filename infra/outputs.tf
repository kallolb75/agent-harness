output "image" {
  description = "Push the image here before the first execution."
  value       = local.image
}

output "job" {
  value = google_cloud_run_v2_job.harness.name
}

output "runs_bucket" {
  value = google_storage_bucket.runs.url
}

output "service_account" {
  value = google_service_account.runner.email
}
