"""
Agent package for DeCOBOL.
Exports base Agent class and the five individual agents conforming to docs/CONTRACTS.md §4, §14.
"""

from app.agents.base import Agent, AgentResult, ToolResult, StubAgent
from app.agents.parser_agent import ParserAgent
from app.agents.converter_agent import ConverterAgent
from app.agents.optimizer_agent import OptimizerAgent
from app.agents.validator_agent import ValidatorAgent
from app.agents.documenter_agent import DocumenterAgent

__all__ = [
    "Agent",
    "AgentResult",
    "ToolResult",
    "StubAgent",
    "ParserAgent",
    "ConverterAgent",
    "OptimizerAgent",
    "ValidatorAgent",
    "DocumenterAgent",
]
