# Troubleshooting & Maintenance Guide: km_lexicon FastAPI & Typesense Service

* **Date:** 2026-11-02
* **Domain / Category:** Python, FastAPI, Typesense, NLP Pipeline
* **Related Environment:** Local Linux Workstation / Server Infrastructure

---

## 1. Symptom & Context
* **What happened:** FastAPI asynchronous endpoints failing to connect to the local Typesense search instance, or sluggish batch curation during large Khmer text indexing runs.
* **Initial State:** Service health checks returning intermittent 503 errors or timeouts when querying orthographic variants.

## 2. Root Cause
* **Diagnosis:** Socket exhaustion or mismatched API key headers during high-concurrency requests, coupled with missing index schema definitions for custom Khmer tokenization fields.

## 3. Resolution Steps
Verify and restart services using absolute paths and systemd service checks:

```bash
# Check FastAPI service status via systemd
sudo systemctl status km_lexicon-api.service

# Verify Typesense cluster connectivity and health endpoint
curl http://localhost:8108/health

# Inspect active socket connections and port bindings
sudo ss -tulpn | grep -E '8000|8108|11435'
