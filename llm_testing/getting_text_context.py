import json
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

ollama_instruct = """
You are an LLM who is helping with appointment arrangement.
Your job is based on users input provide the necessary data as a JSON output.
The data should be structured as:
{
    "region": <value or null>, # This is the city that the appointment will be held, ex. Kraków or Warsaw or London
    "specialization": <value or null>, # That's the requested specialization, ex. Dermatologist or Psychologist
    "clinic": <value or null>, # That's the clinic's location name in the city, ex. Medicover Podgórska,
    "doctor": <value or null>, # Doctors name and surname, ex. Jan Kowalski
    "start_date": <value or null>, # Date from when to search the appointment, most probably today's date
    "start_time": <value or null>, # Time from when to search the appointment, most probably 07:00
    "end_date": <value or null>, # Date until when to search the appointment, most probably today's date + one month
    "end_time": <value or null> # Time until when to search the appointment, most probably 22:00
}
Based on the user's input, return the JSON.
If the user has not provided some of the data add in the json a null.

Example use-cases:
1. User: Show me dermatologists in Wroclaw.
OUTPUT:
{
    "region": "Wroclaw",
    "specialization": "Dermatologist",
    "clinic": null,
    "doctor": null,
    "start_date": null,
    "start_time": null,
    "end_date": null,
    "end_time": null
}

2. User: I'm looking for a psychologist in Warsaw named Krystian Kowalski.
OUTPUT:
{
    "region" "Warsaw",
    "specialization: "Psychologist",
    "clinic": null,
    "doctor": "Krystian Kowalski",
    "start_date": null,
    "start_time": null,
    "end_date": null,
    "end_time": null
}

If you need to get the current date, run the get_todays_date() tool.
The start_time and end_time should be in 24h format.
The min value of start_time is 07:00 and the max value is 22:00.
The min value of end_time is 07:00 and the max value is 22:00, but it cannot be equal to start_time and this
value MUST be greater than start_time.
If end_time is not provided, SET IT to 22:00.
If some of the data is not provided, add it as null.
DO NOT ADD ANY COMMENT. JUST RETURN THE JSON.
"""

input_string = "I'm looking for a dermatologist in kraków for next friday after 10am"


@tool
def get_todays_date() -> str:
    """Return the current date in the format YYYY-MM-DD."""
    return date.today().strftime("%Y-%m-%d")


if __name__ == "__main__":
    messages = [SystemMessage(ollama_instruct), HumanMessage(input_string)]
    llama = ChatOllama(model="qwen2.5:7b-instruct-q5_K_M")

    tools = [get_todays_date]
    agent_executor = create_react_agent(llama, tools)
    config = {"configurable": {"thread_id": "abc123"}}

    a = agent_executor.invoke({"messages": messages})
    last_call = a["messages"][-1]

    a = json.loads(output)
    print(a)
