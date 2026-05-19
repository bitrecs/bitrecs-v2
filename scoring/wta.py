"""Winners-take-all scoring over environment subsets with first-commit advantage."""
import numpy as np
from itertools import combinations
from scoring.constants import MIN_THRESHOLD_GAP
from scoring.types import (
    EnvironmentId,
    MinerFirstBlocks,
    MinerScores,
    MinerThresholds,
    MinerUID,
    SubsetWeightScheme
)


def scores_to_weights(
    scores: dict[MinerUID, float],
    temperature: float = 1.0,
    min_weight: float = 0.0,
) -> dict[MinerUID, float]:
    """
    Convert scores to normalized weights via softmax.

    Args:
        scores: Dict mapping uid -> score
        temperature: Softmax temperature (lower = more winner-take-all)
        min_weight: Minimum weight for any miner (0 = pure softmax)

    Returns:
        Dict mapping uid -> normalized weight (sums to 1)

    Raises:
        ValueError: If temperature is not positive
    """
    if temperature <= 0:
        raise ValueError("temperature must be > 0")

    if not scores:
        return {}

    uids = list(scores.keys())
    values = np.array([scores[uid] for uid in uids])

    if np.all(values == 0):
        # All zeros - uniform distribution
        n = len(uids)
        return {uid: 1.0 / n for uid in uids}

    # Softmax with temperature
    # Shift values for numerical stability
    values_shifted = values - np.max(values)
    exp_values = np.exp(values_shifted / temperature)
    weights = exp_values / exp_values.sum()

    # Apply minimum weight if specified
    if min_weight > 0:
        n = len(uids)
        min_total = min_weight * n
        if min_total < 1.0:
            # Scale down current weights and add minimum
            scale = 1.0 - min_total
            weights = weights * scale + min_weight
        # else: min_weight too high, just normalize

    return {uid: float(w) for uid, w in zip(uids, weights, strict=True)}


def compute_subset_scores_with_priority(
    miner_scores: MinerScores,
    miner_thresholds: MinerThresholds,
    miner_first_blocks: MinerFirstBlocks,
    env_ids: list[EnvironmentId],
    subset_weight_scheme: SubsetWeightScheme = SubsetWeightScheme.LINEAR,
) -> dict[MinerUID, float]:
    """
    Compute winners-take-all scores with first-commit advantage.

    For each non-empty subset S of environments:
    1. Find the miner that dominates on S (with time priority)
    2. Award them a score K_|S| based on subset size

    Args:
        miner_scores: Dict mapping uid -> env_id -> score
        miner_thresholds: Dict mapping uid -> env_id -> threshold
        miner_first_blocks: Dict mapping uid -> first committed block
        env_ids: List of environment IDs
        subset_weight_scheme: How to weight subsets

    Returns:
        Dict mapping uid -> total score
    """
    uids = list(miner_scores.keys())
    final_scores = {uid: 0.0 for uid in uids}

    if not uids or not env_ids:
        return final_scores  

    # Iterate over all non-empty subsets
    for subset_size in range(1, len(env_ids) + 1):
        # Compute weight for this subset size
        match subset_weight_scheme:
            case SubsetWeightScheme.LINEAR:
                subset_weight = float(subset_size)
            case SubsetWeightScheme.EXPONENTIAL:
                subset_weight = float(2 ** (subset_size - 1))
            case SubsetWeightScheme.EQUAL:
                subset_weight = 1.0
            case _:
                raise ValueError(f"Unknown subset weight scheme: {subset_weight_scheme}")

        # Check each subset of this size
        for subset in combinations(env_ids, subset_size):
            winner = find_subset_winner_gm(
                miner_scores,
                miner_thresholds,
                miner_first_blocks,
                subset,
            )
            if winner is not None:
                final_scores[winner] += subset_weight

    return final_scores


def find_subset_winner_gm(
    miner_scores: MinerScores,
    miner_thresholds: MinerThresholds,
    miner_first_blocks: MinerFirstBlocks,
    subset: tuple[EnvironmentId, ...],
) -> MinerUID | None:
    # Must have > 0 on EVERY task in subset — a zero disqualifies from the whole subset
    eligible = [
        u for u in miner_scores
        if all(miner_scores[u].get(e, 0.0) > 0.0 for e in subset)
    ]
    if not eligible:
        return None
    if len(eligible) == 1:
        return eligible[0]

    def gm(uid):
        scores = [miner_scores[uid].get(e, 0.0) for e in subset]
        return np.prod(scores) ** (1.0 / len(scores))

    ranked = sorted(
        eligible,
        key=lambda u: (-gm(u), miner_first_blocks.get(u, float("inf")))
    )
    leader, runner_up = ranked[0], ranked[1]

    # Clear winner: GM advantage exceeds the minimum gap
    if gm(leader) > gm(runner_up) + MIN_THRESHOLD_GAP:
        return leader

    # True tie: block seniority as last resort only
    return min(
        [leader, runner_up],
        key=lambda u: (miner_first_blocks.get(u, float("inf")), u)
    )