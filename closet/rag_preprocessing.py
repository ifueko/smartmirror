import database_functions
import json
import os
import torch
from dotenv import load_dotenv
from google import genai
from google.genai import types
from notion_client import Client
from PIL import Image
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from tqdm import tqdm
import numpy as np
load_dotenv()
closet_inventory = database_functions.fetch_closet_inventory(os.getenv('CLOSET_INVENTORY_DB_ID'), False)
closet_inventory = {k: v for k, v in list(closet_inventory.items())}
from transformers import AutoProcessor, AutoModelForImageTextToText
import torch

model_path = "/Users/ifueko/Downloads/SmolVLM2-2.2B-Instruct"
processor = AutoProcessor.from_pretrained(model_path)
model = AutoModelForImageTextToText.from_pretrained(
    model_path,
    torch_dtype=torch.bfloat16,
).to("mps")

def generate_output(messages):
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device, dtype=torch.bfloat16)
    generated_ids = model.generate(**inputs, do_sample=True, top_p=0.9, temperature=0.7, max_new_tokens=256)
    generated_texts = processor.batch_decode(
        [g[inputs['input_ids'].shape[1]:] for g in generated_ids],
        skip_special_tokens=True,
    )
    print(generated_texts)
    print()
    return generated_texts

def generate_description_prompt(name, url, catalog_description):
    prompt = f"""Write a concise, two-sentence product description for the {name} shown in the image. Focus on style, color, texture, fit, and ideal use cases (e.g., casual, formal, layering). Highlight details that would help match this item with complementary outfit pieces.
"""
    messages = {
        "role": "user",
        "content": [
            {"type": "image", "url": url},
            {"type": "text", "text": prompt},
        ],
    }
    print(prompt)
    return messages

def describe_image(name, url, listing):
    return generate_output([generate_description_prompt(name, url, listing)])[0].strip()


def document_to_description(document):
    keys_to_include = ["Color", "Condition", "Season", "Category", "Style Tags", "Fit"]
    name = document["name"]
    condition = document["Condition"]
    category = document["Category"]
    color = document['Color']
    color = ", ".join(color) if type(color) == list else color
    seasons = document["Season"]
    seasons = ", ".join(seasons) if type(seasons) == list else seasons
    style_tags = document["Style Tags"]
    style_tags = ", ".join(style_tags) if type(style_tags) == list else style_tags
    fit = document["Fit"]
    if fit == "N/A":
        fit = ""
    else:
        fit = f"Fit: {fit}\n"
    description = (
        f"Product {name} in category {category}\n"
        f"Item Condition: {condition}\n"
        f"Color: {color}\n{fit}"
        f"Can be worn during the following seasons: {seasons}\n"
        f"Tags describing style: {style_tags}"
    )
    if "item_description" in document:
        description = (
            f"{description}\n"
            f"Item Description: {document['item_description']}"
        )
    return description

inventory_descriptions = []
inventory_items = []
document_ids = []
for name, item in tqdm(closet_inventory.items()):
    document_ids.append(item['notion_page_id'])
    url = item['url'].strip('/')
    description = describe_image(name, url, document_to_description(item))
    item['item_description'] = description
    inventory_descriptions.append(document_to_description(item))
    inventory_items.append(item)
print(inventory_descriptions[0])
print(len(document_ids))
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
embeddings = model.encode(inventory_descriptions)
print(embeddings.shape, type(embeddings), len(document_ids))
np.save("embeddings.npy", embeddings)
with open("embeddings_info.jsonl", "w") as f:
    for i, (document_id, document, description) in enumerate(zip(document_ids, inventory_items, inventory_descriptions)):
        item = {
            "index": i,
            "notion_id": document_id,
            "category": document["Category"],
            "embedding_description": json.dumps(description),
        }
        f.write(json.dumps(item))

# USAGE
query = "I would like to wear a cute, feminine, vibrant outfit for a picnic"
#query = "Its pretty chilly today, and i want to wear jeans and the color black"
query_embedding = model.encode(query)
similarity_scores = model.similarity(embeddings, query_embedding)
k = 3
topk_values, topk_indices = torch.topk(similarity_scores.squeeze(), k)
indices = [int(v) for v in topk_indices.numpy()]
top_k_docs = [inventory_items[i] for i in indices]
top_k_scores = [similarity_scores[i].numpy() for i in indices]
print(f"Query: {query}")
for doc, score in zip(top_k_docs, top_k_scores):
    score = float(score[0])
    print(json.dumps(doc))
    print(f"{score:.3f}\n")
