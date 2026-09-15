# ADR 0001: Authoritative Documentation Reconciliation and Hierarchy

## Status
ACCEPTED

## Context
During the initial repository discovery of AAE Phase 0, two key documentation anomalies were observed:
1. An empty (0-byte) file existed at `docs/N8N_CAPABILITY_MAP.md`, while an extensive capability document existed at `SKILLS/N8N_CAPABILITY_MAP (1).md` (22,655 bytes).
2. The expected "Master Product Requirements Document" was not present as an individual standalone file (such as `PRD.md` or `MASTER_PRD.md`) in the repository root or docs directories.

## Decision

### 1. Capability Map Reconciliation
Before adopting `SKILLS/N8N_CAPABILITY_MAP (1).md` as authoritative, its contents were audited and cross-referenced against:
- `SKILLS/N8N_CONTROL_SURFACE.md`
- `SKILLS/AAE Architecture.md`
- `SKILLS/AAE_MASTER_CODEX_ENGINEERING_PROMPT.md`
- Actual runtime evidence gathered from the running n8n 2.38.7 instance on `http://localhost:5678`.

Findings:
- `SKILLS/N8N_CAPABILITY_MAP (1).md` perfectly aligns with the verified control surface in `N8N_CONTROL_SURFACE.md` (e.g. tracking `POST /api/v1/workflows/{workflow_id}/run` as returning 405 Method Not Allowed, documenting webhook triggering as verified, noting that GET `/openapi.json` returns editor HTML, and noting Python task runner limitations).
- The `(1)` in the filename indicates an artifact naming artifact from workspace preparation.
- The 0-byte `docs/N8N_CAPABILITY_MAP.md` is an unpopulated placeholder.

Therefore, the content of `SKILLS/N8N_CAPABILITY_MAP (1).md` is recognized as the authoritative capability baseline for n8n 2.38.7. `docs/N8N_CAPABILITY_MAP.md` is populated with this reconciled authoritative content.

### 2. Standalone Master PRD Gap
The repository lacks a standalone Master PRD. Instead, requirements are distributed across:
- `SKILLS/AAE_MASTER_CODEX_ENGINEERING_PROMPT.md`
- `SKILLS/AAE Architecture.md`
- `SKILLS/AAE Agent Specification.md`
- `SKILLS/AAE_REQUIREMENT_TRANSLATION_SPEC.md`
- `SKILLS/AAE Security Policy.md`

We classify this as:
```text
Master PRD: NOT FOUND AS A STANDALONE DOCUMENT
Distributed requirements: FOUND
Requirement sufficiency: ASSESSED (Sufficient for Phase 0 bootstrap and architectural alignment)
Risk: DOCUMENTATION GAP
```
A dedicated traceability assessment has been placed in `docs/prd/PRD_TRACEABILITY_ASSESSMENT.md`.

## Consequences
- The repository documentation structure is consistent and authoritative.
- No requirements are fabricated or assumed without evidence.
