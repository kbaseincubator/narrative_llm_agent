def get_processed_app_spec_params(app_spec: dict) -> dict:
    """
    This processes the given KBase app spec and returns the
    parameter structure out of it in a way that a fairly dim LLM
    can populate it. Hopefully.
    TODO: build an AppSpec class that maintains the structure. But, YAGNI.
    """
    return {}

def process_app_params(app_spec: dict, params: dict) -> dict:
    """
    Processes the given parameters to run the app. This returns
    the validated structure that can be passed along to the Execution
    Engine.
    """
    return {}

def build_run_job_params(app_spec: dict, params: dict, narrative_id: int) -> dict:
    """
    This process the parameters along with the app spec to build the
    packet that gets sent to the Execution Engine's run_job command.
    This also creates a cell_id and run_id and various other required metadata.
    """
    return {}
