# infra: AgentHarness as a Cloud Run job

Meets REQ-010 of the simulated Lone Star Foodservice engagement: the harness runs in the
client's own Google Cloud project. `terraform validate` passes. Nothing here has been
applied to a real project yet.

## What it creates

| Resource | Why |
| --- | --- |
| Artifact Registry repo `agent-harness` | Holds the image built from the root `Dockerfile` |
| Service account `agent-harness-runner` | The job's own identity, with three grants only |
| Bucket `<project>-agent-harness-runs` | Mounted at `/app/runs`: every run's result, token ledger and trace (REQ-009) |
| Secret `anthropic-api-key` | The POC model route. Created empty; a person adds the value |
| `roles/aiplatform.user` on the service account | Ready for the production route, Claude on Vertex AI (ADR-002, open question Q2) |
| Cloud Run job `agent-harness` | One bounded run per execution, no retries, 15-minute timeout |

## Deploy

```bash
cd infra
terraform init
terraform apply -var project_id=YOUR_PROJECT            # fake mode: no key, no model calls

# build and push the image (from the repo root)
gcloud builds submit --tag "$(terraform -chdir=infra output -raw image)" .

gcloud run jobs execute agent-harness --region us-central1 --wait
gcloud storage ls "$(terraform -chdir=infra output -raw runs_bucket)"
```

For real model calls, add the key once and re-apply with `live=true`:

```bash
printf '%s' "$ANTHROPIC_API_KEY" | gcloud secrets versions add anthropic-api-key --data-file=-
terraform apply -var project_id=YOUR_PROJECT -var live=true
```

## Choices worth defending

- **A job, not a service.** Each run starts, writes its evidence and exits. Nothing listens on a port, so there is no endpoint to secure.
- **No retries.** A failed run is evidence. A silent retry spends the budget twice.
- **The key never enters Terraform state.** Terraform creates the secret; `gcloud` adds the value.
- **Evidence outlives the container.** The run bucket is versioned and mounted where the harness already writes.
