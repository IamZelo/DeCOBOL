"""
Event models and streaming representations for DeCOBOL orchestration.
Conforms to docs/CONTRACTS.md v1.0.0 §6.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import time
from typing import Dict, Any, Optional, Callable


class EventType(str, Enum):
    PIPELINE_STARTED = "pipeline_started"
    AGENT_STARTED = "agent_started"
    AGENT_FINISHED = "agent_finished"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    LLM_CALLED = "llm_called"
    LLM_REPLIED = "llm_replied"
    DECISION = "decision"
    RETRY_SCHEDULED = "retry_scheduled"
    ERROR = "error"
    PIPELINE_FINISHED = "pipeline_finished"


@dataclass
class Event:
    type: EventType
    message: str
    seq: int = 0
    job_id: str = ""
    agent: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert Event to JSON-serializable dictionary matching CONTRACTS.md §6."""
        return {
            "seq": self.seq,
            "ts": round(self.ts, 3),
            "job_id": self.job_id,
            "type": self.type.value if isinstance(self.type, EventType) else str(self.type),
            "agent": self.agent,
            "message": self.message,
            "data": self.data or {},
        }

    def to_sse(self) -> str:
        """Format Event as Server-Sent Event data frame."""
        payload = json.dumps(self.to_dict())
        return f"data: {payload}\n\n"


# Callback type for event consumers
EventCallback = Callable[[Event], None]
