import os
from narrative_llm_agent.agents.analyst import AnalystAgent
from narrative_llm_agent.agents.KnowledgeGraph import KGAgent
from langchain_openai import ChatOpenAI
from crewai import Task, Crew
import chainlit as cl

# Set the environment variable
os.environ['CHAINLIT_RUN'] = '1'

def set_keys():
    neo4j_uri = os.environ["NEO4J_URI"] 
    neo4j_username  = os.environ["NEO4J_USERNAME"]
    neo4j_password = os.environ["NEO4J_PASSWORD"]
    return True

# App title

# Display the image
# st.image(image, width=400)
# st.title('KBase Research Assistant')

# with st.sidebar:
#     # Get the OPENAI key from the user
#     OPENAI_API_KEY = st.text_input("OpenAI API Key", type="password")
#     # Get the KBase token from the user
#     KBase_auth_token = st.text_input('KBase authentication token',type="password")

set_keys()
@cl.on_chat_start
async def on_chat_start():

    open_ai_key = await cl.AskUserMessage("Please enter your OpenAI key here:").send()
    KBase_auth_token = await cl.AskUserMessage("Please enter your KBase token key here:").send()
    await cl.Message(content="Thank you").send()
    user_query = "What app can I use to determine the quality of pair end reads?"
    llm = ChatOpenAI(temperature=0, model="gpt-4",streaming=True)
    # callbacks=[cl.LangchainCallbackHandler()]
    researcher = AnalystAgent(token=KBase_auth_token, llm=llm)
    KGer = KGAgent(token=KBase_auth_token, llm=llm)
    
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
    # Store the crew in the user session for reusability
    cl.user_session.set("crew", crew)


@cl.on_message
async def on_message(message: cl.Message):
    print(os.getenv('CHAINLIT_RUN'))
    # Retrieve the chain from the user session
    crew = cl.user_session.get("crew")
    # Call the chain asynchronously
    res = crew.kickoff()
    await cl.Message(content=res).send()