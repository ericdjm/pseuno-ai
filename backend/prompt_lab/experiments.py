"""
Experiment definitions for speed optimization benchmarks.

Each ExperimentConfig defines parameter overrides applied to the AgentPromptGraph
pipeline.  The `apply_experiment` function creates a configured graph instance
for a given experiment.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from app.config import Settings
from app.services.agent_prompt_graph import AgentPromptGraph, GeminiChatClient


@dataclass
class ExperimentConfig:
    name: str
    description: str
    # Per-operation max_output_tokens: key = model config field name
    # e.g. {"style_model": 1500, "lyrics_model": 3000, "genre_disambiguation_model": 2000}
    max_output_tokens_by_model_field: Optional[Dict[str, int]] = None
    # Thinking overrides (apply to ALL clients using the matching model family)
    thinking_budget_override: Optional[int] = None  # 2.5 models: None=default(1024), 0=disable
    thinking_level_override: Optional[str] = None   # 3.x models: None=default(dynamic), "minimal"/"low"/"medium"/"high"
    use_native_async: bool = False
    parallel_style_name: bool = False
    # Per-model-field temperature overrides
    temperature_by_model_field: Optional[Dict[str, float]] = None


# ── Experiment definitions ────────────────────────────────────────────────────

BASELINE = ExperimentConfig(
    name="baseline",
    description="Current production pipeline with no changes",
)

EXP1_MAX_TOKENS_STYLE = ExperimentConfig(
    name="max_tokens_style",
    description="max_output_tokens=1500 on style generation (3-flash)",
    max_output_tokens_by_model_field={"style_model": 1500},
)

EXP2_MAX_TOKENS_LYRICS = ExperimentConfig(
    name="max_tokens_lyrics",
    description="max_output_tokens=3000 on lyrics generation (2.5-flash)",
    max_output_tokens_by_model_field={"lyrics_model": 3000},
)

EXP3_MAX_TOKENS_GENRE = ExperimentConfig(
    name="max_tokens_genre",
    description="max_output_tokens=2000 on genre disambiguation (3-flash)",
    max_output_tokens_by_model_field={"genre_disambiguation_model": 2000},
)

EXP4A_THINKING_512 = ExperimentConfig(
    name="thinking_512",
    description="thinking_budget=512 on lyrics model (2.5-flash)",
    thinking_budget_override=512,
)

EXP4B_THINKING_0 = ExperimentConfig(
    name="thinking_0",
    description="thinking_budget=0 on lyrics model (2.5-flash) — disable thinking",
    thinking_budget_override=0,
)

EXP5_THINKING_MINIMAL_3FLASH = ExperimentConfig(
    name="thinking_minimal_3flash",
    description='Set thinking_level="minimal" on all 3-flash calls',
    thinking_level_override="minimal",
)

EXP6_NATIVE_ASYNC = ExperimentConfig(
    name="native_async",
    description="Replace run_in_executor with native async Gemini client",
    use_native_async=True,
)

EXP7_PARALLEL_STYLE_NAME = ExperimentConfig(
    name="parallel_style_name",
    description="Start style name gen right after genre disambig (parallel with style gen)",
    parallel_style_name=True,
)

EXP8_LOW_TEMP_GENRE = ExperimentConfig(
    name="low_temp_genre",
    description="temperature=0.3 for genre disambiguation model",
    temperature_by_model_field={"genre_disambiguation_model": 0.3},
)


ALL_EXPERIMENTS = [
    BASELINE,
    EXP1_MAX_TOKENS_STYLE,
    EXP2_MAX_TOKENS_LYRICS,
    EXP3_MAX_TOKENS_GENRE,
    EXP4A_THINKING_512,
    EXP4B_THINKING_0,
    EXP5_THINKING_MINIMAL_3FLASH,
    EXP6_NATIVE_ASYNC,
    EXP7_PARALLEL_STYLE_NAME,
    EXP8_LOW_TEMP_GENRE,
]

EXPERIMENTS_BY_NAME = {e.name: e for e in ALL_EXPERIMENTS}


def apply_experiment(
    settings: Settings,
    config: ExperimentConfig,
) -> AgentPromptGraph:
    """
    Create an AgentPromptGraph with the experiment's overrides applied.

    Pre-populates the LLM cache keyed by *role name* (matching
    ``_get_or_create_llm``'s cache-by-role convention) so that experiment
    overrides take precedence over production ``DEFAULT_ROLE_CONFIGS``.
    """
    graph = AgentPromptGraph(
        settings=settings,
        parallel_style_name=config.parallel_style_name,
    )

    # Clear the LLM cache so we can re-create clients with overrides
    graph._llm_cache = {}

    # Map: role name -> model name
    role_to_model = {
        "style_model": settings.style_model,
        "lyrics_model": settings.lyrics_model,
        "genre_disambiguation_model": settings.genre_disambiguation_model,
        "profile_inference_model": settings.profile_inference_model,
        "title_generation_model": settings.title_generation_model,
    }

    # Collect per-role overrides
    role_overrides: Dict[str, dict] = {}

    if config.max_output_tokens_by_model_field:
        for role, tokens in config.max_output_tokens_by_model_field.items():
            if role in role_to_model:
                role_overrides.setdefault(role, {})["max_output_tokens"] = tokens

    if config.temperature_by_model_field:
        for role, temp in config.temperature_by_model_field.items():
            if role in role_to_model:
                role_overrides.setdefault(role, {})["temperature"] = temp

    # Apply thinking overrides to matching model families
    for role, model_name in role_to_model.items():
        if config.thinking_budget_override is not None and "2.5" in model_name:
            role_overrides.setdefault(role, {})["thinking_budget_override"] = config.thinking_budget_override
        if config.thinking_level_override and "2.5" not in model_name and model_name.startswith("gemini-"):
            role_overrides.setdefault(role, {})["thinking_level_override"] = config.thinking_level_override

    # Apply native_async to all roles
    if config.use_native_async:
        for role in role_to_model:
            role_overrides.setdefault(role, {})["use_native_async"] = True

    # Pre-populate the cache keyed by role name
    for role, overrides in role_overrides.items():
        model_name = role_to_model[role]
        client = GeminiChatClient(
            api_key=settings.gemini_api_key,
            model=model_name,
            temperature=overrides.get("temperature", settings.llm_temperature),
            timeout=settings.http_timeout,
            max_output_tokens=overrides.get("max_output_tokens"),
            thinking_budget_override=overrides.get("thinking_budget_override"),
            thinking_level_override=overrides.get("thinking_level_override"),
            use_native_async=overrides.get("use_native_async", False),
        )
        graph._llm_cache[role] = client

    return graph
