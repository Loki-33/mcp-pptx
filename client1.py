from llama_cpp import Llama 
from typing import List, Tuple 
import asyncio 
import json 
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client 
import re 


class LlamaClient:
    def __init__(self, model_path, mcp_server_script):
        self.model = Llama(
            model_path,
            n_ctx=2048,
            n_threads=4,
            verbose=False 
        )
        self.mcp_server_script = mcp_server_script
        self.tools = []

    async def connect_mcp(self):
        server_params = StdioServerParameters(
            command='python',
            args=[self.mcp_server_script]
        )
        self.server_params = server_params

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                self.tools = tools_response.tools 
        print(f"Connected to MCP server. Available tools: {[t.name for t in self.tools]}\n")

    async def call_mcp_tool(self, tool_name, parameters):
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, parameters)
                return result.content[0].text if result.content else "No response"

    def extract_tool_call(self, response: str):
        """
        Extract the first valid JSON object from the response using stack-based parsing.
        """
        start = response.find('{')
        if start == -1:
            return None

        stack = []
        for i in range(start, len(response)):
            if response[i] == '{':
                stack.append('{')
            elif response[i] == '}':
                stack.pop()
                if not stack:
                    json_str = response[start:i + 1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f" JSON parse error: {e}")
                        return None
        return None

    def extract_json_from_text(self, text: str):
        """
        Extracts all valid JSON objects from text using brace depth parsing.
        Returns a list of parsed JSON dicts.
        """
        json_objects = []
        start = None
        depth = 0

        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    json_str = text[start:i + 1]
                    try:
                        obj = json.loads(json_str)
                        json_objects.append(obj)
                    except json.JSONDecodeError:
                        pass
                    start = None

        return json_objects

    async def run(self, user_message):
        """Run with automatic tool chaining for search -> presentation"""
        tools_desc = '\n'.join([
            f"- {tool.name}: {tool.description}\n  Parameters: {json.dumps(tool.inputSchema, indent=2)}"
            for tool in self.tools 
        ])

        # tools_desc = '\n'.join([
        #     f"- {tool.name}: {tool.description}\n  Example usage: {{\"tool\": \"{tool.name}\", \"parameters\": {{...}}}}"
        #     for tool in self.tools
        # ])


        prompt = f'''You are an AI assistant that can use tools to help users.

RULES:
- To call a tool: output ONLY {{"tool": "name", "parameters": {{...}}}}
- After getting tool results, you can call another tool OR give your final answer
- Final answer: respond in plain text with NO JSON

AVAILABLE TOOLS:
{tools_desc}

EXAMPLE - Multi-step task:
User: Search for cats then make a presentation
Assistant: {{"tool": "web_search", "parameters": {{"query": "cats"}}}}
[After getting search results...]
Assistant: {{"tool": "create_presentation", "parameters": {{"title": "Cats", "slides": [...]}}}}
[After presentation created...]
Assistant: I've created your 3-slide presentation about cats using the search results.

User: {user_message}'''

        for step in range(5):
            output = self.model(
                prompt,
                max_tokens=1024, 
                temperature=0.3,
                stop=['User:', '\n\nUser:'])


            response = output['choices'][0]['text'].strip()
            print(f"Model step {step+1} outupt:\n{response}\n")

            
            json_ = self.extract_json_from_text(response)
            if not json_:
                print('No json detected!!')
                return response 

            prompt += f"\n{response}\n"

            for tool_call in json_:
                if 'tool' not in tool_call or 'parameters' not in tool_call:
                    print('Invalid format')
                    continue 
                tool_name = tool_call['tool']
                parameters = tool_call['parameters']
                print(f"Calling tool: {tool_name}")
                print(f"Parameters: {json.dumps(parameters, indent=2)}")

                try:
                    result = await self.call_mcp_tool(tool_name, parameters)
                    prompt += f"Tool '{tool_name}' returned: {result}\nAssistant:"

                except Exception as e:
                    print(f"Error calling tool '{tool_name}': {e}")

        return "REACHED MAXIMMUN RASONING DEPTH"

async def main():
    client = LlamaClient(
        model_path='models/phi-2.Q3_K_L.gguf',
        mcp_server_script='server.py'
    )

    await client.connect_mcp()

    user_input = 'Write a 3 slide presentation on "ROMANCE" using web search'
        
    response = await client.run(user_input)
    print(f"\n✓ Final Result: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
