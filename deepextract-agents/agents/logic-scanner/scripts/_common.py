"""Shared utilities for logic-scanner agent.

This agent is an LLM-only agent — all analysis is performed by the language
model using the threat model and callgraph context prepared by ai-logic-scanner
skill scripts. This _common.py exists for infrastructure consistency.
"""
from __future__ import annotations
from pathlib import Path
from skills._shared import bootstrap, make_db_resolvers

WORKSPACE_ROOT = bootstrap(__file__)
resolve_db_path, resolve_tracking_db = make_db_resolvers(WORKSPACE_ROOT)

__all__ = ["WORKSPACE_ROOT", "resolve_db_path", "resolve_tracking_db"]
