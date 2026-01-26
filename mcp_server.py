from fastmcp import FastMCP

# Import your tool modules here
from mcp_tools import news, telegram, email

# Initialize FastMCP server
mcp = FastMCP("Unified MCP Tools Server")

# 自动注册所有模块的工具
modules_to_load = [news, telegram, email]

for module in modules_to_load:
    if hasattr(module, "MCP_TOOLS"):
        for tool in module.MCP_TOOLS:
            mcp.add_tool(tool)
            print(f"Registered tool: {tool.__name__} from {module.__name__}")

if __name__ == "__main__":
    mcp.run()