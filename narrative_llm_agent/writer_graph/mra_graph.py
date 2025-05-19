from langgraph.graph import START, END
from langgraph.graph.state import StateGraph, CompiledStateGraph

from narrative_llm_agent.tools.narrative_tools import get_narrative_state, create_markdown_cell
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine

from narrative_llm_agent.config import get_llm
from langchain_core.prompts import ChatPromptTemplate

from narrative_llm_agent.writer_graph.writeup_state import WriteupState


# Writer agent workflow(s)

# Tasks to do
#     1. Download the narrative (or a reduced version of it), formatted to separate report summaries from apps and output cells
#     2. Summarize the narrative
#         A. to make a brief summary (or)
#         B. to build an MRA paper, following the MRA paper template and rules.
#     3. Format the summary for export, and run the export function.

# So, really, we start with a function call which doesn't need an LLM to run it.
# Feed that as context to the summary / writing prompt.
# Get output and dump that to text, somewhere, as a function. Doesn't need a LLM, either.

# Does this even need to be a graph? Just an LLM call, right?

# Let's go further with it.
# 1. Get narrative. Fine.
# 2. Examine narrative against initial setup. Does it satisfy goals?
#     1. Yes: Go to writeup.
#     2. No: Go to error.
# 3. Writeup - do the thing and return. Go to save.
# 4. Save - write to output whereever.
# 5. Error - Narrative not done (also, not good enough, or not worth summarizing, whatever? Maybe it has errors that mean it shouldn't count?
# 6. End.

# Now we're looking at a Graph workflow.


WRITING_SYSTEM_PROMPT = """You are a scientific writing assistant tasked with interpreting biological data and
composing clear, accurate summaries. Your writing should reflect scientific precision while remaining accessible
to non-specialist readers. Explain key findings, contextualize results, and highlight biological significance using
well-structured, concise language. Avoid jargon where possible, and define any necessary technical terms. Tailor
tone and detail to a professional yet readable standard, suitable for reports, research summaries, or funding
communications."""

MRA_WRITING_PROMPT = """This KBase Narrative document contains a series of apps used to assemble and annotate
one (or more) sets of genomic reads.
Document: {narrative}

Use the information in the Narrative to draft a genome announcement publication, which may be published in the
ASM Microbiology Resource Announcements journal.

Follow the following template. Leave clear places for the user to add a list of Authors, Affiliations, corresponding
email address

Use the following template with further instructions:
Article title
* Write a brief title that describes the genome — the name of the microbe, the type of sample it was
isolated or assembled from, and any additional information.

Authors
* Leave this section blank for the user to fill out

Affiliations
* Leave this section blank for the user to fill out

Running title
* Should not exceed 54 characters (including spaces)

Corresponding author's email address
* Leave this section blank for the user to fill out

Abstract
* Limit the abstract to 50 words or fewer and concisely summarize the main content of the paper without
presenting extensive experimental details. Avoid abbreviations and references, and do not include diagrams.

Announcement
* Limit the announcement to 500 words or fewer (exclusive of the Abstract and Acknowledgments).
* Announcements may include one figure and one table to help summarize the data set or provide a context for the
resource, but supplemental material is not permitted. If a figure or table seem appropriate, do not create them,
but do reference them in the text, and create a caption that describes the figure for the user to make.
* Include the following information in the announcement:
  * First section (introduction and rationale)
    * A rationale or significance for the sequencing.
    * The provenance for the organism sequenced.
    * If the organism has been taxonomically identified prior to genome sequencing, provide (or cite) detailed
    methods for DNA extraction, PCR (including primers), sequencing, and comparison of the 16S rRNA gene sequences.
    Also please provide the accession number of the best match.
    * A description of how the isolate was acquired, with accession numbers where applicable.
    * Provide or cite detailed isolation methods, including medium, isolation technique, sampling location
    (GPS coordinates), sampling methods, etc.
    * Growth conditions for cultivation.
    * For single-cell amplified genomes, authors should instead supply information about how the cell was
    identified and isolated.
    * For research involving human or animal subjects, include a statement documenting the approval number and
    name of the Institutional Review Board per the ASM Ethics Guidelines.
    * If CLSI standards were used to determine antibiotic resistance, please include appropriate references
    and methods for this. If a clinical lab made the assessment, please describe which one.
  * Second section (methods and related outcomes)
    * A description of growth conditions for cultivation leading to DNA isolation
    * Detailed methods for DNA isolation, library preparation, and sequencing (including the technology and
    chemistry used).

    * For Illumina sequencing, please include
      * detailed methods for library preparation (e.g., kit name and vendor with modifications)
      * Illumina platform description
      * read length
      * number of reads in total and/or the sequencing depth
      * a description of how the reads were quality controlled

    * For Pacific Biosciences (PacBio) sequencing, please include
      * detailed methods for library preparation (e.g., kit name and vendor with modifications)
      * if and how DNA was sheared
      * if and how DNA was size-selected
      * PacBio platform description
      * PacBio chemistry used
      * read N50 and number of raw reads
      * description of read quality control, error correction, and adapter trimming, if appropriate

    * For Oxford Nanopore Technologies sequencing, please include
      * detailed methods for library preparation (e.g., kit name and vendor with modifications)
      * if constructed with ligation method (and not RAD/RAPID), if and how DNA was sheared
      * if constructed with ligation method (and not RAD/RAPID), if and how DNA was size-selected
      * if and how DNA was size-selected
      * description of device and flow cell
      * read N50 and number of raw reads
      * description of base calling algorithm
      * description of read quality control, error correction, and adapter trimming, if appropriate

    * Details on how the genome was assembled and, if applicable, annotated. (Note: if multiple assemblies
    and/or annotations were performed, the announcement should ideally mention only the methods used for
    the publicly available genome referred to in the "Data Availability" paragraph.)
    * Relevant statistics for the assembly (e.g., number of contigs and N50 values).
    * A citation, list of options, and version number for every piece of software used. Please include
    options for all software and/or a statement that says "Default parameters were used except where
    otherwise noted."

Final section (results)
  * Genome GC content and total size.
  * Final genome coverage.
  * For draft genomes, relevant statistics for the draft genome assembly (e.g., number of contigs and N50 values) and estimate of completeness (where relevant).
  * For linear genomes, explain how the ends were determined to be complete
  * For circular genomes, explain how the overlap was identified and trimmed. Was the genome rotated? If so, how?
  * If the genome is annotated, information on number of predicted genes.

Acknowledgments
* Leave this section blank for the user to fill out

References
* Leave this section blank for the user to fill out
"""


class MraWriterGraph:
    """
    Usage:
    Instantiate a WriterGraph object with a narrative id, and optionally a KBase auth token.
    If not, one will be taken from the KB_AUTH_TOKEN environment variable.

    When ready, run run_workflow, which will execute the graph and output the document.

    # TODO: add a reference check that'll automatically grab refs from apps, where applicable
    """
    def __init__(self, ws_client: Workspace, ee_client: ExecutionEngine, token: str = None):
        self._token = token
        self._ws_client = ws_client
        self._ee_client = ee_client
        self._workflow = self._build_graph()

    def run_workflow(self, narrative_id: int):
        initial_state = WriteupState(
            narrative_data=get_narrative_state(
                narrative_id,
                self._ws_client,
                self._ee_client,
            ),
            narrative_id=narrative_id
        )
        self._workflow.invoke(initial_state)

    def save_writeup(self, state: WriteupState) -> WriteupState:
        create_markdown_cell(state.narrative_id, state.writeup_doc, self._ws_client)
        return state

    def error(self, state: WriteupState) -> WriteupState:
        print(f"error: {state.error}")
        return state

    def _build_graph(self) -> CompiledStateGraph:
        writer_graph = StateGraph(WriteupState)
        writer_graph.add_node("analyze", self.checker_node)
        writer_graph.add_node("writeup", self.writer_node)
        writer_graph.add_node("save_writeup", self.save_writeup)
        writer_graph.add_node("error_state", self.error)

        writer_graph.add_edge(START, "analyze")
        writer_graph.add_conditional_edges(
            "analyze", self.check_analysis_state, {"ok": "writeup", "error": "error_state"}
        )
        writer_graph.add_edge("writeup", "save_writeup")
        writer_graph.add_edge("save_writeup", END)
        writer_graph.add_edge("error_state", END)

        workflow = writer_graph.compile()
        return workflow

    def check_analysis_state(self, state: WriteupState) -> str:
        if state.error is not None:
            return "error"
        return "ok"

    def checker_node(self, state: WriteupState) -> WriteupState:
        """
        Checks the state of the Narrative before passing it on to the writer node.
        If the Narrative looks incomplete, this adds an error to the state.
        Otherwise, it just passes the state along.

        TODO: actually make this check the Narrative state. Should probably be in two forms
        1. Programmatically check for presense of every app. I don't think an LLM needs
        to get involved with that.
        2. Make sure each app looks finished, and the overall summary looks like an overall
        summary. An LLM should do that.
        """
        # msg = llm.invoke(f"check state is ok with context: {state.narrative_data}")
        is_ok = True
        if is_ok:
            return state
        else:
            return state.model_copy(update={"error": "error: some error happened"})

    def writer_node(self, state: WriteupState) -> WriteupState:
        """
        Makes a call to (ideally) a more reasoning LLM to write up the document about the
        narrative. Expects state.narrative_data to be populated.
        """
        mra_writing_prompt_template = ChatPromptTemplate(
            [("system", WRITING_SYSTEM_PROMPT), ("user", MRA_WRITING_PROMPT)]
        )

        llm = get_llm("gpt-o1-cborg")
        msg = llm.invoke(
            mra_writing_prompt_template.invoke({"narrative": state.narrative_data})
        )
        return state.model_copy(update={"writeup_doc": msg.content})
