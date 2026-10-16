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

## Deploy checklist

**Before you start**

- [ ] A Google Cloud project with billing on, and its ID: `export PROJECT=your-project-id`
- [ ] `gcloud` and Terraform 1.6 or later installed
- [ ] Your account can enable APIs, create service accounts, buckets, secrets, registries
      and Cloud Run jobs, and grant IAM roles (project Owner covers it)
- [ ] `gcloud auth login` and `gcloud auth application-default login` (Terraform uses the second)
- [ ] `gcloud config set project $PROJECT`

**1. Create the registry first.** The job cannot be created until its image exists.

```bash
cd infra
terraform init
terraform apply -var project_id=$PROJECT \
  -target=google_project_service.apis -target=google_artifact_registry_repository.harness
```

**2. Build and push the image** (from the repo root, with Cloud Build):

```bash
cd ..
export IMAGE=us-central1-docker.pkg.dev/$PROJECT/agent-harness/agent-harness:latest
gcloud builds submit --tag $IMAGE .
```

**3. Create everything else.**

```bash
terraform -chdir=infra apply -var project_id=$PROJECT
```

**4. Run it once, in fake mode** (no key, no model calls):

```bash
gcloud run jobs execute agent-harness --region us-central1 --wait
gcloud storage ls gs://$PROJECT-agent-harness-runs/
gcloud storage cat "gs://$PROJECT-agent-harness-runs/*-engagement-report.md"
```

- [ ] The execution succeeded
- [ ] The bucket holds one folder per use case plus an engagement report
- [ ] The report shows REQ-001 to REQ-009 MET

**5. Switch to real model calls** (after the live run checks in `simulation/README.md`):

```bash
printf '%s' "$ANTHROPIC_API_KEY" | gcloud secrets versions add anthropic-api-key --data-file=-
terraform -chdir=infra apply -var project_id=$PROJECT -var live=true
gcloud run jobs execute agent-harness --region us-central1 --wait
```

**6. Tear down** when finished. The run bucket is versioned and keeps its evidence, so
empty it first or `destroy` stops at the bucket:

```bash
gcloud storage rm -r "gs://$PROJECT-agent-harness-runs/**" --all-versions
terraform -chdir=infra destroy -var project_id=$PROJECT
```

## If something fails

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| API "has not been used in project" | API enablement still propagating | Wait a minute, apply again |
| Job create fails: image not found | Step 2 skipped or a different tag | Push the image to the exact `$IMAGE` tag |
| `Permission denied` writing under `/app/runs` | The image runs as a non-root user and the bucket mount is owned by root | Add `mount_options = ["uid=1000", "gid=1000"]` to the `gcs` volume (newer provider versions), or drop the `USER` line in the Dockerfile for the POC |
| `secret ... versions/latest not found` | `live=true` before a key version was added | Run the `gcloud secrets versions add` line first |

## Choices worth defending

- **A job, not a service.** Each run starts, writes its evidence and exits. Nothing listens on a port, so there is no endpoint to secure.
- **No retries.** A failed run is evidence. A silent retry spends the budget twice.
- **The key never enters Terraform state.** Terraform creates the secret; `gcloud` adds the value.
- **Evidence outlives the container.** The run bucket is versioned and mounted where the harness already writes.
