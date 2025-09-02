from langchain_core.messages import AIMessage, HumanMessage
from langchain.load import loads


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

        # Extract metadata from conversation using pattern matching
        for msg in chat_history_obj:
            if isinstance(msg, HumanMessage):
                content = msg.content.lower()

                # Try to extract narrative ID
                if any(
                    keyword in content for keyword in ["narrative id", "narrative"]
                ) and any(char.isdigit() for char in msg.content):
                    import re

                    numbers = re.findall(r"\d+", msg.content)
                    if numbers:
                        collected_data["narrative_id"] = numbers[0]

                # Try to extract UPA/reads ID
                if "/" in msg.content and any(char.isdigit() for char in msg.content):
                    import re

                    upa_pattern = r"\d+/\d+/\d+"
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

                    organism_match = re.search(
                        r"organism[:\s]+([^,\n\.]+)", content, re.IGNORECASE
                    )
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

    print(collected_data)
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
        recent_messages = (
            chat_history_obj[-3:] if len(chat_history_obj) > 3 else chat_history_obj
        )

        completion_indicators = [
            "successfully stored conversation",
            "stored conversation to narrative",
            "conversation summary",
            "workflow is complete",
            "analysis can now begin",
            "ready to proceed",
            "metadata collection complete",
        ]

        for msg in recent_messages:
            if isinstance(msg, AIMessage):
                if any(
                    indicator in msg.content.lower()
                    for indicator in completion_indicators
                ):
                    return True, extract_metadata_from_conversation(chat_history_obj)

        # Alternative check: see if we have essential data
        collected_data = extract_metadata_from_conversation(chat_history_obj)
        has_essential_data = collected_data.get("narrative_id") and collected_data.get(
            "reads_id"
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


def process_metadata_chat(agent_executor, user_input, chat_history):
    """Static method to process chat - used by the Dash app"""
    try:
        if not isinstance(chat_history, list):
            chat_history = []

        response = agent_executor.invoke(
            {
                "input": user_input
                if user_input
                else "Start the conversation by asking for the narrative ID",
                "chat_history": chat_history,
            }
        )

        return response.get("output", "No response generated")

    except Exception as e:
        return f"Error in agent processing: {str(e)}"
