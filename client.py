from llama_cpp import Llama 
from typing import List, Tuple 
import asyncio 
import json 
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client 
import re 
'''
Generating Powerpoint presentation by connecting phi-model with the python-pptx library using MCP 


'''

class LlamaClient:
    def __init__(self, model_path, mcp_server_script):
        self.model = Llama(
            model_path,
            n_ctx=2048,
            n_threads=4,
            verbose=False 
        )

        self.mcp_server_script = mcp_server_script
        self.tools=[]

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


    async def run(self, user_message):
        tools_desc = '\n'.join([
            f"- {tool.name}: {tool.description}\n parameters: {json.dumps(tool.inputSchema, indent=2)}"
            for tool in self.tools 
        ])

        prompt = '''You are a helpful assistant with access to tools. When you need to create a presentation, you should generate ALL the content yourself including titles and bullet points for each slide.
            
        When using tools, respond with JSON in this exact format:
        {{"tool":"tool_name", "parameters": {{"param1":"value1"}}}}

        Available tools:
        {tools_desc}
        
        Example of creating a 3-slide presentation about Python:
        {{"tool": "create_presentation", "parameters": {{
        "title": "Introduction to Python",
        "slides": [
            {{
                "title": "What is Python?",
                "bullet_points": ["High-level programming language", "Easy to learn and read", "Versatile for many applications"]
            }},
            {{
                "title": "Key Features",
                "bullet_points": ["Dynamic typing", "Extensive standard library", "Large community support"]
            }},
            {{
                "title": "Getting Started",
                "bullet_points": ["Install Python from python.org", "Use pip for packages", "Start with simple scripts"]
            }}
        ],
        "filename": "python_intro.pptx"
        }}}}
        If you don't need to use a tool, just respond normally in plain text.
        
        User: {user_message}'''.format(tools_desc=tools_desc, user_message=user_message)
        
        
        
        output = self.model(
            prompt, 
            max_tokens=512,
            temperature=0.7,
            stop=['User:', '\n\n\n'],
        )
        
        response = output['choices'][0]['text'].strip()
        tool_call = self.extract_tool_call(response)

        try:
    
            if "tool" in tool_call and "parameters" in tool_call:
                print(f"\n Calling tool: {tool_call['tool']}")
                print(f" parameters: {tool_call['parameters']}")

                result = await self.call_mcp_tool(
                    tool_name = tool_call['tool'],
                    parameters= tool_call['parameters']
                )

                return result

        except json.JSONDecodeError as e:
            print("JSON DESCODING ERROR:",e) 

        return response

async def main():
    client = LlamaClient(
        model_path='models/phi-2.Q3_K_L.gguf',
        mcp_server_script='server.py'
    )

    await client.connect_mcp()

    user_input= 'Write me a 3-slide presentation on "Romance"'
    user_input1 = 'Hello how are you?'
    response = await client.run(user_input)
    print(f"Result: {response}\n")

if __name__ == "__main__":
    asyncio.run(main())
