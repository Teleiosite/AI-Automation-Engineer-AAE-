# AI AUTOMATION ENGINEER (AAE)

## COMMERCIAL ROLLBACK CHECKLIST
### Emergency Rollback, Incident Remediation & State Restoration

**Product:** AI Automation Engineer (AAE)  
**Release Target:** `v1.0.0-rc1`  
**Owner:** Teleiocraft Solutions  
**Repository:** `C:\Users\Owner\Desktop\AAE`  

---

## 1. Rollback Triggers & Criteria

An emergency rollback must be initiated immediately if any of the following conditions occur:
1. **Critical Pipeline Regression:** Systemic failure in workflow generation or 7-layer validation affecting $> 5\%$ of incoming requests.
2. **Database Migration Defect:** Migration failure resulting in database lockup, data corruption, or schema inconsistency.
3. **Security Invariant Breach:** Detection of unauthorized workflow deployment, plaintext secret leak, or SSRF policy failure.
4. **Target Canvas Outage:** Unrecoverable desynchronization between PostgreSQL state and live n8n workflow states.

---

## 2. Emergency Rollback Execution Steps

### Step 1: Immediate Inbound Traffic Halt
- Stop the AAE application service to prevent new state changes:
  ```bash
  systemctl stop aae-engine   # or kill uvicorn process
  ```

### Step 2: Revert Application Software
- Check out the previous known stable git release or switch container tag:
  ```bash
  git checkout tags/v0.24.0-stable
  ```
- Re-install previous dependencies if pyproject.toml changed:
  ```bash
  pip install -e .
  ```

### Step 3: Database Schema & State Restoration
- If database migration was executed:
  - Run Alembic downgrade to the previous revision:
    ```bash
    alembic downgrade -1
    ```
- If data corruption occurred:
  - Restore PostgreSQL 16 database from the pre-deployment snapshot:
    ```bash
    pg_restore -h localhost -p 5432 -U postgres -d aae_dev --clean pre_deployment_snapshot.dump
    ```

### Step 4: Live n8n Workflow State Reconciliation
- Deactivate any unstable workflows deployed during the failed release:
  - In n8n UI, navigate to `Workflows` and deactivate the affected workflow.
  - Alternatively, use n8n REST API to update active state:
    ```bash
    curl -X PATCH -H "X-N8N-API-KEY: $N8N_API_KEY" -H "Content-Type: application/json" \
         -d '{"active": false}' \
         http://localhost:5678/api/v1/workflows/<FAILED_WORKFLOW_ID>
    ```

### Step 5: Restart Application Service
- Relaunch previous stable AAE service:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
  ```

---

## 3. Post-Rollback Verification & Smoke Testing

- [ ] **Verify Service Health:**
  ```bash
  curl http://localhost:8000/healthz
  ```
- [ ] **Run Regression Test Suite:**
  ```bash
  pytest tests/
  ```
- [ ] **Confirm Database Consistency:**
  - Verify tables exist, indexes are intact, and recent valid deployments are accessible.
- [ ] **Record Rollback Event in Audit Trail:**
  - Record the incident and rollback rationale:
    ```sql
    INSERT INTO audit_events (id, event_type, status, details, created_at)
    VALUES (gen_random_uuid(), 'SYSTEM_ROLLBACK', 'COMPLETED', 'Rolled back to v0.24.0 due to incident', NOW());
    ```

---

## 4. Rollback Incident Post-Mortem Authorization

- **Incident Commander:** _____________________ Date: ______________
- **Release Engineer:** ________________________ Date: ______________
- **Post-Mortem Scheduled:** [ ] Yes  [ ] No
