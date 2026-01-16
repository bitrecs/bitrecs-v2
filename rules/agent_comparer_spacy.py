import numpy as np
import spacy
from typing import List
from models.agent import Agent

class LightweightAgentComparer:
    """
    A lightweight, CPU-only version of AgentComparer that calculates cosine distance between two Agent instances.
    
    This version uses spaCy for sentence embeddings (averaged word vectors), without any network calls or heavy dependencies like torch/transformers.
    Only specific fields are considered for comparison: provider, model, 
    system_prompt_template, user_prompt_template, sampling_params, and fewshot_examples.
    
    Uses the 'en_core_web_sm' spaCy model by default (lightweight, ~12MB).
    """
    
    def __init__(self, model_name: str = 'en_core_web_sm'):
        """
        Initialize the comparator with a lightweight spaCy model.
        
        Args:
            model_name: Name of the spaCy model to use (must include vectors).
        """
        self.nlp = spacy.load(model_name)
        # Get embedding dimension from the model's vector size
        self.embedding_dim = self.nlp.vocab.vectors_length
    
    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Get embeddings for a list of texts using spaCy (averaged word vectors).
        
        Args:
            texts: List of strings to embed.
        
        Returns:
            Numpy array of shape (len(texts), embedding_dim).
        """
        embeddings = []
        for text in texts:
            doc = self.nlp(text)
            # Use the document vector (average of word vectors)
            embeddings.append(doc.vector)
        return np.array(embeddings)
    
    def _vectorize_agent(self, agent: Agent) -> np.ndarray:
        """
        Vectorize the relevant fields of an Agent into a single numerical vector.
        
        - Text fields (provider, model, system_prompt_template, user_prompt_template): 
          Use embeddings from spaCy.
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
        Returns the embedding dimension of the spaCy model.
        """
        return self.embedding_dim