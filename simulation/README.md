# Simulation: Lone Star Foodservice

A simulated client engagement, start to finish, built on the real use cases in this
repository. **Lone Star Foodservice is a fictional company.** The people, the meeting
and the data are invented.

The client distributes food to about 4,000 restaurants, schools and government kitchens.
Order entry runs on a mainframe, pricing changes take six weeks, two of three COBOL experts
retire within two years, and the data center lease ends in nine months. They want three
things in three weeks. Each one is a use case on one harness.

| Client asked for | Phase | Use case | Requirement IDs |
| --- | --- | --- | --- |
| A disposition for each of five applications | Assess | Portfolio triage | REQ-001, REQ-002 |
| The ORDPRICE pricing rules, written down and tested | Understand | Legacy intake | REQ-003, REQ-004 |
| Proof CUSTMAST moves without losing a cent | Migrate data | Data mapping | REQ-005, REQ-006, REQ-007 |
| Cost cap, a trail, and their own cloud | All | The harness and `infra/` | REQ-008, REQ-009, REQ-010 |

## The engagement, in the order it happened

| Step | Artifact | Made with |
| --- | --- | --- |
| 1. Discovery meeting | [01-meeting/transcript.md](01-meeting/transcript.md) | An AI note-taker (simulated export) |
| 2. Recap sent the same day | [01-meeting/recap.md](01-meeting/recap.md) | Drafted by AI from the transcript, edited by the architect |
| 3. Numbered requirements | [01-meeting/requirements.md](01-meeting/requirements.md) | Every line cites the minute it came from |
| 4. Design | [02-design/](02-design/README.md) | Mermaid in the repo, Lucidchart for the client |
| 5. Decisions | [03-decisions/](03-decisions/) | Four ADRs, each naming the requirements it serves |
| 6. Prototype | [run_engagement.py](run_engagement.py) | The three use cases, unchanged, run in one command |
| 7. Evidence | [report.md](report.md) | Generated: every requirement traced to what the run proved |
| 8. Deploy | [../infra/](../infra/README.md) | Dockerfile and Terraform for a Cloud Run job |

## Run it

```bash
uv run python -m simulation.run_engagement           # fake mode: scripted replies, no API key
uv run python -m simulation.run_engagement --live    # real model calls, needs ANTHROPIC_API_KEY
uv run pytest simulation                             # 4 tests, fake mode
```

The run prints one line per requirement and writes `report.md`. In fake mode it reports
REQ-001 to REQ-008 as MET, REQ-009 as PARTIAL (only legacy intake has a full span trace
so far) and REQ-010 as READY, NOT APPLIED. Saying what is not done is part of the report.

## What a person still decides

The agents recommend and prove. People decide: the enterprise architect owns every
disposition, the business owner confirms the 2003 volume discount (open question Q1), and
the data owner signs off the mapping after it reconciles.
