# AI AUTOMATION ENGINEER (AAE)

## COMMERCIAL DEPLOYMENT CHECKLIST
### Pre-Flight, Cutover & Post-Deployment Verification

**Product:** AI Automation Engineer (AAE)  
**Release Target:** `v1.0.0-rc1`  
**Owner:** Teleiocraft Solutions  
**Repository:** `C:\Users\Owner\Desktop\AAE`  

---

## 1. Pre-Deployment Infrastructure Verification

- [ ] **PostgreSQL 16 Database Available:**
  - Verify PostgreSQL 16 is accessible on configured host/port:
    ```bash
    pg_isready -h localhost -p 5432 -d aae_dev
    ```
- [ ] **Alembic Database Migrations Applied:**
  - Verify database schema is up to date:
    ```bash
    alembic upgrade head
    ```
- [ ] **n8n Target Instance Healthy:**
  - Verify n8n instance is running and responding:
    ```bash
    curl -f http://localhost:5678/healthz
    ```
- [ ] **n8n API Key Provisioned:**
  - Verify valid API key is generated in n8n (`Settings > n8n API`) and set in environment:
    ```bash
    export N8N_API_KEY="your-api-key"
    ```
- [ ] **Environment Configuration Loaded:**
  - `DATABASE_URL` (format: `postgresql+psycopg://user:pass@host:port/dbname`)
  - `N8N_BASE_URL` (format: `http://localhost:5678`)
  - `LOG_LEVEL` (default: `INFO`)
- [ ] **Full Test Suite Clean:**
  - Execute full regression suite to ensure zero build regressions:
    ```bash
    pytest tests/
    ```

---

## 2. Deployment Execution Steps

- [ ] **Step 1: Tag Release Version:**
  - Tag git commit with release candidate:
    ```bash
    git tag -a v1.0.0-rc1 -m "Release Candidate 1.0.0-rc1"
    ```
- [ ] **Step 2: Start AAE Service:**
  - Launch application service:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    ```
- [ ] **Step 3: Verify Health Endpoints:**
  - Confirm API service is healthy and ready to accept traffic:
    ```bash
    curl http://localhost:8000/healthz
    curl http://localhost:8000/readyz
    ```

---

## 3. Post-Deployment Verification (Smoke Tests)

- [ ] **Run Live End-to-End Reference Automation:**
  - Run the reference test script to verify full translation-to-deployment pipeline:
    ```bash
    python scripts/test_real_life.py
    ```
  - Verify workflow appears on n8n canvas (`http://localhost:5678/workflow/{id}`).
- [ ] **Verify Webhook Ingestion:**
  - Send test HTTP payload to generated webhook and verify HTTP 200 response:
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"name":"Test Lead","email":"test@example.com"}' http://localhost:5678/webhook/lead
    ```
- [ ] **Verify Database Audit Trail:**
  - Query PostgreSQL `audit_events` table to confirm deployment event was logged:
    ```sql
    SELECT id, event_type, status, created_at FROM audit_events ORDER BY created_at DESC LIMIT 5;
    ```
- [ ] **Verify Observability Logs:**
  - Confirm structured JSON log entries are being emitted without `ERROR` or `CRITICAL` entries.

---

## 4. Sign-Off & Cutover Authorization

- **Deployment Lead:** _________________________ Date: ______________
- **QA Lead:** ________________________________ Date: ______________
- **Release Sign-Off Status:** `DEPLOYMENT APPROVED`
