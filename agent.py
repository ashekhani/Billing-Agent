import asyncio
import sys
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# LAYER 3: DATA AGENT
# Connects to MCP server and fetches data
# ─────────────────────────────────────────
class DataAgent:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect(self, server_path: str):
        server_params = StdioServerParameters(
            command="python",
            args=[server_path],
            env=None
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        print("[Data Agent] Connected to MCP server.")

    async def fetch_tools(self):
        response = await self.session.list_tools()
        return response.tools

    async def call_tool(self, tool_name: str, tool_args: dict):
        print(f"[Data Agent] Calling MCP tool: {tool_name} with args: {tool_args}")
        result = await self.session.call_tool(tool_name, tool_args)
        return result

    async def cleanup(self):
        await self.exit_stack.aclose()


# ─────────────────────────────────────────
# LAYER 2: SERVING AGENT
# Uses Claude + data from Data Agent to answer prompts
# ─────────────────────────────────────────
class ServingAgent:
    def __init__(self, data_agent: DataAgent):
        self.anthropic = Anthropic()
        self.data_agent = data_agent
        self.context_memory = []  # RAG-style context memory

    async def answer(self, prompt: str) -> str:
        print(f"[Serving Agent] Received prompt: {prompt}")

        tools = await self.data_agent.fetch_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in tools]

        self.context_memory.append({"role": "user", "content": prompt})

        response = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=self.context_memory,
            tools=available_tools
        )

        final_text = []

        for content in response.content:
            if content.type == "text":
                final_text.append(content.text)
            elif content.type == "tool_use":
                tool_name = content.name
                tool_args = content.input

                # Data Agent fetches the data via MCP server
                result = await self.data_agent.call_tool(tool_name, tool_args)

                print(f"[Serving Agent] Received data from Data Agent.")

                self.context_memory.append({"role": "assistant", "content": response.content})
                self.context_memory.append({"role": "user", "content": result.content})

                follow_up = self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    messages=self.context_memory,
                )
                final_answer = follow_up.content[0].text
                self.context_memory.append({"role": "assistant", "content": final_answer})
                final_text.append(final_answer)

        return "\n".join(final_text)


# ─────────────────────────────────────────
# LAYER 1: ORCHESTRATOR AGENT
# Receives user prompts and coordinates the agents
# ─────────────────────────────────────────
class OrchestratorAgent:
    def __init__(self, serving_agent: ServingAgent):
        self.serving_agent = serving_agent

    async def run(self):
        print("\n[Orchestrator] Billing Agent started. Type 'quit' to exit.\n")
        while True:
            try:
                prompt = input("User Prompt: ").strip()
                if prompt.lower() == "quit":
                    break
                response = await self.serving_agent.answer(prompt)
                print(f"\n[Orchestrator] Response: {response}\n")
            except Exception as e:
                print(f"[Orchestrator] Error: {str(e)}")


# ─────────────────────────────────────────
# MAIN — Wire everything together
# ─────────────────────────────────────────
async def main():
    if len(sys.argv) < 2:
        print("Usage: python agent.py <path_to_billing_server.py>")
        sys.exit(1)

    data_agent = DataAgent()
    await data_agent.connect(sys.argv[1])

    serving_agent = ServingAgent(data_agent)
    orchestrator = OrchestratorAgent(serving_agent)

    try:
        await orchestrator.run()
    finally:
        await data_agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
