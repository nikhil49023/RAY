import re


def should_promote_to_user_memory(text: str) -> bool:
    """Determine if text should be promoted to persistent user memory."""
    
    # Signals for persistent preferences
    persistent_signals = [
        "always", "never", "prefer", "avoid", "my style",
        "for me", "from now on", "remember", "don't",
        "minimalist", "concise", "detailed", "explain"
    ]
    
    # Signals for ephemeral facts (should NOT be promoted)
    ephemeral_signals = [
        "today", "right now", "currently", "this time",
        "at the moment", "just now", "temporary"
    ]
    
    text_lower = text.lower()
    
    # Reject if too short
    if len(text.strip()) < 15:
        return False
    
    # Reject if contains ephemeral signals
    if any(signal in text_lower for signal in ephemeral_signals):
        return False
    
    # Promote if contains persistent signals
    if any(signal in text_lower for signal in persistent_signals):
        return True
    
    return False


def classify_memory_type(text: str) -> str:
    """Classify memory as preference, constraint, correction, or project_state."""
    
    text_lower = text.lower()
    
    # Correction signals
    if any(signal in text_lower for signal in ["actually", "correction", "wrong", "mistake", "instead"]):
        return "correction"
    
    # Constraint signals
    if any(signal in text_lower for signal in ["budget", "limit", "cannot", "must not", "privacy", "vram"]):
        return "constraint"
    
    # Project state signals
    if any(signal in text_lower for signal in ["working on", "project", "repo", "codebase", "objective"]):
        return "project_state"
    
    # Default: preference
    return "preference"


def extract_stable_preferences(text: str) -> list:
    """Extract only stable, persistent preferences from text."""
    
    phrases = re.split(r"[.\n!?]+", text)
    stable = []
    
    for phrase in phrases:
        phrase = phrase.strip()
        if should_promote_to_user_memory(phrase):
            stable.append({
                "text": phrase,
                "type": classify_memory_type(phrase)
            })
    
    return stable
