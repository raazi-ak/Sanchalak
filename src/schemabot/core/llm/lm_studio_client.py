"""
LM Studio Client for Schemabot

Provides a client interface to LM Studio API that integrates with schemabot's LLM architecture.
"""

import requests
import asyncio
import time
import structlog
from typing import Optional, Dict, Any, Generator, List, Tuple
from dataclasses import dataclass
from contextlib import asynccontextmanager

logger = structlog.get_logger(__name__)

@dataclass
class GenerationMetrics:
    """Metrics for generation performance tracking"""
    tokens_generated: int
    generation_time: float
    tokens_per_second: float
    memory_used: float
    model_load_time: Optional[float] = None

class LMStudioClient:
    """LM Studio client for schemabot integration"""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:1234",
        model_name: str = "google/gemma-3-4b",
        max_concurrent_requests: int = 4,
        timeout: float = 30.0
    ):
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        self.max_concurrent_requests = max_concurrent_requests
        self.timeout = timeout
        
        # Performance tracking
        self.generation_metrics: List[GenerationMetrics] = []
        self.request_count = 0
        
        # Test connection on init
        self._test_connection()
    
    def _test_connection(self) -> None:
        """Test connection to LM Studio"""
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            if response.status_code == 200:
                models = response.json()
                available_models = [model['id'] for model in models.get('data', [])]
                
                if self.model_name in available_models:
                    logger.info(f"LM Studio connected successfully. Using model: {self.model_name}")
                else:
                    logger.warning(f"Model {self.model_name} not found. Available: {available_models}")
                    if available_models:
                        self.model_name = available_models[0]
                        logger.info(f"Switched to available model: {self.model_name}")
            else:
                logger.error(f"LM Studio connection failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to connect to LM Studio: {e}")
    
    async def generate_response_async(
        self, 
        prompt: str, 
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: float = None
    ) -> Optional[str]:
        """Generate response asynchronously using LM Studio"""
        if timeout is None:
            timeout = self.timeout
            
        try:
            start_time = time.time()
            
            # Prepare the request payload
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
            
            # Make the request
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Calculate metrics
                generation_time = time.time() - start_time
                usage = result.get('usage', {})
                completion_tokens = usage.get('completion_tokens', 0)
                
                # Store metrics
                metrics = GenerationMetrics(
                    tokens_generated=completion_tokens,
                    generation_time=generation_time,
                    tokens_per_second=completion_tokens / generation_time if generation_time > 0 else 0,
                    memory_used=0.0  # LM Studio manages memory
                )
                self.generation_metrics.append(metrics)
                self.request_count += 1
                
                logger.info(
                    f"LM Studio generation successful",
                    model=self.model_name,
                    tokens=completion_tokens,
                    time=f"{generation_time:.2f}s",
                    tps=f"{metrics.tokens_per_second:.1f}"
                )
                
                return content
            else:
                logger.error(f"LM Studio API error: {response.status_code} - {response.text}")
                return "I'm sorry, I encountered an error while processing your request."
                
        except requests.exceptions.Timeout:
            logger.error(f"LM Studio request timeout after {timeout}s")
            return "I apologize, but I'm taking too long to respond. Please try again."
        except Exception as e:
            logger.error(f"LM Studio generation error: {e}")
            return "I'm sorry, I encountered an error while processing your request."
    
    async def generate_streaming_response(
        self, 
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> Generator[str, None, None]:
        """Generate streaming response using LM Studio"""
        try:
            start_time = time.time()
            
            # Prepare the request payload for streaming
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True
            }
            
            # Make streaming request
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            if data == '[DONE]':
                                break
                            try:
                                chunk = eval(data)  # Parse JSON-like string
                                if 'choices' in chunk and chunk['choices']:
                                    delta = chunk['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        yield content
                            except:
                                continue
                
                # Calculate final metrics
                generation_time = time.time() - start_time
                logger.info(f"LM Studio streaming completed in {generation_time:.2f}s")
            else:
                logger.error(f"LM Studio streaming error: {response.status_code}")
                yield "I'm sorry, I encountered an error while processing your request."
                
        except Exception as e:
            logger.error(f"LM Studio streaming error: {e}")
            yield "I'm sorry, I encountered an error while processing your request."
    
    def validate_response(self, response: str, scheme_context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate response against scheme context"""
        # Basic validation - can be enhanced based on specific scheme requirements
        errors = []
        
        if not response or response.strip() == "":
            errors.append("Empty response")
        
        if len(response) < 10:
            errors.append("Response too short")
        
        # Add more validation logic as needed
        return len(errors) == 0, errors
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.generation_metrics:
            return {"message": "No generation metrics available"}
        
        total_requests = len(self.generation_metrics)
        avg_generation_time = sum(m.generation_time for m in self.generation_metrics) / total_requests
        avg_tokens_per_second = sum(m.tokens_per_second for m in self.generation_metrics) / total_requests
        total_tokens = sum(m.tokens_generated for m in self.generation_metrics)
        
        return {
            "model": self.model_name,
            "total_requests": total_requests,
            "avg_generation_time": f"{avg_generation_time:.2f}s",
            "avg_tokens_per_second": f"{avg_tokens_per_second:.1f}",
            "total_tokens_generated": total_tokens,
            "base_url": self.base_url
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check LM Studio health"""
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            if response.status_code == 200:
                models = response.json()
                available_models = [model['id'] for model in models.get('data', [])]
                
                return {
                    "status": "healthy",
                    "model": self.model_name,
                    "model_available": self.model_name in available_models,
                    "available_models": available_models,
                    "base_url": self.base_url
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": f"API returned {response.status_code}",
                    "base_url": self.base_url
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "base_url": self.base_url
            }

def get_lm_studio_client() -> LMStudioClient:
    """Get LM Studio client instance"""
    return LMStudioClient()

@asynccontextmanager
async def lm_studio_client_lifespan():
    """Context manager for LM Studio client lifecycle"""
    client = get_lm_studio_client()
    try:
        yield client
    finally:
        # Cleanup if needed
        pass