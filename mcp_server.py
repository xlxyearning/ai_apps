from fastmcp import FastMCP

# Import your tool modules here
from mcp_tools import news, telegram, email

# Initialize FastMCP server
mcp = FastMCP("Unified MCP Tools Server")

# 自动注册所有模块的工具
modules_to_load = [news, telegram, email]

for module in modules_to_load:
    if hasattr(module, "MCP_TOOLS"):
        for tool_func in module.MCP_TOOLS:
            # Use the decorator syntax to register the function
            mcp.tool()(tool_func)
            print(f"Registered tool: {tool_func.__name__} from {module.__name__}")

if __name__ == "__main__":
    mcp.run()