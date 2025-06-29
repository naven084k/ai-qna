import os
import json
import shutil
import tempfile
from typing import List, Dict, Any
from google.cloud import storage
import logging

class PersistenceManager:
    def __init__(self, data_dir: str = "data", use_cloud_storage: bool = False, bucket_name: str = None):
        """
        Initialize the persistence manager
        
        Args:
            data_dir: Directory to store data locally
            use_cloud_storage: Whether to use Google Cloud Storage
            bucket_name: Name of the GCS bucket to use
        """
        self.data_dir = data_dir
        self.uploads_dir = os.path.join(data_dir, "uploads")
        self.stats_file = os.path.join(data_dir, "stats.json")
        self.files_info_file = os.path.join(data_dir, "files_info.json")
        
        self.use_cloud_storage = use_cloud_storage
        self.bucket_name = bucket_name
        
        # Initialize cloud storage client if needed
        self.storage_client = None
        self.bucket = None
        if self.use_cloud_storage:
            try:
                self.storage_client = storage.Client()
                self.bucket = self.storage_client.bucket(bucket_name)
                if not self.bucket.exists():
                    self.bucket = self.storage_client.create_bucket(bucket_name)
                logging.info(f"Connected to GCS bucket: {bucket_name}")
            except Exception as e:
                logging.error(f"Error connecting to GCS: {str(e)}")
                self.use_cloud_storage = False
        
        # Create local directories if they don't exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
    
    def save_uploaded_file(self, file_content: bytes, file_name: str) -> str:
        """
        Save an uploaded file to disk or cloud storage
        
        Args:
            file_content: Content of the file
            file_name: Name of the file
            
        Returns:
            str: Path to the saved file (local path or cloud URI)
        """
        if self.use_cloud_storage and self.bucket:
            try:
                # Save to GCS
                blob_path = f"uploads/{file_name}"
                blob = self.bucket.blob(blob_path)
                blob.upload_from_string(file_content)
                
                # Also save locally for processing
                local_path = os.path.join(self.uploads_dir, file_name)
                with open(local_path, 'wb') as f:
                    f.write(file_content)
                
                return local_path
            except Exception as e:
                logging.error(f"Error saving to GCS: {str(e)}")
                # Fall back to local storage
        
        # Save locally
        file_path = os.path.join(self.uploads_dir, file_name)
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return file_path
    
    def save_files_info(self, files_info: List[Dict[str, Any]]):
        """
        Save information about uploaded files
        
        Args:
            files_info: List of file information dictionaries
        """
        # Prepare data for persistence (remove temporary paths)
        persistent_files_info = []
        for file_info in files_info:
            persistent_file_info = {
                "name": file_info["name"],
                "doc_id": file_info["doc_id"],
                "path": os.path.join(self.uploads_dir, file_info["name"])
            }
            persistent_files_info.append(persistent_file_info)
        
        # Convert to JSON string
        json_data = json.dumps(persistent_files_info)
        
        if self.use_cloud_storage and self.bucket:
            try:
                # Save to GCS
                blob = self.bucket.blob("files_info.json")
                blob.upload_from_string(json_data, content_type="application/json")
            except Exception as e:
                logging.error(f"Error saving files info to GCS: {str(e)}")
        
        # Always save locally as well
        with open(self.files_info_file, 'w') as f:
            f.write(json_data)
    
    def load_files_info(self) -> List[Dict[str, Any]]:
        """
        Load information about uploaded files
        
        Returns:
            List[Dict[str, Any]]: List of file information dictionaries
        """
        if self.use_cloud_storage and self.bucket:
            try:
                # Try to load from GCS
                blob = self.bucket.blob("files_info.json")
                if blob.exists():
                    json_data = blob.download_as_text()
                    return json.loads(json_data)
            except Exception as e:
                logging.error(f"Error loading files info from GCS: {str(e)}")
                # Fall back to local file
        
        # Try to load from local file
        if os.path.exists(self.files_info_file):
            try:
                with open(self.files_info_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading files info from local file: {str(e)}")
        
        return []
    
    def save_stats(self, stats: Dict[str, Any]):
        """
        Save statistics
        
        Args:
            stats: Statistics dictionary
        """
        # Convert to JSON string
        json_data = json.dumps(stats)
        
        if self.use_cloud_storage and self.bucket:
            try:
                # Save to GCS
                blob = self.bucket.blob("stats.json")
                blob.upload_from_string(json_data, content_type="application/json")
            except Exception as e:
                logging.error(f"Error saving stats to GCS: {str(e)}")
        
        # Always save locally as well
        with open(self.stats_file, 'w') as f:
            f.write(json_data)
    
    def load_stats(self) -> Dict[str, Any]:
        """
        Load statistics
        
        Returns:
            Dict[str, Any]: Statistics dictionary
        """
        if self.use_cloud_storage and self.bucket:
            try:
                # Try to load from GCS
                blob = self.bucket.blob("stats.json")
                if blob.exists():
                    json_data = blob.download_as_text()
                    return json.loads(json_data)
            except Exception as e:
                logging.error(f"Error loading stats from GCS: {str(e)}")
                # Fall back to local file
        
        # Try to load from local file
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading stats from local file: {str(e)}")
        
        return {"conversation_count": 0}
    
    def remove_file(self, file_name: str):
        """
        Remove a file from disk or cloud storage
        
        Args:
            file_name: Name of the file to remove
        """
        if self.use_cloud_storage and self.bucket:
            try:
                # Remove from GCS
                blob_path = f"uploads/{file_name}"
                blob = self.bucket.blob(blob_path)
                if blob.exists():
                    blob.delete()
            except Exception as e:
                logging.error(f"Error removing file from GCS: {str(e)}")
        
        # Always try to remove from local storage as well
        file_path = os.path.join(self.uploads_dir, file_name)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    def file_exists(self, file_name: str) -> bool:
        """
        Check if a file exists in local storage or cloud storage
        
        Args:
            file_name: Name of the file to check
            
        Returns:
            bool: True if the file exists, False otherwise
        """
        if self.use_cloud_storage and self.bucket:
            try:
                # Check in GCS
                blob_path = f"uploads/{file_name}"
                blob = self.bucket.blob(blob_path)
                if blob.exists():
                    return True
            except Exception as e:
                logging.error(f"Error checking file existence in GCS: {str(e)}")
        
        # Check in local storage
        file_path = os.path.join(self.uploads_dir, file_name)
        return os.path.exists(file_path)
