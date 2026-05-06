"""Provider-agnostic LLM client.

Agents depend on this interface instead of importing SDKs directly. It supports
OpenAI by default (`gpt-4o-mini` per the lab brief) and Anthropic as an optional
alternative. SDK imports are lazy so CI/tests can run without optional LLM packages.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

try:  # tenacity is a declared dependency, but keep the module robust.
    from tenacity import retry, stop_after_attempt, wait_exponential
except Exception:  # pragma: no cover - only used in minimal environments
    F = TypeVar("F", bound=Callable[..., object])

    def retry(*args: object, **kwargs: object) -> Callable[[F], F]:
        def _decorator(fn: F) -> F:
            return fn

        return _decorator

    def stop_after_attempt(_attempts: int) -> None:
        return None

    def wait_exponential(*args: object, **kwargs: object) -> None:
        return None

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.observability.tracing import _langfuse_client

logger = logging.getLogger(__name__)

_PRICING = {
    # (input_per_1M, output_per_1M)
    "gpt-4o-mini": (0.15, 0.60),
    "claude-3-5-sonnet-latest": (3.0, 15.0),
}


@dataclass
class LLMResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    model: str = ""
    latency_seconds: float = 0.0


class LLMClient:
    """Small completion interface used by all agents.

    `complete(system_prompt, user_prompt, temperature)` is the only required method,
    making it easy to replace OpenAI with Anthropic/Gemini/mocks while preserving the
    assignment's agent contracts and Pydantic schemas.
    """

    def __init__(self, model: str | None = None, max_tokens: int = 2048) -> None:
        settings = get_settings()
        self.provider = "anthropic" if settings.anthropic_api_key and not settings.openai_api_key else "openai"
        self.model = model or (settings.anthropic_model if self.provider == "anthropic" else settings.openai_model)
        self.max_tokens = max_tokens
        self._settings = settings

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Return a model completion with token accounting and latency timing."""
        if self.provider == "anthropic":
            return self._complete_anthropic(system_prompt, user_prompt, temperature)
        return self._complete_openai(system_prompt, user_prompt, temperature)

    def _complete_openai(self, system_prompt: str, user_prompt: str, temperature: float) -> LLMResponse:
        if not self._settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Use MockLLMClient or provide a key.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError("openai package is not installed. Install optional LLM dependencies.") from exc

        t0 = time.perf_counter()
        client = OpenAI(api_key=self._settings.openai_api_key)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        langfuse = _langfuse_client()
        generation_cm = (
            langfuse.start_as_current_generation(
                name="LLMClient.complete",
                input=messages,
                model=self.model,
                model_parameters={"temperature": temperature, "max_tokens": self.max_tokens},
                metadata={"provider": "openai"},
            )
            if langfuse is not None
            else None
        )
        if generation_cm is not None:
            generation_cm.__enter__()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:
            if generation_cm is not None:
                generation_cm.__exit__(type(exc), exc, exc.__traceback__)
            raise
        latency = time.perf_counter() - t0
        content = response.choices[0].message.content or ""
        usage = response.usage
        in_tok = int(usage.prompt_tokens if usage else 0)
        out_tok = int(usage.completion_tokens if usage else 0)
        if langfuse is not None:
            try:
                langfuse.update_current_generation(
                    output=content,
                    usage_details={"input": in_tok, "output": out_tok, "total": in_tok + out_tok},
                    cost_details={"total": self._cost_for_tokens(in_tok, out_tok)},
                )
            except Exception:
                pass
        if generation_cm is not None:
            generation_cm.__exit__(None, None, None)
        return self._response(content, in_tok, out_tok, latency)

    def _complete_anthropic(self, system_prompt: str, user_prompt: str, temperature: float) -> LLMResponse:
        if not self._settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Use MockLLMClient or provide a key.")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError("anthropic package is not installed. Install optional LLM dependencies.") from exc

        t0 = time.perf_counter()
        client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        messages = [{"role": "user", "content": user_prompt}]
        langfuse = _langfuse_client()
        generation_cm = (
            langfuse.start_as_current_generation(
                name="LLMClient.complete",
                input=[{"role": "system", "content": system_prompt}, *messages],
                model=self.model,
                model_parameters={"temperature": temperature, "max_tokens": self.max_tokens},
                metadata={"provider": "anthropic"},
            )
            if langfuse is not None
            else None
        )
        if generation_cm is not None:
            generation_cm.__enter__()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages,
                temperature=temperature,
            )
        except Exception as exc:
            if generation_cm is not None:
                generation_cm.__exit__(type(exc), exc, exc.__traceback__)
            raise
        latency = time.perf_counter() - t0
        content = response.content[0].text if response.content else ""
        in_tok = int(response.usage.input_tokens)
        out_tok = int(response.usage.output_tokens)
        if langfuse is not None:
            try:
                langfuse.update_current_generation(
                    output=content,
                    usage_details={"input": in_tok, "output": out_tok, "total": in_tok + out_tok},
                    cost_details={"total": self._cost_for_tokens(in_tok, out_tok)},
                )
            except Exception:
                pass
        if generation_cm is not None:
            generation_cm.__exit__(None, None, None)
        return self._response(content, in_tok, out_tok, latency)

    def _cost_for_tokens(self, in_tok: int, out_tok: int) -> float:
        in_price, out_price = _PRICING.get(
            self.model,
            (self._settings.input_token_price_usd, self._settings.output_token_price_usd),
        )
        return (in_tok * in_price + out_tok * out_price) / 1_000_000

    def _response(self, content: str, in_tok: int, out_tok: int, latency: float) -> LLMResponse:
        cost = self._cost_for_tokens(in_tok, out_tok)
        logger.debug(
            "LLM[%s] in=%d out=%d cost=$%.5f lat=%.2fs",
            self.model,
            in_tok,
            out_tok,
            cost,
            latency,
        )
        return LLMResponse(
            content=content,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            model=self.model,
            latency_seconds=latency,
        )
