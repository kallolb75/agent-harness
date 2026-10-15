# Meeting recap: Lone Star Foodservice discovery (simulated)

> Drafted by AI from the transcript, reviewed and sent by the lead architect the same
> day. Lone Star Foodservice is a fictional company.

## Situation

Lone Star Foodservice distributes food to about 4,000 restaurants, schools and
government kitchens. Order entry runs on a mainframe. A pricing change takes a
six-week release while the business wants weekly changes, and two of the three COBOL
experts retire within two years. The data center lease ends in nine months.

## What the client wants in three weeks (success criteria)

1. A recommended disposition for each of the five applications, with its reason,
   reviewed by the enterprise architect.
2. The ORDPRICE pricing rules written down, each traced to source lines, with parity
   tests whose expected results come from the legacy program.
3. Proof that CUSTMAST can move to the new schema, reconciled to the end-of-day
   control report.

A funded program goes to the board in January if these are met.

## Decisions made in the meeting

- The agent recommends; the enterprise architect decides every disposition.
- Test expected results come from the legacy program, never from the model.
- Reconciliation to the control report is the exit gate for the data mapping.
- No unmasked customer personal data goes to a model.
- The solution runs in the client's own Google Cloud project.

## Constraints

- Masked or synthetic data only in the POC.
- Every model call costed, with a budget cap per run.
- A full trail of what each agent did.

## Open questions

| # | Question | Owner |
| --- | --- | --- |
| Q1 | Is the 2003 volume discount (pricing memo PM-114) still current policy? | Dana Whitfield |
| Q2 | Which model access route does security approve for production: the model provider's API or the cloud provider's managed model service? | Angela Brooks |
| Q3 | Are there downstream consumers of CUSTMAST besides ORDER-ENTRY? | Marcus Reyes |

## Next steps

| What | Who | When |
| --- | --- | --- |
| Masked CUSTMAST extract and last night's control report | Marcus Reyes | Friday |
| ORDPRICE source and the application inventory | Angela Brooks | Friday |
| Confirm or correct the numbered requirements | Dana Whitfield | Monday |
| Architecture and POC plan | Lead architect | End of week 1 |
