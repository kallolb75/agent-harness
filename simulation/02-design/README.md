# Design (simulated)

Two views, kept as Mermaid here so they version with the code. Lucidchart copies, with the
same content, are what the client sees.

- `context.mmd`: what runs where. Legacy sources on the left, the client's Google Cloud
  project in the middle, the architect who decides on the right.
- `roadmap.mmd`: three weeks, three phases, a human or deterministic gate at the end of each.

## System context

```mermaid
flowchart LR
  subgraph LSF["Lone Star Foodservice: today"]
    MF["Mainframe order entry<br/>COBOL: ORDPRICE, ORDER-ENTRY"]
    CM[("CUSTMAST<br/>VSAM customer master")]
    INV["Application inventory<br/>5 applications"]
    CR["End-of-day control report"]
  end

  subgraph GCP["Client Google Cloud project"]
    MASK["Masking step<br/>REQ-007"]
    JOB["Cloud Run job: AgentHarness"]
    subgraph UC["Use cases on one harness"]
      PT["Portfolio triage<br/>REQ-001, REQ-002"]
      LI["Legacy intake<br/>REQ-003, REQ-004"]
      DM["Data mapping<br/>REQ-005, REQ-006"]
    end
    DOOR["LLM.call: the one door<br/>budget cap, priced ledger<br/>REQ-008"]
    MODEL["Claude on Vertex AI"]
    BUCKET[("Run bucket<br/>result.json, tokens.jsonl, trace.jsonl<br/>REQ-009")]
  end

  ARCH(["Enterprise architect<br/>reviews and decides"])

  INV --> PT
  MF --> LI
  CM --> MASK --> DM
  CR --> DM
  JOB --> UC
  PT --> DOOR
  LI --> DOOR
  DM --> DOOR
  DOOR --> MODEL
  UC --> BUCKET
  BUCKET --> ARCH
```

## Roadmap

```mermaid
flowchart LR
  S(["Discovery meeting<br/>REQ-001 to REQ-010"]) --> A
  subgraph A["Week 1: Assess"]
    A1["Portfolio triage agent<br/>one disposition per app"] --> A2{"Architect review<br/>REQ-002"}
  end
  subgraph U["Week 2: Understand"]
    U1["Legacy intake agent<br/>ORDPRICE rules with line citations"] --> U2["Parity tests<br/>expected values from the legacy oracle"] --> U3{"Eval gate<br/>recall, citations, accuracy"}
  end
  subgraph M["Week 3: Migrate data"]
    M1["Data mapping agent<br/>masked samples, fixed transforms"] --> M2{"Reconcile to control report<br/>rows, balance, status"} --> M3["Submit mapping"]
  end
  A2 -->|approved| U1
  U3 -->|pass| M1
  M2 -->|fail: fix and retry| M1
  M3 --> D(["Client demo and<br/>January board decision"])
```

## What the design says, in one line each

- One harness, three use cases; every model call goes through one door that prices it and enforces the budget (REQ-008).
- Personal data is masked before any model sees it (REQ-007).
- Every gate is either a person (architect review) or arithmetic (oracle, reconciliation). No model grades a model.
- Evidence lands in a bucket the client owns (REQ-009, REQ-010).
