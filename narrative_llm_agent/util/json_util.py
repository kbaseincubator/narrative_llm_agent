import re
import json

def extract_json_from_string(string_data):
    """Extract JSON array from a string."""
    # Use regex to find the JSON content within the string
    json_match = re.search(r'\[.*\]', string_data, re.DOTALL)
    
    if json_match:
        json_str = json_match.group(0)
        try:
            # Load the JSON string as Python object
            json_data = json.loads(json_str)
            return json_data
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
    else:
        print("No JSON data found in the string.")
        return None

def extract_json_from_string_curly(string_data):
    """Extract JSON object from a string, supporting both objects and arrays."""
    # First try to find JSON content within curly braces (for objects)
    json_match = re.search(r'\{.*\}', string_data, re.DOTALL)
    
    if json_match:
        json_str = json_match.group(0)
    else:
        # Try to find JSON content within square brackets (for arrays)
        json_match = re.search(r'\[.*\]', string_data, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            print("No JSON data found in the string.")
            return None
    
    try:
        # Load the JSON string as Python object
        json_data = json.loads(json_str)
        return json_data
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None