import streamlit as st
import os
import re
import json
from typing import List, Dict, Any, Optional
import pandas as pd

# Set page config
st.set_page_config(
    page_title="KBase Research Agent",
    page_icon="🧬",
    layout="wide"
)


# KBase Integration Classes
@st.cache_resource
def load_kbase_classes():
    """Load and cache KBase classes"""
    try:
        from narrative_llm_agent.workflow_graph.graph import AnalysisWorkflow
        from narrative_llm_agent.writer_graph.mra_graph import MraWriterGraph
        from narrative_llm_agent.writer_graph.summary_graph import SummaryWriterGraph
        from narrative_llm_agent.kbase.clients.workspace import Workspace
        from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
        
        return True, {
            "AnalysisWorkflow": AnalysisWorkflow,
            "MraWriterGraph": MraWriterGraph,
            "SummaryWriterGraph": SummaryWriterGraph,
            "Workspace": Workspace,
            "ExecutionEngine": ExecutionEngine
        }
    except ImportError as e:
        return False, f"ImportError: {str(e)}"
    except Exception as e:
        return False, f"Error loading KBase classes: {str(e)}"

# MRA Generation function
def generate_mra_draft(narrative_id, credentials):
    """Generate MRA draft using the MraWriterGraph"""
    try:
        # Set environment variables
        kb_auth_token = credentials.get("kb_auth_token", "")
        provider = credentials.get("provider", "openai")
        
        if provider == "cborg":
            api_key = credentials.get("cborg_api_key", os.environ.get("CBORG_API_KEY", ""))
        else:
            api_key = credentials.get("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))

        # Set environment variables
        os.environ["KB_AUTH_TOKEN"] = kb_auth_token
        if provider == "cborg":
            os.environ["CBORG_API_KEY"] = api_key
        else:
            os.environ["OPENAI_API_KEY"] = api_key
        
        # Set Neo4j environment variables if they exist
        neo4j_uri = credentials.get("neo4j_uri", os.environ.get("NEO4J_URI", ""))
        neo4j_username = credentials.get("neo4j_username", os.environ.get("NEO4J_USERNAME", ""))
        neo4j_password = credentials.get("neo4j_password", os.environ.get("NEO4J_PASSWORD", ""))

        if neo4j_uri:
            os.environ["NEO4J_URI"] = neo4j_uri
        if neo4j_username:
            os.environ["NEO4J_USERNAME"] = neo4j_username
        if neo4j_password:
            os.environ["NEO4J_PASSWORD"] = neo4j_password

        # Load the KBase classes
        success, result = load_kbase_classes()
        if not success:
            return {
                "mra_draft": None,
                "error": result
            }

        MraWriterGraph = result["MraWriterGraph"]
        Workspace = result["Workspace"]
        ExecutionEngine = result["ExecutionEngine"]

        # Display progress
        progress_placeholder = st.empty()
        progress_placeholder.info("📝 Initializing MRA writer...")

        # Create KBase clients
        with st.spinner("Creating KBase clients..."):
            ws_client = Workspace()
            ee_client = ExecutionEngine()

        # Create MRA writer
        with st.spinner("Initializing MRA writer..."):
            mra_writer = MraWriterGraph(ws_client, ee_client)

        progress_placeholder.info("📝 Generating MRA draft...")

        # Run the MRA workflow
        with st.spinner("Generating MRA draft... This may take several minutes..."):
            mra_result = mra_writer.run_workflow(narrative_id)

        progress_placeholder.success("✅ MRA draft generated successfully")

        return {
            "mra_draft": mra_result,
            "error": None
        }

    except Exception as e:
        st.error(f"Error generating MRA draft: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return {
            "mra_draft": None,
            "error": str(e)
        }
def run_genome_analysis(narrative_id, reads_id, description, credentials):
    """Run the genome analysis using the refactored workflow"""
    try:
        # Get credentials and set environment variables
        kb_auth_token = credentials.get("kb_auth_token", "")
        provider = credentials.get("provider", "openai")
        
        if provider == "cborg":
            api_key = credentials.get("cborg_api_key", os.environ.get("CBORG_API_KEY", ""))
        else:
            api_key = credentials.get("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))

        # Set environment variables
        os.environ["KB_AUTH_TOKEN"] = kb_auth_token
        if provider == "cborg":
            os.environ["CBORG_API_KEY"] = api_key
        else:
            os.environ["OPENAI_API_KEY"] = api_key
        
        # Set Neo4j environment variables if they exist
        neo4j_uri = credentials.get("neo4j_uri", os.environ.get("NEO4J_URI", ""))
        neo4j_username = credentials.get("neo4j_username", os.environ.get("NEO4J_USERNAME", ""))
        neo4j_password = credentials.get("neo4j_password", os.environ.get("NEO4J_PASSWORD", ""))

        if neo4j_uri:
            os.environ["NEO4J_URI"] = neo4j_uri
        if neo4j_username:
            os.environ["NEO4J_USERNAME"] = neo4j_username
        if neo4j_password:
            os.environ["NEO4J_PASSWORD"] = neo4j_password

        # Load the KBase classes
        success, result = load_kbase_classes()
        if not success:
            return {
                "narrative_id": narrative_id,
                "reads_id": reads_id,
                "description": description,
                "analysis_plan": None,
                "results": None,
                "error": result
            }

        AnalysisWorkflow = result["AnalysisWorkflow"]

        # Create workflow instance
        with st.spinner("Initializing workflow..."):
            custom_workflow = AnalysisWorkflow()

        # Display progress
        progress_placeholder = st.empty()
        progress_placeholder.info("🔬 Running analysis workflow...")

        # Run the workflow
        with st.spinner("Running analysis..."):
            workflow_result = custom_workflow.run(
                narrative_id=narrative_id,
                reads_id=reads_id,
                description=description
            )

        progress_placeholder.success("✅ Analysis completed successfully")

        # Extract results from workflow
        if hasattr(workflow_result, 'get'):
            # If it's a dict-like object
            analysis_plan = workflow_result.get("analysis_plan")
            results = workflow_result.get("results")
            error = workflow_result.get("error")
        else:
            # If it's a different type of object, try to extract what we can
            analysis_plan = getattr(workflow_result, 'analysis_plan', None)
            results = getattr(workflow_result, 'results', workflow_result)
            error = getattr(workflow_result, 'error', None)

        return {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "analysis_plan": analysis_plan,
            "results": results,
            "error": error
        }

    except Exception as e:
        st.error(f"Error in genome analysis: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "analysis_plan": None,
            "results": None,
            "error": str(e)
        }

# UI Components
def display_provider_selection():
    """Display provider selection dropdown"""
    provider = st.selectbox(
        "LLM Provider",
        options=["openai", "cborg"],
        index=0 if st.session_state.get("provider", "openai") == "openai" else 1,
        format_func=lambda x: "OpenAI" if x == "openai" else "CBORG (LBL)"
    )

    # Update session state when provider changes
    if st.session_state.get("provider") != provider:
        st.session_state.provider = provider

    return provider

def display_credentials_form():
    """Display credentials input form"""
    with st.expander("🔑 KBase Credentials", expanded=True):
        # Provider selection
        provider = display_provider_selection()

        # KB Auth Token input
        kb_auth_token = st.text_input("KB Auth Token",
                                    value=st.session_state.get("kb_auth_token", ""),
                                    type="password",
                                    help="Your KBase authentication token")

        # API Key input based on provider
        if provider == "cborg":
            api_key = st.text_input("CBORG API Key",
                                    value=st.session_state.get("cborg_api_key", os.environ.get("CBORG_API_KEY", "")),
                                    type="password",
                                    help="Your CBORG API key for LBL services")
        else:
            api_key = st.text_input("OpenAI API Key",
                                    value=st.session_state.get("openai_api_key", os.environ.get("OPENAI_API_KEY", "")),
                                    type="password",
                                    help="Your OpenAI API key")

        # Save credentials button
        if st.button("Save Credentials"):
            st.session_state.credentials = {
                "neo4j_uri": os.environ.get("NEO4J_URI", ""),
                "neo4j_username": os.environ.get("NEO4J_USERNAME", ""),
                "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
                "provider": provider,
                "kb_auth_token": kb_auth_token,
            }
            
            # Add the appropriate API key
            if provider == "cborg":
                st.session_state.credentials["cborg_api_key"] = api_key
            else:
                st.session_state.credentials["openai_api_key"] = api_key

            # Save individual values for convenience
            st.session_state.neo4j_uri = os.environ.get("NEO4J_URI", "")
            st.session_state.neo4j_username = os.environ.get("NEO4J_USERNAME", "")
            st.session_state.neo4j_password = os.environ.get("NEO4J_PASSWORD", "")
            st.session_state.kb_auth_token = kb_auth_token
            st.session_state.provider = provider
            st.session_state[f"{provider}_api_key"] = api_key

            st.success("Credentials saved to session!")

    # Initialize credentials if not already done
    if not st.session_state.get("credentials"):
        provider = st.session_state.get("provider", "openai")
        st.session_state.credentials = {
            "neo4j_uri": os.environ.get("NEO4J_URI", ""),
            "neo4j_username": os.environ.get("NEO4J_USERNAME", ""),
            "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
            "kb_auth_token": kb_auth_token if 'kb_auth_token' in locals() else "",
            "provider": provider,
        }
        
        # Add appropriate API key
        if provider == "cborg":
            st.session_state.credentials["cborg_api_key"] = api_key if 'api_key' in locals() else os.environ.get("CBORG_API_KEY", "")
        else:
            st.session_state.credentials["openai_api_key"] = api_key if 'api_key' in locals() else os.environ.get("OPENAI_API_KEY", "")

def display_input_form():
    """Display input form for analysis parameters"""
    st.subheader("📝 Analysis Parameters")

    # Create columns for better layout
    col1, col2 = st.columns(2)
    
    with col1:
        narrative_id = st.text_input("Narrative ID", value="217789", help="KBase narrative ID where your data is stored")
        reads_id = st.text_input("Reads ID", value="217789/2/1", help="UPA of the reads object in KBase")
    
    with col2:
        sequencing_technology = st.selectbox("Sequencing Technology", 
                                           options=["Illumina sequencing", "PacBio", "Oxford Nanopore"],
                                           help="Technology used for sequencing")
        organism = st.text_input("Organism", value="Bacillus subtilis sp. strain UAMC", 
                                help="Name of the organism being analyzed")
        genome_type = st.selectbox("Genome Type", 
                                 options=["isolate", "metagenome", "transcriptome"],
                                 help="Type of genome data")

    # Generate description based on inputs
    description = st.text_area("Analysis Description", height=200,
                               value=f"""The user has uploaded paired-end sequencing reads into the narrative. Here is the metadata for the reads:
sequencing_technology: {sequencing_technology}
organism: {organism}
genome type: {genome_type}

I want you to generate an analysis plan for annotating the uploaded pair-end reads obtained from {sequencing_technology} for a {genome_type} genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe.""")

    return narrative_id, reads_id, description

def display_results(state, show_mra_button=False, narrative_id=None, key_suffix=""):
    """Display analysis results"""
    st.subheader("📊 Analysis Results")

    # Display analysis plan if available
    if state.get("analysis_plan"):
        st.subheader("📋 Analysis Plan")
        
        # Create a formatted table for the analysis steps
        analysis_plan = state["analysis_plan"]
        if isinstance(analysis_plan, list) and len(analysis_plan) > 0:
            # Create DataFrame for better display
            df_data = []
            for step in analysis_plan:
                df_data.append({
                    "Step": step.get("Step", "N/A"),
                    "Name": step.get("Name", "N/A"),
                    "Description": step.get("Description", "N/A")[:100] + "..." if len(step.get("Description", "")) > 100 else step.get("Description", "N/A"),
                    "App ID": step.get("app_id", "N/A"),
                    "Creates Object": "Yes" if step.get("expect_new_object", False) else "No"
                })
            
            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True)
            
            # Show detailed steps in expandable sections
            st.subheader("📝 Detailed Steps")
            for step in analysis_plan:
                with st.expander(f"Step {step.get('Step', 'N/A')}: {step.get('Name', 'Unnamed Step')}"):
                    st.write(f"**Description:** {step.get('Description', 'No description available')}")
                    st.write(f"**App ID:** `{step.get('app_id', 'N/A')}`")
                    st.write(f"**Creates New Object:** {'Yes' if step.get('expect_new_object', False) else 'No'}")

    # Display workflow results if available
    if state.get("results"):
        st.subheader("🧪 Workflow Results")
        
        results = state["results"]
        if isinstance(results, dict):
            # Handle structured results
            for key, value in results.items():
                if key in ["summary", "status"]:
                    st.success(f"**{key.title()}:** {value}")
                elif key == "apps_run":
                    st.metric("Apps Run", value)
                elif key == "output_objects":
                    st.subheader("Output Objects")
                    if isinstance(value, list):
                        for obj in value:
                            st.code(str(obj))
                    else:
                        st.code(str(value))
                else:
                    st.write(f"**{key}:** {value}")
        elif hasattr(results, 'raw'):
            # Handle CrewAI result objects
            st.write("**Workflow Result:**")
            st.text_area("Results", value=str(results.raw), height=200)
        else:
            # Handle other result types
            st.text_area("Results", value=str(results), height=200,key=f"results_text_area_{key_suffix}")

    # Display errors if any
    if state.get("error"):
        st.error(f"❌ Error: {state['error']}")
    
    # Show MRA generation button if analysis completed successfully
    if show_mra_button and state.get("results") and not state.get("error") and narrative_id:
        st.divider()
        st.subheader("📄 Generate MRA Draft")
        st.info("Analysis completed successfully! You can now generate a Microbiology Resource Announcements (MRA) draft paper.")
        
        if st.button("📝 Generate MRA Draft", type="primary"):
            with st.spinner("Generating MRA draft..."):
                mra_result = generate_mra_draft(narrative_id, st.session_state.credentials)
                
                if mra_result.get("error"):
                    st.error(f"❌ Error generating MRA draft: {mra_result['error']}")
                else:
                    st.success("✅ MRA draft generated successfully!")
                    
                    # Display MRA draft
                    st.subheader("📄 MRA Draft")
                    mra_draft = mra_result.get("mra_draft")
                    
                    if isinstance(mra_draft, dict):
                        # Handle structured MRA result
                        for section, content in mra_draft.items():
                            st.subheader(f"📝 {section.title()}")
                            st.write(content)
                    elif hasattr(mra_draft, 'raw'):
                        # Handle CrewAI result objects
                        st.text_area("MRA Draft", value=str(mra_draft.raw), height=400)
                    else:
                        # Handle other result types
                        st.text_area("MRA Draft", value=str(mra_draft), height=400,key=f"mra_draft_area_{key_suffix}")
                    
                    # Add download button for the MRA draft
                    if mra_draft:
                        mra_text = str(mra_draft.raw) if hasattr(mra_draft, 'raw') else str(mra_draft)
                        st.download_button(
                            label="📥 Download MRA Draft",
                            data=mra_text,
                            file_name=f"mra_draft_narrative_{narrative_id}.txt",
                            mime="text/plain"
                        )

def display_connection_test():
    """Display connection test functionality"""
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
                    st.info("Make sure the required libraries are installed: `narrative_llm_agent`")
                    return

            # Test workflow initialization
            with st.spinner("Testing workflow initialization..."):
                try:
                    AnalysisWorkflow = result["AnalysisWorkflow"]
                    test_workflow = AnalysisWorkflow()
                    st.success("✅ Successfully initialized AnalysisWorkflow")
                except Exception as e:
                    st.error(f"❌ Failed to initialize workflow: {str(e)}")
                    return

            st.success("✅ All connections successful! You're ready to run analyses.")

        except Exception as e:
            st.error(f"❌ Connection test failed: {str(e)}")

def display_debug_info():
    """Display debug information"""
    st.subheader("🐛 Debug Information")

    with st.expander("Show Environment Variables", expanded=False):
        env_vars = {
            "NEO4J_URI": os.environ.get("NEO4J_URI", "Not set"),
            "NEO4J_USERNAME": os.environ.get("NEO4J_USERNAME", "Not set"),
            "KB_AUTH_TOKEN": "***" if os.environ.get("KB_AUTH_TOKEN") else "Not set",
            "CBORG_API_KEY": "***" if os.environ.get("CBORG_API_KEY") else "Not set",
            "OPENAI_API_KEY": "***" if os.environ.get("OPENAI_API_KEY") else "Not set"
        }

        for key, value in env_vars.items():
            st.code(f"{key}: {value}")

    with st.expander("Show Session State", expanded=False):
        # Show session state (excluding sensitive information)
        safe_session_state = {}
        for key, value in st.session_state.items():
            if "api_key" in key.lower() or "token" in key.lower() or "password" in key.lower():
                safe_session_state[key] = "***" if value else "Not set"
            else:
                safe_session_state[key] = value
        
        st.json(safe_session_state)

# Main app
def main():
    """Main Streamlit application"""
    # Initialize session state
    if 'credentials' not in st.session_state:
        st.session_state.credentials = {}
    if 'analysis_history' not in st.session_state:
        st.session_state.analysis_history = []

    st.title("🧬 KBase Research Agent")
    

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["🔬 Run Analysis", "ℹ️ About", "🔧 Connection Test"])

    with tab1:
        display_credentials_form()

        # Input form
        narrative_id, reads_id, description = display_input_form()

        # Check dependencies
        try:
            from narrative_llm_agent.workflow_graph.graph import AnalysisWorkflow
            has_dependencies = True
        except ImportError:
            has_dependencies = False
            st.warning("⚠️ KBase libraries not found. Please install the required dependencies.")

        # Run analysis button
        run_button = st.button("🚀 Run Analysis", type="primary", disabled=not has_dependencies)

        if run_button:
            if not st.session_state.get("credentials", {}).get("kb_auth_token"):
                st.error("Please enter your KB Auth Token in the credentials section.")
            else:
                with st.spinner("Running genome analysis..."):
                    # Run the analysis
                    state = run_genome_analysis(narrative_id, reads_id, description, st.session_state.credentials)

                    # Save to history
                    st.session_state.analysis_history.append({
                        "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "narrative_id": narrative_id,
                        "reads_id": reads_id,
                        "state": state
                    })

                    # Display results
                    display_results(state)

        # Show previous analyses
        if st.session_state.analysis_history:
            st.subheader("📚 Previous Analyses")
            
            # Show only the last 5 analyses
            recent_analyses = list(reversed(st.session_state.analysis_history[-5:]))
            
            for i, analysis in enumerate(recent_analyses):
                analysis_num = len(st.session_state.analysis_history) - i
                with st.expander(f"Analysis #{analysis_num} - {analysis['timestamp']}"):
                    st.write(f"**Narrative ID:** {analysis['narrative_id']}")
                    st.write(f"**Reads ID:** {analysis['reads_id']}")
                    display_results(analysis['state'],key_suffix=f"{analysis_num}")

    with tab2:
        st.subheader("About KBase Research Agent")
        st.write("""
        This application provides a streamlined interface for running automated analysis workflows on the KBase platform.
        The system uses LLM agents to plan and execute complex bioinformatics analyses.

        ### Key Features:
        - **Automated Workflow Planning**: AI determines the optimal sequence of analysis steps
        - **KBase Integration**: Direct integration with DOE KBase platform and applications  
        - **Multi-Provider LLM Support**: Works with OpenAI and CBORG (LBL) language models
        - **Analysis History**: Track and review previous analyses
        - **Real-time Progress**: Monitor workflow execution in real-time

        ### Workflow Steps:
        1. **Data Input**: Specify your KBase narrative and reads data
        2. **AI Planning**: The system analyzes your sample metadata and creates an optimal workflow
        3. **Execution**: KBase applications are run automatically in sequence
        4. **Results**: View comprehensive analysis results and generated data objects
        """)

        st.image("KBase_Logo.png", width=300)

    with tab3:
        display_connection_test()
        display_debug_info()

if __name__ == "__main__":
    main()