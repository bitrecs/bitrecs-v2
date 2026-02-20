import os
from pathlib import Path

import httpx
from scoring.engine import get_current_eval_set_id
from scoring.pareto import compute_pareto_frontier
from scoring.persist import ScorePersister
from pathlib import Path

from scoring.types import MinerFirstBlocks, MinerScores
root_path = Path(__file__).parent.parent.absolute()


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


def test_miner_first_blocks():
    miner_blocks = miners_first_blocks(None)  # The function makes its own API call, so we can pass None
    print(f"Miner first blocks: {miner_blocks}")
    assert isinstance(miner_blocks, dict)
    for hotkey, block in miner_blocks.items():
        assert isinstance(hotkey, str)
        assert isinstance(block, int)
        assert block >= 0


def test_pareto_frontier_from_db():    
    current_set_id = get_current_eval_set_id()
    print(f"Current evaluation_set_id: {current_set_id}")
    
    persister = ScorePersister(base_path=os.path.join(root_path, "data", "weights"), filename="scores2.db")
    print(f"{persister.file_path}")    
    
    data = persister.load_scores(evaluation_set_id=current_set_id)   

    miner_scores = df_to_miner_scores(data)
    samples = samples_per_environment(data)    
    envs = list(samples.keys())    
    
    pareto_result = compute_pareto_frontier(miner_scores=miner_scores, env_ids=envs, n_samples_per_env=samples)
    
    # Display properties
    print("Pareto Frontier Properties:")
    print(f"  Frontier UIDs: {pareto_result.frontier_uids}")
    print(f"  UID Mapping: {pareto_result.uid_mapping}")
    print(f"  Dominance Matrix Shape: {pareto_result.dominance_matrix.shape}")
    print(f"  Score Matrix Shape: {pareto_result.score_matrix.shape}")
    print(f"  Dominance Matrix:\n{pareto_result.dominance_matrix}")
    print(f"  Score Matrix:\n{pareto_result.score_matrix}")
    
    # Optional: Convert to DataFrame for easier viewing
    import pandas as pd
    score_df = pd.DataFrame(pareto_result.score_matrix, columns=envs, index=pareto_result.uid_mapping)
    print(f"  Score DataFrame:\n{score_df}")
    
    assert len(pareto_result.frontier_uids) > 0


def df_to_miner_scores(df) -> MinerScores:
    miner_scores: MinerScores = {}
    for _, row in df.iterrows():
        uid = row['uid']
        env_id = row['task_name']
        score = row['score']
        
        if uid not in miner_scores:
            miner_scores[uid] = {}
        miner_scores[uid][env_id] = score
    return miner_scores


def samples_per_environment(df) -> dict[str, int]:
    samples = {}
    for _, row in df.iterrows():
        env_id = row['task_name']
        sample_size = row['sample_size']
        if env_id not in samples:
            samples[env_id] = 0
        samples[env_id] = sample_size
    return samples


def miners_first_blocks(df) -> MinerFirstBlocks:
    #SERVICE_URL = os.environ.get("RIDGES_PLATFORM_URL", "")
    SERVICE_URL = "http://localhost:8000"
    client = httpx.Client(base_url=SERVICE_URL)
    response = client.get("/retrieval/miner-blocks")
    assert response.status_code == 200
    data = response.json()
    return data    
    