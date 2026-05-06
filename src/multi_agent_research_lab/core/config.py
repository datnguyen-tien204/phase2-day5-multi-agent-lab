"""Application configuration.

Keep config small and explicit. Do not read environment variables directly in agents.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # OpenAI default required by the lab brief. A different provider can still be used
    # as long as LLMClient.complete implements the same contract.
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")

    # Optional Anthropic fallback/alternative.
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-5-sonnet-latest", validation_alias="ANTHROPIC_MODEL")

    langsmith_api_key: str | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="multi-agent-research-lab", validation_alias="LANGSMITH_PROJECT"
    )
    langfuse_public_key: str | None = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_base_url: str | None = Field(default=None, validation_alias="LANGFUSE_BASE_URL")
    langfuse_host: str | None = Field(default=None, validation_alias="LANGFUSE_HOST")

    tavily_api_key: str | None = Field(default=None, validation_alias="TAVILY_API_KEY")
    searxng_base_url: str = Field(
        default="http://localhost:8088", validation_alias="SEARXNG_BASE_URL"
    )
    searxng_timeout_seconds: float = Field(
        default=10.0, ge=1.0, le=60.0, validation_alias="SEARXNG_TIMEOUT_SECONDS"
    )
    search_fetch_top_k: int = Field(default=4, ge=0, le=10, validation_alias="SEARCH_FETCH_TOP_K")
    search_fetch_timeout_seconds: float = Field(
        default=6.0, ge=1.0, le=30.0, validation_alias="SEARCH_FETCH_TIMEOUT_SECONDS"
    )

    # Required guardrails from the assignment.
    max_iterations: int = Field(default=6, ge=1, le=20, validation_alias="MAX_ITERATIONS")
    timeout_seconds: int = Field(default=60, ge=5, le=600, validation_alias="TIMEOUT_SECONDS")

    # AgenticAI-inspired quality/context controls; additive only, no schema bypassing.
    quality_threshold: float = Field(default=8.0, ge=0, le=10, validation_alias="QUALITY_THRESHOLD")
    max_revision_rounds: int = Field(default=1, ge=0, le=5, validation_alias="MAX_REVISION_ROUNDS")
    max_context_chars: int = Field(default=8_000, ge=1_000, le=100_000, validation_alias="MAX_CONTEXT_CHARS")
    enable_parallel_research: bool = Field(default=True, validation_alias="ENABLE_PARALLEL_RESEARCH")

    # Pricing (USD per 1M tokens) – used for cost estimation
    input_token_price_usd: float = Field(default=0.15, validation_alias="INPUT_TOKEN_PRICE_USD")
    output_token_price_usd: float = Field(default=0.60, validation_alias="OUTPUT_TOKEN_PRICE_USD")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
