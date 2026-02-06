# MCP Architecture – Quick Read (Engineer / AI)
**Updated (Cursor + Rust Core + TestSprite)**

---

## 🎯 Goal

ควบคุม workflow การพัฒนา software ให้:

- deterministic
- audit-able
- ไม่มีใครข้ามขั้น
- มนุษย์ต้อง approve ก่อนเสมอ

Workflow หลัก:

research → spec → coding → test → review → done

> AI ช่วยคิดได้  
> QA รันเทสต์ได้  
> แต่ **ตัดสินใจไม่ได้**

---

## 🧠 Roles & Responsibilities

### Cursor
- Entry point เดียวของมนุษย์
- Chat + IDE
- Orchestrates intent ไปยัง MCP / TestSprite / GPT
- ไม่ตัดสินใจเอง

---

### MCP Server (ของเรา)
- Control Plane
- Source of truth ของ state
- บังคับ rule + approval gate
- ไม่เขียนโค้ด
- ไม่รันเทสต์
- ไม่ตัดสินใจด้วย AI

---

### Rust Core
- State machine
- Approval gate
- Deterministic rules
- Persistence (SQLite)
- ไม่มี heuristic / ไม่มี ML

> Rust core = authority จริง  
> Control layer = adapter เท่านั้น

---

### GPT
- Research
- Spec
- Review
- Advisory only
- ไม่มี authority

---

### TestSprite
- QA engine
- Run / generate tests
- รายงานผล test
- ไม่ควบคุม workflow

---

### Human
- เขียนโค้ด
- approve / reject เท่านั้น
- Authority สูงสุด

---

## 🧱 System Architecture

Cursor (Chat / IDE)
│
├── MCP Control (stdin/stdout)
│     └── Rust Core (State + Gate)
│           └── SQLite
│
└── TestSprite (QA)

---

## 🔑 Intents (What MCP Understands)

All commands are sent via Cursor chat.

- research → request AI research
- spec → request spec + test design
- full → decide next legal step based on state
- approve → human approval only
- reject → reset / reject feature
- status (optional) → read-only state
- coding (optional) → human signals coding start

Example:

