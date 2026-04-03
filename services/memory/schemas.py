from typing import TypedDict, Literal


class Preference(TypedDict):
    """User preference for tone, formatting, UI, explanation level."""
    type: Literal["preference"]
    category: Literal["tone", "formatting", "ui", "explanation"]
    rule: str
    confidence: float


class Constraint(TypedDict):
    """User constraint for budget, privacy, hardware, latency."""
    type: Literal["constraint"]
    category: Literal["budget", "privacy", "hardware", "latency"]
    rule: str
    hard_limit: bool


class Correction(TypedDict):
    """User correction to prevent repeating mistakes."""
    type: Literal["correction"]
    mistake: str
    correction: str
    timestamp: str


class ProjectState(TypedDict):
    """Active project context."""
    type: Literal["project_state"]
    repo_path: str
    objective: str
    pending_artifacts: list
    last_updated: str
