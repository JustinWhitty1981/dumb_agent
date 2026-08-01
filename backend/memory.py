"""
Markdown-based memory storage for the LangChain agent.
Stores and retrieves memory entries in markdown format.
"""

import os
import re
from datetime import datetime
from typing import List, Optional, Tuple

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "memory_store")


def ensure_memory_dir():
    """Ensure the memory directory exists."""
    os.makedirs(MEMORY_DIR, exist_ok=True)


def _get_memory_file(key: str) -> str:
    """Get the file path for a memory key."""
    # Sanitize key to be a valid filename
    safe_key = re.sub(r'[^\w\-_\.]', '_', key)
    return os.path.join(MEMORY_DIR, f"{safe_key}.md")


def save_memory(key: str, content: str) -> str:
    """
    Save a piece of information to memory.
    
    Args:
        key: A unique identifier for this memory
        content: The content to store
        
    Returns:
        Confirmation message
    """
    ensure_memory_dir()
    filepath = _get_memory_file(key)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Append to existing or create new
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"\n---\n")
        f.write(f"**Timestamp:** {timestamp}\n")
        f.write(f"**Content:**\n{content}\n")
    
    return f"Memory saved with key '{key}'"


def get_memory(key: str) -> str:
    """
    Retrieve stored information by key.
    
    Args:
        key: The memory key to look up
        
    Returns:
        The stored content or a not found message
    """
    ensure_memory_dir()
    filepath = _get_memory_file(key)
    
    if not os.path.exists(filepath):
        return f"No memory found with key '{key}'"
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    return f"Memory for '{key}':\n{content}"


def list_memories() -> str:
    """
    List all saved memory keys.
    
    Returns:
        A list of memory keys
    """
    ensure_memory_dir()
    
    if not os.listdir(MEMORY_DIR):
        return "No memories stored yet."
    
    files = [f.replace(".md", "") for f in os.listdir(MEMORY_DIR) if f.endswith(".md")]
    return f"Stored memories: {', '.join(sorted(files))}"


def delete_memory(key: str) -> str:
    """
    Delete a memory entry.
    
    Args:
        key: The memory key to delete
        
    Returns:
        Confirmation message
    """
    ensure_memory_dir()
    filepath = _get_memory_file(key)
    
    if not os.path.exists(filepath):
        return f"No memory found with key '{key}'"
    
    os.remove(filepath)
    return f"Memory '{key}' deleted"


def search_memories(query: str) -> str:
    """
    Search through all memories for a keyword.
    
    Args:
        query: The search term
        
    Returns:
        Matching memories or no results message
    """
    ensure_memory_dir()
    
    if not os.listdir(MEMORY_DIR):
        return "No memories stored yet."
    
    matches = []
    for filename in os.listdir(MEMORY_DIR):
        if filename.endswith(".md"):
            filepath = os.path.join(MEMORY_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                if query.lower() in content.lower():
                    key = filename.replace(".md", "")
                    matches.append(f"---\n**Memory: {key}**\n{content}")
    
    if not matches:
        return f"No memories found containing '{query}'"
    
    return f"Memories containing '{query}':\n\n" + "\n\n".join(matches)