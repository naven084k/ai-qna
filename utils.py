import re
import tiktoken

def is_query_about_documents(query: str, vector_store) -> bool:
    """
    Check if a query is related to the uploaded documents
    
    Args:
        query: User query
        vector_store: Vector store instance
        
    Returns:
        bool: True if the query is about the documents, False otherwise
    """
    # Get relevant chunks for the query
    results = vector_store.similarity_search(query, k=1)
    
    # If no results or similarity score is too low, consider it unrelated
    if not results:
        return False
    
    # For simplicity, we consider any query that returns a result as related
    # In a production system, you might want to implement a threshold-based approach
    return True

def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string
    
    Args:
        text: Text string
        
    Returns:
        int: Number of tokens
    """
    try:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(text))
    except:
        # Fallback: rough estimate (1 token ~= 4 chars)
        return len(text) // 4
