"""Cost and runaway-loop limits for Gemini orchestration."""

DEFAULT_AGENT_MAX_STEPS = 20
HARD_AGENT_MAX_STEPS = 20


def validated_agent_max_steps(value: int) -> int:
    if not 1 <= value <= HARD_AGENT_MAX_STEPS:
        raise ValueError(
            f"max_steps must be between 1 and {HARD_AGENT_MAX_STEPS}"
        )
    return value
