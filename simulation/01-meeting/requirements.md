# Requirements: Lone Star Foodservice modernization POC (simulated)

Drafted by AI from the transcript, confirmed by the client. Every requirement has an
ID that is carried into the design decisions, the code, the tests and the demo.

| ID | Requirement | Source in the transcript | Met by |
| --- | --- | --- | --- |
| REQ-001 | Recommend a disposition for each of the five applications, with a reason | 00:05:35 Angela Brooks | Portfolio triage |
| REQ-002 | No disposition is final until the enterprise architect reviews it | 00:05:35 Angela Brooks | Portfolio triage: the report lists every decision as pending review |
| REQ-003 | Write down the ORDPRICE business rules, each traced to the source lines that prove it | 00:07:00 Dana Whitfield | Legacy intake |
| REQ-004 | Parity tests whose expected results come from the legacy program, never from the model | 00:08:20 Angela Brooks | Legacy intake: the oracle |
| REQ-005 | Map CUSTMAST to the new customers schema | 00:09:30 Marcus Reyes | Data mapping |
| REQ-006 | The mapping reconciles to the end-of-day control report before it can be submitted | 00:10:15 Marcus Reyes | Data mapping: reconciliation gate |
| REQ-007 | No unmasked customer personal data is sent to a model | 00:11:40 Marcus Reyes | Data mapping: masked samples only |
| REQ-008 | Every model call is costed, each run has a budget cap, and the report shows cost per run | 00:13:10 Dana Whitfield | All three use cases |
| REQ-009 | A full trail of what each agent did | 00:14:20 Angela Brooks | Legacy intake trace; printed step logs in the others |
| REQ-010 | Runs in the client's own Google Cloud project | 00:15:30 Angela Brooks | `infra/`: a container and Terraform for a Cloud Run job |
