# Document Q&A Application Requirements

## Core Functionality

1. Build a web application using Python, Streamlit, Google Gemini Flash 1.5 API, and vector embedding technique

2. File Upload Capabilities:
   - Support for PDF, DOCX, and TXT files
   - Single file upload at a time
   - Maximum 5 files total
   - Maximum file size of 1 MB per file

3. Vector Embedding:
   - Use small CPU-friendly models for vector embedding
   - Use ChromaDB for vector storage
   - Integrate ChromaDB with Google Cloud Storage for persistence

4. Document Processing:
   - Extract text from documents
   - Create embeddings for efficient retrieval

5. User Interface:
   - Left panel showing list of uploaded files
   - Display document count and conversation count
   - Enable viewing file content when clicking on files in the sidebar
   - Persist information in JSON files for consistent storage
   - Files should be listed from Google Cloud Storage when available

6. Q&A Functionality:
   - Use Google Gemini Flash 1.5 model for answering questions
   - Allow questions on existing documents
   - Use embeddings to identify relevant document chunks to send to Google Gemini
   - Filter out random queries not related to documents

7. Deployment:
   - Single server for UI and backend for easy deployment
   - Support for headless mode in Docker for API-based or automated interactions

8. Storage:
   - Use Google Cloud Storage for storing uploaded files
   - Use Google Cloud Storage for ChromaDB persistence

9. Additional Files:
   - Add necessary .gitignore file
   - Add comprehensive README.md file