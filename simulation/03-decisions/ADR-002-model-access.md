# ADR-002: Model access inside the client's cloud boundary

Status: accepted for the POC; production route open (Q2). Requirements: REQ-007, REQ-008, REQ-010.

## Context

The client wants everything in its own Google Cloud project and no unmasked customer data
sent to a model. Security has not yet said which route it approves for production:
the model provider's API, or Claude through Vertex AI (open question Q2, owner Angela Brooks).

## Decision

- POC: the model provider's API, with the key in Secret Manager, read only by the job's
  service account. Only masked or synthetic data in the POC.
- Production target: Claude on Vertex AI, so calls stay under the client's Google Cloud
  controls and billing. The service account already holds `roles/aiplatform.user`.
- Every model call goes through one door. The switch is a change to how the client is
  built in that one place, not a change to any agent.

## Consequences

- The POC can run before security answers Q2.
- Model IDs and prices differ by route. The price table is re-checked when the route changes.
- Masking happens at the tool boundary in the POC (the only tool that shows data rows
  masks names and birth dates). In production the masked extract is produced upstream,
  before the harness sees it.
