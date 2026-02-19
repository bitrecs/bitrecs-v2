from scoring.engine import get_current_eval_set_id
from scoring.pareto import compute_pareto_frontier



def test_latest_eval_set_id():
    set_id = get_current_eval_set_id()
    assert isinstance(set_id, int)
    assert set_id > 0


def test_pareto_frontier():
    miner_scores = {
        1: {"env1": 0.8, "env2": 0.6},
        2: {"env1": 0.7, "env2": 0.7},
        3: {"env1": 0.9, "env2": 0.5},
        4: {"env1": 0.6, "env2": 0.8},
    }
    env_ids = ["env1", "env2"]
    n_samples_per_env = {"env1": 1, "env2": 1}
    
    pareto_result = compute_pareto_frontier(miner_scores, env_ids=env_ids, n_samples_per_env=n_samples_per_env)

    assert set(pareto_result.frontier_uids) == {1, 2, 3, 4}
    assert pareto_result.dominance_matrix.shape == (4, 4)
    assert pareto_result.score_matrix.shape == (4, 2)
    assert pareto_result.uid_mapping == [1, 2, 3, 4]