"""
OpenAI infrastructure — async client with retry, timeout, and strict output.
Only this module may call the OpenAI API. Services must go through this interface.
"""

import asyncio
import logging

from app.config import get_settings
from app.domain.enums import TicketCategory, TicketPriority
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


# ── Output Schema ──────────────────────────────────────────────────────────────


class AITicketAnalysis(BaseModel):
    """Strict Pydantic model that the AI MUST conform to."""

    category: TicketCategory
    priority: TicketPriority
    ai_response: str
    confidence: float  # 0.0 – 1.0


class AIServiceError(Exception):
    """Raised when AI is unavailable after all retries."""

    def __init__(self, message: str, retry_after: int = 30):
        super().__init__(message)
        self.retry_after = retry_after


# ── System Prompt ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a support ticket triage assistant. Analyze the user's
support message and return ONLY valid JSON (no markdown, no explanation) matching
this exact schema:
{
  "category": "<billing|technical|general>",
  "priority": "<low|medium|high>",
  "ai_response": "<A helpful, professional response to the user (2-4 sentences)>",
  "confidence": <float between 0.0 and 1.0>
}
Categorization rules:
- billing: payment issues, refunds, subscriptions, invoices, pricing
- technical: bugs, errors, performance, integrations, API issues
- general: feature requests, account info, other questions
Priority rules:
- high: service outage, data loss, payment failure, security issue
- medium: feature broken, significant inconvenience, billing discrepancy
- low: general question, minor issue, feature request
Return ONLY the JSON object. No surrounding text."""

# ── Client ─────────────────────────────────────────────────────────────────────


class OpenAIClient:
    """
    Async-safe OpenAI client wrapper.
    - 15s timeout
    - 2 retries with exponential backoff
    - Strict JSON validation via Pydantic
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
            max_retries=0,  # We handle retries ourselves for better control
        )
        self._model = settings.OPENAI_MODEL
        self._max_retries = settings.OPENAI_MAX_RETRIES

    async def analyze_ticket(self, message: str) -> AITicketAnalysis:
        """
        Send ticket message to OpenAI and return a validated analysis.

        Raises:
            AIServiceError: If all retries fail or response is invalid.
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                backoff = 2**attempt  # 2s, 4s
                logger.warning(
                    "Retrying OpenAI call",
                    extra={"attempt": attempt, "backoff_seconds": backoff},
                )
                await asyncio.sleep(backoff)

            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": message[:2000]},  # enforce max
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,  # low temp for consistent structured output
                    max_tokens=500,
                )

                raw_text = response.choices[0].message.content or ""

                # Pydantic validates the AI response strictly
                try:
                    analysis = AITicketAnalysis.model_validate_json(raw_text)
                    logger.info(
                        "AI ticket analysis complete",
                        extra={
                            "category": analysis.category,
                            "priority": analysis.priority,
                            "confidence": analysis.confidence,
                        },
                    )
                    return analysis
                except (ValidationError, ValueError) as ve:
                    logger.error(
                        "AI returned invalid JSON schema",
                        extra={"error": str(ve), "raw": raw_text[:200]},
                    )
                    last_error = ve
                    continue

            except APITimeoutError as e:
                logger.warning("OpenAI timeout", extra={"attempt": attempt})
                last_error = e
            except RateLimitError as e:
                logger.error("OpenAI rate limit hit")
                last_error = e
                await asyncio.sleep(10)  # extra backoff on rate limit
            except APIConnectionError as e:
                logger.error("OpenAI connection error", extra={"error": str(e)})
                last_error = e
            except Exception as e:
                logger.exception("Unexpected OpenAI error")
                last_error = e

        raise AIServiceError(
            f"AI service unavailable after {self._max_retries + 1} attempts: {last_error}",
            retry_after=30,
        )

    _CHAT_SYSTEM_PROMPT = """You are a friendly, knowledgeable support assistant.
    You are helping a user who has opened a support ticket.
    Use the ticket description as context.
    Keep replies concise (2-4 sentences), professional, and helpful.
    Never mention that you are an AI unless directly asked.
    Do not output JSON — respond in plain conversational text."""

    async def chat_reply(
        self,
        ticket_description: str,
        history: list[dict],
    ) -> str:
        """
        Generate a conversational support reply given:
        - ticket_description : the original ticket text (context)
        - history            : list of {"role": "user"|"assistant", "content": str}

        Returns the assistant's plain-text reply string.
        Raises AIServiceError after all retries fail.
        """
        system = self._CHAT_SYSTEM_PROMPT
        if ticket_description:
            system += f"\n\nTicket context: {ticket_description[:500]}"

        messages = [{"role": "system", "content": system}] + history

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                await asyncio.sleep(2**attempt)
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=0.5,
                    max_tokens=300,
                )
                return (response.choices[0].message.content or "").strip()
            except (APITimeoutError, APIConnectionError, RateLimitError) as e:
                last_error = e
            except Exception as e:
                last_error = e

        raise AIServiceError(
            f"Chat AI unavailable after {self._max_retries + 1} attempts: {last_error}"
        )


# ── Singleton ──────────────────────────────────────────────────────────────────

_client_instance: OpenAIClient | None = None


def get_openai_client() -> OpenAIClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = OpenAIClient()
    return _client_instance
