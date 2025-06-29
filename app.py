import streamlit as st
import os
import tempfile
import logging
import time
import math
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
vector_store = VectorStore(persist_directory=CHROMA_DIR)

# Initialize persistence manager
persistence_manager = PersistenceManager(
    data_dir=DATA_DIR,
    use_cloud_storage=USE_CLOUD_STORAGE,
    bucket_name=GCS_BUCKET_NAME
)

# Initialize session state
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = persistence_manager.load_files_info()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_page" not in st.session_state:
    st.session_state.current_page = 1
if "docs_per_page" not in st.session_state:
    st.session_state.docs_per_page = 5

# Load statistics
stats = persistence_manager.load_stats()
if "conversation_count" not in st.session_state:
    st.session_state.conversation_count = stats.get("conversation_count", 0)

# Page configuration
st.set_page_config(page_title="Document Q&A", layout="wide")

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
                        
                        # Extract text from document
                        document_text = get_document_text(file_path, uploaded_file.name)
                        
                        # Process document and add to vector store
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
            
        # Display documents for current page
        start_idx = (st.session_state.current_page - 1) * st.session_state.docs_per_page
        end_idx = min(start_idx + st.session_state.docs_per_page, total_docs)
        
        for i in range(start_idx, end_idx):
            file = st.session_state.uploaded_files[i]
            st.write(f"{i+1}. {file['name']}")
        
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
                
                # Get relevant document chunks
                relevant_chunks = vector_store.similarity_search(query, k=1)
                
                if not relevant_chunks:
                    response_text = "No relevant information found in the documents."
                    sources = []
                else:
                    # Prepare context for Gemini
                    context = "\n\n".join([chunk["page_content"] for chunk in relevant_chunks])
                    sources = [chunk["metadata"].get("source", "Unknown") for chunk in relevant_chunks]
                    
                    try:
                        # Generate response using Gemini
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        prompt = f"""
                        Answer the question based ONLY on the following context:
                        
                        {context}
                        
                        Question: {query}
                        
                        If the answer cannot be found in the context, say "I don't have enough information to answer this question."
                        """
                        
                        response = model.generate_content(prompt)
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

# Add a button to clear chat history
if st.session_state.messages:
    if st.sidebar.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
