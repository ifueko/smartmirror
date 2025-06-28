import os
from typing import List, Literal, Optional
from mcp.server.fastmcp import FastMCP

#from database_functions import add_outfit_suggestion

try:
    from django.conf import settings
    closet_inventory = settings.CLOSET_INVENTORY
except:
    from dotenv import load_dotenv
    from database_functions import fetch_closet_inventory
    load_dotenv()
    closet_inventory = fetch_closet_inventory(os.getenv('CLOSET_INVENTORY_DB_ID'), True)

mcp = FastMCP("Smart Closet MCP Server")
CLOTHING_CATEGORIES = ["Tops", "Pants", "Skirts", "Dresses", "Shoes", "Outerwear", "Accessories"]

@mcp.tool(
    name="query_closet",
    description=(
        "Gets the 'top_k' items related to 'query' in clothing category 'category' from the closet inventory. "
        "If 'top_k' is None, will return all items matching filters. "
        "If 'query' is None, will return most recently added items from the coset. "
        "If 'category' is not None, will filter the inventory for that category before querying. "
        "If all parameters are None, the entire closet is returned."
    ),
)   
async def query_closet(query: Optional[str]=None, top_k: Optional[int] = None, category: Optional[Literal[tuple(CLOTHING_CATEGORIES)]] = None):
    # TODO use embedding distance to get top k
    closet_keys = list(closet_inventory.keys())[:top_k]
    clothing_items = [closet_inventory[k] for k in closet_keys] 
    return {
        "function_called": "query_closet",
        "status": "Success",
        "clothing_items": clothing_items,
    }

def suggest_outfit(date, outfit_items):
    return {"date": date, "outfit_items": outfit_items}

@mcp.tool(
    name="create_outfit_suggestion",
    description="Create an outfit suggestion for the given ISO date. This allows the user to see the outfit suggestion on the dashboard without committing to the outfit for that date. An 'outfit' is designated as a list of clothing items, denoted by their notion page IDs, which can be found in each closet inventory listing under the key 'notion_page_id'",
)
async def create_outfit_suggestion(date: str,  outfit_items: List[str]):
    outfit_info = suggest_outfit(date, outfit_items)
    return {
        "function_called": "create_outfit_suggestion",
        "status": "Success",
        "outfit_info": outfit_info,
    }

@mcp.tool(
    name="virtual_try_on",
    description="Given an outfit, defined as a list of clothing items, this function updates the user interface to display a virtual try on of the specified outfit. Clothing items can be identified using their 'notion_page_id' within the closet inventory."
)
async def virtual_try_on(outfit: List[str]):
    return {
        "function_called": "virtual_try_on",
        "status": "Success",
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")
