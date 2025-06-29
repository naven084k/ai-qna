# Document Q&A Application

A Streamlit web application that allows users to upload documents (PDF, DOCX, TXT) and ask questions about their content using Google Gemini Flash 1.5 API and vector embeddings. The application persists uploaded files and conversation statistics for consistent storage between sessions and can be deployed to Google Cloud Run with support for headless mode and Google Cloud Storage integration.

## Features

- Upload and process PDF, DOCX, and TXT files (max 5 files, 1MB each)
- Extract text from documents and create vector embeddings
- Store document embeddings in ChromaDB with Google Cloud Storage integration
- Ask questions about uploaded documents using Google Gemini Flash 1.5
- Filter out queries not related to the uploaded documents
- View conversation history and document statistics
- View file content by clicking on files in the sidebar
- List files from Google Cloud Storage when available
- Persist uploaded files and statistics in JSON files for consistent storage between sessions
- Cloud deployment ready with Google Cloud Run and Google Cloud Storage
- Headless mode support for API-based or automated interactions

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

### Normal Mode (with UI)

Start the Streamlit app:
```
streamlit run app.py
```

The application will be available at http://localhost:8501

### Headless Mode (without UI)

Run the application in headless mode for API-based or automated interactions:
```
python app.py --headless
```

In headless mode, the application runs without the Streamlit UI and can be used as a backend service.

## Deploying to Google Cloud Run

### Prerequisites

1. [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and initialized
2. A Google Cloud project with billing enabled
3. Required APIs enabled:
   - Cloud Run API
   - Cloud Build API
   - Cloud Storage API

### Environment Variables

The following environment variables can be set for deployment:

- `GOOGLE_API_KEY`: Your Google Gemini API key
- `GCS_BUCKET_NAME`: Name of the Google Cloud Storage bucket to use
- `CLOUD_RUN_SERVICE`: Set to `true` when deploying to Cloud Run
- `HEADLESS`: Set to `true` to run in headless mode

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
3. Click on any document in the sidebar to view its content
4. Ask questions about your documents in the main panel
5. View answers and conversation history
6. Use the Clear Chat History or New Conversation buttons to manage your conversation

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
- **Vector Database**: ChromaDB with Google Cloud Storage integration
- **LLM**: Google Gemini Flash 1.5
- **Cloud Deployment**: Google Cloud Run with headless mode support
- **Cloud Storage**: Google Cloud Storage for documents and ChromaDB persistence

## Cloud Architecture

- **Compute**: Google Cloud Run (serverless container)
- **Persistence**: 
  - Google Cloud Storage for document files and application state
  - Google Cloud Storage for ChromaDB persistence
  - Ephemeral local storage in /tmp for temporary processing
- **Security**: Environment variables for API keys
- **Scaling**: Automatic scaling based on demand
- **Modes**: Support for both UI mode (Streamlit) and headless mode
