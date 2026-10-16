# Requirements: Lone Star Foodservice modernization POC (simulated)

Drafted by AI from the [transcript](transcript.md), confirmed by the client. Every
requirement has an ID that travels: meeting, design, decision records, code, tests,
and the run report, which comes back with a status for every ID.

| ID | Short form | Requirement in full | Source | Met by |
| --- | --- | --- | --- | --- |
| REQ-001 | A disposition for each of five apps | Recommend a disposition for each of the five applications, with a reason | 00:05:35 Angela Brooks | Portfolio triage |
| REQ-002 | The architect reviews every call | No disposition is final until the enterprise architect reviews it | 00:05:35 Angela Brooks | Portfolio triage: every decision is reported as pending review |
| REQ-003 | Each rule traced to source lines | Write down the ORDPRICE business rules, each traced to the source lines that prove it | 00:07:00 Dana Whitfield | Legacy intake |
| REQ-004 | Expected values from the legacy program | Parity tests whose expected results come from the legacy program, never from the model | 00:08:20 Angela Brooks | Legacy intake: the oracle. In this POC, `evals/oracle.py` stands in for running the COBOL |
| REQ-005 | Map CUSTMAST to the new schema | Map CUSTMAST to the new customers schema | 00:09:30 Marcus Reyes | Data mapping |
| REQ-006 | Reconcile before it can submit | The mapping reconciles to the end-of-day control report before it can be submitted | 00:10:15 Marcus Reyes | Data mapping: reconciliation gate |
| REQ-007 | No unmasked personal data to a model | No unmasked customer personal data is sent to a model | 00:11:40 Marcus Reyes | Data mapping: masked samples only |
| REQ-008 | Every call costed, a cap per run | Every model call is costed, each run has a budget cap, and the report shows cost per run | 00:13:10 Dana Whitfield | All three use cases |
| REQ-009 | A full trail of what each agent did | A full trail of what each agent did | 00:14:20 Angela Brooks | All three use cases: a `trace.jsonl` per run |
| REQ-010 | Runs in the client's own cloud | Runs in the client's own Google Cloud project | 00:15:30 Angela Brooks | `infra/`: a container and Terraform for a Cloud Run job |
