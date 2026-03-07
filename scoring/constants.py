"""Shared scoring constants."""

MINER_BURN: float = 0.5      # Fraction of score to burn for non-winning miners
MIN_THRESHOLD_GAP: float = 0.02   # Minimum score gap a later miner must beat
MAX_THRESHOLD_GAP: float = 0.08   # Maximum score gap cap
DEFAULT_Z_SCORE: float = 1.5      # Statistical confidence level
DEFAULT_EPISODES_PER_ENV: int = 50 # Default episode count if env not found
MIN_EPSILON: float = 0.005        # Minimum epsilon for ε-dominance
MAX_EPSILON: float = 0.05          # Maximum epsilon for ε-dominance