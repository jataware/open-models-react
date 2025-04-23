from typing import Literal, TypedDict
from pathlib import Path
import json
import hashlib
from rich import print
from functools import cache, partial
from tqdm import tqdm
import os

from archytas.models.anthropic import AnthropicModel
from archytas.models.openai import OpenAIModel
from archytas.models.base import BaseArchytasModel
from archytas.tools import PythonTool
from archytas.react import ReActAgent

from .groq_agent import GroqReActAgent, python_tool_schema
from .utils import move_to_isolated_dir, make_str_pathsafe, redirect_stdout

import pdb


here = Path(__file__).parent
api_docs = (here / '../apis/ECMWF_docs.md').read_text()

# this needs to be within about 2 days of today (because ECMWF doesn't keep older forecasts)
current_date = '2025-04-22'  # Format: YYYYMMDD
# sha256sum path/to/file
sha256sum = '6668c059283404b5dd39afdeff59c93acc1810c515a0fbad00329812b682be44'
# stat -c %s path/to/file
bytesize = 129056697

BASELINE_TASK_PROMPT = f"""\
Please download a short time forecast from ECMWF for the current date {current_date}.
The forecast should start at 06:00 UTC and have a step size of 24 hours.
The forecast should be in grib2 format and saved in the current directory.

After downloading the data, please verify it was downloaded successfully.

Here is the documentation for using the ECMWF API:\n{api_docs}
"""
# An easy way to do this is by checking the file size, which should be on the order of 100 MB

TOOL_ASSISTED_TASK_PROMPT = f"""\
Please download a short time forecast from ECMWF for the current date {current_date}.
The forecast should start at 06:00 UTC and have a step size of 24 hours.
The forecast should be in grib2 format and saved in the current directory.

After downloading the data, please verify it was downloaded successfully.
"""


"""
Task
1. download current data for short range weather forecast from ECMWF
2. open it, select (tbd) variable, crop data to (tbd) lat/lon bounds
3. plot the data
"""



class Result(TypedDict):
    success: bool
    notes: str

ModelResultMap = dict[str, list[Result]]  # map from model name to all runs results
TestCaseMap = dict[str, ModelResultMap]  # map from test case name to model result map


groq_baseline_toolbox: list[dict] = [python_tool_schema]
groq_tool_assisted_toolbox: list[dict] = [] # TODO: toolset for direct API access
# TODO: also need hosted versions of these containing the archytas tools for the archytas version of the test


Model = Literal[
    # 'gemma2-9b-it',
    'llama-3.3-70b-versatile',
    'llama-3.1-8b-instant',
    # 'llama-guard-3-8b',
    # 'llama3-70b-8192',
    # 'llama3-8b-8192',
    # 'allam-2-7b',
    # 'deepseek-r1-distill-llama-70b',
    # 'meta-llama/llama-4-maverick-17b-128e-instruct',
    # 'meta-llama/llama-4-scout-17b-16e-instruct',
    # 'mistral-saba-24b',
    # 'qwen-qwq-32b',
]


HostedModel = Literal[
    # 'claude-3-7-sonnet-latest',
    'gpt-4o',
]
Provider = Literal['ANTHROPIC', 'OPENAI']
models_map: dict[HostedModel, tuple[type[BaseArchytasModel], Provider]] = {
    'claude-3-7-sonnet-latest': (AnthropicModel, 'ANTHROPIC'),
    'gpt-4o': (OpenAIModel, 'OPENAI'),
}

hosted_baseline_toolbox = [PythonTool]
hosted_tool_assisted_toolbox = []  # TODO: toolset for direct API access




@cache
def get_test_case_map():
    return {
        BASELINE_TASK_PROMPT: 'baseline',
        TOOL_ASSISTED_TASK_PROMPT: 'tool_assisted',
    }

@cache
def get_groq_toolbox_map():
    return {
        BASELINE_TASK_PROMPT: groq_baseline_toolbox,
        TOOL_ASSISTED_TASK_PROMPT: groq_tool_assisted_toolbox,
    }

@cache
def get_hosted_toolbox_map():
    return {
        BASELINE_TASK_PROMPT: hosted_baseline_toolbox,
        TOOL_ASSISTED_TASK_PROMPT: hosted_tool_assisted_toolbox,
    }





def benchmark_suite(prompt:str, n_trials:int):
    
    groq_toolbox = get_groq_toolbox_map()[prompt]
    for model_name in tqdm(Model.__args__, desc='Groq models'):
        for i in tqdm(range(n_trials), desc=f'Trial: {model_name}', leave=False):
            with redirect_stdout(partial(tqdm.write, end='')):
                try:
                    groq_benchmark(model_name, groq_toolbox, prompt)
                except:
                    pass

            
    
    hosted_toolbox = get_hosted_toolbox_map()[prompt]
    for model_name in tqdm(HostedModel.__args__, desc='Hosted models'):
        for i in tqdm(range(n_trials), desc=f'Trial: {model_name}', leave=False):
            with redirect_stdout(partial(tqdm.write, end='')):
                try:
                    hosted_benchmark(model_name, hosted_toolbox, prompt)
                except:
                    pass

    
    # TODO: plot results






def groq_benchmark(model_name: Model, toolbox: list[dict], prompt: str):
    agent = GroqReActAgent(model=model_name, tool_schemas=toolbox)
    pathsafe_model_name = make_str_pathsafe(model_name)
    with move_to_isolated_dir(dirname=f'runs/{{timestamp}}--{pathsafe_model_name}'):
        agent.ReAct(prompt)

        # evaluate and save the results into the result file
        autograde(Path.cwd(), model_name, prompt)



def hosted_benchmark(model_name: HostedModel, toolbox: list, prompt: str):
    model_class, provider = models_map[model_name]

    agent = ReActAgent(
        model=model_class({'model_name': model_name, 'api_key': os.environ.get(f'{provider}_API_KEY')}),
        tools=toolbox,
        allow_ask_user=False,
        verbose=True
    )
    pathsafe_model_name = make_str_pathsafe(model_name)
    with move_to_isolated_dir(dirname=f'runs/{{timestamp}}--{pathsafe_model_name}'):
        agent.react(prompt)

        # evaluate and save the results into the result file
        autograde(Path.cwd(), model_name, prompt)
    





def autograde(workdir: Path, model_name: Model, prompt: str):


    test_case = get_test_case_map()[prompt]

    result_file = here / f'../runs/results.json'
    
    # ensure the results file exists
    if not result_file.exists():
        result_file.write_text('{}')
    

    # # DEBUG for testing just put the following in the result file:
    # result = {'success': True, 'notes': ''}
    # do actual grading here
    # check all files in the workdir, see if any match the sha256sum
    result = {'success': False, 'notes': ''}
    for file in workdir.iterdir():
        if file.is_file() and file.stat().st_size == bytesize and hashlib.sha256(file.read_bytes()).hexdigest() == sha256sum:
            result['success'] = True
            result['notes'] = f'File {file.name} is valid.'
            break
    else:
        result['notes'] = 'No valid file found.'

    # save the result into the result file
    prev_results = json.loads(result_file.read_text())
    if test_case not in prev_results:
        prev_results[test_case] = {}
    if model_name not in prev_results[test_case]:
        prev_results[test_case][model_name] = []
    prev_results[test_case][model_name].append(result)
    result_file.write_text(json.dumps(prev_results, indent=4))
    print(f'[green]Test Case: {test_case}\nModel: {model_name}\nResults: {result}[green]', end='\n', flush=True)



if __name__ == '__main__':
    n_trials = 2 #10
    benchmark_suite(prompt=BASELINE_TASK_PROMPT, n_trials=n_trials)
    # benchmark_suite(prompt=TOOL_ASSISTED_TASK_PROMPT, n_trials=n_trials)
    
    # DEBUG individual test runs
    # groq_benchmark('meta-llama/llama-4-maverick-17b-128e-instruct', groq_baseline_toolbox, BASELINE_TASK_PROMPT)
    # hosted_benchmark('gpt-4o', hosted_baseline_toolbox, BASELINE_TASK_PROMPT)