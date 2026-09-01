# Scope

This document is non-negotiable. Phases 2, 3 and 4 do not amend it.

If a phase hits a problem that appears to require something on the out-of-scope
list, **the correct action is to document the limitation, not to build the thing.**
Write it in your phase report and in `docs/DECISIONS.md`. A documented limitation is
a finding; an out-of-scope feature built to route around it is scope creep that the
next phase inherits.

## In scope, permanently

- Document intake → structured extraction → CRM write
- Human review queue for low-confidence fields
- Retrieval-augmented Q&A with citations and abstention
- Model routing between Anthropic and OpenAI
- Evaluation harness (accuracy, latency, cost per task)
- PII redaction before any third-party API call
- Audit logging of every model call
- Metrics endpoint

## Out of scope, permanently

- Agent frameworks, tool-calling loops, multi-step autonomous planning
- Fine-tuning or training any model
- Building a CRM UI, or replacing any part of EspoCRM's own interface
- Generating customer-facing proposal PDFs
- Multi-tenancy, user management, role-based access control
- Real-time streaming responses
- Any second vector database, any second queue, any second web framework

## Why these particular exclusions

Recorded so a later phase does not re-derive a different answer.

**Agent frameworks and tool-calling loops.** Both capabilities are single-shot:
document in, validated record out; question in, cited answer out. Neither needs a
model to decide what to do next. An agent loop would add non-determinism to a system
whose entire value proposition is that its outputs are auditable and measurable.

**Fine-tuning.** The failure modes here are extraction accuracy and abstention
calibration. Both are addressable with better prompts, better retrieval and better
confidence scoring, and all three are measurable within a day. Fine-tuning is a
weeks-long loop that would have to be redone every time the schema changes.

**A CRM UI.** EspoCRM already has one. VoltDesk is a service beside the CRM, not a
replacement for it — the moment it renders a screen the boundary is gone.

**Proposal PDFs.** Customer-facing document generation is a different product with
different review requirements. VoltDesk populates the technical fields on a
`Proposal` record and stops there.

**Multi-tenancy and RBAC.** One company, one deployment, deployed inside that
company's network boundary. This is a real constraint on where the service may run,
not an omission — it is stated in `docs/ARCHITECTURE.md` under the trust boundary.

**Streaming.** Nothing here is read by a human as it is generated. Documents are
processed by a worker; questions are answered in one response. Streaming would add a
code path with no reader.

**A second database, queue or framework.** The deployment target is one small VM.
Every additional stateful service is another thing to back up, monitor and restart.
