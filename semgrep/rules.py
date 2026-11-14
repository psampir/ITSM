# ai-generated: 60% - test cases for semgrep/rules.yml, written with an assistant from the two guards in this package
"""Test cases for semgrep/rules.yml (CI-SPEC.md P-31).

Semgrep pairs a test file with the config of the same name (`semgrep --test semgrep/`). A comment naming a rule
above a line says that line must be reported by it; a comment saying ok says it must not.
"""

import sqlite3
from typing import Optional

from fastapi import Query


# ruleid: svcdesk-unbounded-query-string
async def unbounded_filter(
    state: Optional[str] = Query(default=None),
):
    return state


# ok: svcdesk-unbounded-query-string
async def bounded_filter(
    state: Optional[str] = Query(default=None, max_length=8),
    count: int = Query(default=50, le=200),
):
    return state, count


def open_shared(path):
    # ruleid: svcdesk-shared-sqlite-connection
    return sqlite3.connect(path, check_same_thread=False)


def open_local(path):
    # ok: svcdesk-shared-sqlite-connection
    return sqlite3.connect(path)
