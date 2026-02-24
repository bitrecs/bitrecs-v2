import os
import httpx
import typer
from pathlib import Path
from scoring.engine import get_current_eval_set_id
from scoring.pareto import compute_pareto_frontier
from scoring.persist import ScorePersister
from scoring.threshold import compute_miner_thresholds
from scoring.types import MinerFirstBlocks, MinerScores
from scoring.wta import compute_subset_scores_with_priority, scores_to_weights
root_path = Path(__file__).parent.parent.absolute()

DATA_FILE_PATH = os.path.join(root_path, "data", "weights")
DATA_FILE = "scores.db"

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
    miner_blocks = miners_first_blocks()
    print(f"Miner first blocks: {miner_blocks}")
    assert isinstance(miner_blocks, dict)
    for hotkey, block in miner_blocks.items():
        assert isinstance(hotkey, str)
        assert isinstance(block, int)
        assert block >= 0


def test_pareto_frontier_from_db():    
    current_set_id = get_current_eval_set_id()
    print(f"Current evaluation_set_id: {current_set_id}")
    
    persister = ScorePersister(base_path=DATA_FILE_PATH, filename=DATA_FILE)
    print(f"{persister.file_path}")    
    if not os.path.exists(persister.file_path):
        raise FileNotFoundError(f"Database file not found at {persister.file_path}")
    
    data = persister.load_scores(evaluation_set_id=current_set_id)   

    miner_scores = df_to_miner_scores(data)
    samples = df_to_samples(data)    
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


def test_scoring_wta():    
    current_set_id = get_current_eval_set_id()
    print(f"Current evaluation_set_id: {current_set_id}")    
    persister = ScorePersister(base_path=DATA_FILE_PATH, filename=DATA_FILE)
    data = persister.load_scores(evaluation_set_id=current_set_id)
    miner_scores = df_to_miner_scores(data)
    samples = df_to_samples(data)
    envs = list(samples.keys())
    #pareto_result = compute_pareto_frontier(miner_scores=miner_scores, env_ids=envs, n_samples_per_env=samples)
    
    miner_blocks = df_to_miner_blocks(data)
   # Compute thresholds and scores with priority
    miner_thresholds = compute_miner_thresholds(miner_scores, episodes_per_env=samples)
    subset_scores = compute_subset_scores_with_priority(
        miner_scores, miner_thresholds, miner_blocks, envs
    )
    weights = scores_to_weights(subset_scores)
    typer.echo("\nSubset scores:")
    for uid, score in sorted(subset_scores.items(), key=lambda x: x[1], reverse=True):
        typer.echo(f"  UID {uid}: {score:.1f} points")

    typer.echo("\nFinal weights:")
    for uid, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        typer.echo(f"  UID {uid}: {weight:.4f}")

    top_weight_uid = max(weights, key=weights.get)
    typer.echo(f"\nTop weight UID: {top_weight_uid} with weight {weights[top_weight_uid]:.4f}")



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


def df_to_samples(df) -> dict[str, int]:
    samples = {}
    for _, row in df.iterrows():
        env_id = row['task_name']
        sample_size = row['sample_size']
        if env_id not in samples:
            samples[env_id] = 0
        samples[env_id] = sample_size
    return samples


def miners_first_blocks() -> MinerFirstBlocks:
    SERVICE_URL = os.environ.get("RIDGES_PLATFORM_URL", "")
    #SERVICE_URL = "http://localhost:8000"
    client = httpx.Client(base_url=SERVICE_URL)
    response = client.get("/retrieval/miner-blocks")
    assert response.status_code == 200
    data = response.json()
    return data    
    

def df_to_miner_blocks(df) -> MinerFirstBlocks:
    miner_blocks = miners_first_blocks()
    # miner blocks uses hotkey as key, but we want to map to uid, so we need to convert
    hotkey_to_uid = {}
    for _, row in df.iterrows():
        hotkey = row['hotkey']
        uid = row['uid']
        hotkey_to_uid[hotkey] = uid
    miner_first_blocks: MinerFirstBlocks = {}
    for hotkey, block in miner_blocks.items():
        uid = hotkey_to_uid.get(hotkey)
        if uid is not None:
            miner_first_blocks[uid] = block
    return miner_first_blocks