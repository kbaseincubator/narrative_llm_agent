import re
from dash import html

def format_agent_response(response_text):
    """
    Convert plain text agent responses into nicely formatted HTML components
    """
    if not response_text:
        return response_text

    # Handle the actual format:
    # 1. Name: Bsubtilis_rawdata
    #    - UPA: 223857/2/1
    #    - Type: KBaseFile.PairedEndLibrary-2.1

    lines = response_text.split('\n')
    formatted_components = []
    current_paragraph = []
    current_object = {}

    for line in lines:
        original_line = line
        line = line.strip()

        # Check for numbered object name (e.g., "1. Name: Bsubtilis_rawdata")
        name_match = re.match(r'^\d+\.\s*Name:\s*(.+)', line)

        # Check for indented UPA/Type lines (starts with spaces/tabs followed by -)
        if re.match(r'^\s+[-•]\s*UPA:\s*(.+)', original_line):
            upa_match = re.match(r'^\s+[-•]\s*UPA:\s*(.+)', original_line)
            if current_object and upa_match:
                current_object['upa'] = upa_match.group(1).strip()
        elif re.match(r'^\s+[-•]\s*Type:\s*(.+)', original_line):
            type_match = re.match(r'^\s+[-•]\s*Type:\s*(.+)', original_line)
            if current_object and type_match:
                current_object['type'] = type_match.group(1).strip()
        elif name_match:
            # If we have a complete previous object, add it
            if current_object and len(current_object) == 3:
                formatted_components.append(create_kbase_object_card(current_object))

            # If we were building a paragraph, add it first
            if current_paragraph:
                formatted_components.append(
                    html.P(' '.join(current_paragraph), className="mb-2")
                )
                current_paragraph = []

            # Start new object
            current_object = {'name': name_match.group(1).strip()}

        elif line == '':
            # Empty line - complete current object if ready
            if current_object and len(current_object) == 3:
                formatted_components.append(create_kbase_object_card(current_object))
                current_object = {}
            elif current_paragraph:
                formatted_components.append(
                    html.P(' '.join(current_paragraph), className="mb-2")
                )
                current_paragraph = []

        else:
            # Regular text line (not part of object listing)
            # Complete current object if ready
            if current_object and len(current_object) == 3:
                formatted_components.append(create_kbase_object_card(current_object))
                current_object = {}

            # Only add to paragraph if it's not an indented line (sub-item)
            if not re.match(r'^\s+[-•]', original_line):
                current_paragraph.append(line)

    # Handle remaining content
    if current_object and len(current_object) == 3:
        formatted_components.append(create_kbase_object_card(current_object))
    elif current_paragraph:
        formatted_components.append(
            html.P(' '.join(current_paragraph), className="mb-2")
        )

    return html.Div(formatted_components) if formatted_components else response_text

def create_kbase_object_card(obj):
    """Create a formatted card for a KBase object"""
    return html.Div([
        html.Div([
            html.Strong("Name: ", className="text-primary"),
            html.Span(obj.get('name', ''))
        ], className="mb-1"),
        html.Div([
            html.Strong("UPA: ", className="text-secondary"),
            html.Code(obj.get('upa', ''), className="text-info")
        ], className="mb-1"),
        html.Div([
            html.Strong("Type: ", className="text-muted"),
            html.Span(obj.get('type', ''), className="font-monospace text-success")
        ])
    ], className="kbase-object mb-3")

def format_list_item_content(content):
    """
    Format individual list item content, especially for KBase object listings
    """
    # Check if this looks like a KBase object description
    # Pattern: Name: X - UPA: Y - Type: Z
    kbase_pattern = r'Name:\s*([^-]+)\s*-\s*UPA:\s*([^-]+)\s*-\s*Type:\s*(.+)'
    match = re.match(kbase_pattern, content)

    if match:
        name, upa, obj_type = match.groups()
        return html.Div([
            html.Strong("Name: ", className="text-primary"),
            html.Span(name.strip()),
            html.Br(),
            html.Strong("UPA: ", className="text-secondary"),
            html.Code(upa.strip(), className="text-info"),
            html.Br(),
            html.Strong("Type: ", className="text-muted"),
            html.Span(obj_type.strip(), className="font-monospace text-success")
        ])

    # Look for other common patterns like "Key: Value"
    key_value_pattern = r'^([^:]+):\s*(.+)$'
    kv_match = re.match(key_value_pattern, content)

    if kv_match:
        key, value = kv_match.groups()
        return html.Div([
            html.Strong(f"{key.strip()}: ", className="text-primary"),
            html.Span(value.strip())
        ])

    # Default: return as-is
    return html.Span(content)

