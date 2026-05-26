"""Assistant agent with PydanticAI.

The main conversational agent that can be extended with custom tools.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider
from pydantic_ai.settings import ModelSettings

from app.agents.prompts import get_system_prompt_with_rag
from app.agents.tools import get_current_datetime
from app.agents.tools.rag_tool import search_knowledge_base
from app.agents.tools.web_search_tool import search_web
from app.core.cloudwatch_metrics import schedule_bedrock_agent_invocation_metrics
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Deps:
    """Dependencies for the assistant agent.

    These are passed to tools via RunContext.
    """

    user_id: str | None = None
    user_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AssistantAgent:
    """Assistant agent wrapper for conversational AI.

    Encapsulates agent creation and execution with tool support.
    """

    def __init__(
        self,
        model_name: str | None = None,
        temperature: float | None = None,
        system_prompt: str | None = None,
    ):
        self.model_name = model_name or settings.AI_MODEL
        self.temperature = temperature or settings.AI_TEMPERATURE
        self.system_prompt = system_prompt or get_system_prompt_with_rag()
        self._agent: Agent[Deps, str] | None = None

    def _create_agent(self) -> Agent[Deps, str]:
        """Create and configure the PydanticAI agent."""
        model = BedrockConverseModel(
            self.model_name,
            provider=BedrockProvider(region_name=settings.AWS_REGION),
        )

        agent = Agent[Deps, str](
            model=model,
            model_settings=ModelSettings(temperature=self.temperature),
            system_prompt=self.system_prompt,
        )

        self._register_tools(agent)

        return agent

    def _register_tools(self, agent: Agent[Deps, str]) -> None:
        """Register all tools on the agent."""

        @agent.tool
        async def current_datetime(ctx: RunContext[Deps]) -> str:
            """Get the current date and time.

            Use this tool when you need to know the current date or time.
            """
            return get_current_datetime()

        @agent.tool
        async def search_documents(ctx: RunContext[Deps], query: str, top_k: int = 5) -> str:
            """Search the knowledge base for relevant documents.

            Use this tool to find information from uploaded documents before answering user queries.
            Searches across all available collections automatically.
            Cite sources by referring to the document filename from the search results.

            Args:
                query: The search query string.
                top_k: Number of top results to retrieve (default: 5).

            Returns:
                Formatted string with search results including content and scores.
            """
            return await search_knowledge_base(query=query, top_k=top_k)

        @agent.tool
        async def search_internet(ctx: RunContext[Deps], query: str, max_results: int = 5) -> str:
            """Search the internet for up-to-date information.

            Use this tool when:
            - The knowledge base has already returned relevant information.
            - Live web data is needed only to support that knowledge-base-grounded answer.

            Do not use this tool when the knowledge base has no relevant match.
            In that case, respond exactly: I do not know

            Args:
                query: The search query string.
                max_results: Number of results to return (1-10, default: 5).

            Returns:
                Formatted web search results with titles, URLs, and snippets.
            """
            return await search_web(query=query, max_results=max_results)

    @property
    def agent(self) -> Agent[Deps, str]:
        """Get or create the agent instance."""
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent

    async def run(
        self,
        user_input: str,
        history: list[dict[str, str]] | None = None,
        deps: Deps | None = None,
    ) -> tuple[str, list[Any], Deps]:
        """Run agent and return the output along with tool call events."""
        model_history: list[ModelRequest | ModelResponse] = []

        for msg in history or []:
            if msg["role"] == "user":
                model_history.append(ModelRequest(parts=[UserPromptPart(content=msg["content"])]))
            elif msg["role"] == "assistant":
                model_history.append(ModelResponse(parts=[TextPart(content=msg["content"])]))
            elif msg["role"] == "system":
                model_history.append(ModelRequest(parts=[SystemPromptPart(content=msg["content"])]))

        agent_deps = deps if deps is not None else Deps()

        logger.info("Running agent with user input: %s...", user_input[:100])
        started_at = time.perf_counter()
        result = await self.agent.run(user_input, deps=agent_deps, message_history=model_history)
        schedule_bedrock_agent_invocation_metrics(
            latency_ms=(time.perf_counter() - started_at) * 1000,
            operation="agent_run",
            model_name=self.model_name,
        )

        tool_events: list[Any] = []
        for message in result.all_messages():
            if hasattr(message, "parts"):
                for part in message.parts:
                    if hasattr(part, "tool_name"):
                        tool_events.append(part)

        logger.info("Agent run complete. Output length: %d chars", len(result.output))

        return result.output, tool_events, agent_deps

    async def iter(
        self,
        user_input: str,
        history: list[dict[str, str]] | None = None,
        deps: Deps | None = None,
    ) -> Any:
        """Stream agent execution with full event access."""
        model_history: list[ModelRequest | ModelResponse] = []

        for msg in history or []:
            if msg["role"] == "user":
                model_history.append(ModelRequest(parts=[UserPromptPart(content=msg["content"])]))
            elif msg["role"] == "assistant":
                model_history.append(ModelResponse(parts=[TextPart(content=msg["content"])]))
            elif msg["role"] == "system":
                model_history.append(ModelRequest(parts=[SystemPromptPart(content=msg["content"])]))

        agent_deps = deps if deps is not None else Deps()

        async with self.agent.iter(
            user_input,
            deps=agent_deps,
            message_history=model_history,
        ) as run:
            async for event in run:
                yield event


def get_agent(model_name: str | None = None) -> AssistantAgent:
    """Factory function to create an AssistantAgent."""
    return AssistantAgent(model_name=model_name)


async def run_agent(
    user_input: str,
    history: list[dict[str, str]],
    deps: Deps | None = None,
) -> tuple[str, list[Any], Deps]:
    """Run agent and return the output along with tool call events."""
    agent = get_agent()
    return await agent.run(user_input, history, deps)
