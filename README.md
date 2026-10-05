# WAL-K — Workflow Agent Layers Kernel

> **AI Game Studio Kernel** — kernel điều phối một đội AI agents theo role chuyên môn để tự vận hành production game Unity từ GDD, theo từng phase, và chỉ cần user can thiệp tại các quyết định quan trọng hoặc Phase Gate.

**Trạng thái:** Draft — đang ở giai đoạn requirement, chưa có code.

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

User đóng vai trò **Game Director / Product Authority / Studio Owner**, không trực tiếp điều phối từng task, từng agent hay từng tool.

WAL-K là một **production orchestration system**, không chỉ là coding agent framework. Kernel phải duy trì trạng thái production xuyên suốt nhiều agent, nhiều AI model, nhiều session, nhiều machine, nhiều phase và nhiều tháng phát triển.

---

## Nguyên tắc thiết kế cốt lõi

| Nguyên tắc | Ý nghĩa |
|---|---|
| **Role ≠ Model** | Role mang professional identity; model chỉ là worker có thể thay thế, route và fallback. |
| **Project Knowledge ≠ Model Context** | Tri thức dự án sống trong repository, không sống trong context window. |
| **Work State ≠ Project Knowledge** | Work state quản lý qua Jira; implementation state quản lý qua Git. |
| **Implementation ≠ Verification** | Code review và QC phải độc lập với người implement. |
| **Evidence > Assertion** | Mọi kết luận phải có bằng chứng; Phase Gate sinh evidence package, không chỉ text report. |
| **Conflict is a Feature** | Agents được phép phản biện và tranh luận có cấu trúc (structured debate). |
| **Context First** | Agent phải load đúng context trước khi hành động. |
| **Autonomy Must Have Boundaries** | Tự chủ trong phạm vi approved phase; escalate theo autonomy level. |
| **Recoverable & Auditable** | Mọi quyết định và hành động quan trọng đều phục hồi được và truy vết được. |
| **User Retains Final Product Authority** | User là thẩm quyền cuối cùng về sản phẩm. |

---

## Kiến trúc tổng quan

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

| Role | Trách nhiệm chính |
|---|---|
| Orchestrator | Điều phối toàn bộ production, routing task, phase gate |
| Product Owner | Thẩm quyền về requirement / GDD, resolution cấp PO |
| Scrum Master | Workflow, Jira, tiến độ |
| Design Leader | Game design, GDD interpretation |
| Art Director | Art direction, asset pipeline, visual validation |
| Lead Developer | Kiến trúc kỹ thuật, code review độc lập |
| Senior Developer | Implementation theo Executable Story Contract |
| Quality Control | Kiểm thử độc lập, bug workflow |
| UA / Release | Release candidate, store metadata, publishing |

Game Director agent là tùy chọn.

---

## Phạm vi MVP

MVP nhằm **chứng minh kernel**, chưa hoàn thiện toàn bộ AI studio.

- **Roles:** Orchestrator, Lead Dev, Senior Dev, QC (tùy chọn sớm: PO, Design Leader)
- **Models:** Claude, Codex — phải chứng minh được `Role ≠ Model`, preferred model, fallback model và handover
- **Integrations:** Local repository, Git, Jira, Unity project (khuyến nghị: Graphify)

### Non-goals (giai đoạn đầu)

Không tự sinh GDD từ một prompt, không thay thế Unity Editor / Jira / Git, không train hay tự xây LLM, không hỗ trợ engine ngoài Unity, không hoàn thiện art pipeline hay tự publish build trong MVP, không phụ thuộc một AI provider duy nhất.

---

## Roadmap

| Stage | Nội dung |
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

## Cấu trúc repository dự kiến

```text
kernel/
├── orchestrator/   ├── workflow/      ├── agents/        ├── runtime/
├── model-router/   ├── effort/        ├── budgets/       ├── context/
├── memory/         ├── decisions/     ├── debate/        ├── skills/
├── tools/          ├── hooks/         ├── integrations/  ├── permissions/
├── persistence/    ├── telemetry/     ├── improvement/   └── cli/
```

Game project sử dụng kernel sẽ giữ project memory trong thư mục `.ai/` (project, phases, features, bugs, decisions, approved, reports, handovers, improvements, agents).

---

## Tài liệu

- [`requirements/WAL_K_REQ.md`](requirements/WAL_K_REQ.md) — Master Requirements Specification (Draft v0.2), 140 mục, bao gồm design principles, agent roles, model policy, context & memory, workflow, phase gate, continuous improvement, MVP strategy, roadmap, invariants, risks và open design questions.

Các câu hỏi thiết kế còn mở (schema constitution, format `.ai/`, workflow engine, model adapter API, scheduler, sandbox, Unity automation...) sẽ được chốt trong giai đoạn Architecture / Technical Design.

---

## Triết lý

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
