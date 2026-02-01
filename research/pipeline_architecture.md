# TransMax Pharma-Grade Architecture

This document outlines the **LangGraph State Machine with Bounded Refinement Cycles** and the defense-in-depth strategy to ensure a **Near-Zero Critical Escape Rate**.

---

## 1. The Pipeline: State Machine

We do not use a simple DAG. We use a **State Machine** with conditional refinement loops (Max N=2) to deterministically fix errors.

### Step 1: Ingestion (Risk-Aware)
- **Service**: `PDFService`
- **Output**: Structured Content Blocks (`block_id`, `type`, `content`, `confidence`).
- **Control**: **Layout Confidence Score**.
    - If `confidence < threshold` (e.g., complex nested table), the block is flagged for **Mandatory HITL**.

### Step 2: Context & PII Defense
- **Context**: Vector Search retrieves Glossary/TM.
- **PII Strategy**: **Stable Token Rehydration**.
    - Usage: `[[PII:NAME:8f3a]]` instead of `[NAME_1]`.
    - **Gate**: Source/Target must match PII tokens exactly by ID and Count. Mismatch = **BLOCK**.

### Step 3: Draft Translation (Role-Based)
- **Action**: LLM translates block-by-block with injected Constraints.
- **Resilience**: `ResilienceService` handles API failures.

### Step 4: Deterministic Quality Gates (The Core Defense)
We categorize failures by severity.

| Gate Category | Check | Severity | Action |
| :--- | :--- | :--- | :--- |
| **Safety** | PII Token Mismatch | **CRITICAL** | **BLOCK** (No Refinement) |
| **Safety** | Unit/Number Mismatch (Canonical) | **CRITICAL** | **BLOCK** |
| **Meaning** | Negation Flip (Do -> Do Not) | **CRITICAL** | Refine -> Block if fails |
| **Meaning** | Modality Drift (Must -> Should) | **MAJOR** | Refine -> Review |
| **Compliance** | Glossary Violation (Forbidden var.) | **MAJOR** | Refine -> Review |
| **Style** | Length / Formatting | **MINOR** | Auto-fix / Pass |

*Note: "BLOCK" means the system refuses to finalize the document without Human Intervention.*

### Step 5: Refinement (Fix Packets)
- **Trigger**: Major/Critical errors that are fixable.
- **Mechanism**: We do not send raw errors. We send a **Fix Packet**:
    ```json
    {
      "segment_id": "b1_s1",
      "violation": "Glossary Error: 'renal'",
      "required_fix": "Use 'insuffisance rénale'",
      "constraints": ["Do not change numbers", "Preserve [[PII:NAME:8f3a]]"]
    }
    ```
- **Loop Limit**: Max 2 iterations. If validation fails after Iteration 2 -> **REVIEW_REQUIRED**.

### Step 6: Immutable Audit
- **Action**: SHA-256 Hash of `{Input + Decision + Process_Log}`.
- **Goal**: Reproducibility. We record model version, prompt hash, and glossary version.

---

## 2. HITL Triggers (Proactive)

We do not aim for "100% automation". We aim for **100% detection**.

1.  **Critical Gate Failure**: Any CRITICAL error that survives refinement.
2.  **Section Risk**: High-risk sections (e.g., *4.2 Posology*, *4.3 Contraindications*) may trigger mandatory review regardless of quality score.
3.  **Layout Uncertainty**: Low confidence in PDF extraction.
4.  **Signal Disagreement**: Semantic Reviewer (LLM) disagrees with Deterministic Gates.

---

## 3. Near-Zero Critical Escape Rate

Our promise to Pharma operations:
**"We cannot guarantee the machine is perfect. We guarantee it will not be confident when it is wrong."**

*Updated: 2026-01-17 based on Lead Architect Feedback.*
