SELECT ags.*, ag.model, ag.provider, ag.miner_uid
FROM agent_scores AS ags
LEFT JOIN agents ag ON ags.agent_id = ag.agent_id
WHERE ags.set_id = (SELECT MAX(set_id) FROM evaluation_sets)
AND ags.agent_id NOT IN (SELECT agent_id FROM benchmark_agent_ids)
ORDER BY ags.created_at DESC;


SELECT a.name, a.miner_uid, ass.final_score, a.*,  ass.created_at as score_created_at, ass.set_id, ass.approved, ass.validator_count
FROM agents a
JOIN agent_scores ass ON a.agent_id = ass.agent_id
WHERE ass.set_id = (SELECT MAX(set_id) FROM evaluation_sets)
AND a.agent_id NOT IN (SELECT agent_id FROM benchmark_agent_ids)
ORDER BY ROUND(ass.final_score::numeric, 6) DESC, a.created_at ASC


SELECT 
    schemaname,
    relname                  AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    pg_size_pretty(pg_table_size(relid))          AS table_size,
    pg_size_pretty(pg_indexes_size(relid))        AS indexes_size,
    n_live_tup                                    AS row_count_live_est,
    n_dead_tup                                    AS dead_tuples
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;


-- INSERT INTO evaluation_sets (set_id, set_group, problem_name)
-- VALUES 
--   (7, 'screener_1', 'bitrecs_basic_daily'),
--   (7, 'screener_1', 'bitrecs_artifact_pricing'),
--   (7, 'screener_2', 'bitrecs_safe_daily'),
--   (7, 'screener_2', 'bitrecs_haystack_daily'),
--   (7, 'screener_2', 'bitrecs_qos_daily'),
--   (7, 'validator', 'bitrecs_prompt_daily'),
--   (7, 'validator', 'bitrecs_reason_daily'),
--   (7, 'validator', 'bitrecs_sku_daily'),
--   (7, 'validator', 'bitrecs_predict_daily'),  
--   (7, 'validator', 'amazon_health_and_personal_care_100'),  
--   (7, 'validator', 'ndcg_at10_curated_all_beauty_100'),
--   (7, 'validator', 'ndcg_at10_curated_electronics_100');


SELECT miner_hotkey, MIN(block) as first_block 
FROM hotkey_gist 
WHERE block != 0
GROUP BY miner_hotkey
ORDER BY first_block


SELECT * FROM AGENTS WHERE created_at >= (
SELECT MIN(created_at) FROM evaluation_sets
WHERE set_id = (SELECT MAX(set_id) FROM evaluation_sets))
ORDER BY created_at DESC



SELECT 
    e.agent_id,  
    a.name,
    r.evaluation_run_id,
    r.evaluation_id,
    r.problem_name,
    r.status,
    r.test_results,
    r.created_at,
    i.provider,
    i.model,
    i.temperature,
    i.status_code,
    i.num_input_tokens,
    i.num_output_tokens,
    i.cost_usd  
FROM evaluation_runs r
LEFT JOIN inferences i ON r.evaluation_run_id = i.evaluation_run_id
LEFT JOIN evaluations e ON r.evaluation_id = e.evaluation_id
INNER JOIN agents a ON e.agent_id = a.agent_id
WHERE a.agent_id = ''