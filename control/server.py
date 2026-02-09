import subprocess
import sys
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# ==========================================================
# ENV
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent
# Load .env from project root so Cursor/spawned process finds it
load_dotenv(ROOT / ".env", override=True)

# Paths: use env for deploy (Docker/CI), else repo-relative
MCP_DB_PATH = os.environ.get("MCP_DB_PATH") or str(ROOT / "control" / "mcp.db")
CORE_BIN = os.environ.get("MCP_CORE_BIN") or str(ROOT / "core" / "target" / "release" / "core")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ==========================================================
# PROMPTS
# ==========================================================

SYSTEM_PROMPTS = {
    "research": """You are a software research assistant.

Rules:
- Advisory only
- Do NOT make decisions
- Do NOT approve or reject
- Do NOT assume missing context

Output:
- Summary
- Options
- Trade-offs
- Open questions
""",
    "review": """You are a code reviewer.

Rules:
- Feedback only
- No approval or rejection
- No large refactors
- Focus on correctness, security, architecture

Output:
- Issues (with severity)
- Suggestions
- Questions
"""
}

# ==========================================================
# TOOLS (MCP SCHEMA – IMPORTANT)
# ==========================================================

TOOLS = [
    {
        "name": "full",
        "description": "Decide next step based on current state",
        "inputSchema": {
            "type": "object",
            "properties": {
                "feature": {"type": "string"}
            },
            "required": ["feature"]
        }
    },
    {
        "name": "approve",
        "description": "Approve current step (human only)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "feature": {"type": "string"}
            },
            "required": ["feature"]
        }
    },
    {
        "name": "research",
        "description": "Run GPT research (advisory only)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "feature": {"type": "string"}
            },
            "required": ["feature"]
        }
    },
    {
        "name": "review",
        "description": "Run GPT code review (advisory only)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "diff": {"type": "string"}
            },
            "required": ["diff"]
        }
    }
]

# ==========================================================
# RUST CORE (lazy init – avoid startup failure)
# ==========================================================

_core_proc = None

def _get_core():
    global _core_proc
    if _core_proc is None:
        env = os.environ.copy()
        env["MCP_DB_PATH"] = MCP_DB_PATH
        _core_proc = subprocess.Popen(
            [CORE_BIN],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(MCP_DB_PATH),
            env=env,
        )
    return _core_proc

def forward_to_core(method, params):
    try:
        core = _get_core()
        core.stdin.write(json.dumps({
            "method": method,
            "params": params
        }) + "\n")
        core.stdin.flush()

        line = core.stdout.readline()
        out = json.loads(line) if line else {}
        # MCP tool result format
        text = out.get("result", out.get("output", str(out)))
        return {"content": [{"type": "text", "text": str(text)}], "isError": False}
    except Exception as e:
        sys.stderr.write(f"[mcp] core error: {e}\n")
        sys.stderr.flush()
        return {"content": [{"type": "text", "text": f"[ERROR] Core: {e}"}], "isError": True}

# ==========================================================
# OPENAI
# ==========================================================

def call_gpt(system_prompt, user_prompt):
    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        # Safe extraction: output_text or fallback to output[0].content[0].text
        text = getattr(resp, "output_text", None)
        if text is None and resp.output:
            item = resp.output[0]
            if getattr(item, "content", None):
                for c in item.content:
                    if getattr(c, "text", None):
                        text = c.text
                        break
        # MCP tool result format so Cursor displays it in chat
        return {"content": [{"type": "text", "text": text or "[No output]"}], "isError": False}
    except Exception as e:
        sys.stderr.write(f"[mcp] GPT error: {e}\n")
        sys.stderr.flush()
        raise

# ==========================================================
# JSON-RPC HELPERS
# ==========================================================

def reply_result(req_id, result):
    if req_id is None:
        return
    sys.stdout.write(json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result
    }) + "\n")
    sys.stdout.flush()

def reply_error(req_id, code, message):
    if req_id is None:
        return
    sys.stdout.write(json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": code,
            "message": message
        }
    }) + "\n")
    sys.stdout.flush()

# ==========================================================
# MCP MAIN LOOP
# ==========================================================

def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method") or ""
        params = req.get("params") or {}

        try:
            # -------------------- INITIALIZE --------------------

            if method == "initialize":
                reply_result(req_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "prompts": {},
                        "resources": {}
                    },
                    "serverInfo": {
                        "name": "mcp-control-plane",
                        "version": "1.0.0"
                    }
                })

            # -------------------- DISCOVERY --------------------

            elif method == "tools/list":
                reply_result(req_id, {"tools": TOOLS})

            elif method == "prompts/list":
                reply_result(req_id, {"prompts": []})

            elif method == "resources/list":
                reply_result(req_id, {"resources": []})

            # -------------------- TOOL CALL --------------------

            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})

                try:
                    if name == "research":
                        reply_result(req_id, call_gpt(
                            SYSTEM_PROMPTS["research"],
                            arguments.get("feature", "")
                        ))

                    elif name == "review":
                        reply_result(req_id, call_gpt(
                            SYSTEM_PROMPTS["review"],
                            arguments.get("diff", "")
                        ))

                    elif name in ("full", "approve"):
                        reply_result(req_id, forward_to_core(name, arguments))

                    else:
                        reply_error(req_id, -32601, f"Unknown tool: {name}")
                except Exception as e:
                    reply_error(req_id, -32603, str(e))

            # -------------------- NOTIFICATIONS (no reply) --------------------

            elif method == "notifications/initialized":
                pass  # MCP client notification, no response

            # -------------------- SHUTDOWN --------------------

            elif method in ("shutdown", "exit"):
                reply_result(req_id, {})
                break

            # -------------------- UNKNOWN --------------------

            else:
                reply_error(req_id, -32601, f"Unknown method: {method}")

        except Exception as e:
            sys.stderr.write(f"[mcp] request error: {e}\n")
            sys.stderr.flush()
            reply_error(req_id, -32603, str(e))

# ==========================================================

if __name__ == "__main__":
    main()
