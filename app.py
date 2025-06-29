import streamlit as st
import os
import tempfile
import logging
import time
import math
import argparse
import sys
from dotenv import load_dotenv
import google.generativeai as genai
from document_processor import process_document, get_document_text
from vector_store import VectorStore
from persistence import PersistenceManager
from utils import is_query_about_documents, count_tokens

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Configure Google Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("Google API key not found. Please set it in the .env file.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# Check if running in Google Cloud Run
IS_CLOUD_RUN = os.environ.get('CLOUD_RUN_SERVICE', False)
GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'document-qa-storage')

# Set up persistence directories
if IS_CLOUD_RUN:
    # In Cloud Run, use /tmp for temporary storage
    DATA_DIR = "/tmp/data"
    CHROMA_DIR = "/tmp/chroma_db"
    USE_CLOUD_STORAGE = True
    logging.info(f"Running in Cloud Run, using GCS bucket: {GCS_BUCKET_NAME}")
else:
    # Local development
    DATA_DIR = "data"
    CHROMA_DIR = "chroma_db"
    USE_CLOUD_STORAGE = False
    logging.info("Running locally, using local file storage")

# Initialize vector store
vector_store = VectorStore(
    persist_directory=CHROMA_DIR,
    use_cloud_storage=USE_CLOUD_STORAGE,
    bucket_name=GCS_BUCKET_NAME
)

# Initialize persistence manager
persistence_manager = PersistenceManager(
    data_dir=DATA_DIR,
    use_cloud_storage=USE_CLOUD_STORAGE,
    bucket_name=GCS_BUCKET_NAME
)

# Function to list files from Google Cloud Storage
def list_files_from_gcs(persistence_manager):
    """
    List files from Google Cloud Storage
    
    Args:
        persistence_manager: PersistenceManager instance
        
    Returns:
        List of file names
    """
    if not persistence_manager.use_cloud_storage or not persistence_manager.bucket:
        return []
    
    try:
        # List blobs with the specified prefix
        blobs = list(persistence_manager.bucket.list_blobs(prefix="uploads/"))
        
        # Extract file names
        file_names = []
        for blob in blobs:
            # Skip directory markers
            if blob.name.endswith('/'):
                continue
                
            # Extract file name from path
            file_name = blob.name.replace('uploads/', '', 1)
            if file_name:  # Ensure it's not empty
                file_names.append(file_name)
                
        return file_names
    except Exception as e:
        logging.error(f"Error listing files from GCS: {str(e)}")
        return []

# Initialize session state
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = persistence_manager.load_files_info()
    
    # If using cloud storage, check for files in GCS that might not be in local records
    if USE_CLOUD_STORAGE:
        gcs_files = list_files_from_gcs(persistence_manager)
        if gcs_files:
            # Add files from GCS that aren't in the local records
            existing_files = [f["name"] for f in st.session_state.uploaded_files]
            for file_name in gcs_files:
                if file_name not in existing_files:
                    # Add to session state with placeholder doc_id
                    st.session_state.uploaded_files.append({
                        "name": file_name,
                        "doc_id": "gcs_file",  # Placeholder
                        "path": f"uploads/{file_name}"
                    })
            
            # Save updated file info
            persistence_manager.save_files_info(st.session_state.uploaded_files)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_page" not in st.session_state:
    st.session_state.current_page = 1
if "docs_per_page" not in st.session_state:
    st.session_state.docs_per_page = 5
if "conversation_context" not in st.session_state:
    st.session_state.conversation_context = []

# Load statistics
stats = persistence_manager.load_stats()
if "conversation_count" not in st.session_state:
    st.session_state.conversation_count = stats.get("conversation_count", 0)

# Page configuration with hidden menu and footer
st.set_page_config(
    page_title="Document Q&A",
    layout="wide",
    menu_items={}
)

# Hide Streamlit style elements
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display:none;}
.viewerBadge_container__1QSob {display: none;}
.viewerBadge_link__1S137 {display: none;}
.viewerBadge_text__1JaDK {display: none;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Custom CSS for chat-like interface
st.markdown("""
<style>
.chat-message {
    padding: 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem; display: flex;
    border: 1px solid rgba(0,0,0,0.1);
}
.chat-message.user {
    background-color: #f0f2f6;
}
.chat-message.assistant {
    background-color: #e6f7ff;
}
.chat-message .avatar {
    width: 20%;
}
.chat-message .avatar img {
    max-width: 78px;
    max-height: 78px;
    border-radius: 50%;
    object-fit: cover;
}
.chat-message .message {
    width: 80%;
}

/* Pagination styling */
.pagination {
    display: flex;
    justify-content: center;
    margin-top: 1rem;
}
.pagination-button {
    margin: 0 0.25rem;
}
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("Document Q&A")
    
    # File upload with progress indicator
    uploaded_file = st.file_uploader(
        "Upload a document (PDF, DOCX, TXT)", 
        type=["pdf", "docx", "txt"],
        key="file_uploader"
    )
    
    # Process uploaded file
    if uploaded_file is not None:
        # Check if maximum number of files is reached
        if len(st.session_state.uploaded_files) >= 5:
            st.error("Maximum number of files (5) reached. Please remove some files before uploading more.")
        else:
            # Check file size (1MB = 1048576 bytes)
            if uploaded_file.size > 1048576:
                st.error("File size exceeds the maximum limit of 1MB.")
            else:
                # Check if file is already uploaded
                if uploaded_file.name in [f["name"] for f in st.session_state.uploaded_files]:
                    st.warning(f"File '{uploaded_file.name}' is already uploaded.")
                else:
                    try:
                        # Save the file permanently
                        file_path = persistence_manager.save_uploaded_file(
                            uploaded_file.getvalue(), 
                            uploaded_file.name
                        )
                        
                        # Process the document
                        with st.spinner(f"Processing {uploaded_file.name}..."):
                            document_text = get_document_text(uploaded_file.name, persistence_manager)
                            doc_id = process_document(document_text, uploaded_file.name, vector_store)
                        
                        # Add to session state
                        st.session_state.uploaded_files.append({
                            "name": uploaded_file.name,
                            "path": file_path,
                            "doc_id": doc_id
                        })
                        
                        # Save files info to disk
                        persistence_manager.save_files_info(st.session_state.uploaded_files)
                        
                        # Reset to first page when adding new documents
                        st.session_state.current_page = 1
                        
                        st.success(f"File '{uploaded_file.name}' uploaded and processed successfully!")
                    except Exception as e:
                        st.error(f"Error processing file: {str(e)}")
    
    # Display uploaded files with pagination
    st.subheader("Uploaded Documents")
    if not st.session_state.uploaded_files:
        st.info("No documents uploaded yet.")
    else:
        # Calculate pagination
        total_docs = len(st.session_state.uploaded_files)
        total_pages = math.ceil(total_docs / st.session_state.docs_per_page)
        
        # Ensure current page is valid
        if st.session_state.current_page > total_pages:
            st.session_state.current_page = total_pages
        if st.session_state.current_page < 1:
            st.session_state.current_page = 1
        
        # Calculate start and end indices
        start_idx = (st.session_state.current_page - 1) * st.session_state.docs_per_page
        end_idx = min(start_idx + st.session_state.docs_per_page, total_docs)
        
        # Initialize selected file state if not exists
        if "selected_file_index" not in st.session_state:
            st.session_state.selected_file_index = None
        if "selected_file_content" not in st.session_state:
            st.session_state.selected_file_content = None
        
        # Display files as clickable buttons
        for i in range(start_idx, end_idx):
            file = st.session_state.uploaded_files[i]
            if st.button(f"{i+1}. {file['name']}", key=f"file_{i}"):
                # Set selected file index
                st.session_state.selected_file_index = i
                
                # Get file content
                try:
                    file_content = get_document_text(file["name"], persistence_manager)
                    st.session_state.selected_file_content = {
                        "name": file["name"],
                        "content": file_content
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Error loading file content: {str(e)}")
        
        # Display selected file content if available
        if st.session_state.selected_file_content:
            with st.expander(f"Content of {st.session_state.selected_file_content['name']}", expanded=True):
                st.text(st.session_state.selected_file_content['content'])
                
                # Add a button to close the file view
                if st.button("Close File View"):
                    st.session_state.selected_file_content = None
                    st.session_state.selected_file_index = None
                    st.rerun()
        
        # Pagination controls
        if total_pages > 1:
            st.markdown("<div class='pagination'>", unsafe_allow_html=True)
            col1, col2, col3, col4, col5 = st.columns([1, 1, 3, 1, 1])
            
            with col1:
                if st.button("<<", key="first_page", disabled=(st.session_state.current_page == 1)):
                    st.session_state.current_page = 1
                    st.rerun()
            
            with col2:
                if st.button("<", key="prev_page", disabled=(st.session_state.current_page == 1)):
                    st.session_state.current_page -= 1
                    st.rerun()
            
            with col3:
                st.markdown(f"<div style='text-align: center;'>Page {st.session_state.current_page} of {total_pages}</div>", unsafe_allow_html=True)
            
            with col4:
                if st.button(">", key="next_page", disabled=(st.session_state.current_page == total_pages)):
                    st.session_state.current_page += 1
                    st.rerun()
            
            with col5:
                if st.button(">>", key="last_page", disabled=(st.session_state.current_page == total_pages)):
                    st.session_state.current_page = total_pages
                    st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    # Display statistics
    st.subheader("Statistics")
    st.write(f"Documents: {len(st.session_state.uploaded_files)}")
    st.write(f"Conversations: {st.session_state.conversation_count}")

# Main content - Chat interface
st.title("Document Q&A Chat")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if "sources" in message and message["sources"]:
            with st.expander("Sources"):
                for source in message["sources"]:
                    st.write(f"- {source}")

# Chat input
query = st.chat_input("Ask a question about your documents...")

if query:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": query})
    
    # Display user message
    with st.chat_message("user"):
        st.write(query)
    
    # Check if the query is about the uploaded documents
    if not st.session_state.uploaded_files:
        with st.chat_message("assistant"):
            st.write("Please upload at least one document before asking questions.")
        st.session_state.messages.append({"role": "assistant", "content": "Please upload at least one document before asking questions."})
    elif not is_query_about_documents(query, vector_store):
        with st.chat_message("assistant"):
            st.write("I can only answer questions about the uploaded documents.")
        st.session_state.messages.append({"role": "assistant", "content": "I can only answer questions about the uploaded documents."})
    else:
        # Show assistant thinking with a spinner
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                st.session_state.conversation_count += 1
                
                # Update and save statistics
                stats = {"conversation_count": st.session_state.conversation_count}
                persistence_manager.save_stats(stats)
                
                # Get relevant document chunks - increase to 3 chunks for more context
                relevant_chunks = vector_store.similarity_search(query, k=3)
                
                if not relevant_chunks:
                    response_text = "No relevant information found in the documents."
                    sources = []
                else:
                    # Prepare context for Gemini
                    context = "\n\n".join([chunk["page_content"] for chunk in relevant_chunks])
                    sources = [chunk["metadata"].get("source", "Unknown") for chunk in relevant_chunks]
                    
                    # Build conversation history string
                    conversation_history = ""
                    if st.session_state.conversation_context:
                        conversation_history = "Previous conversation:\n"
                        for i, exchange in enumerate(st.session_state.conversation_context[-3:]):  # Last 3 exchanges
                            conversation_history += f"User: {exchange['user']}\n"
                            conversation_history += f"Assistant: {exchange['assistant']}\n\n"
                    
                    try:
                        # Generate response using Gemini with better parameters
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        generation_config = {
                            "temperature": 0.1,  # Lower temperature for more factual responses
                            "top_p": 0.95,
                            "top_k": 40,
                            "max_output_tokens": 1024,
                        }
                        
                        # Create improved prompt with better instructions
                        if conversation_history:
                            prompt = f"""
                            You are a helpful document assistant. Answer the question based ONLY on the document context provided below.
                            Be specific and extract relevant information directly from the context.
                            
                            DOCUMENT CONTEXT:
                            ```
                            {context}
                            ```
                            
                            PREVIOUS CONVERSATION:
                            {conversation_history}
                            
                            CURRENT QUESTION: {query}
                            
                            INSTRUCTIONS:
                            1. Answer ONLY based on information in the DOCUMENT CONTEXT
                            2. If the answer is not in the context, say "I don't have enough information to answer this question."
                            3. Provide a 2 line answer if you can
                            4. Include specific details from the document when possible
                            5. Do not make up information
                            
                            YOUR ANSWER:
                            """
                        else:
                            prompt = f"""
                            You are a helpful document assistant. Answer the question based ONLY on the document context provided below.
                            Be specific and extract relevant information directly from the context.
                            
                            DOCUMENT CONTEXT:
                            ```
                            {context}
                            ```
                            
                            QUESTION: {query}
                            
                            INSTRUCTIONS:
                            1. Answer ONLY based on information in the DOCUMENT CONTEXT
                            2. If the answer is not in the context, say "I don't have enough information to answer this question."
                            3. Provide a 2 line answer if you can
                            4. Include specific details from the document when possible
                            5. Do not make up information
                            
                            YOUR ANSWER:
                            """
                        
                        response = model.generate_content(
                            prompt,
                            generation_config=generation_config
                        )
                        response_text = response.text
                        
                    except Exception as e:
                        response_text = f"Error generating response: {str(e)}"
                        sources = []
                
                # Display response
                st.write(response_text)
                
                # Show sources if available
                if sources:
                    with st.expander("Sources"):
                        for source in sources:
                            st.write(f"- {source}")
                
                # Add to messages and chat history
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": response_text,
                    "sources": sources
                })
                
                st.session_state.chat_history.append({
                    "query": query,
                    "response": response_text,
                    "sources": sources
                })
                
                # Update conversation context for next exchanges
                st.session_state.conversation_context.append({
                    "user": query,
                    "assistant": response_text
                })
                
                # Limit context length to prevent token overflow
                if len(st.session_state.conversation_context) > 5:  # Keep last 5 exchanges
                    st.session_state.conversation_context.pop(0)
                    
                # Show indicator if using conversation history
                if len(st.session_state.conversation_context) > 1:
                    with st.expander("Using conversation context"):
                        st.write("This response considers your previous questions and answers.")
                        for i, exchange in enumerate(st.session_state.conversation_context[:-1]):
                            st.write(f"**Previous Q{i+1}:** {exchange['user']}")
                            st.write(f"**Previous A{i+1}:** {exchange['assistant']}")
                            st.write("---")

# Add buttons to manage conversation
if st.session_state.messages:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            st.session_state.conversation_context = []
            st.rerun()
    with col2:
        if st.button("New Conversation"):
            st.session_state.conversation_context = []
            st.session_state.messages = []
            st.rerun()

# Headless mode functionality
def run_headless_mode():
    """
    Run the application in headless mode (without Streamlit UI)
    This mode is useful for API-based or automated interactions
    """
    logging.info("Starting application in headless mode")
    
    # Initialize components
    load_dotenv()
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        logging.error("Google API key not found. Please set it in the .env file.")
        sys.exit(1)
    
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # Set up persistence directories
    IS_CLOUD_RUN = os.environ.get('CLOUD_RUN_SERVICE', False)
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'document-qa-storage')
    
    if IS_CLOUD_RUN:
        DATA_DIR = "/tmp/data"
        CHROMA_DIR = "/tmp/chroma_db"
        USE_CLOUD_STORAGE = True
        logging.info(f"Running in Cloud Run (headless), using GCS bucket: {GCS_BUCKET_NAME}")
    else:
        DATA_DIR = "data"
        CHROMA_DIR = "chroma_db"
        USE_CLOUD_STORAGE = False
        logging.info("Running locally (headless), using local file storage")
    
    # Initialize vector store and persistence manager
    vector_store = VectorStore(
        persist_directory=CHROMA_DIR,
        use_cloud_storage=USE_CLOUD_STORAGE,
        bucket_name=GCS_BUCKET_NAME
    )
    persistence_manager = PersistenceManager(
        data_dir=DATA_DIR,
        use_cloud_storage=USE_CLOUD_STORAGE,
        bucket_name=GCS_BUCKET_NAME
    )
    
    # List files from storage
    files_info = persistence_manager.load_files_info()
    
    # If using cloud storage, check for files in GCS that might not be in local records
    if USE_CLOUD_STORAGE:
        gcs_files = list_files_from_gcs(persistence_manager)
        if gcs_files:
            # Add files from GCS that aren't in the local records
            existing_files = [f["name"] for f in files_info]
            for file_name in gcs_files:
                if file_name not in existing_files:
                    # Add with placeholder doc_id
                    files_info.append({
                        "name": file_name,
                        "doc_id": "gcs_file",  # Placeholder
                        "path": f"uploads/{file_name}"
                    })
            
            # Save updated file info
            persistence_manager.save_files_info(files_info)
    
    # Log available files
    logging.info(f"Available files: {[f['name'] for f in files_info]}")
    
    # Initialize Gemini model
    model = genai.GenerativeModel('gemini-1.5-flash')
    generation_config = {
        "temperature": 0.2,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 4096,
    }
    
    # Keep the application running
    logging.info("Headless mode active. Application is running...")
    try:
        while True:
            # In a real implementation, this would be replaced with an API endpoint
            # that accepts queries and returns responses
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down headless application")

# Check if the script is run with the --headless flag
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Document Q&A Application")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode without Streamlit UI")
    args = parser.parse_args()
    
    if args.headless:
        run_headless_mode()
