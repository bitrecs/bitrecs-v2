import time
import httpx
import logging
from utils.token import get_token_count
from llm.llm_provider import LLM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Chutes:
    def __init__(self, 
                 key, 
                 model="deepseek-ai/DeepSeek-V3", 
                 system_prompt="You are a helpful assistant.", 
                 temp=0.0):
        
        self.CHUTES_API_KEY = key
        if not self.CHUTES_API_KEY:
            raise ValueError("CHUTES_API_KEY is not set")
        self.model = model
        self.system_prompt = system_prompt
        self.temp = temp      
        self.provider = LLM.CHUTES.name
                
    def get_embeddings(self, text: str | list[str]) -> list[float] | list[list[float]]:
        """
        Get embeddings for a single text or batch of texts.
        
        Args:
            text: A single string or list of strings to embed
            
        Returns:
            - If input is str: returns list[float] (single embedding)
            - If input is list[str]: returns list[list[float]] (multiple embeddings)
        """
        url = "https://chutes-qwen-qwen3-embedding-8b.chutes.ai/v1/embeddings"       
        if "qwen3-embedding-8b" not in self.model:
            raise ValueError("Only qwen/qwen3-embedding-8b model is supported for embeddings")
        
        headers = {
            "Authorization": f"Bearer {self.CHUTES_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://bitrecs.ai",
            "X-Title": "bitrecs"
        }
        data = {
            "model": None,
            "input": text  # Accepts both str and list[str]
        }
        timeout = (5, 30) #connect, read timeout
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    url,
                    headers=headers,
                    json=data
                )
                response.raise_for_status()
                result = response.json()
                
                # If single text input, return single embedding
                if isinstance(text, str):
                    return result['data'][0]['embedding']
                
                # If list input, return all embeddings
                return [item['embedding'] for item in result['data']]
                
        except httpx.ConnectTimeout:
            raise TimeoutError(f"Chutes connect timed out after {timeout[0]}s")
        except httpx.ReadTimeout:
            raise TimeoutError(f"Chutes read timed out after {timeout[1]}s")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Chutes request failed: {e}") from e 
        except httpx.RequestError as e:
            raise RuntimeError(f"Chutes request failed: {e}") from e
        

    def call_chutes(self, prompt) -> str:
        if not prompt or len(prompt) < 10:
            raise ValueError()
        url = "https://llm.chutes.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.CHUTES_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "max_tokens": 2048,
            "temperature": self.temp
        }      
        timeout = (5, 60) #connect, read timeout     
        try:
            with httpx.Client(timeout=timeout) as client:
                if logger.level <= logging.DEBUG:
                    start_time = time.perf_counter()
                    content = data["messages"][0]["content"]
                    token_count = get_token_count(content)
                    logger.debug(f"CHUTES request token count: {token_count} tokens")
                response = client.post(
                    url,
                    headers=headers,
                    json=data
                )
                response.raise_for_status()
                data = response.json()
                if logger.level <= logging.DEBUG:
                    end_time = time.perf_counter()
                    duration = end_time - start_time
                    logger.debug(f"CHUTES request completed in {duration:.2f}s")
                #print(data)
                return data['choices'][0]['message']['content']
        except httpx.ConnectTimeout:
            raise TimeoutError(f"CHUTES connect timed out after {timeout[0]}s")
        except httpx.ReadTimeout:
            raise TimeoutError(f"CHUTES read timed out after {timeout[1]}s")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"CHUTES request failed: {e}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"CHUTES request failed: {e}") from e

