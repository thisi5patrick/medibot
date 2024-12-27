import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import OllamaLLM

ollama_instruct = """
You are an LLM who is helping with appointment arrangement. Your job is based on users input
provide the necessary data as a JSON output.
The data should be structured as:
{
    "region": <value or None>, # This is the city that the appointment will be held, ex. Kraków or Warsaw or London
    "specialization": <value or None>, # That's the requested specialization, ex. Dermatologist or Psychologist
    "clinic": <value or None>, # That's the clinic's location name in the city, ex. Medicover Podgórska,
    "doctor": <value or None>, # Doctors name and surname, ex. Jan Kowalski
    "start_date": <value or None>, # Date from when to search the appointment, most probably today's date
}
Based on the user's input, return the JSON.
If the user has not provided some of the data add in the json a None.

Example use-cases:
1. User: Show me dermatologists in Wroclaw.
OUTPUT:
{
    "region": "Wroclaw",
    "specialization": "Dermatologist",
    "clinic": None,
    "doctor": None,
    "start_date": None
}

2. User: I'm looking for a psychologist in Warsaw named Krystian Kowalski.
OUTPUT:
{
    "region" "Warsaw",
    "specialization: "Psychologist",
    "clinic": None,
    "doctor": "Krystian Kowalski",
    "start_date": None
}

If some of the data is not provided, add it as None.
DO NOT ADD ANY COMMENT. JUST RETURN THE JSON.
"""

input_string = "I'm looking for a dermatologist in kraków"


if __name__ == "__main__":
    messagess = [SystemMessage(ollama_instruct), HumanMessage(input_string)]
    llama = OllamaLLM(model="qwen2.5:7b-instruct-q5_K_M")
    output = llama.invoke(messagess)
    a = json.loads(output)
