# TransMax Program Backlog

**Protocol**:
1.  **Work**: Pick `[READY]` tickets.
2.  **Questions**: Write in `.context/questions_to_lead.md`.
3.  **Decisions**: Read `.context/lead_decisions.md`.

## 👑 Program Lead (Antigravity) Priority
- [ ] **[READY]** Ticket-10: Error Taxonomy & Golden Set Definition (QA/Validation).
    - *Goal*: Define Critical/Major/Minor errors and create golden set schema.
- [x] **[Done]** Ticket-11: Authentication & Tenancy Design.
    - *Outcome*: Selected OAuth2 + Postgres RLS. See `auth_design.md`.
- [x] **[Done]** Ticket-12: Composite Scoring Logic.
    - *Outcome*: Implemented deterministic scoring in `quality_gate.py` with unit tests.

## 👷 Worker Agent Queue (Open Tickets)
- [x] **[Done]** Ticket-13: Production Dockerfile (Multi-stage, Optimized).
    - *Resolution*: Fixed in Ticket-04 (Supabase/Pydantic pinning, Build deps added).
- [x] **[Done]** Ticket-14: CI/CD Pipeline Setup (GitHub Actions).
    - *Lane C (Infra)*
- [x] **[Done]** Ticket-16: Resilience Patterns (LLM Retries).
    - *Outcome*: Implemented `ResilienceService` with `tenacity` exponential backoff.
- [x] **[Done]** Ticket-17: Observability (Latency, Cost, Violations).
    - *Outcome*: Implemented `ObservabilityService` & Middleware.
- [x] **[Done]** Ticket-18: Immutable Audit Logs (SHA-256 Hashing).
    - *Lane B (Services)*
- [x] **[Done]** Ticket-19: PII Redaction (Sanitization).
    - *Outcome*: Implemented generic `PIIService` and LangGraph node.

## 📦 Recently Completed
- [x] **[Done]** Phase 3: Core Logic - Implement `draft_translate` with real LLM calls.
- [x] **[Lead Implemented]** Phase 3: Core Logic - Connect `compile_constraints` to pgvector.
    - **Goal**: Implement `app/services/queue_service.py` (or similar) to handle background job processing.
    - **Acceptance**: `POST /translate` returns immediately with "PENDING" status.
    - **Lane**: Lane D (API).

- [x] **[Done]** Ticket-03: PDF Ingestion Prototype
    - **Goal**: Research and create a prototype `app/services/pdf_ingestion.py` using `pypdf` or `unstructured`.
    - **Acceptance**: Extract text from a sample PDF while preserving block structure.
    - **Lane**: Lane B (Services).

- [x] **[Done]** Ticket-04: Infrastructure Hardening
    - **Goal**: Add Redis to `docker-compose.yml` (required for caching) and create a `Dockerfile` for the app.
    - **Acceptance**: `docker-compose up` spins up both Postgres and Redis. App image builds successfully.
    - **Lane**: Lane C (Infra).

- [x] **[x]** Ticket-20: API Refinement (Structured Input).
    - **Goal**: Update `TranslationRequest` to accept `List[ContentBlock]` instead of raw string.
    - **Lane**: Lane D (API).
- [x] **[x]** Ticket-22: Pharma Hardening (Gates, PII, Fix Packets).
    - **Goal**: Implement "Near-Zero Critical Escape" architecture.
    - **Lane**: Lane D (API/Backend).
- [x] **[x]** Ticket-23: Next-Gen Frontend (Shazam-style).
    - **Goal**: Implement "Magic Button" Upload and "Glass Box" status.
    - **Lane**: Lane A (Frontend).
- [x] **[x]** Ticket-21: Next-Gen Frontend (React/Next.js).
    - **Goal**: Create beautiful agentic UI for document upload & translation visualization.
    - **Lane**: Lane A (Frontend).

## 🏁 Completed
- [x] Phase 1: Config & Migration
- [x] Phase 2: DB Schema
- [x] Phase 2.5: Infrastructure
