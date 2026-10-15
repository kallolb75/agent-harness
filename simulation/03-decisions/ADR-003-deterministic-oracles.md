# ADR-003: Deterministic oracles decide, never a model

Status: accepted. Requirements: REQ-002, REQ-004, REQ-006.

## Context

A model that writes a test can also write the wrong expected value, and a model that
grades another model shares its blind spots. The client said it directly: expected results
come from the legacy program, never from the model.

## Decision

Every pass/fail in the POC is computed by code.

- Parity tests: each expected value is re-computed by the legacy pricing logic. A test
  whose value disagrees is counted wrong, whatever the model claimed.
- Data mapping: the mapping cannot be submitted until row count, balance total, status
  counts and required fields reconcile to the legacy control report.
- Portfolio triage: agreement with the architect is measured, and the architect decides.

## Consequences

- The same output always gets the same score, so a score change means the output changed.
- Keyword matching for rule recall can miss a rephrased rule. The gate allows one miss and
  a person reads the rest.
