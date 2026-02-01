# Multi-Agent Collaboration Protocol: "TransMax Program"

# Multi-Agent Collaboration Protocol: "TransMax Program"

## 1. Hierarchy & Roles

### 🕴️ CEO (The User)
-   **Role**: Vision, Strategy, "Tie-breaker".
-   **When to involve**: ONLY for major scope changes or unresolvable architectural trade-offs.

### 👑 Program Lead (Antigravity)
-   **Role**: PM & Tech Lead.
-   **Responsibilities**:
    -   Manages the backlog (`active_tasks.md`).
    -   Unblocks workers (`lead_decisions.md`).
    -   Reviews code (via `handoff_log.md` audit).
    -   Merges "Lanes" into the Core.

### 👷 Worker Agents
-   **Role**: Developers (Lane A/B/C/D).
-   **Responsibilities**: Execution, Testing, Reporting Blockers.

## 2. Communication Channels

### 📋 The Board: `active_tasks.md`
-   **Lead**: Writes tickets.
-   **Workers**: Read tickets -> Change to `[WIP]` -> Execute -> Change to `[Done]`.

### ❓ Asking for Help: `questions_to_lead.md` (Worker -> Lead)
-   If you are stuck, have a design question, or need a dependency approval:
    1.  **Write** your question in `questions_to_lead.md`.
    2.  Check for existing answers in `lead_decisions.md`.
    3.  If critical blocker, stop and notify user to "Wake up Lead".

### 📢 The Oracle: `lead_decisions.md` (Lead -> Worker)
-   Contains answers to FAQs, architectural rulings, and global announcements.
-   **Mandatory Read** at session start.

## 3. The "Ticket" System
1.  Ticket naming: `Ticket-XX: [Title]`.
2.  Lanes:
    -   **Lane A**: Core (Lead)
    -   **Lane B**: Services
    -   **Lane C**: Infra
    -   **Lane D**: API

## 4. Context Protocol and Handoff
*(Same as previous: Read Lane files only, run tests, update handoff_log.md)*

## 4. Context Engineering (CRITICAL)
To maintain high performance and avoid hallucination, agents must strictly limit their context.

-   **Initial Read**: ONLY read `status.md`, `active_tasks.md`, and `COLLABORATION.md`.
-   **Lane Restriction**: Do NOT read files outside your Lane unless absolutely necessary for an interface check.
-   **No Dump**: Never read the entire `app/` folder. Use `ls` to find specific files.
-   **Reset**: If you feel lost, clear context and re-read `status.md`.

## 5. Quality Control & Handoff
Every Session **MUST** end with a valid Handoff Log entry containing "Proof of Life".

### The Handoff Checklist
1.  [ ] Code compiles/parses (no syntax errors).
2.  [ ] `pytest` passed for your lane (include summary).
3.  [ ] No new linter errors.
4.  [ ] `active_tasks.md` updated.

### Log Format
Append to `.context/handoff_log.md`:
```markdown
## [YYYY-MM-DD HH:MM] Agent: [Name] (Lane [X])
- **Ticket**: [Ticket-ID]
- **Status**: [Done/Blocked]
- **Context Added**: [List of NON-Lane files read, if any]
- **Verification**: `25 passed in 0.45s` (Paste pytest output)
- **Next Steps**: [Clear instruction]
```

## 5. Directory Structure
```
transmax/
├── .context/           <-- THE BRAIN
│   ├── roadmap.md      <-- High level goals (Lead Managed)
│   ├── active_tasks.md <-- The Backlog (Claimable)
│   └── handoff_log.md  <-- Session History
```
