import os
import uuid
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict, Any
import logging

class VectorStore:
    def __init__(self, persist_directory: str = "chroma_db"):
        """
        Initialize the vector store with a CPU-friendly embedding model
        
        Args:
            persist_directory: Directory to persist the ChromaDB
        """
        # Create directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        try:
            # Initialize embedding function directly through ChromaDB
            sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2",
                device="cpu"
            )
            
            # Initialize ChromaDB with explicit settings
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                    is_persistent=True
                )
            )
            
            # Create or get collection
            self.collection = self.client.get_or_create_collection(
                name="documents", 
                embedding_function=sentence_transformer_ef
            )
            logging.info(f"Successfully initialized ChromaDB at {persist_directory}")
        except Exception as e:
            logging.error(f"Error initializing ChromaDB: {str(e)}")
            # Fallback to in-memory client if persistent client fails
            logging.info("Falling back to in-memory ChromaDB client")
            self.client = chromadb.Client()
            self.collection = self.client.get_or_create_collection(
                name="documents",
                embedding_function=sentence_transformer_ef
            )
    
    def add_documents(self, documents: List[Dict[str, Any]]) -> str:
        """
        Add documents to the vector store
        
        Args:
            documents: List of document chunks with metadata
            
        Returns:
            str: Document ID
        """
        # Generate a unique ID for this document
        doc_id = str(uuid.uuid4())
        
        # Add document ID to metadata
        for doc in documents:
            doc["metadata"]["doc_id"] = doc_id
        
        # Add to vector store
        ids = [f"{doc_id}_{i}" for i in range(len(documents))]
        texts = [doc["page_content"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]
        
        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
        
        return doc_id
    
    def similarity_search(self, query: str, k: int = 3):
        """
        Search for similar documents
        
        Args:
            query: Query string
            k: Number of results to return
            
        Returns:
            List of similar documents
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=k
        )
        
        documents = []
        if results["documents"] and len(results["documents"][0]) > 0:
            for i, doc in enumerate(results["documents"][0]):
                documents.append({
                    "page_content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
                })
                
        return documents
    
    def delete_document(self, doc_id: str):
        """
        Delete a document from the vector store
        
        Args:
            doc_id: Document ID to delete
        """
        self.collection.delete(
            where={"doc_id": doc_id}
        )
    
    def get_all_documents(self):
        """
        Get all documents in the vector store
        
        Returns:
            List of all documents
        """
        results = self.collection.get()
        
        documents = []
        if results["documents"]:
            for i, doc in enumerate(results["documents"]):
                documents.append({
                    "page_content": doc,
                    "metadata": results["metadatas"][i] if results["metadatas"] else {}
                })
                
        return documents
