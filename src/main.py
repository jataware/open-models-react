import os
from groq import Groq
from groq.types.chat import ChatCompletionMessageParam, ChatCompletionSystemMessageParam, ChatCompletionAssistantMessageParam, ChatCompletionToolMessageParam, ChatCompletionMessageToolCallParam
from groq.types.chat.chat_completion_chunk import ChoiceDeltaToolCallFunction, ChoiceDeltaToolCall
from easyrepl import REPL
from rich import print
import json
from typing import cast

from archytas.tools import PythonTool



import pdb


python_tool = PythonTool()

python_tool_schema = {
    "type": "function",
    "function": {
        "name": "PythonTool.run",
        "description": "Runs Python code in a persistent environment. Variables and state are preserved between calls. stdout/stderr is returned as a string (so all other side effects are invisible, meaning you should use print/etc. if you want to view any results)",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute. Must use print statements to view any program state."
                }
            },
            "required": ["code"]
        }
    }
}



def main():
    client = Groq()
    messages: list[ChatCompletionMessageParam] = []
    for query in REPL(history_file='.chat'):
        messages.append(
            {
                "role": "user",
                "content": query,
            }
        )
        gen = client.chat.completions.create(
            messages=messages,
            model="deepseek-r1-distill-llama-70b",
            stream=True,
            # stream=False,
            tools=[python_tool_schema],
            tool_choice="auto"
        )


        # results = []
        reasoning_chunks: list[str] = []
        content_chunks: list[str] = []
        tool_calls = []
        tool_call_results: list[dict] = []
        # TBD about how function calls work/are different from tool calls...
        # actually the api says function calls is deprecated in favor of tool calls

        for chunk in gen:
            # done streaming
            if chunk.choices[0].finish_reason is not None:
                print(f'[red]{chunk.choices[0].finish_reason}[red]', end='', flush=True)
                break

            delta = chunk.choices[0].delta
            
            if delta.content is not None:
                print(delta.content, end='', flush=True)
                content_chunks.append(delta.content)
            
            elif delta.reasoning is not None:
                print(f'[green]{delta.reasoning}[green]', end='', flush=True)
                reasoning_chunks.append(delta.reasoning)
            
            elif delta.tool_calls is not None:
                for tool_call in delta.tool_calls:
                    #tool_call: ChatCompletionMessageToolCallParam
                    res = exec_tool_call(tool_call)
                    tool_calls.append(tool_call)
                    tool_call_results.append(res)
                    # pdb.set_trace()
                    # f = tool_call.function
                    # if f is None:
                    #     print(f'[red]Tool Call with no tool name: {tool_call}[red]', end='', flush=True)
                    #     continue

                    # print(f'[blue]{f.name}[blue]', end='', flush=True)
                    # arguments = {}
                    # if f.arguments is not None:
                    #     arguments = json.loads(f.arguments)
                    #     print(f'[yellow]{arguments}[yellow]', end='', flush=True)
                    # res = exec_tool_call(f.name, arguments)

            elif delta.function_call is not None:
                print(f'[red]Function call is currently not supported[red]', end='', flush=True)
                print(f'[yellow]{delta.function_call}[yellow]', end='', flush=True)
            
            else: ... # nothing to do

        print()

        # reconstruct the agent message and append it to the list of messages
        content = ''.join(content_chunks)
        reasoning = ''.join(reasoning_chunks)
        message: ChatCompletionAssistantMessageParam = {
            'role': 'assistant',
            'content': content,
            'tool_calls': tool_calls,
        }
        messages.append(message)
        for tool_call_result in tool_call_results:
            messages.append(tool_call_result)

        # pdb.set_trace()
        # ...

        # TODO: this is where we need to deal with looping into the ReAct loop based on what tool was selected
        # make a final response
        final_response = client.chat.completions.create(
            messages=messages,
            model="deepseek-r1-distill-llama-70b",
            tools=[python_tool_schema],
            tool_choice="auto"
        )
        print(final_response.choices[0].message.content) 


from typing import Callable
tool_fn_map: dict[str, Callable] = {
    'PythonTool.run': python_tool.run,
}


# TBD on the type of the return here...
def exec_tool_call(tool_call: ChoiceDeltaToolCall):
    try:
        fn = tool_fn_map[tool_call.function.name]
    except KeyError:
        raise Exception(f"Unknown tool name: {tool_call.function.name}")
    
    print(f'[blue]{tool_call.function.name}[blue]', end='', flush=True)

    arguments = {}
    if tool_call.function.arguments is not None:
        arguments = json.loads(tool_call.function.arguments)
    
    print(f'[yellow]{arguments}[yellow]', end='\n', flush=True)

    # TODO: this assume super simple function signatures containing only primitive types
    result = fn(**arguments)

    print(f'[green]{result}[green]', end='\n', flush=True)

    res = {'role': 'tool', 'content': str(result), 'tool_call_id': tool_call.id}

    return res

    # pdb.set_trace()
    # if name == 'PythonTool.run':
    #     # since python tool takes only string args, we can skip argument parsing
    #     res = python_tool.run(**arguments)
    #     print(f'[green]{res}[green]', end='', flush=True)
    #     return res
    # else:
    #     raise Exception(f"Unknown tool name: {name}")

if __name__ == "__main__":
    main()
