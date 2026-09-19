"""Claude Code coding agent interface.

Runs `claude -p --output-format stream-json` and tails its JSONL stdout line
by line, exactly as `agent_pi` does for pi — the same `PiRequest` in, the same
`PiResult` out, the same pi-shaped tool events forwarded to the caller, so
`agents.py`, the tracer and the visualizer do not know which coding agent ran.

Sessions: Claude Code needs a UUID session id. The first send of a session
passes `--session-id <uuid>`; every later send `--resume <uuid>`, which
continues the same context window. Which one applies is decided by a marker
file under `request.session_dir`, written after the first send succeeds.

Model: written in the config as `anthropic/<model-id>` (`anthropic/claude-opus-5`).
The provider segment is the resolver's guard — Claude Code speaks to Anthropic
only — and the id is handed to `--model` as is.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from .data_types import PiRequest, PiResult
from .utils import now_iso, operator_env

CLAUDE_PATH = os.environ.get("CLAUDE_PATH", "claude")
PROVIDER = "anthropic"

# pi's reasoning ladder -> Claude Code's --effort levels. pi has three rungs
# below `medium`; Claude Code's floor is `low`.
EFFORT = {"off": "low", "minimal": "low", "low": "low", "medium": "medium",
          "high": "high", "xhigh": "xhigh", "max": "max"}

# pi builtin names -> Claude Code builtin names. `ls` has no dedicated tool in
# Claude Code (Bash covers it); the pi subagent extension tools map onto
# Claude Code's own Agent tool, which is the same capability natively.
TOOLS = {"read": "Read", "bash": "Bash", "edit": "Edit", "write": "Write",
         "grep": "Grep", "find": "Glob", "ls": "Bash",
         "subagent_create": "Agent", "subagent_continue": "Agent",
         "subagent_list": "Agent", "subagent_remove": "Agent"}

# A nested `claude` inherits these from the Claude Code session that launched
# the ADW and then behaves as a child of it: ignoring --session-id, sharing its
# messaging socket. The agent must be its own top-level session.
NESTING_ENV_PREFIXES = ("CLAUDECODE", "CLAUDE_CODE_", "CLAUDE_PID", "CLAUDE_EFFORT")

RESULT_SNIPPET_CHARS = 20_000


def resolve_model(pattern: str) -> tuple[str, str]:
    """`anthropic/<id>` -> ("anthropic", "<id>"); anything else is a config error."""
    provider, _, model_id = pattern.partition("/")
    if provider != PROVIDER or not model_id:
        raise ValueError(f"model pattern {pattern!r} must be written as "
                         f"{PROVIDER}/<model-id> for coding_agent claude_code "
                         f"(e.g. {PROVIDER}/claude-opus-5)")
    if shutil.which(CLAUDE_PATH) is None:
        raise ValueError(f"claude CLI not found on PATH ({CLAUDE_PATH!r}) — "
                         "install Claude Code or set CLAUDE_PATH")
    return provider, model_id


def _tools_flag(tools: Optional[list[str]]) -> Optional[str]:
    """Translate the config allowlist; None keeps Claude Code's default set."""
    if tools is None:
        return None
    mapped: list[str] = []
    for tool in tools:
        name = TOOLS.get(tool, tool)
        if name not in mapped:
            mapped.append(name)
    return ",".join(mapped)


def _agent_env() -> dict[str, str]:
    env = operator_env()
    for key in list(env):
        if key.startswith(NESTING_ENV_PREFIXES):
            env.pop(key)
    return env


def _text_of(content) -> str:
    """Join the text of a Claude content list, or pass a plain string through."""
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content or []
                   if isinstance(part, dict) and part.get("type") == "text")


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _turn_usage(usage: dict) -> dict:
    """Reshape one Claude usage block into pi's usage keys, which
    `UsageBreakdown.add_turn` and the visualizer already understand."""
    parts = {
        "input": int(usage.get("input_tokens") or 0),
        "output": int(usage.get("output_tokens") or 0),
        "cacheRead": int(usage.get("cache_read_input_tokens") or 0),
        "cacheWrite": int(usage.get("cache_creation_input_tokens") or 0),
    }
    parts["totalTokens"] = sum(parts.values())
    return parts


class EventTranslator:
    """Fold Claude Code's stream into the pi-shaped events `agents.py` forwards.

    `assistant` messages carry tool_use blocks -> `tool_execution_start`;
    `user` messages carry their tool_result blocks -> `tool_execution_end`.
    The tool name and args travel with the start, so the end only needs the id
    — `ToolCallTracker` pairs them.
    """

    def __init__(self) -> None:
        self._open: dict[str, dict] = {}

    def translate(self, event: dict) -> list[dict]:
        etype = event.get("type")
        message = event.get("message") or {}
        out: list[dict] = []
        if etype == "assistant":
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    call_id = str(block.get("id") or "")
                    self._open[call_id] = {"tool": block.get("name"),
                                           "args": block.get("input") or {}}
                    out.append({"type": "tool_execution_start", "toolCallId": call_id,
                                "toolName": block.get("name"),
                                "args": block.get("input") or {},
                                "timestamp": now_iso()})
        elif etype == "user":
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    call_id = str(block.get("tool_use_id") or "")
                    opened = self._open.pop(call_id, {})
                    text = _clip(_text_of(block.get("content")), RESULT_SNIPPET_CHARS)
                    out.append({"type": "tool_execution_end", "toolCallId": call_id,
                                "toolName": opened.get("tool"),
                                "args": opened.get("args") or {},
                                "isError": bool(block.get("is_error")),
                                "result": {"content": [{"type": "text", "text": text}]},
                                "timestamp": now_iso()})
        return out


def _command(request: PiRequest, model_id: str, resume: bool) -> list[str]:
    # The prompt rides directly behind -p: --tools is variadic and would
    # otherwise swallow a trailing positional prompt as one more tool name.
    cmd = [
        CLAUDE_PATH, "-p", request.prompt,
        "--output-format", "stream-json", "--verbose",
        "--model", model_id,
        "--effort", EFFORT.get(request.thinking, "medium"),
        "--system-prompt", request.system_prompt,
        # The ADW is the permission boundary: what an agent may change is
        # enforced after the call by adw_modules/permissions.py, not by a
        # prompt no one is there to answer.
        "--permission-mode", "bypassPermissions",
        # The engineer's MCP servers (mail, docs, browser) are theirs, not the
        # agent's. Tools come from the config allowlist only.
        "--strict-mcp-config",
    ]
    cmd += ["--resume", request.session_id] if resume else ["--session-id", request.session_id]
    tools = _tools_flag(request.tools)
    if tools is not None:
        cmd += ["--tools", tools]
    return cmd


def run(request: PiRequest, on_event: Optional[Callable[[dict], None]] = None,
        on_spawn: Optional[Callable[[int], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None) -> PiResult:
    """Run one non-interactive Claude Code turn — create or continue the session."""
    _, model_id = resolve_model(request.model)
    marker_dir = Path(request.session_dir)
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = marker_dir / f"{request.session_id}.session"
    cmd = _command(request, model_id, resume=marker.exists())

    raw_path = Path(request.raw_output_path)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    result = PiResult(session_id=request.session_id)
    translator = EventTranslator()
    started = time.monotonic()
    # stdin is DEVNULL for the same reason as in agent_pi: the prompt is in
    # argv, and an inherited non-TTY stdin is a silent way to hang.
    process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, bufsize=1, cwd=request.cwd,
                               env=_agent_env())
    if on_spawn:
        on_spawn(process.pid)
    final: dict = {}
    with raw_path.open("a") as raw:
        assert process.stdout is not None
        for line in process.stdout:
            raw.write(line)
            raw.flush()
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = event.get("type")
            if etype == "assistant":
                message = event.get("message") or {}
                text = _text_of(message.get("content"))
                if text:
                    result.text = text            # last assistant text wins
                usage = _turn_usage(message.get("usage") or {})
                turn = usage["totalTokens"]
                if turn:
                    result.tokens += turn
                    result.usage.add_turn(usage, turn)
                    result.context_tokens = turn  # occupancy after this turn
            elif etype == "result":
                final = event
            if on_event:
                for translated in translator.translate(event):
                    on_event(translated)

    stderr = process.stderr.read() if process.stderr else ""
    result.returncode = process.wait()
    if on_exit:
        on_exit(process.pid)

    if final:
        if final.get("result"):
            result.text = str(final["result"])
        result.cost = float(final.get("total_cost_usd") or 0.0)
        result.usage.total_cost = result.cost
        window = ((final.get("modelUsage") or {}).get(model_id) or {}).get("contextWindow")
        result.context_window = int(window or 0)
        if final.get("is_error"):
            raise RuntimeError(f"claude reported an error after "
                               f"{int(time.monotonic() - started)}s: "
                               f"{_clip(result.text or stderr.strip(), 800)}")
    if result.returncode != 0 and not result.text:
        raise RuntimeError(f"claude exited {result.returncode}: {stderr.strip()[-800:]}")
    marker.write_text(now_iso())
    return result
