SELECT ags.*, ag.model, ag.provider, ag.miner_uid
FROM agent_scores AS ags
LEFT JOIN agents ag ON ags.agent_id = ag.agent_id
WHERE ags.set_id = (SELECT MAX(set_id) FROM evaluation_sets)
AND ags.agent_id NOT IN (SELECT agent_id FROM benchmark_agent_ids)
ORDER BY ags.created_at DESC;

