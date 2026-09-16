# AI Automation Engineer (AAE) — Production Incident Response Playbook

**Product:** AI Automation Engineer (AAE)  
**Classification:** Operational Reliability & Security Playbook  
**Status:** ACTIVE  
**Last Updated:** September 16, 2026  

---

## 1. Incident Severity Classifications

| Severity | Definition | Target Response Time | Escalation Path |
| :--- | :--- | :--- | :--- |
| **P1 - Critical** | Complete service outage; inability to deploy or execute workflows; database down; security breach or unauthorized deployment. | **< 15 minutes** | Lead Production Engineer, Security Lead, Systems Architect |
| **P2 - Major** | External orchestrator (n8n) unreachable; degradation of deployment pipeline; high error rate (> 5%) on executions. | **< 30 minutes** | Reliability Engineer, Backend Lead |
| **P3 - Minor** | Rate limiting warnings; non-blocking telemetry delay; isolated workflow failure diagnosed by repair loop. | **< 2 hours** | On-call Engineer |
| **P4 - Low** | Minor cosmetic log warnings; non-urgent documentation or metrics discrepancy. | **< 1 business day** | Engineering Team Backlog |

---

## 2. Core Incident Response Workflow

```
[1. Detection] ---> [2. Triage & Severity] ---> [3. Containment (Fail-Closed)]
                                                              |
[6. Post-Mortem] <--- [5. Verification] <--- [4. Remediation / Rollback]
```

### Invariant 1: Fail-Closed Security
During any suspected compromise or state ambiguity, the system MUST fail closed:
- Block automated deployments.
- Reject unauthenticated or unapproved actions.
- Preserve immutable audit events.

---

## 3. Incident Playbooks

### Playbook 1: Database Connectivity Loss / Pool Exhaustion
**Symptoms:**
- `/ready` endpoint reports `"database": "disconnected"`.
- Application logs contain `psycopg.OperationalError` or `TimeoutError: QueuePool limit of size 20 overflow 10 reached`.

**Immediate Actions:**
1. Check PostgreSQL container health:
   ```bash
   docker ps --filter "name=aae-postgres"
   docker logs --tail 100 aae-postgres
   ```
2. Verify host connectivity:
   ```bash
   Test-NetConnection localhost -Port 5432
   ```
3. If pool is exhausted, inspect active connections:
   ```sql
   SELECT pid, usename, state, query, age(clock_timestamp(), query_start) 
   FROM pg_stat_activity 
   WHERE datname = 'aae_dev' AND state != 'idle';
   ```
4. Restart container if unresponsive:
   ```bash
   docker compose restart postgres
   ```

---

### Playbook 2: n8n Provider Disconnect or Unreachable
**Symptoms:**
- `/ready` endpoint reports `"n8n": "disconnected"`.
- Outbound requests to `http://localhost:5678` timeout or return HTTP 5xx.

**Immediate Actions:**
1. Check n8n service status:
   ```bash
   curl -i http://localhost:5678/healthz
   ```
2. Inspect n8n process / container logs for crash loops or memory exhaustion.
3. Validate API key:
   ```bash
   curl -H "X-N8N-API-KEY: <key>" http://localhost:5678/api/v1/workflows
   ```
4. While n8n is degraded, AAE deployment gates will automatically block new deployments (`DeploymentAuthorizationPolicy`), ensuring no orphaned workflows are marked deployed without provider confirmation.

---

### Playbook 3: Unauthorized Deployment or Token Replay Attempt
**Symptoms:**
- Alert in audit logs: `deployment.rejected` or `InvariantViolationError: Approval must be in ACTIVE status`.
- High frequency of rejected deployment requests from unauthorized actors.

**Immediate Actions:**
1. Audit log inspection:
   ```sql
   SELECT timestamp, event_type, actor, target_id, outcome, metadata 
   FROM audit_events 
   WHERE outcome != 'SUCCESS' 
   ORDER BY timestamp DESC LIMIT 50;
   ```
2. Single-winner approval protection: confirm database correctly blocked replay.
3. If actor credentials appear compromised, immediately revoke access tokens and rotate `AAE_SECRET_KEY`.

---

### Playbook 4: Ingress Rate Limit & DoS Detection
**Symptoms:**
- HTTP 429 Too Many Requests returned to clients.
- Rate limiting middleware alert triggered in logs.

**Immediate Actions:**
1. Identify offending client IP from reverse proxy / ingress access logs.
2. If traffic is malicious, block IP at firewall / reverse-proxy level (e.g. Nginx / Cloudflare).
3. If legitimate traffic burst, adjust `RATE_LIMIT_MAX_REQUESTS` in production environment configuration.

---

## 4. Post-Incident Review (PIR) Requirements
Within 48 hours of resolving any P1 or P2 incident:
1. Conduct root cause analysis (RCA) using the 5 Whys methodology.
2. Verify that no audit records or approval invariants were compromised.
3. Create remediation tickets for preventative automated tests or architectural hardening.
