"""LLM-based image description for RAG document processing."""

import base64
import logging
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

IMAGE_DESCRIPTION_PROMPT = (
    "Describe this image in detail. Focus on any text, data, charts, diagrams, "
    "or visual information that would be useful for document search and retrieval. "
    "Be concise but comprehensive."
)


class BaseImageDescriber(ABC):
    """Abstract base for LLM-based image description."""

    @abstractmethod
    async def describe(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Generate a text description of an image."""


def _b64_encode(image_bytes: bytes) -> str:
    """Base64-encode raw image bytes."""
    return base64.b64encode(image_bytes).decode("utf-8")


class PydanticAIImageDescriber(BaseImageDescriber):
    """Image description using PydanticAI with Bedrock."""

    def __init__(self, model_name: str | None = None):
        from app.core.config import settings

        self.model_name = (
            model_name
            or getattr(settings, "RAG_IMAGE_DESCRIPTION_MODEL", None)
            or settings.AI_MODEL
        )

    async def describe(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        try:
            from pydantic_ai import Agent
            from pydantic_ai.messages import BinaryContent
            from pydantic_ai.models.bedrock import BedrockConverseModel
            from pydantic_ai.providers.bedrock import BedrockProvider

            from app.core.config import settings

            model = BedrockConverseModel(
                self.model_name,
                provider=BedrockProvider(region_name=settings.AWS_REGION),
            )
            agent = Agent(model)
            started_at = time.perf_counter()
            result = await agent.run(
                [
                    BinaryContent(data=image_bytes, media_type=mime_type),
                    IMAGE_DESCRIPTION_PROMPT,
                ]
            )
            from app.core.cloudwatch_metrics import schedule_bedrock_agent_invocation_metrics

            schedule_bedrock_agent_invocation_metrics(
                latency_ms=(time.perf_counter() - started_at) * 1000,
                operation="image_description",
                model_name=self.model_name,
            )
            return result.output if hasattr(result, "output") else str(result.data)
        except Exception as e:
            logger.error(f"PydanticAI image description failed: {e}")
            return ""
