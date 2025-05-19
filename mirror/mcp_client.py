import asyncio
import aiohttp
import os
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from google import genai
from google.genai import types

INTERACTION_SERVICE_URL = os.getenv(
    "INTERACTION_SERVICE_URL", "http://localhost:8000/api"
)
load_dotenv()
class MCPClient:
    def __init__(self, fake=False):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.genai_client = genai.Client(api_key=os.getenv("GOOGLE_AI_STUDIO_API_KEY"))
        self.model_id = "gemini-1.5-flash"
        self.max_tool_turns = 5
        self.history: list[types.Content] = []
        self.interaction_service_url = INTERACTION_SERVICE_URL
        self.fake = fake

    async def send_thought(self, thought):
        if self.fake:
            print(thought)
            return True
        payload_to_service = {"thought": thought}
        service_url = self.interaction_service_url
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{service_url}/add_thought", json=payload_to_service
            ) as resp:
                if resp.status not in [200, 201, 202]:
                    return False
            return True

    async def _execute_tool_calls(
        self, function_calls: list[types.FunctionCall],
    ) -> list[types.Part]:
        tool_response_parts: list[types.Part] = []
        await self.send_thought(f"Executing {len(function_calls)} tool call{'s' if len(function_calls) > 1 else ''}...")

        for func_call in function_calls:
            tool_name = func_call.name
            args = func_call.args if isinstance(func_call.args, dict) else {}
            await self.send_thought(f"Attempting to call '{tool_name}' with args '{args}'")

            tool_result_payload: dict[str, Any]
            try:
                tool_result = await self.session.call_tool(tool_name, args)
                await self.send_thought(f"  Session tool '{tool_name}' execution finished.")
                result_text = ""
                if (
                    hasattr(tool_result, "content")
                    and tool_result.content
                    and hasattr(tool_result.content[0], "text")
                ):
                    result_text = tool_result.content[0].text or ""
                if hasattr(tool_result, "isError") and tool_result.isError:
                    error_message = (
                        result_text
                        or f"Tool '{tool_name}' failed without specific error message."
                    )
                    await self.send_thought(f"Tool '{tool_name}' reported an error: {error_message}")
                    tool_result_payload = {"error": error_message}
                else:
                    await self.send_thought(
                        f"Tool '{tool_name}' succeeded. Result snippet: {result_text[:15]}..."
                    )  # Log snippet
                    tool_result_payload = {"result": result_text}

            except Exception as e:
                # Catch exceptions during the tool call itself
                error_message = f"Tool execution framework failed: {type(e).__name__}: {e}"
                await self.send_thought(f"Error executing tool '{tool_name}': {error_message}")
                tool_result_payload = {"error": error_message}

            # Create a FunctionResponse Part to send back to the model
            tool_response_parts.append(
                types.Part.from_function_response(
                    name=tool_name, response=tool_result_payload
                )
            )
        await self.send_thought(f"Finished executing tool call{'s' if len(function_calls)>1 else ''}.")
        return tool_response_parts



    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        if self.session is not None:
            return
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using Gemini and available tools"""
        self.history += [types.Content(role="user", parts=[types.Part(text=query)])]

        session_tool_list = await self.session.list_tools()
        gemini_tool_config = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.inputSchema,  # Assumes inputSchema is compatible
                )
                for tool in session_tool_list.tools
            ]
        )
        response = await self.genai_client.aio.models.generate_content(
            model=self.model_id,
            contents=self.history,  # Send updated history
            config=types.GenerateContentConfig(
                temperature=1.0,
                tools=[gemini_tool_config],
            ),
        )
        if not response.candidates:
            return response.text
        self.history.append(response.candidates[0].content)

        # --- 3. Tool Calling Loop ---
        turn_count = 0
        # Check specifically for FunctionCall objects in the latest response part
        latest_content = response.candidates[0].content
        has_function_calls = any(part.function_call for part in latest_content.parts)
        while has_function_calls and turn_count < self.max_tool_turns:
            turn_count += 1
            await self.send_thought(f"\n--- Tool Turn {turn_count}/{self.max_tool_turns} ---")

            # --- 3.1 Execute Pending Function Calls ---
            function_calls_to_execute = [
                part.function_call for part in latest_content.parts if part.function_call
            ]
            tool_response_parts = await self._execute_tool_calls(
                function_calls_to_execute
            )

            # --- 3.2 Add Tool Responses to History ---
            # Send back the results for *all* function calls from the previous turn
            self.history.append(
                types.Content(role="function", parts=tool_response_parts)
            )  # Use "function" role
            await self.send_thought(f"Added {len(tool_response_parts)} tool response part(s) to history.")

            # --- 3.3 Make Subsequent Model Call with Tool Responses ---
            await self.send_thought("Making subsequent API call to Gemini with tool responses...")
            response = await self.genai_client.aio.models.generate_content(
                model=self.model_id,
                contents=self.history,  # Send updated history
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    tools=[gemini_tool_config],
                ),
            )
            await self.send_thought("Subsequent response received.")

            # --- 3.4 Append latest model response and check for more calls ---
            if not response.candidates:
                await self.send_thought("Warning: Subsequent model response has no candidates.")
                break  # Exit loop if no candidates are returned
            latest_content = response.candidates[0].content
            self.history.append(latest_content)
            has_function_calls = any(part.function_call for part in latest_content.parts)
            if not has_function_calls:
                await self.send_thought(
                    "Model response contains text, no further tool calls requested this turn."
                )

        # --- 4. Loop Termination Check ---
        if turn_count >= self.max_tool_turns and has_function_calls:
            await self.send_thought(
                f"Maximum tool turns ({self.max_tool_turns}) reached. Exiting loop even though function calls might be pending."
            )
        elif not has_function_calls:
            await self.send_thought("Tool calling loop finished naturally (model provided text response).")

        # --- 5. Return Final Response ---
        await self.send_thought("Agent loop finished. Returning final response.")
        print(response.candidates)
        print(response.text)
        return response.text

    async def chat_loop(self):
        """Run an interactive chat loop. For testing at the command line."""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)
    client = MCPClient(fake=True)
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()
if __name__ == '__main__':
    import sys
    asyncio.run(main())
