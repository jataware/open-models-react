from typing import Literal
from pathlib import Path

from .groq_agent import GroqReActAgent, python_tool_schema
from archytas.react import ReActAgent
from .utils import move_to_isolated_dir, make_str_pathsafe


import pdb


here = Path(__file__).parent
api_docs = (here / '../apis/ECMWF_docs.md').read_text()

# this needs to be within about 2 days of today (because ECMWF doesn't keep older forecasts)
current_date = '2025-04-22'  # Format: YYYYMMDD


BASELINE_TASK_PROMPT = f"""\
Please download a short time forecast from ECMWF for the current date {current_date}.
The forecast should start at 06:00 UTC and have a step size of 24 hours.
The forecast should be in grib2 format and saved in the current directory.

After downloading the data, please verify it was downloaded successfully.
An easy way to do this is by checking the file size, which should be on the order of 100 MB

Here is the documentation for using the ECMWF API:\n{api_docs}
"""

TOOL_ASSISTED_TASK_PROMPT = f"""\
"""


"""
Task
1. download current data for short range weather forecast from ECMWF
2. open it, select (tbd) variable, crop data to (tbd) lat/lon bounds
3. plot the data
"""



# agent = GroqReActAgent(
#     model='llama-3.3-70b-versatile',
#     tool_schemas=[python_tool_schema]
# )    
# for query in REPL(history_file='.chat'):
#     agent.ReAct(query)


Model = Literal[
    # 'gemma2-9b-it',
    # 'llama-3.3-70b-versatile',
    # 'llama-3.1-8b-instant',
    # 'llama-guard-3-8b',
    # 'llama3-70b-8192',
    # 'llama3-8b-8192',
    # 'allam-2-7b',
    # 'deepseek-r1-distill-llama-70b',
    'meta-llama/llama-4-maverick-17b-128e-instruct',
    # 'meta-llama/llama-4-scout-17b-16e-instruct',
    # 'mistral-saba-24b',
    # 'qwen-qwq-32b',
]



baseline_toolset: list[dict] = [python_tool_schema]
tool_assisted_toolset: list[dict] = [] # TODO: toolset for direct API access
# TODO: also need hosted versions of these containing the archytas tools for the archytas version of the test




def hosted_benchmark(agent: ReActAgent):
    ...

def groq_benchmark(model_name: Model, tool_set: list[dict], prompt: str):
    agent = GroqReActAgent(model=model_name, tool_schemas=tool_set)
    pathsafe_model_name = make_str_pathsafe(model_name)
    with move_to_isolated_dir(dirname=f'runs/TIMESTAMP--{pathsafe_model_name}'):
        agent.ReAct(prompt)


    # TODO: autograde the agent


if __name__ == '__main__':
    groq_benchmark('meta-llama/llama-4-maverick-17b-128e-instruct', [python_tool_schema], BASELINE_TASK_PROMPT)
    # pdb.set_trace()
    ...