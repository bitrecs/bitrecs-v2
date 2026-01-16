import numpy as np
import httpx
from typing import List
from models.agent import Agent

class AgentComparer:
    """
    A class to calculate cosine distance between two Agent instances.  
    
    Only specific fields are considered for comparison: provider, model, 
    system_prompt_template, user_prompt_template, sampling_params, and fewshot_examples.   
    
    Uses a local embedding server at the provided URL.
    Default URL: 'http://localhost:8080' (defined in docker-compose setup).
    """
    
    def __init__(self, embedding_server_url: str = 'http://localhost:8080'):
        """
        Initialize the comparator with the URL of the local embedding server.
        
        Args:
            embedding_server_url: URL of the local embedding server (e.g., 'http://localhost:8080').
        """
        self.embedding_server_url = embedding_server_url
        self.embedding_dim = 768  #'sentence-transformers/all-mpnet-base-v2';
    
    async def _get_embeddings(self, texts: List[str]) -> List[np.ndarray]:       
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.embedding_server_url}/embed",
                json={"inputs": texts}
            )
            if response.status_code != 200:
                raise RuntimeError(f"Embedding server error: {response.status_code} - {response.text}")
            embeddings = response.json()
            return [np.array(emb) for emb in embeddings]
        
    async def _check_embedding_server(self) -> bool:
        """
        Check if the embedding server is reachable and responding.
        
        Returns:
            True if the server responds with status 200, False otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.embedding_server_url}/health")
                return response.status_code == 200
        except httpx.RequestError:
            return False
    
    async def _vectorize_agent(self, agent: Agent) -> np.ndarray:
        """
        Vectorize the relevant fields of an Agent into a single numerical vector.
        
        - Text fields (provider, model, system_prompt_template, user_prompt_template): 
          Get embeddings from the server.
        - sampling_params: Flatten the dict values (temperature, top_p, max_tokens, etc.) 
          into a list of floats.
        - fewshot_examples: Average embeddings of the 'content' fields from each example.
        
        Returns a concatenated numpy array.
        """
        vectors = []
        # if not await self._check_embedding_server():
        #     return vectors
        
        # Text fields: provider, model, system_prompt_template, user_prompt_template
        text_fields = [
            agent.provider,
            agent.model,
            agent.system_prompt_template,
            agent.user_prompt_template,
            agent.sampling_params.temperature if agent.sampling_params.temperature is not None else "",
        ]
        embeddings = await self._get_embeddings(text_fields)
        vectors.extend(embeddings)
        
        # sampling_params: Extract numerical values
        # sampling_vec = [
        #     agent.sampling_params.temperature,
        #     agent.sampling_params.top_p or 0.0,  # Default to 0 if None
        #     agent.sampling_params.max_tokens or 0,  # Default to 0 if None
        #     len(agent.sampling_params.stop_sequences) if agent.sampling_params.stop_sequences else 0  # Count of stop sequences
        # ]
        # vectors.append(np.array(sampling_vec))
        
        # fewshot_examples: Average embeddings of content
        # if agent.fewshot_examples:
        #     contents = [ex.content for ex in agent.fewshot_examples]
        #     example_embeddings = await self._get_embeddings(contents)
        #     avg_embedding = np.mean(example_embeddings, axis=0)
        # else:
        #     # If no examples, use a zero vector
        #     avg_embedding = np.zeros(self.embedding_dim)
        # vectors.append(avg_embedding)
        
        # Concatenate all vectors into one
        return np.concatenate(vectors)
    
    async def cosine_distance(self, agent1: Agent, agent2: Agent) -> float:
        """
        Calculate the cosine distance between two Agent instances.
        
        Cosine distance = 1 - cosine_similarity.
        Cosine similarity is computed using numpy: (a · b) / (|a| |b|).
        Returns a float between 0 (identical) and 2 (opposite).
        """
        vec1 = await self._vectorize_agent(agent1)
        vec2 = await self._vectorize_agent(agent2)
        
        # Compute cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            # Handle zero vectors (e.g., identical empty agents)
            similarity = 1.0 if np.allclose(vec1, vec2) else 0.0
        else:
            similarity = dot_product / (norm1 * norm2)
        
        # Cosine distance
        distance = 1 - similarity
        return float(distance)
    
    def get_embedding_dimension(self) -> int:
        """
        Returns the embedding dimension (hardcoded for the model).
        """
        return self.embedding_dim