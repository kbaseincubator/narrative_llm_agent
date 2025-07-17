import re
import json


def make_json_serializable(obj, max_depth=10, current_depth=0):
    """Convert objects to JSON serializable format with improved handling"""

    # Prevent infinite recursion
    if current_depth >= max_depth:
        return str(obj)

    try:
        # First, try to serialize directly
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        pass

    # Handle None
    if obj is None:
        return None

    # Handle basic types that should be serializable
    if isinstance(obj, (str, int, float, bool)):
        return obj

    # Handle lists and tuples
    if isinstance(obj, (list, tuple)):
        try:
            return [
                make_json_serializable(item, max_depth, current_depth + 1)
                for item in obj
            ]
        except Exception:
            return [str(item) for item in obj]

    # Handle dictionaries
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            try:
                # Ensure the key is a string
                str_key = str(key)
                result[str_key] = make_json_serializable(
                    value, max_depth, current_depth + 1
                )
            except Exception as e:
                # If we can't serialize the value, convert to string
                result[str(key)] = str(value)
        return result

    # Handle objects with __dict__
    if hasattr(obj, "__dict__"):
        result = {}
        for key, value in obj.__dict__.items():
            try:
                # Skip private attributes and methods
                if key.startswith("_"):
                    continue

                str_key = str(key)
                result[str_key] = make_json_serializable(
                    value, max_depth, current_depth + 1
                )
            except Exception:
                # If we can't serialize the value, convert to string
                result[str(key)] = str(value)
        return result

    # Handle other iterables
    try:
        if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
            return [
                make_json_serializable(item, max_depth, current_depth + 1)
                for item in obj
            ]
    except Exception:
        pass

    # Final fallback - convert to string
    return str(obj)


def safe_json_dumps(obj, indent=2):
    """Safely dump object to JSON string"""
    try:
        serializable_obj = make_json_serializable(obj)
        return json.dumps(serializable_obj, indent=indent, ensure_ascii=False)
    except Exception as e:
        return f"JSON serialization error: {str(e)}"

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
