"""Lightweight permission classification for agent/tool actions.

Inspired by AgenticAI's permission pipeline: classify actions by risk instead of
using one binary allow/deny switch. The current lab only needs search/read and
LLM calls, but the policy is ready for future file or shell tools.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ActionRisk(StrEnum):
    READ_ONLY = "read_only"
    NETWORK = "network"
    FILE_WRITE = "file_write"
    DESTRUCTIVE = "destructive"


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PermissionCheck(BaseModel):
    action: str
    risk: ActionRisk
    decision: PermissionDecision
    reason: str


_DANGEROUS_PATTERNS = ("rm -rf", "sudo", "curl | bash", "wget | bash", "eval", ":(){")
_WRITE_PATTERNS = ("write", "edit", "delete", "append", "overwrite")


class PermissionPolicy:
    """Small deterministic policy used before external or mutating actions."""

    def classify(self, action: str) -> ActionRisk:
        lowered = action.lower()
        if any(pattern in lowered for pattern in _DANGEROUS_PATTERNS):
            return ActionRisk.DESTRUCTIVE
        if lowered.startswith("search ") or lowered.startswith("search:") or lowered.startswith("search network:"):
            return ActionRisk.NETWORK
        if "http" in lowered or "network" in lowered:
            return ActionRisk.NETWORK
        if any(pattern in lowered for pattern in _WRITE_PATTERNS):
            return ActionRisk.FILE_WRITE
        return ActionRisk.READ_ONLY

    def check(self, action: str) -> PermissionCheck:
        risk = self.classify(action)
        if risk == ActionRisk.DESTRUCTIVE:
            return PermissionCheck(action=action, risk=risk, decision=PermissionDecision.DENY, reason="dangerous pattern")
        if risk == ActionRisk.FILE_WRITE:
            return PermissionCheck(action=action, risk=risk, decision=PermissionDecision.ASK, reason="mutates files/state")
        return PermissionCheck(action=action, risk=risk, decision=PermissionDecision.ALLOW, reason="read-only or search")
