"""
Vector Database Agent for Farmer AI Pipeline

Handles document storage, retrieval, and similarity search using ChromaDB
"""

import os
import uuid
import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
import json
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np

from config import get_settings
from models import DocumentChunk, VectorSearchResult, VectorSearchRequest, GovernmentScheme
from utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

class VectorDBAgent:
    """Agent for managing vector database operations with ChromaDB"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.embedding_model = None
        self.embedding_dimension = settings.embedding_dimension
        self.collection_name = "farmer_schemes"
        self.is_initialized = False
        
    async def initialize(self):
        """Initialize ChromaDB client and embedding model"""
        try:
            logger.info("Initializing Vector Database Agent...")
            
            # Initialize ChromaDB client
            await self._initialize_chromadb()
            
            # Initialize embedding model
            await self._initialize_embedding_model()
            
            # Create or get collection
            await self._setup_collection()
            
            self.is_initialized = True
            logger.info("Vector Database Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Vector DB Agent: {str(e)}")
            raise
    
    async def _initialize_chromadb(self):
        """Initialize ChromaDB client"""
        try:
            # Create data directory if it doesn't exist
            db_path = os.path.join(settings.data_path, "chroma_db")
            os.makedirs(db_path, exist_ok=True)
            
            # Initialize ChromaDB client with persistent storage
            self.client = chromadb.PersistentClient(
                path=db_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            logger.info(f"ChromaDB client initialized with path: {db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {str(e)}")
            raise
    
    async def _initialize_embedding_model(self):
        """Initialize sentence transformer model"""
        try:
            model_name = settings.sentence_transformer_model
            
            # Load model in executor to avoid blocking
            loop = asyncio.get_event_loop()
            self.embedding_model = await loop.run_in_executor(
                None,
                SentenceTransformer,
                model_name
            )
            
            # Verify embedding dimension
            test_embedding = self.embedding_model.encode(["test"])
            actual_dim = len(test_embedding[0])
            
            if actual_dim != self.embedding_dimension:
                logger.warning(f"Embedding dimension mismatch. Expected: {self.embedding_dimension}, Got: {actual_dim}")
                self.embedding_dimension = actual_dim
            
            logger.info(f"Embedding model loaded: {model_name} (dim: {self.embedding_dimension})")
            
        except Exception as e:
            logger.error(f"Failed to load embedding model: {str(e)}")
            raise
    
    async def _setup_collection(self):
        """Create or get ChromaDB collection"""
        try:
            # Check if collection exists
            try:
                self.collection = self.client.get_collection(
                    name=self.collection_name
                )
                logger.info(f"Found existing collection: {self.collection_name}")
                
            except Exception:
                # Create new collection
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={
                        "description": "Government schemes and agricultural information",
                        "embedding_model": settings.sentence_transformer_model,
                        "dimension": self.embedding_dimension
                    }
                )
                logger.info(f"Created new collection: {self.collection_name}")
                
                # Add some default schemes if collection is empty
                await self._add_default_schemes()
                
        except Exception as e:
            logger.error(f"Failed to setup collection: {str(e)}")
            raise
    
    async def _add_default_schemes(self):
        """Add default government schemes to the collection"""
        try:
            default_schemes = [
                {
                    "id": "pm_kisan",
                    "content": "PM-KISAN Pradhan Mantri Kisan Samman Nidhi provides income support of Rs 6000 per year to eligible farmer families having combined land holding of 2 hectares",
                    "metadata": {
                        "scheme_name": "PM-KISAN",
                        "category": "income_support",
                        "benefit_amount": 6000,
                        "eligibility": "land_holding_2_hectares"
                    }
                },
                {
                    "id": "pmfby",
                    "content": "Pradhan Mantri Fasal Bima Yojana PMFBY provides crop insurance coverage against crop loss due to natural calamities",
                    "metadata": {
                        "scheme_name": "PMFBY",
                        "category": "crop_insurance",
                        "eligibility": "all_farmers"
                    }
                },
                {
                    "id": "kcc",
                    "content": "Kisan Credit Card provides credit support for crop production and allied activities to farmers",
                    "metadata": {
                        "scheme_name": "Kisan Credit Card",
                        "category": "credit",
                        "eligibility": "land_owning_farmers"
                    }
                }
            ]
            
            for scheme in default_schemes:
                await self.add_document(
                    content=scheme["content"],
                    metadata=scheme["metadata"],
                    doc_id=scheme["id"]
                )
            
            logger.info(f"Added {len(default_schemes)} default schemes")
            
        except Exception as e:
            logger.error(f"Failed to add default schemes: {str(e)}")
    
    async def add_document(
        self,
        content: str,
        metadata: Dict[str, Any] = None,
        doc_id: str = None
    ) -> str:
        """
        Add a document to the vector database
        
        Args:
            content: Document content
            metadata: Additional metadata
            doc_id: Optional document ID
            
        Returns:
            Document ID
        """
        try:
            if not self.is_initialized:
                raise ValueError("Vector DB Agent not initialized")
            
            # Generate ID if not provided
            if not doc_id:
                doc_id = str(uuid.uuid4())
            
            # Generate embedding
            embedding = await self._generate_embedding(content)
            
            # Prepare metadata
            if metadata is None:
                metadata = {}
            
            metadata.update({
                "added_at": time.time(),
                "content_length": len(content)
            })
            
            # Add to ChromaDB
            self.collection.add(
                documents=[content],
                embeddings=[embedding.tolist()],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            logger.info(f"Added document: {doc_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to add document: {str(e)}")
            raise
    
    async def search_schemes(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """
        Search for relevant schemes using vector similarity
        
        Args:
            query: Search query
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score
            filters: Optional metadata filters
            
        Returns:
            List of search results
        """
        try:
            if not self.is_initialized:
                raise ValueError("Vector DB Agent not initialized")
            
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)
            
            # Prepare where clause for filtering
            where_clause = filters if filters else None
            
            # Search ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # Process results
            search_results = []
            
            if results["documents"] and results["documents"][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0] if results["metadatas"] else [{}] * len(results["documents"][0]),
                    results["distances"][0] if results["distances"] else [0] * len(results["documents"][0])
                )):
                    # Convert distance to similarity score (ChromaDB uses L2 distance)
                    similarity_score = max(0, 1 - (distance / 2))
                    
                    if similarity_score >= similarity_threshold:
                        search_results.append(VectorSearchResult(
                            chunk_id=results["ids"][0][i] if results["ids"] else f"result_{i}",
                            content=doc,
                            similarity_score=similarity_score,
                            metadata=metadata if metadata else {},
                            source_url=metadata.get("source_url") if metadata else None
                        ))
            
            logger.info(f"Found {len(search_results)} relevant schemes for query: {query[:50]}")
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return []
    
    async def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text"""
        try:
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                self.embedding_model.encode,
                [text]
            )
            return embedding[0]
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            raise
    
    async def add_scheme(self, scheme: GovernmentScheme) -> str:
        """
        Add a government scheme to the vector database
        
        Args:
            scheme: GovernmentScheme object
            
        Returns:
            Document ID
        """
        try:
            # Create comprehensive content for embedding
            content_parts = [
                scheme.name,
                scheme.description
            ]
            
            if scheme.name_hindi:
                content_parts.append(scheme.name_hindi)
            if scheme.description_hindi:
                content_parts.append(scheme.description_hindi)
            
            # Add target beneficiaries and keywords
            if scheme.target_beneficiaries:
                content_parts.extend(scheme.target_beneficiaries)
            
            content = " ".join(content_parts)
            
            # Prepare metadata
            metadata = {
                "scheme_id": scheme.scheme_id,
                "scheme_name": scheme.name,
                "benefit_type": scheme.benefit_type,
                "implementing_agency": scheme.implementing_agency,
                "is_active": scheme.is_active
            }
            
            if scheme.benefit_amount:
                metadata["benefit_amount"] = scheme.benefit_amount
            
            if scheme.target_beneficiaries:
                metadata["target_beneficiaries"] = scheme.target_beneficiaries
            
            # Add to database
            doc_id = await self.add_document(
                content=content,
                metadata=metadata,
                doc_id=scheme.scheme_id
            )
            
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to add scheme: {str(e)}")
            raise
    
    async def update_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Update an existing document"""
        try:
            # Delete existing document
            await self.delete_document(doc_id)
            
            # Add updated document
            await self.add_document(content, metadata, doc_id)
            
            logger.info(f"Updated document: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update document {doc_id}: {str(e)}")
            return False
    
    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the database"""
        try:
            self.collection.delete(ids=[doc_id])
            logger.info(f"Deleted document: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {str(e)}")
            return False
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            count = self.collection.count()
            
            return {
                "total_documents": count,
                "collection_name": self.collection_name,
                "embedding_dimension": self.embedding_dimension,
                "embedding_model": settings.sentence_transformer_model
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            return {}
    
    async def rebuild_index(self) -> bool:
        """Rebuild the vector index (useful after bulk updates)"""
        try:
            # ChromaDB handles indexing automatically
            # This is a placeholder for future optimizations
            logger.info("Vector index rebuild completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rebuild index: {str(e)}")
            return False
    
    async def is_ready(self) -> bool:
        """Check if the agent is ready"""
        return self.is_initialized and self.client is not None and self.collection is not None
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.client:
                # ChromaDB client doesn't need explicit cleanup
                pass
            
            self.client = None
            self.collection = None
            self.embedding_model = None
            self.is_initialized = False
            
            logger.info("Vector DB Agent cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during Vector DB cleanup: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Get health status of the vector database"""
        try:
            stats = await self.get_collection_stats()
            
            return {
                "status": "healthy" if self.is_initialized else "not_ready",
                "client_connected": self.client is not None,
                "collection_ready": self.collection is not None,
                "embedding_model_loaded": self.embedding_model is not None,
                "collection_stats": stats
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }