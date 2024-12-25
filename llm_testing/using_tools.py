from pprint import pp

import requests
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent


@tool
def get_temperature(location: str) -> int:
    """Return the temperature in a given location."""
    return 40


@tool
def request_ip(ip: str) -> dict[str, str]:
    """Return a dict with the ip address of the requester given the ip provided as parameter."""
    resp = requests.get("https://api.ipify.org?format=json", {"ip": ip}).json()
    return resp


@tool
def calculator_tool(query: str) -> str:
    """Simple calculator to evaluate basic math expressions.
    query is str that is passed to eval function.
    """
    try:
        result = eval(query)
        return str(result)
    except Exception as e:
        return str(e)


if __name__ == "__main__":
    memory = MemorySaver()
    model = ChatOllama(model="llama3.2:1b")
    tools = [calculator_tool, request_ip]
    agent_executor = create_react_agent(model, tools)
    config = {"configurable": {"thread_id": "abc123"}}

    a = agent_executor.invoke({"messages": [HumanMessage(content="whats the ip of 1.1.1.1?")]})

    pp(a)

    b = agent_executor.invoke({"messages": [HumanMessage(content="whats is 100+200?")]})

    pp(b)

    # for chunk in agent_executor.stream(
    #         {"messages": [HumanMessage(content="whats the ip of 1.1.1.1?")]}, config
    # ):
    #     print(chunk)
    #     print("----")
