import os
import hashlib
import numpy as np
from typing import List, Dict
from models.agent import Agent

class AgentComparer:
    """
    A class to calculate cosine distance between two Agent instances.
    """
    
    def __init__(self, provider):
        if not provider:
            raise ValueError("Provider instance is required")
        
        self.provider = provider
        self.embedding_dim = 4096
        self._embedding_cache: Dict[str, np.ndarray] = {}
    
    def _get_agent_key(self, agent: Agent) -> str:
        """Generate a unique cache key for an agent based on compared fields."""
        key = f"{agent.miner_hotkey}.{agent.agent_id}.{agent.provider}.{agent.model}.{agent.system_prompt_template}.{agent.user_prompt_template}.{agent.sampling_params.temperature}"
        sha = hashlib.sha256()
        sha.update(key.encode('utf-8'))
        return sha.hexdigest()
    
    async def _get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Get embeddings for a list of texts using batch API.
        Each text gets its own embedding vector, preserving semantic separation.
        """
        # Convert all to strings
        text_strs = [str(text) for text in texts]
        
        # Use batch embedding API (returns list[list[float]])
        embeddings = self.provider.get_embeddings(text_strs)
        
        # Convert each embedding to numpy array
        return [np.array(emb) for emb in embeddings]
    
    async def _vectorize_agent(self, agent: Agent) -> np.ndarray:
        """
        Vectorize the relevant fields of an Agent into a single numerical vector.
        
        Each field gets its own embedding, then all are concatenated.
        This preserves the semantic meaning of each field independently.
        """
        cache_key = self._get_agent_key(agent)
        
        # Return cached embedding if available
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        # Text fields: each will get its own embedding
        text_fields = [
            agent.provider,
            agent.model,
            agent.system_prompt_template,
            agent.user_prompt_template,
            str(agent.sampling_params.temperature) if agent.sampling_params.temperature is not None else "0.0",
        ]
        
        # Get individual embeddings for each field (batch API call)
        embeddings = await self._get_embeddings(text_fields)
        
        # Concatenate all embeddings into one long vector
        # Result: [provider_emb (4096) + model_emb (4096) + sys_prompt_emb (4096) + ...]
        vector = np.concatenate(embeddings)
        
        # Cache the result
        self._embedding_cache[cache_key] = vector
        
        return vector
    
    async def cosine_distance(self, agent1: Agent, agent2: Agent) -> float:
        """
        Calculate the cosine distance between two Agent instances.
        
        Cosine distance = 1 - cosine_similarity.
        Returns 0.0 for identical agents.
        """
        # Short-circuit for identical agents
        if agent1.agent_id == agent2.agent_id:
            return 0.0
        
        vec1 = await self._vectorize_agent(agent1)
        vec2 = await self._vectorize_agent(agent2)
        
        # Compute cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            similarity = 1.0 if np.allclose(vec1, vec2) else 0.0
        else:
            similarity = dot_product / (norm1 * norm2)
        
        distance = 1 - similarity
        return float(distance)
    
    def get_embedding_dimension(self) -> int:
        """Returns the total embedding dimension (5 fields × 4096)."""
        return self.embedding_dim * 5  # 5 text fields
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._embedding_cache.clear()