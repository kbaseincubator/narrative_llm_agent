import streamlit as st
import os
from langchain.schema import ChatMessage
from langchain_openai import ChatOpenAI
from crewai import Agent, Task, Crew
from narrative_llm_agent.util.stream_handler import StreamHandler

st.title('KBase Research Assistant')
def set_keys():
    api_key = os.environ["OPENAI_API_KEY"]
    neo4j_uri = os.environ["NEO4J_URI"] 
    neo4j_username  = os.environ["NEO4J_USERNAME"]
    neo4j_password = os.environ["NEO4J_PASSWORD"]
    return True

from narrative_llm_agent.user_interface.dummy_human_tool import HumanInputRun
#@st.cache_resource
# def get_input() -> str:
#     placeholder = st.empty()
#     placeholder.text("Waiting for user input...")
#     user_input = st.text_input('flav', key='user_input')
#     user_input = None
#     while user_input is None:
#         user_input = st.text_input('flav', key='user_input')
#         return user_input
#     # if user_input:
#     #     logging.debug(f"User input received: {user_input}")
#     #     return user_input
#     # else:
#     #     logging.debug("No input received.")
tool = HumanInputRun()

if "crew" not in st.session_state:
    researcher = Agent(
      role='Research Scientist',
      goal='Answer user questions to the best of your ability.',
      backstory="""You are an expert in microbial ecology and the usage of the DOE Systems biology Knowledgebase (KBase). """,
      verbose=True,
      allow_delegation=False,
        llm=ChatOpenAI(model_name="gpt-4", temperature=0),
      tools=[tool],
    )
    task1 = Task(
      description="""I have sequenced a new microbe. I have a fastq file of reads from paired end illumina sequencing.  
      I want to determine its quality Which app can I use. Please suggest one app at a time. Make sure to check with a human if they approve the apps. Ask human for help and always confirm if the apps you suggest are to a users liking.    
    """,
      agent=researcher
    )
#Make sure to check with a human if they approve the apps. Ask human for help and always confirm if the apps you suggest are to a users liking.    
    # Instantiate your crew with a sequential process
    crew = Crew(
      agents=[researcher],
      tasks=[task1],
      verbose=2, # You can set it to 1 or 2 to different logging levels
    )
    st.session_state.crew = crew
crew = st.session_state.crew
    
# Initialize chat history
if "messages" not in st.session_state:
    st.session_state["messages"] = [ChatMessage(role="assistant", content="How can I help you?")]
for msg in st.session_state.messages:
    st.chat_message(msg.role).write(msg.content)
    
if prompt := st.chat_input():
    # Add user message to chat history
    st.session_state.messages.append(ChatMessage(role="user", content=prompt))
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.spinner("thinking .."):
        stream_handler = StreamHandler(st.empty())
        response = crew.kickoff()
        st.session_state.messages.append(ChatMessage(role="assistant", content=response))
        