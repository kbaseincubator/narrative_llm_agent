import streamlit as st
import os
from langchain.schema import ChatMessage
from narrative_llm_agent.agents.analyst import AnalystAgent
from narrative_llm_agent.agents.KnowledgeGraph import KGAgent
from langchain_openai import ChatOpenAI
from crewai import Task, Crew
from narrative_llm_agent.util.stream_handler import StreamHandler

def set_keys():
    neo4j_uri = os.environ["NEO4J_URI"] 
    neo4j_username  = os.environ["NEO4J_USERNAME"]
    neo4j_password = os.environ["NEO4J_PASSWORD"]
    return True

# App title
image = 'Kbase_Logo.png'
# Display the image
st.image(image, width=400)
st.title('KBase Research Assistant')

with st.sidebar:
    # Get the OPENAI key from the user
    OPENAI_API_KEY = st.text_input("OpenAI API Key", type="password")
    # Get the KBase token from the user
    KBase_auth_token = st.text_input('KBase authentication token',type="password")

set_keys()

def assemble_crew(user_query,stream_handler):
    llm = ChatOpenAI(temperature=0, model="gpt-4",streaming=True,callbacks=[stream_handler])

    researcher = AnalystAgent(token=KBase_auth_token, llm=llm)
    KGer = KGAgent(token=KBase_auth_token, llm=llm, stream_handler = stream_handler)
    task1_descr = user_query + """ Please suggest only one app at a time for a particular step. If you must suggest alternative apps please limit to only one."""
    task1 = Task (description=task1_descr, agent=researcher.agent)
    # After you check its availability in the Knowledge Graph, ask a human if they approve of the suggested app and then only return the app ID.
    task2 = Task(
      description="""
      Use the knowledge graph to make sure that the apps that you suggest exist. After you check its availability in the Knowledge Graph, 
      ask a human if they approve of the suggested app and then only return the app ID.
    If not check for the additional recommended app in the Knowledge Graph.""",
      agent=KGer.agent
    )
    # Instantiate your crew with a sequential process
    crew = Crew(
      agents=[researcher.agent,KGer.agent],
      tasks=[task1,task2],
      verbose=2, # You can set it to 1 or 2 to different logging levels
    )
    return crew


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
    if not OPENAI_API_KEY:
        st.info("Please add your OpenAI API key to continue.")
        st.stop()
    with st.spinner("Assembling your crew .."):
        stream_handler = StreamHandler(st.empty())
        crew = assemble_crew(prompt,stream_handler)
        response = crew.kickoff()
        st.session_state.messages.append(ChatMessage(role="assistant", content=response))
        