import os
import uuid
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict, Any, Optional
import logging
from google.cloud import storage
import tempfile
import shutil
import time

class VectorStore:
    def __init__(self, persist_directory: str = "chroma_db", use_cloud_storage: bool = False, bucket_name: Optional[str] = None):
        """
        Initialize the vector store with a CPU-friendly embedding model
        
        Args:
            persist_directory: Directory to persist the ChromaDB
            use_cloud_storage: Whether to use Google Cloud Storage for ChromaDB persistence
            bucket_name: Name of the GCS bucket to use
        """
        self.persist_directory = persist_directory
        self.use_cloud_storage = use_cloud_storage
        self.bucket_name = bucket_name
        self.storage_client = None
        self.bucket = None
        
        # Create directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize cloud storage if needed
        if self.use_cloud_storage and self.bucket_name:
            try:
                self.storage_client = storage.Client()
                self.bucket = self.storage_client.bucket(bucket_name)
                if not self.bucket.exists():
                    self.bucket = self.storage_client.create_bucket(bucket_name)
                logging.info(f"Connected to GCS bucket for ChromaDB: {bucket_name}")
                
                # Download existing ChromaDB data from GCS if available
                self._download_from_gcs()
            except Exception as e:
                logging.error(f"Error connecting to GCS for ChromaDB: {str(e)}")
                self.use_cloud_storage = False
        
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
    
    def _download_from_gcs(self):
        """
        Download ChromaDB data from Google Cloud Storage
        """
        if not self.use_cloud_storage or not self.bucket:
            return
        
        try:
            # Check if ChromaDB data exists in GCS
            blobs = list(self.bucket.list_blobs(prefix="chroma_db/"))
            if not blobs:
                logging.info("No existing ChromaDB data found in GCS")
                return
            
            logging.info(f"Downloading {len(blobs)} ChromaDB files from GCS")
            
            # Clear local directory first
            if os.path.exists(self.persist_directory):
                shutil.rmtree(self.persist_directory)
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Download all files
            for blob in blobs:
                # Skip directory markers
                if blob.name.endswith('/'):
                    continue
                    
                # Get relative path
                rel_path = blob.name.replace('chroma_db/', '', 1)
                local_path = os.path.join(self.persist_directory, rel_path)
                
                # Create directories if needed
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # Download file
                blob.download_to_filename(local_path)
                
            logging.info("Successfully downloaded ChromaDB data from GCS")
        except Exception as e:
            logging.error(f"Error downloading ChromaDB data from GCS: {str(e)}")
    
    def _upload_to_gcs(self):
        """
        Upload ChromaDB data to Google Cloud Storage
        """
        if not self.use_cloud_storage or not self.bucket:
            return
        
        try:
            logging.info("Uploading ChromaDB data to GCS")
            
            # Walk through the directory and upload all files
            for root, dirs, files in os.walk(self.persist_directory):
                for file in files:
                    local_path = os.path.join(root, file)
                    rel_path = os.path.relpath(local_path, start=os.path.dirname(self.persist_directory))
                    blob_path = f"{rel_path}"
                    
                    blob = self.bucket.blob(blob_path)
                    blob.upload_from_filename(local_path)
            
            logging.info("Successfully uploaded ChromaDB data to GCS")
        except Exception as e:
            logging.error(f"Error uploading ChromaDB data to GCS: {str(e)}")

    
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
        
        # Sync to GCS if enabled
        if self.use_cloud_storage:
            self._upload_to_gcs()
        
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
        
        # Sync to GCS if enabled
        if self.use_cloud_storage:
            self._upload_to_gcs()
    
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
