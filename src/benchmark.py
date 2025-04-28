from typing import Literal, TypedDict
from pathlib import Path
import json
import hashlib
from rich import print
from functools import cache, partial
from tqdm import tqdm
import os
import matplotlib.pyplot as plt

from archytas.models.anthropic import AnthropicModel
from archytas.models.openai import OpenAIModel
from archytas.models.gemini import GeminiModel
from archytas.models.base import BaseArchytasModel
from archytas.tools import PythonTool
from archytas.react import ReActAgent

from .groq_agent import GroqReActAgent, python_tool_schema, ecmwf_download_tool_schema
from .utils import move_to_isolated_dir, make_str_pathsafe, redirect_stdout

import pdb


here = Path(__file__).parent
api_docs = (here / '../apis/ECMWF_docs.md').read_text()


# # TODO: replace this with fetching the latest, and dynamically generating the hash for that one
# # this needs to be within about 2 days of today (because ECMWF doesn't keep older forecasts)
# current_date = '2025-04-22'  # Format: YYYYMMDD
# # sha256sum path/to/file
# sha256sum = '6668c059283404b5dd39afdeff59c93acc1810c515a0fbad00329812b682be44'
# # stat -c %s path/to/file
# bytesize = 129056697
from .ecmwf import ecmwf_client
from datetime import datetime
current_date = datetime.now().strftime('%Y-%m-%d')  # Format: YYYY-MM-DD
year, month, day = map(int, current_date.split('-'))
url = ecmwf_client.build_file_url(current_date.replace('-', ''), '06', 'ifs', '0p25', 'scda', '24h', 'fc', 'grib2')
reference_path = here / '../runs/reference' / Path(url).name
if not reference_path.exists():
    print(f'[blue]Downloading ECMWF forecast for {current_date}... [blue]', end='', flush=True)
    ecmwf_client.download_forecast(year, month, day, '06', 'scda', 24, 'fc', 'grib2')
    # move the downloaded file to the reference path
    download_path = Path.cwd() / reference_path.name
    if not download_path.exists():
        raise RuntimeError(f'Failed to download file. File not found: {download_path}')
    download_path.rename(reference_path)
    print(f'[green]Download complete: {reference_path}[green]', end='\n', flush=True)
else:
    print(f'using cached reference file: {reference_path}', end='\n', flush=True)
sha256sum = hashlib.sha256(reference_path.read_bytes()).hexdigest()
bytesize = reference_path.stat().st_size
print(f'[green] Current file: {reference_path}[green]', end='\n', flush=True)
print(f'[green] SHA256: {sha256sum}[green]', end='\n', flush=True)
print(f'[green] Bytesize: {bytesize}[green]', end='\n', flush=True)




BASELINE_TASK_PROMPT = f"""\
Please download a short time forecast (scda) from ECMWF for the current date {current_date}.
The forecast should start at 06:00 UTC and have a step size of 24 hours.
The forecast should be in grib2 format and saved in the current directory.

After downloading the data, please verify it was downloaded successfully.

Here is the documentation for using the ECMWF API:\n{api_docs}
"""
# An easy way to do this is by checking the file size, which should be on the order of 100 MB

TOOL_ASSISTED_TASK_PROMPT = f"""\
Please download a short time forecast (scda) from ECMWF for the current date {current_date}.
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
    error: None|str

ModelResultMap = dict[str, list[Result]]  # map from model name to all runs results
TestCaseMap = dict[str, ModelResultMap]  # map from test case name to model result map


groq_baseline_toolbox: list[dict] = [python_tool_schema]
groq_tool_assisted_toolbox: list[dict] = [ecmwf_download_tool_schema]


Model = Literal[
    'gemma2-9b-it',
    'llama-3.3-70b-versatile',
    'llama-3.1-8b-instant',
    # 'llama-guard-3-8b', # doesn't support tool calls
    'llama3-70b-8192',
    'llama3-8b-8192',
    # 'allam-2-7b',       # doesn't support tool calls
    'deepseek-r1-distill-llama-70b',
    'meta-llama/llama-4-maverick-17b-128e-instruct',
    'meta-llama/llama-4-scout-17b-16e-instruct',
    'mistral-saba-24b',
    'qwen-qwq-32b',
]


HostedModel = Literal[
    'claude-3-7-sonnet-latest',
    'gpt-4o',
    # 'gemini-1.5-pro'
]
Provider = Literal['ANTHROPIC', 'OPENAI']
models_map: dict[HostedModel, tuple[type[BaseArchytasModel], Provider]] = {
    'claude-3-7-sonnet-latest': (AnthropicModel, 'ANTHROPIC'),
    'gpt-4o': (OpenAIModel, 'OPENAI'),
    # 'gemini-1.5-pro': (GeminiModel, 'GEMINI'),
}

hosted_baseline_toolbox = [PythonTool]
hosted_tool_assisted_toolbox = [ecmwf_client.download_forecast]




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

@cache
def get_plot_titles_map():
    return {
        'baseline': '(Baseline) Download ECMWF forecast Success Rate',
        'tool_assisted': '(Tool-assisted) Download ECMWF forecast Success Rate',
    }




def groq_benchmark_suite(prompt:str, n_trials:int):
    
    groq_toolbox = get_groq_toolbox_map()[prompt]
    for model_name in tqdm(Model.__args__, desc='Groq models'):
        for i in tqdm(range(n_trials), desc=f'Trial: {model_name}', leave=False):
            with redirect_stdout(partial(tqdm.write, end='')):
                try:
                    groq_benchmark(model_name, groq_toolbox, prompt)
                except:
                    pass

            
def hosted_benchmark_suite(prompt:str, n_trials:int):
    
    hosted_toolbox = get_hosted_toolbox_map()[prompt]
    for model_name in tqdm(HostedModel.__args__, desc='Hosted models'):
        for i in tqdm(range(n_trials), desc=f'Trial: {model_name}', leave=False):
            with redirect_stdout(partial(tqdm.write, end='')):
                try:
                    hosted_benchmark(model_name, hosted_toolbox, prompt)
                except:
                    pass

    
    # # plot results
    # plot_all_experiments(here / '../runs/results.json')



def plot_all_experiments(results_path: Path):
    # Load JSON data
    data: TestCaseMap = json.loads(results_path.read_text())

    for experiment_name, experiment_results in data.items():
        model_names = []
        success_rates = []
        success_labels = []

        for model_name, runs in experiment_results.items():
            total = len(runs)
            n_success = sum(run["success"] for run in runs)
            model_names.append(model_name)
            success_percentage = (n_success / total) * 100
            success_rates.append(success_percentage)
            success_labels.append(f"{n_success}/{total}")

        # Plotting
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(model_names, success_rates)

        ax.set_ylabel('Success Rate (%)')
        ax.set_title(get_plot_titles_map()[experiment_name])
        ax.set_ylim(0, 100)
        plt.xticks(rotation=-30, ha='left')

        # Annotate each bar with n_success/total
        for bar, label in zip(bars, success_labels):
            height = bar.get_height()
            ax.annotate(
                label,
                xy=(bar.get_x() + bar.get_width() / 2, height / 2),
                xytext=(0, 3) if height == 0 else (0, -3), # offset
                textcoords="offset points",
                ha='center', va='bottom'
            )

        plt.tight_layout()
        # save the plot
        fig.savefig(results_path.parent / f'{experiment_name}_success_rate.png')
        plt.show()






def groq_benchmark(model_name: Model, toolbox: list[dict], prompt: str):
    agent = GroqReActAgent(model=model_name, tool_schemas=toolbox)
    pathsafe_model_name = make_str_pathsafe(model_name)
    with move_to_isolated_dir(dirname=f'runs/{{timestamp}}--{pathsafe_model_name}'):
        error = None
        try:
            agent.ReAct(prompt)
        except Exception as e:
            error = e


        # evaluate and save the results into the result file
        autograde(Path.cwd(), model_name, prompt, error, agent.messages[2:])



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
        error = None
        try:
            agent.react(prompt)
        except Exception as e:
            error = e

        # evaluate and save the results into the result file
        autograde(Path.cwd(), model_name, prompt, error, agent.messages[1:])
    




autograder = ReActAgent(model=OpenAIModel({'model_name': 'gpt-4o', 'api_key': os.environ.get('OPENAI_API_KEY')}))
AUTOGRADER_PROMPT = """\
Please look at the following conversation history of an agent attempting to download a file.

'''
{conversation}
'''

Please provide a brief 1 or so sentence summary of the conversation. Do not output any other comments.
"""

def autograde(workdir: Path, model_name: Model, prompt: str, error: Exception | None, chat_history: list[dict]):

    test_case = get_test_case_map()[prompt]

    result_file = here / f'../runs/results.json'
    
    # ensure the results file exists
    if not result_file.exists():
        result_file.write_text('{}')
    
    # grading process: check all files in the workdir, see if any match the sha256sum
    error = repr(error) if error is not None else None
    result = {'success': False, 'notes': '', 'error': error}
    for file in workdir.iterdir():
        if file.is_file() and file.stat().st_size == bytesize and hashlib.sha256(file.read_bytes()).hexdigest() == sha256sum:
            result['success'] = True
            result['notes'] = f'File {file.name} is valid.'
            break
    else:
        result['notes'] = 'No valid file found.'

    # Add AI comments about the conversation
    ai_notes = autograder.oneshot_sync('you are a helpful assistant', AUTOGRADER_PROMPT.format(conversation=chat_history))
    result['notes'] += f' (AI notes): {ai_notes}'

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
    # plot_all_experiments(here / '../runs/results.json')
    # exit(0)

    n_trials = 5 #10
    # groq_benchmark_suite(prompt=BASELINE_TASK_PROMPT, n_trials=n_trials)
    # hosted_benchmark_suite(prompt=BASELINE_TASK_PROMPT, n_trials=n_trials)
    groq_benchmark_suite(prompt=TOOL_ASSISTED_TASK_PROMPT, n_trials=n_trials)
    # hosted_benchmark_suite(prompt=TOOL_ASSISTED_TASK_PROMPT, n_trials=n_trials)
    
    # DEBUG individual test runs
    # groq_benchmark('meta-llama/llama-4-maverick-17b-128e-instruct', groq_baseline_toolbox, BASELINE_TASK_PROMPT)
    # hosted_benchmark('gpt-4o', hosted_baseline_toolbox, BASELINE_TASK_PROMPT)

    # TBD why not working...
    # hosted_benchmark('gemini-1.5-pro', hosted_baseline_toolbox, BASELINE_TASK_PROMPT)