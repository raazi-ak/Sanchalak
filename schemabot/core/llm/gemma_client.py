#schemabot\core\llm\gemma_client.py

import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    GenerationConfig,
    BitsAndBytesConfig
)
from typing import Optional, Dict, Any, Generator, List
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import structlog
import time
from contextlib import asynccontextmanager
import gc
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

@dataclass
class GenerationMetrics:
    """Metrics for generation performance tracking"""
    tokens_generated: int
    generation_time: float
    tokens_per_second: float
    memory_used: float
    model_load_time: Optional[float] = None

class GemmaClient:
    """Production-grade Gemma client with optimizations and monitoring"""
    
    def __init__(
        self, 
        model_name: str = "google/gemma-2b-it",
        device: str = "auto",
        quantization: bool = True,
        max_concurrent_requests: int = 4
    ):
        self.model_name = model_name
        self.device = self._determine_device(device)
        self.quantization = quantization
        self.max_concurrent_requests = max_concurrent_requests
        
        # Model components
        self.model = None
        self.tokenizer = None
        self.generation_config = None
        
        # Performance tracking
        self.generation_metrics: List[GenerationMetrics] = []
        self.model_load_time = None
        
        # Thread safety
        self._model_lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent_requests)
        
        # Load model
        self._load_model()
    
    def _determine_device(self, device: str) -> str:
        """Determine optimal device for model execution"""
        if device == "auto":
            if torch.cuda.is_available():
                # Check VRAM availability
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"GPU detected with {gpu_memory:.1f}GB VRAM")
                return "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                logger.info("Using Apple Silicon MPS")
                return "mps"
            else:
                logger.info("Using CPU")
                return "cpu"
        return device
    
    def _load_model(self) -> None:
        """Load Gemma model with optimizations"""
        start_time = time.time()
        
        try:
            logger.info(f"Loading Gemma model: {self.model_name} on {self.device}")
            
            # Configure quantization for memory efficiency
            quantization_config = None
            if self.quantization and self.device == "cuda":
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
                logger.info("Using 4-bit quantization for memory efficiency")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                padding_side="left"  # Important for batch processing
            )
            
            # Add pad token if not present
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model with appropriate configuration
            model_kwargs = {
                "trust_remote_code": True,
                "quantization_config": quantization_config,
                "torch_dtype": torch.float16 if self.device != "cpu" else torch.float32,
                "low_cpu_mem_usage": True,
            }
            
            if self.device == "cuda" and not self.quantization:
                model_kwargs["device_map"] = "auto"
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                **model_kwargs
            )
            
            # Move to device if not using device_map
            if self.device != "cuda" or self.quantization:
                self.model = self.model.to(self.device)
            
            # Set to evaluation mode
            self.model.eval()
            
            # Configure generation parameters
            self.generation_config = GenerationConfig(
                max_new_tokens=512,
                temperature=0.7,
                top_p=0.9,
                top_k=50,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                repetition_penalty=1.1,
                length_penalty=1.0,
                early_stopping=True
            )
            
            self.model_load_time = time.time() - start_time
            
            # Log model info
            total_params = sum(p.numel() for p in self.model.parameters())
            trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
            
            logger.info(
                f"Model loaded successfully",
                load_time=f"{self.model_load_time:.2f}s",
                total_params=f"{total_params:,}",
                trainable_params=f"{trainable_params:,}",
                device=self.device,
                quantized=self.quantization
            )
            
        except Exception as e:
            logger.error(f"Failed to load Gemma model: {e}")
            raise RuntimeError(f"Model loading failed: {e}")
    
    async def generate_response_async(
        self, 
        prompt: str, 
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: float = 30.0
    ) -> Optional[str]:
        """Generate response asynchronously"""
        try:
            # Run generation in thread pool to avoid blocking
            future = self._executor.submit(
                self._generate_response_sync,
                prompt,
                max_tokens,
                temperature
            )
            
            # Wait for result with timeout
            response = await asyncio.wait_for(
                asyncio.wrap_future(future),
                timeout=timeout
            )
            
            return response
            
        except asyncio.TimeoutError:
            logger.error(f"Generation timeout after {timeout}s")
            return "I apologize, but I'm taking too long to respond. Please try again."
        except Exception as e:
            logger.error(f"Async generation error: {e}")
            return "I'm sorry, I encountered an error while processing your request."
    
    def _generate_response_sync(
        self, 
        prompt: str, 
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> Optional[str]:
        """Synchronous generation with metrics tracking"""
        start_time = time.time()
        
        try:
            with self._model_lock:
                # Tokenize input
                inputs = self.tokenizer(
                    prompt,
                    return_tensors="pt",
                    truncation=True,
                    max_length=2048,
                    padding=True
                ).to(self.device)
                
                input_length = inputs['input_ids'].shape[1]
                
                # Generate with memory tracking
                initial_memory = self._get_memory_usage()
                
                with torch.no_grad():
                    # Update generation config
                    generation_config = GenerationConfig(
                        **self.generation_config.to_dict(),
                        max_new_tokens=max_tokens,
                        temperature=temperature
                    )
                    
                    outputs = self.model.generate(
                        **inputs,
                        generation_config=generation_config,
                        use_cache=True
                    )
                
                # Decode response
                response_tokens = outputs[0][input_length:]
                response = self.tokenizer.decode(
                    response_tokens,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=True
                ).strip()
                
                # Track metrics
                generation_time = time.time() - start_time
                tokens_generated = len(response_tokens)
                final_memory = self._get_memory_usage()
                
                metrics = GenerationMetrics(
                    tokens_generated=tokens_generated,
                    generation_time=generation_time,
                    tokens_per_second=tokens_generated / generation_time if generation_time > 0 else 0,
                    memory_used=final_memory - initial_memory
                )
                
                self.generation_metrics.append(metrics)
                
                # Keep only last 100 metrics
                if len(self.generation_metrics) > 100:
                    self.generation_metrics = self.generation_metrics[-100:]
                
                logger.info(
                    f"Generated response",
                    tokens=tokens_generated,
                    time=f"{generation_time:.2f}s",
                    tokens_per_sec=f"{metrics.tokens_per_second:.1f}",
                    memory_delta=f"{metrics.memory_used:.1f}MB"
                )
                
                return response
                
        except torch.cuda.OutOfMemoryError:
            logger.error("CUDA out of memory during generation")
            self._cleanup_memory()
            return "I'm sorry, I'm currently experiencing high load. Please try again in a moment."
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return None
    
    async def generate_streaming_response(
        self, 
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> Generator[str, None, None]:
        """Generate streaming response for real-time interaction"""
        try:
            # This is a simplified streaming implementation
            # In production, you'd implement proper token-by-token streaming
            response = await self.generate_response_async(prompt, max_tokens, temperature)
            
            if response:
                # Simulate streaming by yielding words
                words = response.split()
                for i, word in enumerate(words):
                    if i == 0:
                        yield word
                    else:
                        yield f" {word}"
                    await asyncio.sleep(0.05)  # Small delay for streaming effect
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield "I apologize, but I'm having trouble generating a response."
    
    def validate_response(self, response: str, scheme_context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate generated response against scheme constraints"""
        issues = []
        
        # Check response length
        if len(response.strip()) < 10:
            issues.append("Response too short")
        
        if len(response) > 2000:
            issues.append("Response too long")
        
        # Check for scheme-specific keywords
        scheme_name = scheme_context.get('scheme_name', '').lower()
        if scheme_name and scheme_name not in response.lower():
            issues.append(f"Response doesn't mention {scheme_name}")
        
        # Check for prohibited content (basic implementation)
        prohibited_terms = ['investment advice', 'medical advice', 'legal advice']
        response_lower = response.lower()
        
        for term in prohibited_terms:
            if term in response_lower:
                issues.append(f"Contains prohibited content: {term}")
        
        return len(issues) == 0, issues
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.generation_metrics:
            return {"status": "no_data"}
        
        recent_metrics = self.generation_metrics[-10:]  # Last 10 generations
        
        avg_tokens_per_sec = sum(m.tokens_per_second for m in recent_metrics) / len(recent_metrics)
        avg_generation_time = sum(m.generation_time for m in recent_metrics) / len(recent_metrics)
        avg_memory_usage = sum(m.memory_used for m in recent_metrics) / len(recent_metrics)
        
        return {
            "model_name": self.model_name,
            "device": self.device,
            "quantized": self.quantization,
            "model_load_time": self.model_load_time,
            "recent_performance": {
                "avg_tokens_per_second": round(avg_tokens_per_sec, 2),
                "avg_generation_time": round(avg_generation_time, 2),
                "avg_memory_usage_mb": round(avg_memory_usage, 2),
                "total_generations": len(self.generation_metrics)
            },
            "memory_info": self._get_memory_info()
        }
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        if self.device == "cuda":
            return torch.cuda.memory_allocated() / 1024**2
        else:
            # For CPU, this is approximate
            import psutil
            return psutil.Process().memory_info().rss / 1024**2
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """Get detailed memory information"""
        if self.device == "cuda":
            return {
                "allocated_mb": torch.cuda.memory_allocated() / 1024**2,
                "cached_mb": torch.cuda.memory_reserved() / 1024**2,
                "max_allocated_mb": torch.cuda.max_memory_allocated() / 1024**2,
                "total_memory_mb": torch.cuda.get_device_properties(0).total_memory / 1024**2
            }
        else:
            import psutil
            memory = psutil.virtual_memory()
            return {
                "used_mb": memory.used / 1024**2,
                "available_mb": memory.available / 1024**2,
                "total_mb": memory.total / 1024**2,
                "percent": memory.percent
            }
    
    def _cleanup_memory(self):
        """Clean up GPU/CPU memory"""
        if self.device == "cuda":
            torch.cuda.empty_cache()
        gc.collect()
        logger.info("Memory cleanup completed")
    
    def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        try:
            # Quick generation test
            test_prompt = "Hello, this is a test."
            start_time = time.time()
            
            with self._model_lock:
                inputs = self.tokenizer(test_prompt, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    outputs = self.model.generate(**inputs, max_new_tokens=5)
                response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            test_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "model_loaded": self.model is not None,
                "tokenizer_loaded": self.tokenizer is not None,
                "device": self.device,
                "test_generation_time": round(test_time, 3),
                "memory_info": self._get_memory_info(),
                "total_generations": len(self.generation_metrics)
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "model_loaded": self.model is not None,
                "tokenizer_loaded": self.tokenizer is not None
            }
    
    def __del__(self):
        """Cleanup on destruction"""
        try:
            if hasattr(self, '_executor'):
                self._executor.shutdown(wait=False)
            self._cleanup_memory()
        except:
            pass

# Singleton pattern for global model instance
_gemma_client_instance = None

def get_gemma_client() -> GemmaClient:
    """Get global Gemma client instance"""
    global _gemma_client_instance
    if _gemma_client_instance is None:
        _gemma_client_instance = GemmaClient()
    return _gemma_client_instance

@asynccontextmanager
async def gemma_client_lifespan():
    """Context manager for Gemma client lifecycle"""
    client = get_gemma_client()
    try:
        yield client
    finally:
        client._cleanup_memory()
