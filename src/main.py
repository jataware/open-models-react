import os
from groq import Groq, APIError
from groq.types.chat import ChatCompletionMessageParam, ChatCompletionSystemMessageParam, ChatCompletionAssistantMessageParam, ChatCompletionToolMessageParam, ChatCompletionUserMessageParam, ChatCompletionMessageToolCallParam
from groq.types.chat.chat_completion_chunk import ChoiceDeltaToolCallFunction, ChoiceDeltaToolCall, ChatCompletionChunk
from easyrepl import REPL
from rich import print
import json
from typing import Callable, Literal, Generator

from archytas.tools import PythonTool



import pdb

# # TODO: this is a pretty hacky/manual way for managing tools
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
python_tool = PythonTool() # e.g. whether or not to instantiate the tool should be left to the library user
tool_fn_map: dict[str, Callable] = {
    'PythonTool.run': python_tool.run,
}


SYSTEM_MESSAGE = '''\
You are a helpful assistant. When the user asks you a question, if useful, you can make use of the tools available to you to answer.
The system will show you the result of any tool calls, and let you continue working until you decide you are done. 
'''

Model = Literal[
    'deepseek-r1-distill-llama-70b',
    'meta-llama/llama-4-maverick-17b-128e-instruct',
    'llama-3.3-70b-versatile',

]

class GroqReActAgent():
    def __init__(self, model:Model, tool_schemas:list[dict]):
        self.messages = [ChatCompletionSystemMessageParam(role='system', content=SYSTEM_MESSAGE)]
        self.tool_schemas = tool_schemas
        self.model = model
        self.client = Groq()

        # TODO: could take functions for doing side effects on each chunk
    
    def ReAct(self, query: str):
        self.messages.append(ChatCompletionUserMessageParam(role="user", content=query))
        
        while True:
        
            gen = self.client.chat.completions.create(
                messages=self.messages,
                model=self.model,
                stream=True,
                tools=self.tool_schemas,
                tool_choice="auto"
            )

            # process the stream (combining all chunks into a single message)
            print(f'[blue]<new message>[blue]', flush=True)
            reasoning, message = self.process_stream(gen)
            self.messages.append(message)

            # process each of the tool calls, and show the agent the results
            # TODO: handle tool errors
            # tool_call_results = [self.exec_tool_call(tool_call) for tool_call in message["tool_calls"]]
            # self.messages.extend(tool_call_results)
            for tool_call in message['tool_calls']:
                try:
                    result = self.exec_tool_call(tool_call)
                    self.messages.append(result)
                except Exception as e:
                    print(f'[red]Error in tool call: {e}[red]', end='', flush=True)
                    self.messages.append(ChatCompletionToolMessageParam(role='tool', content=str(e), tool_call_id=tool_call.id))


            # exit react loop if tool message was empty
            if not message['tool_calls']:# and not message["content"]:
                print(f'[yellow]Breaking out of react loop[yellow]', flush=True)
                break
            

            # # handle any special tool calls
            # # handle exiting the loop
            # for tool_call in message["tool_calls"]:
            #     if tool_call.function.name == 'done_working':
            #         print(f'[green]{tool_call.function.arguments}[green]', end='', flush=True)
            #         break # skip the else clause, causing us to break out of the react loop
            # else:
            #     # continue the react loop
            #     continue
            
            # # exit the react loop
            # break

    def process_stream(self, gen: Generator[ChatCompletionChunk, None, None]) -> tuple[str, ChatCompletionAssistantMessageParam]:

        reasoning_chunks: list[str] = []
        content_chunks: list[str] = []
        tool_calls = []


        try:
            for chunk in gen:
                
                # done streaming
                if chunk.choices[0].finish_reason is not None:
                    print(f'[red]<finish_reason {chunk.choices[0].finish_reason} />[red]', end='', flush=True)
                    break

                delta = chunk.choices[0].delta
                
                if delta.content is not None:
                    print(delta.content, end='', flush=True)
                    content_chunks.append(delta.content)
                
                elif delta.reasoning is not None:
                    print(f'[green]{delta.reasoning}[green]', end='', flush=True)
                    reasoning_chunks.append(delta.reasoning)
                
                elif delta.tool_calls is not None:
                    tool_calls.extend(delta.tool_calls)

                else: ... # nothing to do
        except APIError as e:
            print(f'[red]Error in stream: {e}[red]', end='', flush=True)
            content_chunks.append(f'\nMESSAGE ERROR: {e}')

        print()

        # reconstruct the agent message and append it to the list of messages
        content = ''.join(content_chunks)
        reasoning = ''.join(reasoning_chunks)
        message = ChatCompletionAssistantMessageParam(role = 'assistant', content = content, tool_calls = tool_calls)

        return reasoning, message

    def exec_tool_call(self, tool_call: ChoiceDeltaToolCall) -> ChatCompletionToolMessageParam:
        """Safe tool call interface. Failures are caught and converted to a message"""
        try:
            return self._exec_tool_call(tool_call)
        except Exception as e:
            print(f'[red]Error in tool call: {e}[red]', end='', flush=True)
            return ChatCompletionToolMessageParam(role='tool', content=str(e), tool_call_id=tool_call.id)

    def _exec_tool_call(self, tool_call: ChoiceDeltaToolCall) -> ChatCompletionToolMessageParam:
        """Inner attempt to call a tool. can raise exceptions"""
        try:
            fn = tool_fn_map[tool_call.function.name]
        except KeyError:
            # TODO: apparently you can return a message with "is_error": true, but I'm not seeing it in the docs/types
            raise Exception(f"Unknown tool name: {tool_call.function.name}")
        
        print(f'[blue]{tool_call.function.name}[blue]', end='', flush=True)

        arguments = {}
        if tool_call.function.arguments is not None:
            arguments = json.loads(tool_call.function.arguments)
        
        print(f'[yellow]{arguments}[yellow]', end='\n', flush=True)

        # TODO: this assume super simple function signatures containing only primitive types
        result = fn(**arguments)

        print(f'[green](tool results){result}[green]', end='\n', flush=True)

        res = ChatCompletionToolMessageParam(role='tool', content=str(result), tool_call_id=tool_call.id)

        return res


def claude_version():
    from archytas.react import ReActAgent
    from archytas.models.anthropic import AnthropicModel

    agent = ReActAgent(
        model=AnthropicModel({
            'model_name':'claude-3-7-sonnet-latest',
            'api_key':os.environ.get('ANTHROPIC_API_KEY'),
        }),
        tools=[python_tool],
        allow_ask_user=False,
        verbose=True
    )

    for query in REPL(history_file='.chat'):
        res = agent.react(query)
        print(f'[green]{res}[green]', end='\n', flush=True)


def main():
    
    agent = GroqReActAgent(
        model='llama-3.3-70b-versatile',
        tool_schemas=[python_tool_schema]
    )    
    for query in REPL(history_file='.chat'):
        agent.ReAct(query)
    
    
    

if __name__ == "__main__":
    # main()
    claude_version()
