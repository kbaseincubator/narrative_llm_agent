import json
import os
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from langchain.load import dumps, loads
from langchain_core.tools import tool
from pydantic import BaseModel
from narrative_llm_agent.tools.narrative_tools import create_markdown_cell
from narrative_llm_agent.tools.workspace_tools import get_object_metadata
from narrative_llm_agent.util.tool import process_tool_input
from narrative_llm_agent.kbase.clients.workspace import Workspace

# Global variable for user input handling
current_user_input = None

class MetadataInput(BaseModel):
    obj_upa: str = "UPA for reads data object"

class UserInputModel(BaseModel):
    prompt: str = "Prompt to show the user for input"


@tool("get-user-input")
def get_user_input_tool(prompt: str) -> str:
    """Get input from the user by displaying a prompt. Use this tool when you need information from the user."""
    global current_user_input
    
    try:
        if current_user_input is not None:
            user_response = current_user_input
            current_user_input = None  # Clear after use
            return f"User responded: {user_response}"
        else:
            return f"Please provide: {prompt}"
    except Exception as e:
        return f"Error getting user input: {str(e)}"

@tool("get-object-metadata")
def get_object_metadata_tool(obj_upa: str) -> str:
    """Return the metadata for a KBase Workspace object with the given UPA."""
    return json.dumps(get_object_metadata(process_tool_input(obj_upa, "obj_upa"), Workspace()))

@tool("list-objects")
def list_objects_tool(narrative_id: int) -> str:
    """Fetch a list of objects available in a KBase Narrative."""
    ws = Workspace()
    return json.dumps(
        ws.list_workspace_objects(
            process_tool_input(narrative_id, "narrative_id"), as_dict=True
        )
    )

@tool("store-conversation")
def store_introduction_tool(narrative_id: int, conversation: str) -> str:
    """Store introduction tool. This securely stores the introduction to a Narrative workflow as a
    markdown cell in a KBase Narrative."""
    create_markdown_cell(narrative_id, conversation, Workspace())
    return f"Successfully stored conversation to narrative {narrative_id}"

# ----------------------------
# Agent Setup

def create_metadata_agent():
    """Create and return the metadata collection agent executor"""
    
    llm = ChatOpenAI(temperature=0.7)
    tools = [get_user_input_tool, get_object_metadata_tool, list_objects_tool, store_introduction_tool]

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a Human Interaction Manager and expert project manager for computational biology projects.

Your role: Gather initial information about the genome assembly and annotation pipeline from the user.

Your goal: You are detail-oriented and use experience to gather relevant information about an analysis project. 
You are friendly and skilled at interaction with users to make sure that they've provided necessary 
information to make sure a project is successful before it begins.

Follow this workflow in order:

1. STARTUP: Ask the user which narrative ID they are using. This will be a number. Once you have it, proceed to the next step.

2. FETCH OBJECTS: Use the list_workspace_objects_tool to fetch all objects available in the user's narrative using the narrative ID. 
   Do NOT ask the user for the narrative ID again or ask them to list objects directly - use the tool.
   Filter out any objects with type "KBaseNarrative.Narrative". Present the name, UPA, and type for each remaining object.

3. SELECT OBJECT: From the list of available objects, ask the user what data they want to assemble and annotate. 
   Get the narrative ID, UPA of the chosen data object, and the name of the object.

4. GATHER METADATA: For the selected UPA, first use get_object_metadata_tool to retrieve metadata.
   If the metadata doesn't provide enough information to choose appropriate applications for assembly and annotation,
   ask the user targeted questions about:
   - Sequencing machine used
   - Project goals and requirements  
   - Any other relevant technical details
   Note: The user may not know certain information - this is valid. Don't keep repeating requests if they say they don't have more information.

5. STORE CONVERSATION: Once you have sufficient information, use store_conversation_tool to save the conversation to the narrative.
   Format the conversation as markdown text resembling a biological article abstract.
   Write as though you are the scientist (avoid "the user prefers..." language).
   Focus on the goals (assembling and annotating genomic reads) and context about data source and nature.
   Do NOT ask the user any more questions during this step.

Available tools:
- get_user_input_tool: Use this to ask the user questions and get their responses
- get_object_metadata_tool: To retrieve metadata for KBase objects using UPA
- list_workspace_objects_tool: To list all objects in a workspace using narrative/workspace ID
- store_conversation_tool: To save the conversation summary to a KBase Narrative

Be conversational, ask follow-up questions when needed, but follow the workflow systematically. Always use tools first before asking users for information that tools can provide."""),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    return agent_executor

# ----------------------------
# Processing Function

def process_metadata_chat(agent_executor, user_input, chat_history):
    """Process a chat interaction with the metadata collection agent"""
    global current_user_input
    
    try:
        current_user_input = user_input
        
        if not isinstance(chat_history, list):
            chat_history = []
        
        response = agent_executor.invoke({
            "input": user_input if user_input else "Start the conversation by asking for the narrative ID",
            "chat_history": chat_history
        })
        
        return response.get("output", "No response generated")
        
    except Exception as e:
        return f"Error in agent processing: {str(e)}"

# ----------------------------
# Metadata Extraction Utilities

def extract_metadata_from_conversation(chat_history):
    """Extract structured metadata from conversation history"""
    collected_data = {}
    
    if not chat_history:
        return collected_data
    
    try:
        # Handle both string and list formats
        if isinstance(chat_history, str):
            chat_history_obj = loads(chat_history)
        else:
            chat_history_obj = chat_history
        
        full_conversation = " ".join([msg.content for msg in chat_history_obj])
        
        # Extract metadata from conversation using pattern matching
        for msg in chat_history_obj:
            if isinstance(msg, HumanMessage):
                content = msg.content.lower()
                
                # Try to extract narrative ID
                if any(keyword in content for keyword in ["narrative id", "narrative"]) and any(char.isdigit() for char in msg.content):
                    import re
                    numbers = re.findall(r'\d+', msg.content)
                    if numbers:
                        collected_data["narrative_id"] = numbers[0]
                
                # Try to extract UPA/reads ID
                if "/" in msg.content and any(char.isdigit() for char in msg.content):
                    import re
                    upa_pattern = r'\d+/\d+/\d+'
                    upa_matches = re.findall(upa_pattern, msg.content)
                    if upa_matches:
                        collected_data["reads_id"] = upa_matches[0]
        
        # Extract metadata from agent responses
        for msg in chat_history_obj:
            if isinstance(msg, AIMessage):
                content = msg.content.lower()
                
                # Look for sequencing technology
                if "illumina" in content:
                    collected_data["sequencing_technology"] = "Illumina sequencing"
                elif "pacbio" in content:
                    collected_data["sequencing_technology"] = "PacBio"
                elif "nanopore" in content:
                    collected_data["sequencing_technology"] = "Oxford Nanopore"
                
                # Look for organism information
                if "organism" in content:
                    # Try to extract organism name after "organism:"
                    import re
                    organism_match = re.search(r'organism[:\s]+([^,\n\.]+)', content, re.IGNORECASE)
                    if organism_match:
                        collected_data["organism"] = organism_match.group(1).strip()
                
                # Look for genome type
                if "isolate" in content:
                    collected_data["genome_type"] = "isolate"
                elif "metagenome" in content:
                    collected_data["genome_type"] = "metagenome"
                elif "transcriptome" in content:
                    collected_data["genome_type"] = "transcriptome"
        
    except Exception as e:
        print(f"Error extracting metadata: {e}")
    
    return collected_data

def check_metadata_completion(chat_history):
    """Check if metadata collection is complete based on conversation indicators"""
    if not chat_history:
        return False, {}
    
    try:
        # Handle both string and list formats
        if isinstance(chat_history, str):
            chat_history_obj = loads(chat_history)
        else:
            chat_history_obj = chat_history
        
        # Check for completion indicators in the last few messages
        recent_messages = chat_history_obj[-3:] if len(chat_history_obj) > 3 else chat_history_obj
        
        completion_indicators = [
            "successfully stored conversation",
            "stored conversation to narrative",
            "conversation summary",
            "workflow is complete",
            "analysis can now begin",
            "ready to proceed",
            "metadata collection complete"
        ]
        
        for msg in recent_messages:
            if isinstance(msg, AIMessage):
                if any(indicator in msg.content.lower() for indicator in completion_indicators):
                    return True, extract_metadata_from_conversation(chat_history_obj)
        
        # Alternative check: see if we have essential data
        collected_data = extract_metadata_from_conversation(chat_history_obj)
        has_essential_data = (
            collected_data.get("narrative_id") and 
            collected_data.get("reads_id")
        )
        
        return has_essential_data, collected_data
        
    except Exception as e:
        print(f"Error checking completion: {e}")
        return False, {}

def generate_description_from_metadata(collected_data):
    """Generate analysis description from collected metadata"""
    if not collected_data:
        return ""
    
    sequencing_tech = collected_data.get("sequencing_technology", "Unknown sequencing")
    organism = collected_data.get("organism", "Unknown organism")
    genome_type = collected_data.get("genome_type", "isolate")
    
    description = f"""The user has uploaded paired-end sequencing reads into the narrative. Here is the metadata for the reads:
sequencing_technology: {sequencing_tech}
organism: {organism}
genome type: {genome_type}

I want you to generate an analysis plan for annotating the uploaded pair-end reads obtained from {sequencing_tech} for a {genome_type} genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe."""
    
    return description