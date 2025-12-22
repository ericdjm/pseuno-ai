"""
Shared FastAPI dependencies.
"""

from fastapi import Request

from app.services.agent_prompt_graph import AgentPromptGraph


def get_song_agent(request: Request) -> AgentPromptGraph:
    """Return the startup-initialized LangGraph agent."""
    return request.app.state.song_agent
