# Document Q&A Application

A Streamlit web application that allows users to upload documents (PDF, DOCX, TXT) and ask questions about their content using Google Gemini Flash 1.5 API and vector embeddings. The application persists uploaded files and conversation statistics for consistent storage between sessions and can be deployed to Google Cloud Run.

## Features

- Upload and process PDF, DOCX, and TXT files (max 5 files, 1MB each)
- Extract text from documents and create vector embeddings
- Store document embeddings in ChromaDB
- Ask questions about uploaded documents using Google Gemini Flash 1.5
- Filter out queries not related to the uploaded documents
- View conversation history and document statistics
- Persist uploaded files and statistics in JSON files for consistent storage between sessions
- Cloud deployment ready with Google Cloud Run and Google Cloud Storage

## Local Setup

1. Clone the repository:
```
git clone <repository-url>
cd ai-qna
```

2. Create a virtual environment and install dependencies:
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file with your Google API key:
```
cp .env.example .env
```
Then edit the `.env` file and add your Google Gemini API key.

## Running the Application Locally

Start the Streamlit app:
```
streamlit run app.py
```

The application will be available at http://localhost:8501

## Deploying to Google Cloud Run

### Prerequisites

1. [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and initialized
2. A Google Cloud project with billing enabled
3. Required APIs enabled:
   - Cloud Run API
   - Cloud Build API
   - Cloud Storage API

### Deployment Steps

1. Make sure you're authenticated with Google Cloud:
```
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

2. Make the deployment script executable:
```
chmod +x deploy.sh
```

3. Run the deployment script:
```
./deploy.sh
```

The script will:
- Create a Google Cloud Storage bucket for persistent storage
- Build and push the Docker container to Google Container Registry
- Deploy the application to Google Cloud Run
- Set up the necessary environment variables

4. Once deployed, the script will output the URL where your application is accessible.

## Usage

1. Upload documents using the file uploader in the sidebar (PDF, DOCX, TXT)
2. View uploaded documents and statistics in the sidebar
3. Ask questions about your documents in the main panel
4. View answers and conversation history

## Project Structure

- `app.py`: Main Streamlit application
- `document_processor.py`: Functions to extract text from different document types
- `vector_store.py`: Vector embedding and similarity search functionality
- `persistence.py`: File and statistics persistence management
- `utils.py`: Utility functions
- `requirements.txt`: Project dependencies
- `.env.example`: Template for environment variables
- `Dockerfile`: Container definition for Google Cloud Run deployment
- `deploy.sh`: Deployment script for Google Cloud Run
- `data/`: Directory containing persistent data (local development)
  - `uploads/`: Directory containing uploaded files
  - `stats.json`: File containing conversation statistics
  - `files_info.json`: File containing information about uploaded files

## Technical Details

- **Frontend/Backend**: Streamlit
- **Document Processing**: PyPDF2, python-docx
- **Embeddings**: Sentence-Transformers (all-MiniLM-L6-v2)
- **Vector Database**: ChromaDB
- **LLM**: Google Gemini Flash 1.5
- **Cloud Deployment**: Google Cloud Run
- **Cloud Storage**: Google Cloud Storage

## Cloud Architecture

- **Compute**: Google Cloud Run (serverless container)
- **Persistence**: 
  - Google Cloud Storage for document files and application state
  - Ephemeral local storage in /tmp for ChromaDB during container runtime
- **Security**: Environment variables for API keys
- **Scaling**: Automatic scaling based on demand
