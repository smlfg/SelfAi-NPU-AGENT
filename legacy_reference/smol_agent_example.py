import os
from smolagents.agents import CodeAgent
from smolagents.tools import Tool
from smolagents.models import LiteLLM  # Corrected import
from ddgs.sync import DDGS

# Ensure the Hugging Face API token is set as an environment variable.
if "HUGGING_FACE_HUB_TOKEN" not in os.environ:
    print("Please set the HUGGING_FACE_HUB_TOKEN environment variable.")
    exit()

# 1. Define tool: A simple web search wrapper
def web_search(query: str) -> str:
    """Performs a web search and returns the results."""
    with DDGS() as ddgs:
        results = [r["body"] for r in ddgs.text(query, max_results=5)]
        return " ".join(results) if results else "No results found."

# 2. Initialize language model (LLM)
# Use the LiteLLM class and prefix the model name with "huggingface/"
llm = LiteLLM(model_name="huggingface/HuggingFaceH4/zephyr-7b-beta")

# 3. Initialize agent
agent = CodeAgent(
    llm=llm,
    tools=[Tool.from_function(web_search)],
)

# 4. Run agent with a task
prompt = "What is the capital of Germany and what are the top 3 sights there?"
print(f"Question: {prompt}\n")
print("Agent is thinking...\n")

result = agent.run(prompt)

print(f"\nAgent's Answer:\n{result}")
