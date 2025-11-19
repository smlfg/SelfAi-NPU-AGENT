"""Tools for interacting with the file system."""

import os

def write_file(path: str, content: str) -> str:
    """Writes content to a specified file. Creates directories if they don't exist."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing to file: {e}"

def read_file(path: str) -> str:
    """Reads the content of a specified file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def list_directory(path: str) -> str:
    """Lists the contents of a specified directory."""
    try:
        return "\n".join(os.listdir(path))
    except Exception as e:
        return f"Error listing directory: {e}"

