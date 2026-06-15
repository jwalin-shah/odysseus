import json

def load_from_file(path: str) -> dict:
    """Load a JSON configuration file and return its contents as a dictionary.
    
    Args:
        path: Path to the JSON file.
    
    Returns:
        The parsed JSON content as a dict.
    
    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    with open(path, 'r') as f:
        return json.load(f)
