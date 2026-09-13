"""Importing this package registers every tool in CONTRACTS §2.2.

Each tool module registers itself with ``@tool`` (registry.py) as a side
effect of being imported. Callers that reach tools only through
``call_tool("name", ...)`` — the orchestrator, the Flask API — never import
the tool modules directly, so without this the registry would be empty at
call time and every ``call_tool`` would fail with "unknown tool". Importing
them here, once, on package import, means any ``from app.tools... import
...`` anywhere in the app is enough to populate the registry.
"""

from . import cobol_parser  # noqa: F401
from . import filesystem  # noqa: F401
from . import java_compiler  # noqa: F401
from . import java_template  # noqa: F401
from . import semantic_checks  # noqa: F401
from . import semantic_fixes  # noqa: F401
from . import type_mapper  # noqa: F401
from . import workspace_graph  # noqa: F401
