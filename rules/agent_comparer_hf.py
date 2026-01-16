import numpy as np
from typing import List
from sentence_transformers import SentenceTransformer
from models.agent import Agent

class LocalAgentComparer:
    """
    A fully local version of AgentComparer that calculates cosine distance between two Agent instances.
    
    This version uses sentence_transformers directly for embeddings, without any network calls.
    Only specific fields are considered for comparison: provider, model, 
    system_prompt_template, user_prompt_template, sampling_params, and fewshot_examples.
    
    Uses the 'sentence-transformers/all-mpnet-base-v2' model by default.
    """
    
    def __init__(self, model_name: str = 'sentence-transformers/all-mpnet-base-v2'):
        """
        Initialize the comparator with a local sentence transformer model.
        
        Args:
            model_name: Name of the sentence transformer model to use.
        """
        self.embedding_model = SentenceTransformer(model_name)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
    
    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Get embeddings for a list of texts using the local model.
        
        Args:
            texts: List of strings to embed.
        
        Returns:
            Numpy array of shape (len(texts), embedding_dim).
        """
        return self.embedding_model.encode(texts, convert_to_numpy=True)
    
    def _vectorize_agent(self, agent: Agent) -> np.ndarray:
        """
        Vectorize the relevant fields of an Agent into a single numerical vector.
        
        - Text fields (provider, model, system_prompt_template, user_prompt_template): 
          Use embeddings from the local model.
        - sampling_params: Flatten the dict values (temperature, top_p, max_tokens, etc.) 
          into a list of floats.
        - fewshot_examples: Average embeddings of the 'content' fields from each example.
        
        Returns a concatenated numpy array.
        """
        vectors = []
        
        # Text fields: provider, model, system_prompt_template, user_prompt_template
        text_fields = [
            agent.provider,
            agent.model,
            agent.system_prompt_template,
            agent.user_prompt_template
        ]
        embeddings = self._get_embeddings(text_fields)
        for embedding in embeddings:
            vectors.append(embedding)
        
        # sampling_params: Extract numerical values
        sampling_vec = [
            agent.sampling_params.temperature,
            agent.sampling_params.top_p or 0.0,  # Default to 0 if None
            agent.sampling_params.max_tokens or 0,  # Default to 0 if None
            len(agent.sampling_params.stop_sequences) if agent.sampling_params.stop_sequences else 0  # Count of stop sequences
        ]
        vectors.append(np.array(sampling_vec))
        
        # fewshot_examples: Average embeddings of content
        if agent.fewshot_examples:
            contents = [ex.content for ex in agent.fewshot_examples]
            example_embeddings = self._get_embeddings(contents)
            avg_embedding = np.mean(example_embeddings, axis=0)
        else:
            # If no examples, use a zero vector
            avg_embedding = np.zeros(self.embedding_dim)
        vectors.append(avg_embedding)
        
        # Concatenate all vectors into one
        return np.concatenate(vectors)
    
    def cosine_distance(self, agent1: Agent, agent2: Agent) -> float:
        """
        Calculate the cosine distance between two Agent instances.
        
        Cosine distance = 1 - cosine_similarity.
        Cosine similarity is computed using numpy: (a · b) / (|a| |b|).
        Returns a float between 0 (identical) and 2 (opposite).
        """
        vec1 = self._vectorize_agent(agent1)
        vec2 = self._vectorize_agent(agent2)
        
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
        Returns the embedding dimension of the model.
        """
        return self.embedding_dim