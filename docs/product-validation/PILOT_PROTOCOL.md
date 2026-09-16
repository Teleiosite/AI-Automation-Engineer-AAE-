# AI Automation Engineer (AAE)
# Pilot Dry Run Protocol (Stage A)

**Document Reference:** `docs/product-validation/PILOT_PROTOCOL.md`  
**Product:** AI Automation Engineer (AAE)  
**Status:** APPROVED & ACTIVE  

---

## 1. Purpose & Objectives

Before executing the full 10-scenario baseline across the entire system, a controlled **Pilot Dry Run** must be conducted using a single representative scenario (`SCENARIO-001: Contact Enquiry`).

The objective of the Pilot Dry Run is to verify:
1. **Harness Integrity**: The automated validation runner initializes, orchestrates domain services, and executes end-to-end without runtime errors.
2. **Infrastructure Verification**: PostgreSQL 16 transactions and live local n8n API integrations operate seamlessly within the runner context.
3. **Measurement Plumbing**: The 3-level measurement model (Level 1 Transport, Level 2 Technical, Level 3 Semantic) correctly captures, evaluates, and logs telemetry.
4. **Artifact Generation**: The runner correctly outputs formatted scenario markdown reports matching the §19 schema into `docs/product-validation/RESULTS/`.

---

## 2. Pilot Target & Configuration

- **Target Scenario**: `SCENARIO-001` (Website Contact Enquiry)
- **Input Text**: *"Whenever someone sends us an enquiry through the website, save their details and make sure the team knows about it."*
- **Test Fixture**: `synthetic_data.CONTACT_ENQUIRY_PAYLOAD`
- **Expected Outcome**: `EXECUTION` (Level 1 PASS, Level 2 PASS, Level 3 PASS)
- **Expected Risk Tier**: `LOW`

---

## 3. Pre-Flight Checklist

Before launching the pilot execution:
- [ ] PostgreSQL 16 container (`aae-postgres`) is healthy and accepting connections on `localhost:5432`.
- [ ] Live n8n instance is responsive on `http://localhost:5678/healthz`.
- [ ] N8N API key is verified and accessible.
- [ ] Pure domain isolation verified (0 external framework imports).
- [ ] Output directory `docs/product-validation/RESULTS/` exists and is writable.

---

## 4. Execution Steps

1. **Step 1: Test Harness Bootstrapping**  
   Instantiate `ValidationRunner` with target `SCENARIO-001`.
2. **Step 2: Requirement Translation & Ambiguity Analysis**  
   Invoke `RequirementTranslator.translate()`. Assert Level 1 Transport Success.
3. **Step 3: Specification Formulation & Governance**  
   Formulate formal specification via `SpecificationService`. Submit and approve specification.
4. **Step 4: Directed Acyclic Graph (DAG) Planning**  
   Plan workflow topology via `WorkflowPlanner.create_plan()`. Verify node types, connection flow, and idempotency settings.
5. **Step 5: Production Node Synthesis**  
   Generate n8n workflow definition JSON via `WorkflowBuilder.build_workflow_definition()`.
6. **Step 6: 7-Layer Deep Validation**  
   Validate definition via `WorkflowValidator.validate()`. Assert 0 structural or security violations.
7. **Step 7: Semantic Simulation Engine**  
   Execute simulated dry run via `WorkflowTestEngine.run_tests()`.
8. **Step 8: Human Approval Gate & Persistence**  
   Generate `Approval` token. Execute atomic dual-deployment (PostgreSQL 16 UoW commit + n8n live API push). Token must transition to `CONSUMED`.
9. **Step 9: Cryptographic Audit & Telemetry**  
   Append immutable audit record via `AuditService`. Record execution telemetry via `WorkflowMonitor`.
10. **Step 10: Semantic Verification & Report Output**  
    Evaluate semantic fulfillment against `EXPECTED_OUTCOMES.md`. Write `docs/product-validation/RESULTS/SCENARIO-001.md`.

---

## 5. Pilot Pass / Fail Criteria

The Pilot is considered **PASSED** if:
- All 10 execution steps complete without unhandled exceptions.
- PostgreSQL 16 persists the deployment record with consumed approval token.
- n8n returns a valid workflow ID.
- `docs/product-validation/RESULTS/SCENARIO-001.md` is successfully generated with complete Level 1, 2, and 3 evaluation sections.

Once the Pilot passes, the runner is certified for full 10-scenario baseline execution.
