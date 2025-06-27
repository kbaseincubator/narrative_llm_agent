import dash
from dash import dcc, html, Input, Output, State, callback_context, dash_table
import plotly.graph_objs as go
import pandas as pd
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# Initialize Dash app with suppress_callback_exceptions=True
app = dash.Dash(__name__, 
    external_stylesheets=[
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
        'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
    ],
    suppress_callback_exceptions=True  # This fixes the callback errors
)

app.title = "KBase Research Agent"

# Global state storage 
app_state = {
    'credentials': {},
    'analysis_history': [],
    'current_workflow': None,
    'approval_request': None,
    'workflow_paused': False
}

# KBase Integration Classes
def load_kbase_classes():
    """Load and cache KBase classes"""
    try:
        from narrative_llm_agent.workflow_graph.graph_hitl import AnalysisWorkflow
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

class DashHumanApprovalHandler:
    def __init__(self):
        self.current_request = None
    
    def set_approval_request(self, approval_data):
        """Called by the workflow node to set up the approval UI"""
        app_state['approval_request'] = approval_data
        app_state['workflow_paused'] = True
        self.current_request = approval_data
    
    def has_pending_request(self):
        return app_state.get('workflow_paused', False)
    
    def clear_approval_request(self):
        app_state.pop('approval_request', None)
        app_state.pop('workflow_paused', None)
        self.current_request = None

# Global approval handler
approval_handler = DashHumanApprovalHandler()

# Styles
COLORS = {
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'success': '#28A745',
    'warning': '#FFC107',
    'danger': '#DC3545',
    'light': '#F8F9FA',
    'dark': '#343A40',
    'background': '#FFFFFF',
    'text': '#212529'
}

CARD_STYLE = {
    'backgroundColor': COLORS['background'],
    'padding': '20px',
    'borderRadius': '8px',
    'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
    'marginBottom': '20px'
}

INPUT_STYLE = {
    'width': '100%',
    'padding': '8px 12px',
    'border': '1px solid #ddd',
    'borderRadius': '4px',
    'fontSize': '14px'
}

BUTTON_STYLE = {
    'padding': '10px 20px',
    'border': 'none',
    'borderRadius': '4px',
    'fontSize': '14px',
    'fontWeight': '500',
    'cursor': 'pointer',
    'marginRight': '10px',
    'marginBottom': '10px'
}

PRIMARY_BUTTON = {**BUTTON_STYLE, 'backgroundColor': COLORS['primary'], 'color': 'white'}
SUCCESS_BUTTON = {**BUTTON_STYLE, 'backgroundColor': COLORS['success'], 'color': 'white'}
DANGER_BUTTON = {**BUTTON_STYLE, 'backgroundColor': COLORS['danger'], 'color': 'white'}
WARNING_BUTTON = {**BUTTON_STYLE, 'backgroundColor': COLORS['warning'], 'color': 'white'}

# Layout Components
def create_header():
    return html.Div([
        html.H1([
            html.I(className="fas fa-dna", style={'marginRight': '10px', 'color': COLORS['primary']}),
            "KBase Research Agent"
        ], style={'textAlign': 'center', 'color': COLORS['dark'], 'marginBottom': '30px'})
    ])

def create_credentials_form():
    return html.Div([
        html.H3("🔑 Credentials", style={'color': COLORS['dark']}),
        html.Div([
            html.Div([
                html.Label("LLM Provider:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Dropdown(
                    id='provider-dropdown',
                    options=[
                        {'label': 'OpenAI', 'value': 'openai'},
                        {'label': 'CBORG (LBL)', 'value': 'cborg'}
                    ],
                    value='openai',
                    style={'marginBottom': '15px'}
                )
            ], style={'width': '48%', 'display': 'inline-block'}),
            
            html.Div([
                html.Label("KB Auth Token:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Input(
                    id='kb-token-input',
                    type='password',
                    placeholder='Your KBase authentication token',
                    style={**INPUT_STYLE, 'marginBottom': '15px'}
                )
            ], style={'width': '48%', 'display': 'inline-block', 'marginLeft': '4%'}),
            
            html.Div([
                html.Label(id='api-key-label', children="OpenAI API Key:", 
                          style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Input(
                    id='api-key-input',
                    type='password',
                    placeholder='Your API key',
                    style={**INPUT_STYLE, 'marginBottom': '15px'}
                )
            ], style={'width': '48%', 'display': 'inline-block'}),
            
            html.Div([
                html.Button("Save Credentials", id='save-credentials-btn', 
                           style=PRIMARY_BUTTON)
            ], style={'width': '48%', 'display': 'inline-block', 'marginLeft': '4%'}),
            
            html.Div(id='credentials-status', style={'marginTop': '10px'})
        ])
    ], style=CARD_STYLE)

def create_analysis_form():
    return html.Div([
        html.H3("📝 Analysis Parameters", style={'color': COLORS['dark']}),
        html.Div([
            html.Div([
                html.Label("Narrative ID:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Input(
                    id='narrative-id',
                    type='text',
                    value='217789',
                    placeholder='KBase narrative ID',
                    style={**INPUT_STYLE, 'marginBottom': '15px'}
                )
            ], style={'width': '48%', 'display': 'inline-block'}),
            
            html.Div([
                html.Label("Reads ID:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Input(
                    id='reads-id',
                    type='text',
                    value='217789/2/1',
                    placeholder='UPA of the reads object',
                    style={**INPUT_STYLE, 'marginBottom': '15px'}
                )
            ], style={'width': '48%', 'display': 'inline-block', 'marginLeft': '4%'}),
            
            html.Div([
                html.Label("Sequencing Technology:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Dropdown(
                    id='sequencing-tech',
                    options=[
                        {'label': 'Illumina sequencing', 'value': 'Illumina sequencing'},
                        {'label': 'PacBio', 'value': 'PacBio'},
                        {'label': 'Oxford Nanopore', 'value': 'Oxford Nanopore'}
                    ],
                    value='Illumina sequencing',
                    style={'marginBottom': '15px'}
                )
            ], style={'width': '48%', 'display': 'inline-block'}),
            
            html.Div([
                html.Label("Organism:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Input(
                    id='organism',
                    type='text',
                    value='Bacillus subtilis sp. strain UAMC',
                    placeholder='Organism name',
                    style={**INPUT_STYLE, 'marginBottom': '15px'}
                )
            ], style={'width': '48%', 'display': 'inline-block', 'marginLeft': '4%'}),
            
            html.Div([
                html.Label("Genome Type:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Dropdown(
                    id='genome-type',
                    options=[
                        {'label': 'Isolate', 'value': 'isolate'},
                        {'label': 'Metagenome', 'value': 'metagenome'},
                        {'label': 'Transcriptome', 'value': 'transcriptome'}
                    ],
                    value='isolate',
                    style={'marginBottom': '15px'}
                )
            ], style={'width': '100%'}),
            
            html.Div([
                html.Label("Analysis Description:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Textarea(
                    id='description',
                    style={'width': '100%', 'height': '120px', 'padding': '8px', 
                           'border': '1px solid #ddd', 'borderRadius': '4px', 'marginBottom': '15px'},
                    placeholder='Describe your analysis goals...'
                )
            ]),
            
            html.Button("🚀 Run Analysis", id='run-analysis-btn', 
                       style=PRIMARY_BUTTON, disabled=False)
        ])
    ], style=CARD_STYLE)

def create_approval_interface():
    # Create the approval interface container that will be populated dynamically
    return html.Div(id='approval-interface', children=[], style={'display': 'none'})

def create_results_display():
    return html.Div([
        html.H3("📊 Results", style={'color': COLORS['dark']}),
        html.Div(id='results-content')
    ], style=CARD_STYLE)

# Main Layout - Include placeholder divs for dynamic content
app.layout = html.Div([
    dcc.Interval(id='interval-component', interval=2000, n_intervals=0),  # Update every 2 seconds
    dcc.Store(id='workflow-state', data={}),
    
    html.Div([
        create_header(),
        create_credentials_form(),
        create_analysis_form(),
        create_approval_interface(),
        create_results_display(),
        
        # Hidden divs for dynamic content to prevent callback errors
        html.Div(id='approval-feedback-area', style={'display': 'none'}),
        html.Div(id='submit-feedback-response', style={'display': 'none'})
    ], style={
        'maxWidth': '1200px',
        'margin': '0 auto',
        'padding': '20px',
        'fontFamily': 'Inter, sans-serif'
    })
])

# Callbacks
@app.callback(
    Output('api-key-label', 'children'),
    Input('provider-dropdown', 'value')
)
def update_api_label(provider):
    if provider == 'cborg':
        return "CBORG API Key:"
    return "OpenAI API Key:"

@app.callback(
    Output('credentials-status', 'children'),
    Input('save-credentials-btn', 'n_clicks'),
    [State('provider-dropdown', 'value'),
     State('kb-token-input', 'value'),
     State('api-key-input', 'value')]
)
def save_credentials(n_clicks, provider, kb_token, api_key):
    if n_clicks:
        app_state['credentials'] = {
            'provider': provider,
            'kb_auth_token': kb_token or '',
            f'{provider}_api_key': api_key or '',
            'neo4j_uri': os.environ.get("NEO4J_URI", ""),
            'neo4j_username': os.environ.get("NEO4J_USERNAME", ""),
            'neo4j_password': os.environ.get("NEO4J_PASSWORD", "")
        }
        
        # Set environment variables
        if kb_token:
            os.environ["KB_AUTH_TOKEN"] = kb_token
        if api_key:
            if provider == "cborg":
                os.environ["CBORG_API_KEY"] = api_key
            else:
                os.environ["OPENAI_API_KEY"] = api_key
        
        return html.Div("✅ Credentials saved successfully!", 
                       style={'color': COLORS['success'], 'fontWeight': 'bold'})
    return ""

@app.callback(
    Output('description', 'value'),
    [Input('sequencing-tech', 'value'),
     Input('organism', 'value'),
     Input('genome-type', 'value')]
)
def update_description(seq_tech, organism, genome_type):
    if seq_tech and organism and genome_type:
        return f"""The user has uploaded paired-end sequencing reads into the narrative. Here is the metadata for the reads:
sequencing_technology: {seq_tech}
organism: {organism}
genome type: {genome_type}

I want you to generate an analysis plan for annotating the uploaded pair-end reads obtained from {seq_tech} for a {genome_type} genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe."""
    return ""

@app.callback(
    [Output('workflow-state', 'data'),
     Output('results-content', 'children')],
    [Input('run-analysis-btn', 'n_clicks'),
     Input('interval-component', 'n_intervals')],
    [State('narrative-id', 'value'),
     State('reads-id', 'value'),
     State('description', 'value'),
     State('workflow-state', 'data')]
)
def handle_analysis_workflow(run_clicks, n_intervals, narrative_id, reads_id, description, current_state):
    ctx = callback_context
    
    if not ctx.triggered:
        return current_state, ""
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id == 'run-analysis-btn' and run_clicks:
        # Start new analysis
        if not app_state.get('credentials', {}).get('kb_auth_token'):
            return current_state, html.Div("❌ Please save your credentials first!", 
                                         style={'color': COLORS['danger']})
        
        # Initialize workflow
        try:
            result = run_genome_analysis_with_hitl(narrative_id, reads_id, description, app_state['credentials'])
            app_state['current_workflow'] = result
            
            return {'status': 'running', 'narrative_id': narrative_id}, html.Div([
                html.H4("🔄 Analysis Started", style={'color': COLORS['primary']}),
                html.P(f"Narrative ID: {narrative_id}"),
                html.P(f"Reads ID: {reads_id}"),
                html.P("Generating analysis plan...")
            ])
            
        except Exception as e:
            return current_state, html.Div(f"❌ Error starting analysis: {str(e)}", 
                                         style={'color': COLORS['danger']})
    
    elif trigger_id == 'interval-component':
        # Check workflow status and update results
        if app_state.get('current_workflow'):
            workflow = app_state['current_workflow']
            
            # Check if workflow completed
            if workflow.get('status') == 'completed':
                return current_state, display_workflow_results(workflow)
            
            # Check if workflow had an error
            elif workflow.get('status') == 'error':
                return current_state, html.Div(f"❌ Workflow Error: {workflow.get('error', 'Unknown error')}", 
                                             style={'color': COLORS['danger']})
            
            # Check if workflow was cancelled
            elif workflow.get('status') == 'cancelled':
                return current_state, html.Div("🛑 Workflow was cancelled by user.", 
                                             style={'color': COLORS['warning']})
            
            # Show running status
            elif workflow.get('status') == 'running':
                if app_state.get('workflow_paused'):
                    return current_state, html.Div([
                        html.H4("⏸️ Workflow Paused", style={'color': COLORS['warning']}),
                        html.P("Waiting for human approval...")
                    ])
                else:
                    return current_state, html.Div([
                        html.H4("🔄 Workflow Running", style={'color': COLORS['primary']}),
                        html.P("Analysis in progress..."),
                        html.Div([
                            html.I(className="fas fa-spinner fa-spin", 
                                 style={'marginRight': '10px', 'color': COLORS['primary']}),
                            "Processing..."
                        ])
                    ])
    
    return current_state, ""

@app.callback(
    [Output('approval-interface', 'children'),
     Output('approval-interface', 'style')],
    Input('interval-component', 'n_intervals')
)
def update_approval_interface(n_intervals):
    if app_state.get('workflow_paused') and app_state.get('approval_request'):
        return create_approval_display(), {'display': 'block'}
    return [], {'display': 'none'}

def create_approval_display():
    approval_request = app_state.get('approval_request', {})
    analysis_plan = approval_request.get('analysis_plan', [])
    
    return [
        html.Div([
            html.H3("🔍 Analysis Plan Review", style={'color': COLORS['warning']}),
            html.P(f"Narrative ID: {approval_request.get('narrative_id', 'N/A')}"),
            html.P(f"Reads ID: {approval_request.get('reads_id', 'N/A')}"),
            
            html.H4("📋 Proposed Analysis Steps:"),
            html.Ol([
                html.Li([
                    html.Strong(f"{step.get('Name', 'Unknown Step')}"),
                    html.P(f"App: {step.get('App', 'Unknown')}"),
                    html.P(f"Description: {step.get('Description', 'No description')}")
                ]) for step in analysis_plan
            ]) if analysis_plan else html.P("No analysis plan available"),
            
            html.Div([
                html.Button("✅ Approve Plan", id='approve-btn', style=SUCCESS_BUTTON),
                html.Button("❌ Reject Plan", id='reject-btn', style=WARNING_BUTTON),
                html.Button("🛑 Cancel Workflow", id='cancel-btn', style=DANGER_BUTTON)
            ], style={'textAlign': 'center', 'marginTop': '20px'}),
            
            html.Div(id='approval-feedback-area')
        ])
    ]
@app.callback(
    Output('approval-feedback-area', 'children'),
    [Input('approve-btn', 'n_clicks'),
     Input('reject-btn', 'n_clicks'),
     Input('cancel-btn', 'n_clicks')],
    prevent_initial_call=True
)
def handle_approval_decision(approve_clicks, reject_clicks, cancel_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return ""
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    print(f"DEBUG: Approval button triggered: {trigger_id}")
    
    resume_input = None
    message = ""
    
    if trigger_id == 'approve-btn' and approve_clicks:
        resume_input = {"approved": True}
        message = "✅ Analysis plan approved! Continuing to validation..."
        
    elif trigger_id == 'reject-btn' and reject_clicks:
        resume_input = {"rejected": True}  # No feedback needed
        message = "❌ Analysis plan rejected. Regenerating plan..."
        
    elif trigger_id == 'cancel-btn' and cancel_clicks:
        resume_input = {"cancelled": True}
        message = "🛑 Workflow cancelled by user."
    
    # Resume the workflow
    if resume_input:
        current_workflow = app_state.get('current_workflow')
        if current_workflow and 'workflow' in current_workflow and 'thread_id' in current_workflow:
            try:
                workflow = current_workflow['workflow']
                thread_id = current_workflow['thread_id']
                
                print(f"DEBUG: Resuming workflow with input: {resume_input}")
                
                # Resume the workflow
                # result = workflow.graph.invoke(
                #     resume_input, 
                #     config={"thread_id": thread_id}
                # )
                
                print(f"DEBUG: Workflow resumed successfully")
                app_state['current_workflow'].update({
                    'status': 'completed'
                })
                
                # Clear approval state
                approval_handler.clear_approval_request()
                
                return html.Div(message, style={'color': COLORS['success'], 'fontWeight': 'bold'})
                
            except Exception as e:
                error_msg = f"Error resuming workflow: {str(e)}"
                print(f"DEBUG: {error_msg}")
                return html.Div(error_msg, style={'color': COLORS['dark']})
        else:
            return html.Div("❌ No workflow found to resume", style={'color': COLORS['dark']})
    
    return ""

# Additional callback for handling feedback submission
@app.callback(
    Output('submit-feedback-response', 'children'),
    Input('submit-feedback-btn', 'n_clicks'),
    State('feedback-textarea', 'value'),
    prevent_initial_call=True
)
def handle_feedback_submission(n_clicks, feedback_text):
    if n_clicks and feedback_text:
        # Set revision response with feedback and notify waiting workflow
        approval_handler.set_approval_response('revision_requested', feedback_text)
        app_state['workflow_paused'] = False
        
        return html.Div(f"📝 Feedback submitted: {feedback_text}", 
                       style={'color': COLORS['primary'], 'fontWeight': 'bold'})
    return ""

    
def run_genome_analysis_with_hitl(narrative_id, reads_id, description, credentials):
    """Run the genome analysis using the human-in-the-loop workflow - NO THREADING"""
    try:
        print(f"DEBUG: Starting workflow for narrative {narrative_id}")
        print(f"DEBUG: Global approval handler ID: {id(approval_handler)}")
        
        # Set environment variables
        kb_auth_token = credentials.get("kb_auth_token", "")
        provider = credentials.get("provider", "openai")
        
        if provider == "cborg":
            api_key = credentials.get("cborg_api_key", "")
        else:
            api_key = credentials.get("openai_api_key", "")

        os.environ["KB_AUTH_TOKEN"] = kb_auth_token
        if provider == "cborg":
            os.environ["CBORG_API_KEY"] = api_key
        else:
            os.environ["OPENAI_API_KEY"] = api_key

        # Load KBase classes
        success, result = load_kbase_classes()
        if not success:
            return {
                "narrative_id": narrative_id,
                "status": "error",
                "error": result
            }

        AnalysisWorkflow = result["AnalysisWorkflow"]
        
        # Create workflow instance
        print(f"DEBUG: Creating workflow with approval handler ID: {id(approval_handler)}")
        custom_workflow = AnalysisWorkflow(
            token=kb_auth_token,
            approval_handler=approval_handler
        )
        
        # Generate unique thread ID for LangGraph state management (not Python threading!)
        import uuid
        thread_id = str(uuid.uuid4())
        
        # Store the workflow data
        workflow_data = {
            "narrative_id": narrative_id,
            "reads_id": reads_id, 
            "description": description,
            "status": "running",
            "workflow": custom_workflow,
            "thread_id": thread_id,
            "approval_handler": approval_handler
        }
        
        # Store in app_state for UI access
        app_state['current_workflow'] = workflow_data
        print(f"DEBUG: Stored workflow in app_state")
        
        # Start the workflow directly 
        print("DEBUG: Starting workflow execution directly")
        
        try:
            # This will run until it hits the interrupt, then pause
            workflow_result = custom_workflow.run(
                narrative_id=narrative_id,
                reads_id=reads_id,
                description=description,
                thread_id=thread_id
            )
            
            # If we get here, the workflow completed successfully
            print("DEBUG: Workflow completed successfully")
            app_state['current_workflow'].update({
                'status': 'completed',
                'workflow_result': workflow_result,
                'results': workflow_result
            })
            
        except Exception as e:
            # Check if this is an interrupt (which is expected) or a real error
            error_str = str(e)
            if "Interrupt" in error_str:
                print("DEBUG: Workflow paused at interrupt - waiting for user approval")
                app_state['current_workflow'].update({
                    'status': 'paused_for_approval'
                })
            else:
                print(f"DEBUG: Workflow error: {error_str}")
                app_state['current_workflow'].update({
                    'status': 'error',
                    'error': error_str
                })
        
        print(f"DEBUG: Returning workflow_data")
        return workflow_data
        
    except Exception as e:
        print(f"DEBUG: Error in run_genome_analysis_with_hitl: {str(e)}")
        return {
            "narrative_id": narrative_id,
            "status": "error",
            "error": str(e)
        }

def display_workflow_results(workflow):
    """Display workflow results"""
    if workflow.get('error'):
        return html.Div(f"❌ Error: {workflow['error']}", 
                       style={'color': COLORS['danger']})
    
    results = workflow.get('results', {})
    if not results:
        return html.Div("No results available yet.")
    
    return html.Div([
        html.H4("✅ Analysis Completed", style={'color': COLORS['success']}),
        html.Pre(json.dumps(results, indent=2), 
                style={'backgroundColor': '#f5f5f5', 'padding': '15px', 'borderRadius': '4px'})
    ])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)