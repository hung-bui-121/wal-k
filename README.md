# WAL-K — Workflow Agent Layers Kernel

> **AI Game Studio Kernel** — a kernel that orchestrates a team of role-specialized AI agents to autonomously run Unity game production from a GDD, phase by phase, requiring user involvement only at major decisions and Phase Gates.

**Status:** Draft — requirements stage, no code yet.

---

## Vision

```text
USER ── GDD + Project Constraints ──▶ WAL-K
                                        │
                                        ├─ Analyze · Design · Plan · Breakdown
                                        ├─ Create Work · Implement · Generate Assets
                                        └─ Review · Test · Fix · Integrate · Polish
                                        │
                                        ▼
                                   PHASE GATE ──▶ USER: GO / REWORK / CHANGE / STOP
```

The user acts as **Game Director / Product Authority / Studio Owner**, rather than directly coordinating individual tasks, agents, or tools.

WAL-K is a **production orchestration system**, not just a coding agent framework. The kernel must maintain production state across many agents, many AI models, many sessions, many machines, many phases, and many months of development.

---

## Core Design Principles

| Principle | Meaning |
|---|---|
| **Role ≠ Model** | Roles carry professional identity; models are replaceable workers that can be routed and swapped via fallback. |
| **Project Knowledge ≠ Model Context** | Project knowledge lives in the repository, not in the context window. |
| **Work State ≠ Project Knowledge** | Work state is managed through Jira; implementation state is managed through Git. |
| **Implementation ≠ Verification** | Code review and QC must be independent from the implementer. |
| **Evidence > Assertion** | Every conclusion must be backed by evidence; Phase Gates produce evidence packages, not just text reports. |
| **Conflict is a Feature** | Agents are allowed to challenge each other through structured debate. |
| **Context First** | An agent must load the right context before acting. |
| **Autonomy Must Have Boundaries** | Autonomy is scoped to the approved phase; escalation follows autonomy levels. |
| **Recoverable & Auditable** | Every important decision and action can be recovered and traced. |
| **User Retains Final Product Authority** | The user is the final authority on the product. |

---

## High-Level Architecture

```text
┌───────────────────────────────────────┐
│        Production Orchestrator        │
├───────────────────────────────────────┤
│        Workflow / State Engine        │
├───────────────────────────────────────┤
│          Agent Runtime                │
├───────────────────────────────────────┤
│ Model Router / Effort / Budget        │
├───────────────────────────────────────┤
│ Context / Memory / Knowledge          │
├───────────────────────────────────────┤
│ Debate / Decision / Authority         │
├───────────────────────────────────────┤
│ Skill / Tool / Hook Runtime           │
├───────────────────────────────────────┤
│ Jira / Git / Unity / Provider APIs    │
├───────────────────────────────────────┤
│ Execution Ledger / Telemetry          │
├───────────────────────────────────────┤
│ Continuous Improvement                │
└───────────────────────────────────────┘
```

### Agent Instance

```text
Agent Instance = Role Constitution + Authority + Runtime Policy
               + Model + Effort + Budget
               + Skills + Tools + Permissions + Working Context
```

### Agent Roles

| Role | Primary responsibility |
|---|---|
| Orchestrator | Coordinates overall production, task routing, phase gates |
| Product Owner | Authority over requirements / GDD, PO-level resolution |
| Scrum Master | Workflow, Jira, progress tracking |
| Design Leader | Game design, GDD interpretation |
| Art Director | Art direction, asset pipeline, visual validation |
| Lead Developer | Technical architecture, independent code review |
| Senior Developer | Implementation against the Executable Story Contract |
| Quality Control | Independent testing, bug workflow |
| UA / Release | Release candidate, store metadata, publishing |

A Game Director agent is optional.

---

## MVP Scope

The MVP is meant to **prove the kernel**, not to complete the full AI studio.

- **Roles:** Orchestrator, Lead Dev, Senior Dev, QC (optional early: PO, Design Leader)
- **Models:** Claude, Codex — must demonstrate `Role ≠ Model`, preferred model, fallback model, and handover
- **Integrations:** Local repository, Git, Jira, Unity project (recommended: Graphify)

### Non-goals (initial)

No GDD generation from a single prompt; no replacement of Unity Editor, Jira, or Git; no model training or proprietary LLM; no engines other than Unity; no complete art pipeline or self-publishing of builds in the MVP; no dependency on a single AI provider.

---

## Roadmap

| Stage | Scope |
|---|---|
| 1 — Kernel Core | runtime, workflow, persistence, model adapters & router, context manager, tool registry |
| 2 — Production Kit | environment bootstrap, skills, hooks, approved artifacts, permissions |
| 3 — Coding Workflow | Git, Jira, Lead Dev, Senior Dev, QC, CI |
| 4 — Persistent Studio Memory | feature/bug context, decisions, freshness, handovers, code graph |
| 5 — Multi-Agent Reasoning | constitutions, debates, authority, escalation, PO |
| 6 — GDD Compiler | GDD ingestion, readiness analysis, phase decomposition, traceability |
| 7 — Autonomous Phase | scheduler, parallel agents, QC fix loop, evidence, Phase Gate |
| 8 — Art / Design | Design Leader, Art Director, Meshy, OpenArt, asset provenance |
| 9 — Production Intelligence | execution ledger, reporting, cost accounting, dashboards |
| 10 — Continuous Improvement | observations, retrospectives, improvement candidates, experiments, behavior versioning |
| 11 — Release | RC workflow, UA, store metadata, publishing |

---

## Planned Repository Layout

```text
kernel/
├── orchestrator/   ├── workflow/      ├── agents/        ├── runtime/
├── model-router/   ├── effort/        ├── budgets/       ├── context/
├── memory/         ├── decisions/     ├── debate/        ├── skills/
├── tools/          ├── hooks/         ├── integrations/  ├── permissions/
├── persistence/    ├── telemetry/     ├── improvement/   └── cli/
```

A game project using the kernel keeps its project memory in an `.ai/` directory (project, phases, features, bugs, decisions, approved, reports, handovers, improvements, agents).

---

## Documentation

The Master Requirements Specification (Draft v0.2) is maintained outside this repository. It covers design principles, agent roles, model policy, context & memory, workflow, phase gates, continuous improvement, MVP strategy, roadmap, invariants, risks, and open design questions.

Open design questions (constitution schema, `.ai/` format, workflow engine, model adapter API, scheduler, sandbox, Unity automation, ...) will be resolved during the Architecture / Technical Design phases.

---

## Philosophy

> AI models are replaceable workers.
> Roles provide professional identity.
> Constitutions provide judgment.
> Skills provide know-how.
> Tools provide capabilities.
> Project Memory provides continuity.
> Workflow provides control.
> Evidence provides trust.
> Production Kit provides a stable working environment.
> Execution Ledger provides history.
> Continuous Improvement makes the studio better over time.
