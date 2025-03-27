import streamlit as st
import os
import re
import json
from typing import List, Dict, Any, Optional, TypedDict
from pydantic import BaseModel
# Import required libraries for KBase integration
import openai
from crewai import Crew, Agent, Task, LLM
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

# Set page config
st.set_page_config(
    page_title="KBase Research Agent",
    page_icon="🧬",
    layout="wide"
)

# Define models
class AnalysisStep(BaseModel):
    Step: int
    Name: str
    Description: str
    expect_new_object: bool
    app_id: str

class AnalysisPipeline(BaseModel):
    steps_to_run: List[AnalysisStep]

class GenomeAnalysisState(TypedDict):
    narrative_id: str
    reads_id: str
    description: str
    analysis_plan: Optional[List[Dict[str, Any]]]
    steps_to_run: Optional[List[Dict[str, Any]]]
    results: Optional[str]
    error: Optional[str]

# ---------- Core Implementation Functions ----------

def extract_json_from_string(string_data):
    # Use regex to find the JSON content within the string
    json_match = re.search(r'\[.*\]', string_data, re.DOTALL)
    
    if json_match:
        json_str = json_match.group(0)
        try:
            # Load the JSON string as Python object
            json_data = json.loads(json_str)
            return json_data
        except json.JSONDecodeError as e:
            st.error(f"Error decoding JSON: {e}")
            return None
    else:
        st.warning("No JSON data found in the string.")
        return None

# KBase Integration Classes
@st.cache_resource
def load_kbase_classes():
    # This part will be loaded and cached by Streamlit
    try:
        from narrative_llm_agent.crews.job_crew import JobCrew
        from narrative_llm_agent.agents.kbase_agent import KBaseAgent
        from narrative_llm_agent.agents.analyst import AnalystAgent
        from narrative_llm_agent.agents.metadata import MetadataAgent
        
        class AppRunInputs(BaseModel):
            narrative_id: int
            app_id: str
            input_object_upa: str

        class WorkflowRunner(KBaseAgent):
            job_crew: JobCrew
            role: str = "You are a workflow runner, your role is to efficiently run KBase workflows."
            goal: str = "Your goal is to create and run elegant and scientifically meaningful computational biology workflows."
            backstory: str = "You are a dedicated and effective computational biologist. You have deep knowledge of how to run workflows in the DOE KBase system and have years of experience using this to produce high quality scientific knowledge."
            
            def __init__(self, llm, token: str = None):
                from langchain.tools import tool
                
                self.job_crew = JobCrew(llm)
                self._llm = llm
                self._token = token

                @tool(args_schema=AppRunInputs)
                def do_app_run(narrative_id: int, app_id: str, input_object_upa: str):
                    """
                    This invokes a CrewAI crew to run a new KBase app from start to finish and
                    returns the results. It takes in the narrative_id, app_id (formalized as module_name/app_name), and
                    UPA of the input object.
                    """
                    return self.run_app_crew(narrative_id, app_id, input_object_upa)
                    
                self.agent = Agent(
                    role=self.role,
                    goal=self.goal,
                    backstory=self.backstory,
                    verbose=True,
                    tools=[
                        do_app_run
                    ],
                    llm=self._llm,
                    allow_delegation=False,
                    memory=True,
                )
            
            def run_app_crew(self, narrative_id: int, app_id: str, input_object_upa: str):
                return self.job_crew.start_job(app_id, input_object_upa, narrative_id, app_id=app_id)
                
        return True, {"WorkflowRunner": WorkflowRunner, "AnalystAgent": AnalystAgent}
        
    except ImportError as e:
        return False, f"ImportError: {str(e)}"
    except Exception as e:
        return False, f"Error loading KBase classes: {str(e)}"

# Initialize LLM
def initialize_llm(api_key, base_url="https://api.cborg.lbl.gov"):
    return LLM(model="openai/openai/gpt-4o",
    api_key=api_key,
    base_url="https://api.cborg.lbl.gov",  # For LBL-Net, use "https://api-local.cborg.lbl.gov"
    temperature=0)

# Analyst node function
def analyst_node(state: GenomeAnalysisState):
    cborg_api_key = st.session_state.credentials.get("cborg_api_key", os.environ.get("CBORG_API_KEY", ""))
    llm = initialize_llm(cborg_api_key)
    kb_auth_token = st.session_state.credentials.get("kb_auth_token", "")
    try:
        # Display progress in the UI
        progress_placeholder = st.empty()
        progress_placeholder.info("📊 Running analysis planning...")
        
        # Get the existing description from the state
        description = state["description"]
        
        # Add a check for KBase classes
        success, result = load_kbase_classes()
        if not success:
            return {
                **state,
                "analysis_plan": None,
                "steps_to_run": None,
                "error": result
            }
        
        AnalystAgent = result["AnalystAgent"]
        
        # Initialize the analyst agent
        analyst_expert = AnalystAgent(llm, cborg_api_key =cborg_api_key, token=kb_auth_token,tools_model="openai/o1")
        
        # Create the analysis task
        analysis_agent_task = Task(
            description=description,
            expected_output="a json of the analysis workflow",
            output_json=AnalysisPipeline,
            agent=analyst_expert.agent
        )
        
        # Create and run the crew
        crew = Crew(
            agents=[analyst_expert.agent],
            tasks=[analysis_agent_task],
            verbose=True,
        )
        
        # Update UI
        progress_placeholder.info("📊 Generating analysis plan...")
        
        # Run the crew
        output = crew.kickoff()
        
        # Extract the JSON from the output
        analysis_plan = extract_json_from_string(output.raw)
        
        # Update UI
        progress_placeholder.success("✅ Analysis plan generated successfully")
        
        # Return updated state with analysis plan
        return {
            **state,
            "analysis_plan": analysis_plan,
            "steps_to_run": analysis_plan,  
            "error": None
        }
    except Exception as e:
        # Handle errors
        st.error(f"Error in analyst node: {str(e)}")
        return {
            **state,
            "analysis_plan": None,
            "steps_to_run": None,
            "error": str(e)
        }

# Workflow runner node
def workflow_runner_node(state: GenomeAnalysisState):
    cborg_api_key = st.session_state.credentials.get("cborg_api_key", os.environ.get("CBORG_API_KEY", ""))
    llm = initialize_llm(cborg_api_key)
    kb_auth_token = st.session_state.credentials.get("kb_auth_token", "")
    try:
        # Display progress in the UI
        progress_placeholder = st.empty()
        progress_placeholder.info("🔬 Running workflow...")
        
        steps_to_run = state["steps_to_run"]
        narrative_id = state["narrative_id"]
        reads_id = state["reads_id"]
        
        # Add a check for KBase classes
        success, result = load_kbase_classes()
        if not success:
            return {
                **state,
                "results": None,
                "error": result
            }
        
        WorkflowRunner = result["WorkflowRunner"]
        
        # Initialize the workflow runner
        wf_runner = WorkflowRunner(llm, token=kb_auth_token)
        
        # Create the task
        run_apps_task = Task(
            description=f"""
            This task involves running multiple apps where the output of one (if any) is fed into the next as input. 
            Here are the tasks in JSON format: {json.dumps(steps_to_run)}.
            If any task has "expect_new_object" set to True, then that should receive a new data object in its output as a "created_object". That object should be used as input for the next task.
            If a task as "expect_new_object" set to False, then that should not receive a new object to use in the next task. In that case, use the same input object from the previous step for the next one.
            These steps must be run sequentially. 
            These must be run in the narrative with id {narrative_id} and start with using the paired-end reads object {reads_id}.
            If any step ends with an error, immediately stop the task and end with an error.
            In the end, return a brief summary of steps taken and resulting output objects.
            """,
            expected_output="A summary of task completion, the number of apps run, and the upa of any output objects.",
            agent=wf_runner.agent
        )
        
        # Show step progress in UI
        progress_bar = st.progress(0)
        step_status = st.empty()
        
        # Create and run the crew
        crew = Crew(
            agents=[wf_runner.agent],
            tasks=[run_apps_task],
            verbose=True,
        )
        
        # Update UI with step progress simulation
        total_steps = len(steps_to_run)
        for i, step in enumerate(steps_to_run):
            step_status.info(f"Running step {step['Step']}: {step['Name']} using {step['app_id']}")
            progress_bar.progress((i + 0.5) / total_steps)
            # In a real implementation, you would wait for actual completion
        
        # Run the workflow
        result = crew.kickoff()
        
        # Update UI
        progress_bar.progress(1.0)
        progress_placeholder.success("✅ Workflow completed successfully")
        
        # Return updated state with results
        return {
            **state,
            "results": result,
            "error": None
        }
    except Exception as e:
        # Handle errors
        st.error(f"Error in workflow runner: {str(e)}")
        return {
            **state,
            "results": None,
            "error": str(e)
        }

# Router function
def router(state):
    if state["error"]:
        return "handle_error"
    else:
        return "run_workflow"

# Error handler function
def handle_error(state):
    return {**state, "results": f"Error: {state['error']}"}
    
# Build the complete graph with both analyst and workflow nodes
def build_genome_analysis_graph():
    # Create a new graph
    genome_graph = StateGraph(GenomeAnalysisState)
    
    # Add the nodes
    genome_graph.add_node("analyst", analyst_node)
    genome_graph.add_node("run_workflow", workflow_runner_node)
    genome_graph.add_node("handle_error", lambda state: {**state, "results": f"Error: {state['error']}"})
    
    # Define the edges with the router
    genome_graph.add_conditional_edges(
        "analyst",
        router,
        {
            "run_workflow": "run_workflow",
            "handle_error": "handle_error"
        }
    )
    genome_graph.add_edge("run_workflow", END)
    genome_graph.add_edge("handle_error", END)
    
    # Set the entry point
    genome_graph.set_entry_point("analyst")
    
    # Compile the graph
    return genome_graph.compile()
    
# Main analysis pipeline function
def run_genome_analysis(narrative_id, reads_id, description, credentials):
    # Get credentials
    kb_auth_token = credentials.get("kb_auth_token", "")
    cborg_api_key = credentials.get("cborg_api_key", os.environ.get("CBORG_API_KEY", ""))
    
    # Use the environment variables directly
    neo4j_uri = os.environ.get("NEO4J_URI", "")
    neo4j_username = os.environ.get("NEO4J_USERNAME", "")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "")
    
    # Ensure environment variables are set for the current session
    if not os.environ.get("NEO4J_URI"):
        os.environ["NEO4J_URI"] = neo4j_uri
    if not os.environ.get("NEO4J_USERNAME"):
        os.environ["NEO4J_USERNAME"] = neo4j_username
    if not os.environ.get("NEO4J_PASSWORD"):
        os.environ["NEO4J_PASSWORD"] = neo4j_password
    if not os.environ.get("KB_AUTH_TOKEN"):
        os.environ["KB_AUTH_TOKEN"] = kb_auth_token
    if not os.environ.get("CBORG_API_KEY"):
        os.environ["CBORG_API_KEY"] = cborg_api_key
    
    # Initialize LLM
    llm = initialize_llm(cborg_api_key)

    graph = build_genome_analysis_graph()
    # Initialize state
    state = {
        "narrative_id": narrative_id,
        "reads_id": reads_id,
        "description": description,
        "analysis_plan": None,
        "steps_to_run": None,
        "results": None,
        "error": None
    }
    
    final_state = graph.invoke(state)
    
    return state

# UI Components
def display_credentials_form():
    with st.expander("🔑 KBase Credentials", expanded=True):
        # No longer collect Neo4j credentials from user - use env vars only
        
        # Keep KB Auth Token input
        kb_auth_token = st.text_input("KB Auth Token", 
                                    value=st.session_state.get("kb_auth_token", ""), 
                                    type="password")
        
        # CBORG API Key input with environment variable fallback
        cborg_api_key = st.text_input("CBORG API Key", 
                                    value=st.session_state.get("cborg_api_key", os.environ.get("CBORG_API_KEY", "")), 
                                    type="password")
        
        save = st.button("Save Credentials")
        if save:
            # Store Neo4j credentials from environment variables
            st.session_state.credentials = {
                "neo4j_uri": os.environ.get("NEO4J_URI", ""),
                "neo4j_username": os.environ.get("NEO4J_USERNAME", ""),
                "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
                "kb_auth_token": kb_auth_token,
                "cborg_api_key": cborg_api_key
            }
            
            # Also save individual values for convenience
            st.session_state.neo4j_uri = os.environ.get("NEO4J_URI", "")
            st.session_state.neo4j_username = os.environ.get("NEO4J_USERNAME", "")
            st.session_state.neo4j_password = os.environ.get("NEO4J_PASSWORD", "")
            st.session_state.kb_auth_token = kb_auth_token
            st.session_state.cborg_api_key = cborg_api_key
            
            st.success("Credentials saved to session!")
    
    # Check if credentials exist in session
    if not st.session_state.get("credentials"):
        st.session_state.credentials = {
            "neo4j_uri": os.environ.get("NEO4J_URI", ""),
            "neo4j_username": os.environ.get("NEO4J_USERNAME", ""),
            "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
            "kb_auth_token": kb_auth_token if 'kb_auth_token' in locals() else "",
            "cborg_api_key": cborg_api_key if 'cborg_api_key' in locals() else os.environ.get("CBORG_API_KEY", "")
        }

def display_input_form():
    st.subheader("📝 Analysis Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        narrative_id = st.text_input("Narrative ID", value="210107")
        reads_id = st.text_input("Reads ID", value="210107/2/1")
    
    description = st.text_area("Analysis Description", height=200, value="""
The user has uploaded paired-end sequencing reads obtained from Illumina sequencing for an isolate Bacillus subtilis sp. strain UAMC into the narrative.
I want you to generate an analysis plan for annotating the uploaded pair end reads obtained from Illumina sequencing for a isolate genome for me using KBase apps. 
The goal is to have a complete annotated genome and classify the microbe
This analysis is for a Microbiology Resource Announcements (MRA) paper so these need to be a part of analysis. Always keep in mind the following:
- The analysis steps should begin with read quality assessment. 
- Make sure you select appropriate KBase apps based on genome type.
-Relevant statistics for the assembly (e.g., number of contigs and N50 values).
-Estimates of genome completeness, where applicable.
-Classify the microbe for taxonomy, where relevant.
Based on the metadata, devise a detailed step-by-step analysis workflow, the apps and app_ids should be from the app graph.
The analysis plan should be a json with schema as: 
```json
{{"Step": "Integer number indicating the step",
 "Description": "Describe the step",
 "App": "Name of the app",
 "expect_new_object": boolean indicating if this step creates a new data object,
 "app_id": "Id of the KBase app"}}
```
Ensure that app_ids are obtained from the app graph and are correct.
Make sure that the analysis plan is included in the final response.
""")
    
    return narrative_id, reads_id, description

def display_results(state):
    st.subheader("📊 Analysis Plan")
    
    if state["analysis_plan"]:
        # Create a table for the analysis steps
        data = []
        for step in state["analysis_plan"]:
            data.append([
                step["Step"],
                step["Name"],
                step["Description"],
                step["app_id"],
                "Yes" if step["expect_new_object"] else "No"
            ])
        
        st.table({
            "Step": [row[0] for row in data],
            "Name": [row[1] for row in data],
            "Description": [row[2] for row in data],
            "App ID": [row[3] for row in data],
            "Creates Object": [row[4] for row in data]
        })
    
    if state["results"]:
        st.subheader("🧪 Workflow Results")
        
        # Handle various result formats
        if isinstance(state["results"], dict):
            if "summary" in state["results"]:
                st.success(state["results"]["summary"])
                if "apps_run" in state["results"]:
                    st.metric("Apps Run", state["results"]["apps_run"])
                
                if "output_objects" in state["results"]:
                    st.subheader("Output Objects")
                    for obj in state["results"]["output_objects"]:
                        st.code(obj)
            else:
                # Display arbitrary dict
                for key, value in state["results"].items():
                    st.write(f"**{key}**: {value}")
        else:
            # Try to parse as CrewAI result object
            try:
                st.write("**Workflow Result:**")
                st.write(state["results"].raw)
            except:
                # Fall back to simple display
                st.write(state["results"])
    
    if state["error"]:
        st.error(f"Error: {state['error']}")

def display_connection_test():
    st.subheader("🔌 Connection Test")
    
    if st.button("Test KBase Connection"):
        try:
            # Check for credentials
            if not st.session_state.get("credentials", {}).get("kb_auth_token"):
                st.warning("KB Auth Token not found in session. Please save your credentials first.")
                return
                
            # Check if libraries can be imported
            with st.spinner("Testing KBase libraries..."):
                success, result = load_kbase_classes()
                if success:
                    st.success("✅ Successfully loaded KBase libraries")
                else:
                    st.error(f"❌ Failed to load KBase libraries: {result}")
                    st.info("Make sure the required libraries are installed: `narrative_llm_agent`, `crewai`, `langgraph`, etc.")
                    return
            
            # Try to initialize LLM
            with st.spinner("Testing LLM connection..."):
                api_key = st.session_state.get("credentials", {}).get("cborg_api_key", "")
                if not api_key:
                    st.warning("CBORG API Key not found in session. Please save your credentials first.")
                    return
                    
                try:
                    llm = initialize_llm(api_key)
                    st.success("✅ Successfully initialized LLM")
                except Exception as e:
                    st.error(f"❌ Failed to initialize LLM: {str(e)}")
                    return
            
            st.success("✅ All connections successful! You're ready to run analyses.")
            
        except Exception as e:
            st.error(f"❌ Connection test failed: {str(e)}")

def display_debug_info():
    st.subheader("🐛 Debug Information")
    
    with st.expander("Show Environment Variables", expanded=False):
        env_vars = {
            "NEO4J_URI": os.environ.get("NEO4J_URI", "Not set"),
            "NEO4J_USERNAME": os.environ.get("NEO4J_USERNAME", "Not set"),
            "KB_AUTH_TOKEN": "***" if os.environ.get("KB_AUTH_TOKEN") else "Not set",
            "CBORG_API_KEY": "***" if os.environ.get("CBORG_API_KEY") else "Not set"
        }
        
        for key, value in env_vars.items():
            st.code(f"{key}: {value}")

# Main app
def main():
    # Initialize session state if not already done
    if 'credentials' not in st.session_state:
        st.session_state.credentials = {}
    if 'analysis_history' not in st.session_state:
        st.session_state.analysis_history = []
    
    st.title("🧬 KBase Research Agent")
    
    # Add tabs
    tab1, tab2, tab3 = st.tabs(["Run Analysis", "About", "Connection Test"])
    
    with tab1:
        display_credentials_form()
        
        narrative_id, reads_id, description = display_input_form()
        
        # Dependency check
        try:
            import narrative_llm_agent
            has_dependencies = True
        except ImportError:
            has_dependencies = False
            st.warning("⚠️ KBase libraries not found. The app will run in demonstration mode with limited functionality.")
        
        run_button = st.button("🚀 Run Analysis", type="primary", disabled=not has_dependencies)
        
        if run_button:
            with st.spinner("Running analysis"):
                # Run the analysis
                state = run_genome_analysis(narrative_id, reads_id, description, st.session_state.credentials)
                
                # Save to history
                st.session_state.analysis_history.append({
                    "timestamp": str(pd.Timestamp.now()),
                    "narrative_id": narrative_id,
                    "reads_id": reads_id,
                    "state": state
                })
                
                # Display results
                display_results(state)
        
        # Show previous runs
        if st.session_state.analysis_history:
            st.subheader("Previous Analyses")
            for i, analysis in enumerate(reversed(st.session_state.analysis_history[-5:])):
                with st.expander(f"Analysis {len(st.session_state.analysis_history) - i}: {analysis['timestamp']}"):
                    st.write(f"**Narrative ID:** {analysis['narrative_id']}")
                    st.write(f"**Reads ID:** {analysis['reads_id']}")
                    display_results(analysis['state'])
    
    with tab2:
        st.subheader("About KBase Reasearch Agent")
        st.write("""
        This application provides a streamlined interface for running analyses on the KBase platform. 
        The workflow integrates several key steps:
        
        1. **Analysis Planning**: An AI-powered analyst determines the optimal workflow for your genomic data
        2. **Workflow Execution**: The system executes the planned applications in sequence
        3. **Results Visualization**: View and interpret your results directly in this interface
        
        The pipeline is built on KBase's extensive library of bioinformatics applications and is designed to simplify complex genomic analyses.
        """)
        
        st.subheader("Technical Architecture")
        st.write("""
        This Streamlit app interfaces with several underlying technologies:
        
        - **CrewAI**: Orchestrates intelligent agents for workflow planning and execution
        - **LangGraph**: Manages the state transitions in the analysis workflow
        - **KBase API**: Connects to the DOE KBase platform for bioinformatics tool execution
        - **LLM Integration**: Uses large language models to determine optimal analysis strategies
        """)
        
        st.image("https://kbase.us/wp-content/uploads/2021/06/kbase-logo-full.png", width=300)
        
    with tab3:
        display_connection_test()
        display_debug_info()


# Required for pandas import above
import pandas as pd

if __name__ == "__main__":
    main()