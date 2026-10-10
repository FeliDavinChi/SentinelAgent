# SentinelAgent — Self-Verifying, DB-Enforced Agentic RAG

## 1. Team Details

**Team Name / ID:** [Your team name — fill in]

**Team Lead:** M Lakshmi Manas

**Team Members:**

- M Lakshmi Manas | Backend Developer
- P Sruthi |
-
- [Name] | [Role, optional]

**Repo Link (Optional):** [Link, or N/A]

**Demo Link (Optional):** [Link, or N/A]

---

## 2. Problem Statement

Build a secure enterprise research agent that answers employee questions over internal documents while enforcing authorization. Documents have classifications and access rules. Relevant information that the requesting employee is not authorized to access must never be provided to the language model or revealed in the final answer.

Core Requirements

- Accept a natural-language employee question and user context.
- Ingest documents with classification, department, owner, and access-control metadata.
- Search for relevant candidates but enforce authorization before document content reaches the LLM.
- Handle outdated and conflicting authorized documents.
- Return an answer with citations to the evidence the user is allowed to access.
- Record an audit trail of the request, authorization decisions, and evidence used.
- Safely respond when the answer exists only in documents the user cannot access.

---

## 3. TL;DR

**Problem:** RAG agents can leak restricted info if an application-code filter step is buggy or gets bypassed.

**Solution:** An agent retrieves only through a database with row-level security, then verifies its own citations.

**Who benefits:** Employees get accurate, cited answers; security teams get a guarantee enforced by the database.

---

## 4. Scope of the Project

**What are you building?**

SentinelAgent: an agentic RAG system where a tool-calling LLM searches company documents through a Postgres database with Row-Level Security, so unauthorized rows can never be returned regardless of the query written. A second, independent verifier agent checks every citation in the draft answer traces to an authorized row before it ever reaches the employee.

**How does it solve the problem statement?**

Authorization is enforced at the database layer via RLS policies keyed to the employee's role/department/clearance — not by app-layer filtering, so it can't be bypassed by a bug in retrieval code. The verifier independently blocks any ungrounded claim from reaching the user.

**Key features you're building for this hackathon:**

- Row-Level Security in Postgres enforces authorization at the query level, not in app code
- Retrieval agent decides how many searches to run and refines its own queries
- Independent verifier agent checks every citation before the answer is shown
- Full tool-call audit trail: every query issued and every row actually returned
- Safe refusal when RLS returns zero relevant rows for an on-topic question

**What are you deliberately NOT doing? (Optional)**

Not building a document ingestion UI or fine-grained field-level (sub-row) redaction within a single document.

---

## 5. Why an Agentic Approach?

**What does your agent decide or do on its own?**

The retrieval agent decides how many searches to run and how to refine its query if the first pass is ambiguous or insufficient. It hands its draft to a separate verifier agent that independently judges whether each citation is actually grounded, and can force a re-generation if not.

**Why wouldn't a fixed script, if-else rules, or a simple chatbot be enough?**

A fixed script can't tell when a question needs a follow-up search, or when a claim doesn't actually match the source it cites — both require judgment. Row-Level Security handles the deterministic access-control part; the agentic layer only handles the parts that genuinely need reasoning.

---

## 6. Who It's For & What Changes

**Who or what is this for?**

Employees needing answers from internal docs; security/compliance teams who need airtight, database-level access guarantees.

**The world today, without your solution:**

Employees ask IT/HR directly, or an existing RAG tool relies on application-code filters that a future bug could bypass without anyone noticing until it's too late.

**The world with your solution, fully built and scaled to production:**

Every query is provably scoped at the database level. A citation-verification step makes leaked or hallucinated information structurally rare, not just policy-discouraged.

**What your hackathon build actually delivers today:**

Postgres RLS policies enforcing classification/department access; a working agent loop with a search tool; a verifier pass that rejects ungrounded draft answers in our test cases.

**Before vs. After**

| What Changes               | Today                                 | With Our Current Build              | At Production Scale          |
| -------------------------- | ------------------------------------- | ----------------------------------- | ---------------------------- |
| Where access control lives | App code, easy to bypass with a bug   | Database RLS policy, structural     | Same, hardened + monitored   |
| Handling vague questions   | Single fixed search, may miss context | Agent retries/refines its own query | Same, at scale with caching  |
| Hallucination risk         | Unchecked                             | Verifier rejects ungrounded claims  | Verifier + human spot-checks |

---

## 7. Architecture & Agents

**How is your system put together?**

An employee's identity opens an RLS-scoped Postgres session. A retrieval agent calls a search_documents tool against that session — RLS guarantees only authorized rows return. The agent drafts a cited answer; a separate verifier agent checks every citation against the authorized rows, and only a passing answer reaches the employee.

### 7.1 Agents

- **Retrieval Agent:** Decides how many searches to run and refines its query; drafts a cited answer from whatever the RLS-scoped database returns. Uses Gemini for reasoning over multiple sources. Talks to the search_documents tool and the Verifier Agent.
- **Verifier Agent:** Checks every citation in the draft traces to a row the database actually returned; rejects and forces regeneration if not. Uses a smaller model since it's a narrow grounding check. Talks to the Retrieval Agent's draft output only.

### 7.2 Services, APIs, Databases & Memory

- **Postgres + Row-Level Security:** Stores documents, metadata, and permissions; RLS policies enforce that queries can't return unauthorized rows. Used by the search tool.
- **search_documents tool (function-calling):** Wraps a scoped SQL/vector query; the only way the agent can read document content. Used by the Retrieval Agent.
- **Audit log (Postgres table):** Records every tool call, its query text and returned rows, plus the verifier's verdict. Used for compliance review.
- **Web UI (HTML/CSS/JS):** Where employees ask questions and see verified, cited answers.

**How does your system remember things (memory & state)?**

No cross-session conversational memory. Each request opens a fresh RLS-scoped session; audit log entries and document versions persist in Postgres so decisions remain reviewable later.

**Diagram Link (Optional):** N/A — architecture diagrams were sketched during development, not hosted anywhere yet.

### 7.3 Example Walkthrough

**Example input:** An engineer asks: "How much are executive salaries increasing this year?"

1. [Web UI] Opens an RLS-scoped Postgres session for the engineer and sends the question to the Retrieval Agent.
2. [Retrieval Agent] Calls search_documents; RLS returns zero rows for the restricted compensation document.
3. [Retrieval Agent] Refines the query once, still gets no relevant authorized rows back.
4. [Retrieval Agent] Drafts a safe-refusal response since no authorized evidence exists.
5. [Verifier Agent] Confirms the refusal makes no unsupported claims and approves it.
6. [Audit log] Records both search attempts, the zero rows returned, and the final refusal.

**Final output:** A safe refusal message, with a full tool-call audit trail proving RLS never returned the restricted document.

**Anything special about how your workflow runs? (Optional)**

The verifier only ever sees the draft answer and the list of authorized row IDs — never the retrieval agent's full reasoning trace — so it can't be talked into approving something ungrounded by persuasive-sounding reasoning around it.

---

## 8. Tech Stack

| Layer                | Technology                                   |
| -------------------- | -------------------------------------------- |
| Frontend / Interface | HTML / CSS / JavaScript                      |
| Backend              | Python + FastAPI                             |
| Agent Framework      | Custom code (function-calling, no framework) |
| Database / Storage   | Postgres with Row-Level Security             |
| Hosting              | Local machine (hackathon)                    |
| Other                | Gemini API (retrieval + verifier agents)     |

---

## 9. What to Expect From Our Current Build

**Working:**

- Postgres RLS policies, tested to block unauthorized rows at the query level
- Basic agent loop calling a search tool

**Partly working, mocked, or hard-coded:**

- Verifier agent uses a simplified grounding check, not fully robust yet
- Query refinement logic is basic — one retry, not open-ended

**Not working or not built yet:**

- Full document ingestion pipeline (PDF parsing) not wired in
- Frontend is a placeholder

**What we'd most like to be judged on:**

The Row-Level Security enforcement — we can show a raw query against a restricted document returning zero rows, independent of any application-layer code.

---

## 10. Future Scope

### Idea 1

**Name:** Multi-agent department routing

**What it is:** Route each question to department-specific sub-agents (finance, HR, eng) that share the RLS-scoped connection, giving each sub-agent narrower context.

**Why it matters:** Reduces prompt size and improves relevance for large document sets.

**How we'd build it:** A router agent classifies the question's likely department and dispatches to the matching sub-agent.

**Done when:** A finance question only ever invokes the finance sub-agent.

### Idea 2

**Name:** Confidence-scored refusals

**What it is:** The verifier attaches a confidence score to its grounding check instead of a binary pass/fail.

**Why it matters:** Lets borderline cases get flagged for human review instead of an outright refusal.

**How we'd build it:** Verifier prompt returns a 0–1 score plus reasoning; below a threshold, route to a human review queue.

**Done when:** A borderline test case gets routed to review instead of auto-refused or auto-approved.

### Idea 3 (Optional)

**Name:** Real-time document sync

**What it is:** Automatically re-index documents and update RLS-relevant metadata when source systems (SharePoint, Drive) change.

**Why it matters:** Stale permissions are a real leak vector if access is revoked late in a source system.

**How we'd build it:** Webhook listeners from source systems update Postgres metadata, triggering re-embedding.

**Done when:** A permission change in the source system is reflected in RLS behavior within minutes.

---

## 11. Additional Notes (Optional)

Built and validated the RLS policies and the core agent loop first; verifier robustness and full document ingestion are the next things we'd tackle.
