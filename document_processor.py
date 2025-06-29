import os
from typing import List, Dict, Any
import PyPDF2
import docx
import re

def get_document_text(file_path: str, file_name: str) -> str:
    """
    Extract text from different document types (PDF, DOCX, TXT)
    
    Args:
        file_path: Path to the document
        file_name: Name of the document
        
    Returns:
        str: Extracted text from the document
    """
    file_extension = os.path.splitext(file_name)[1].lower()
    
    if file_extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_extension == '.docx':
        return extract_text_from_docx(file_path)
    elif file_extension == '.txt':
        return extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file"""
    text = ""
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX file"""
    doc = docx.Document(file_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def extract_text_from_txt(file_path: str) -> str:
    """Extract text from TXT file"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        return file.read()

def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """
    Split text into chunks of specified size with overlap
    
    Args:
        text: Text to split
        chunk_size: Maximum size of each chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        List[str]: List of text chunks
    """
    # Clean text by removing excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # If text is shorter than chunk_size, return it as a single chunk
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        # Find the end of the chunk
        end = start + chunk_size
        
        # If we're not at the end of the text, try to find a good breaking point
        if end < len(text):
            # Try to find the last period, question mark, or exclamation point
            last_punctuation = max(
                text.rfind('.', start, end),
                text.rfind('?', start, end),
                text.rfind('!', start, end)
            )
            
            # If we found a punctuation mark, use it as the break point
            if last_punctuation != -1 and last_punctuation > start + chunk_size // 2:
                end = last_punctuation + 1
            else:
                # Otherwise, find the last space
                last_space = text.rfind(' ', start, end)
                if last_space != -1:
                    end = last_space + 1
        
        # Add the chunk to our list
        chunks.append(text[start:end].strip())
        
        # Move the start position for the next chunk, accounting for overlap
        start = end - chunk_overlap
    
    return chunks

def process_document(document_text: str, document_name: str, vector_store) -> str:
    """
    Process document text and add to vector store
    
    Args:
        document_text: Extracted text from the document
        document_name: Name of the document
        vector_store: Vector store instance
        
    Returns:
        str: Document ID
    """
    # Split text into chunks
    chunks = split_text(document_text, chunk_size=1000, chunk_overlap=200)
    
    # Create document chunks with metadata
    documents = []
    for i, chunk in enumerate(chunks):
        documents.append({
            "page_content": chunk,
            "metadata": {
                "source": document_name,
                "chunk": i
            }
        })
    
    # Add to vector store
    doc_id = vector_store.add_documents(documents)
    
    return doc_id
