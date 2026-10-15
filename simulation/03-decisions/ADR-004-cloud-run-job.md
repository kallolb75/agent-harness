# ADR-004: Run as a Cloud Run job, defined in Terraform

Status: accepted. Requirements: REQ-008, REQ-009, REQ-010.

## Context

Each run is a bounded batch: read inputs, call the model a few times, write evidence, stop.
Nobody calls it over HTTP.

## Decision

A Cloud Run job, one container image, defined in Terraform from day one (`infra/`).

- No retries: a failed run is evidence, and a retry would spend the budget twice.
- A versioned Cloud Storage bucket mounted at `runs/` keeps every result, token ledger
  and trace after the container exits.
- The job's service account has three grants: write the run bucket, read the key secret,
  call Vertex AI.

## Consequences

- No endpoint to secure and no idle cost.
- Scheduling, if the client wants nightly runs, is a Cloud Scheduler trigger on the job.
- Not yet applied to a project. `terraform validate` passes.
