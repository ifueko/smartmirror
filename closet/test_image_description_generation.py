from transformers import pipeline
from PIL import Image
import requests
pipe = pipeline("image-text-to-text", model="HuggingFaceTB/SmolVLM-256M-Instruct")
prompt = "Concicely describe the clothing item titled `{name}` within this image."

def describe_image(pipe, image, prompt):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    outputs = pipe(text=messages, images=images, max_new_tokens=128, return_full_text=False)
    return outputs[0]["generated_text"]

