# Lone Star Foodservice: POC run report (simulated client)

Generated 2026-10-16 00:32 by `simulation/run_engagement.py`, fake mode: scripted replies, costs are illustrative.

## Requirements traced to evidence

| ID | Status | Evidence |
| --- | --- | --- |
| REQ-001 | MET | 5 of 5 applications have a disposition and a reason |
| REQ-002 | MET | all 5 dispositions are reported as recommendations pending architect review; 5 of 5 match the architect's call |
| REQ-003 | MET | rule recall 1.0, citations valid 1.0 |
| REQ-004 | MET | test accuracy 1.0 against the legacy oracle |
| REQ-005 | MET | 7 of 7 fields match the data owner's mapping |
| REQ-006 | MET | reconciled True, submitted True, 1 submit attempt(s) refused before reconciliation passed |
| REQ-007 | MET | no raw name or birth date in anything the model is shown |
| REQ-008 | MET | triage $0.0337 of $0.25, intake $0.0210 of $0.5, mapping $0.0459 of $0.25 |
| REQ-009 | MET | a trace.jsonl per run: triage 23 spans, intake 16, mapping 23 |
| REQ-010 | READY, NOT APPLIED | Dockerfile and Terraform for a Cloud Run job (infra/), terraform validate passes; not applied |

## Assess: portfolio triage (recommendations, pending architect review)

| Application | Recommended | Reason |
| --- | --- | --- |
| ORDER-ENTRY | refactor | Core revenue system that must change weekly and is losing its last experts, so extract pricing and order services behind a strangler facade. |
| CLAIMS-PORTAL | replatform | Healthy, tested code whose costs are the WebLogic licence and manual deploys, so containerize it onto a managed runtime with CI/CD. |
| PRICING-ENGINE | retain | Already cloud-native and meeting its service levels, so changing it adds risk for no gain. |
| DOC-ARCHIVE | rehost | Stable and rarely changed, but the data center lease ends in nine months, so move it to cloud VMs now and revisit later. |
| HR-REPORTS | retire | Every report now lives in the HR SaaS and the server is out of support, so switch it off once no one is still using it. |

```
  ORDER-ENTRY     agent: refactor    architect: refactor    agree
  HR-REPORTS      agent: retire      architect: retire      agree
  CLAIMS-PORTAL   agent: replatform  architect: replatform  agree
  PRICING-ENGINE  agent: retain      architect: retain      agree
  DOC-ARCHIVE     agent: rehost      architect: rehost      agree
```

## Understand: ORDPRICE legacy intake

Run `20261016-003254-2-fake`. Gate: **PASS**. Verdict: OK.

| Metric | Value | Floor |
| --- | --- | --- |
| rule_recall | 1.0 | 0.875 |
| citations_valid | 1.0 | 1.0 |
| test_accuracy | 1.0 | 0.9 |
| enough_tests | 1.0 | 1.0 |

Rules found: 9. Tests written: 10. Every expected value is re-computed by the legacy oracle before it counts.

## Migrate data: CUSTMAST mapping

```
  customer_id agent: CUST_ID to_int              owner: CUST_ID to_int              agree
  first_name  agent: CUST_NM name_first          owner: CUST_NM name_first          agree
  last_name   agent: CUST_NM name_last           owner: CUST_NM name_last           agree
  birth_date  agent: BIRTH_DT date_yyyymmdd      owner: BIRTH_DT date_yyyymmdd      agree
  status      agent: STATUS_CD status_code       owner: STATUS_CD status_code       agree
  balance     agent: BAL_AMT cents_to_dollars    owner: BAL_AMT cents_to_dollars    agree
  state       agent: STATE_CD copy               owner: STATE_CD copy               agree
```

## What a person still decides

- The enterprise architect accepts or changes each disposition.
- The business owner confirms open question Q1 (pricing memo PM-114) before the volume discount rule is signed off.
- The data owner signs off the mapping after reconciliation; the agent cannot.
