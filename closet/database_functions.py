import os
import re
import requests
from dotenv import load_dotenv
from notion_client import Client
from pathvalidate import sanitize_filepath

CLOSET_SAVE_PATH = "closet"
CLOSET_ROOT_PATH = "/static/closet/inventory"

def fetch_outfits(notion, db_id, start_date, inventory_by_id): 
    global response, query_results
    filt = {"property": "Date", "date": {"equals": start_date}}
    response = notion.databases.query(
        **{
            "database_id": db_id,
            "sorts": [{"property": "Created", "direction": "descending"}], # get most recent outfit if multiple for day
            "filter": filt,
        }
    )
    results = response["results"]
    outfits = []
    for result in results:
        outfit = []
        for item in result["properties"]["Items Worn"]['relation']:
            item_listing = inventory_by_id[item['id']]
            outfit.append(item_listing)
        outfits.append(outfit)
    return outfits

def fetch_closet_inventory(db_id, return_urls=False):
    load_dotenv()
    notion = Client(auth=os.getenv('NOTION_API_KEY'))
    response = {
        "has_more": True,
        "next_cursor": None
    }
    query_results = []
    print("Loading inventory items...")
    while response["has_more"]:
        query_dict = {
            "database_id": db_id,
            "sorts": [{"property": "Item Name", "direction": "descending"}],
        }
        if response['next_cursor'] is not None:
            query_dict['start_cursor'] = response['next_cursor']
        response = notion.databases.query(**query_dict)
        latest = response["results"]
        query_results.extend(latest)
    inventory = {}
    for result in query_results:
        name = result['properties']['Item Name']['title'][0]['plain_text']
        listing = {}
        for key, value in result["properties"].items():
            if key in ["Item Name", "Image"]:
                continue
            prop_type = value["type"]
            value = value[prop_type]
            if type(value) == dict:
                if "name" in value:
                    value = value['name']
                else:
                    value = value['start']
            elif type(value) == list:
                value = [v for i in value for k, v in i.items() if k not in ["id", "color"]]
            listing[key] = value
        if return_urls:
            url = result['properties']['Image']['files'][0]['file']['url']
        else:
            url = name_to_static_path(name)
        listing.update({
            "notion_page_id": result["id"],
            "url": url,
            "name": name,
        })
        inventory[name] = listing
    return inventory

def name_to_static_path(name):
    filepath = ''.join(i for i in name.replace(' ','_') if ord(i) < 128)
    return sanitize_filepath(f"{CLOSET_ROOT_PATH}/{filepath}.jpg")


if __name__ == "__main__":
    import os
    from io import BytesIO
    from PIL import Image
    from tqdm import tqdm
    import json
    load_dotenv()
    # MAKE CLOSET INVENTORY IMAGES
    closet_inventory = fetch_closet_inventory(os.getenv('CLOSET_INVENTORY_DB_ID'), True)
    os.makedirs(CLOSET_ROOT_PATH.strip('/'), exist_ok=True)
    for listing in (pbar := tqdm(closet_inventory.values())):
        response = requests.get(listing['url'])
        path = name_to_static_path(listing['name']).strip('/')
        img = Image.open(BytesIO(response.content)).convert('RGB')
        assert not os.path.exists(path), f"PATH EXISTS {path}"
        img.save(path)
        pbar.set_description(f"Saved {listing['name']} to {path}")
    # TEST LOAD OUTFITS
    """
    from datetime import date, timedelta
    import json

    closet_inventory = fetch_closet_inventory(notion, os.getenv('CLOSET_INVENTORY_DB_ID'), False)
    db_id = os.getenv("OUTFITS_DB_ID")
    today = date.today()
    inventory_by_id = {listing['notion_page_id']: listing | {"name": name, "notion_page_id": ""} for name, listing in closet_inventory.items()} 
    outfits_by_date = {}
    for i in range(7):
        outfit_date = today + timedelta(days=i)
        outfit_date_iso = outfit_date.isoformat()
        outfits = fetch_outfits(notion, db_id, outfit_date_iso, inventory_by_id)
        outfits_by_date[str(outfit_date)] = []
        if len(outfits) > 0:
            outfits_by_date[str(outfit_date)] = outfits[0]
    print(json.dumps(outfits_by_date, indent=2))
    """
