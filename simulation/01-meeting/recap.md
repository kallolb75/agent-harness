# Meeting recap: Lone Star Foodservice discovery (simulated)

> Drafted by AI from the [transcript](transcript.md), edited and sent by the lead
> architect the same day. Lone Star Foodservice is a fictional company.

## The case in four lines (SBAR)

| | |
| --- | --- |
| **Situation** | Pricing changes take six weeks. The data center lease ends in nine months. |
| **Background** | The ORDPRICE rules have not been written down since 2003, and two of three COBOL experts retire within two years. About 4,000 customers order through the mainframe. |
| **Assessment** | The risk sits in knowledge that is walking out the door, and in data that has to balance to the cent. |
| **Recommendation** | A three-week POC on one agent harness, with a person or a hard check at every gate. |

## What the client wants in three weeks

| Week | Phase | Deliverable | Use case |
| --- | --- | --- | --- |
| 1 | Assess | A recommended disposition for each of the five applications, with its reason | Portfolio triage |
| 2 | Understand | The ORDPRICE rules written down, each traced to source lines, with parity tests | Legacy intake |
| 3 | Migrate data | Proof CUSTMAST moves to the new schema without losing a cent | Data mapping |
| January | Board | A funded program, if all three land | The CIO decides |

## Decisions log

| ID | Decision | Who | When |
| --- | --- | --- | --- |
| D-01 | The agent recommends; the enterprise architect decides every disposition | Angela Brooks, lead architect | 00:06:10 |
| D-02 | Rule extraction comes before any code conversion | Dana Whitfield | 00:07:00 |
| D-03 | Test expected results come from the legacy program, never from the model | Angela Brooks, lead architect | 00:08:35 |
| D-04 | Reconciliation to the end-of-day control report is the exit gate for the mapping | Marcus Reyes | 00:10:15 |
| D-05 | No unmasked customer personal data goes to a model | Marcus Reyes | 00:11:40 |
| D-06 | Every model call is priced, and each run has a budget cap | Dana Whitfield, lead architect | 00:13:30 |
| D-07 | The solution runs in the client's own Google Cloud project, on masked or synthetic data for the POC | Angela Brooks | 00:15:45 |

The numbered requirements are in [requirements.md](requirements.md).

## Open questions

| # | Question | Owner | Raised |
| --- | --- | --- | --- |
| Q1 | Is the 2003 volume discount (pricing memo PM-114) still current policy? | Dana Whitfield | 00:07:20 |
| Q2 | Which model route does security approve for production: the model provider's API, or Claude through Vertex AI? | Angela Brooks | 00:16:20 |
| Q3 | Who reads CUSTMAST besides ORDER-ENTRY? Billing does; anything else? | Marcus Reyes | 00:10:05 |

## Next steps

| What | Who | When |
| --- | --- | --- |
| Masked CUSTMAST extract and last night's control report | Marcus Reyes | Friday |
| ORDPRICE source and the application inventory | Angela Brooks | Friday |
| Confirm or correct the numbered requirements | Dana Whitfield | Monday |
| Architecture and POC plan | Lead architect | End of week 1 |
