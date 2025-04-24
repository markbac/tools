#!/usr/bin/env python3
"""
generate_content_from_yaml.py

Script to generate content from a YAML file using OpenAI's Chat API.
It supports (optional) memory to ensure content flows with a common theme.

Dependencies:
- openai
- pyyaml

Install via:
pip install openai pyyaml
"""

import os
import yaml
from openai import OpenAI
from pathlib import Path

# Setup OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Config
INPUT_YAML = "out.yml"  # Path to your YAML file
OUTPUT_DIR = "generated_content"
ENABLE_MEMORY = True

# Ensure output directory exists
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# Load YAML content
with open(INPUT_YAML, "r", encoding="utf-8") as f:
    content = yaml.safe_load(f)

# Prepare memory context (if enabled)
memory_messages = []
system_prompt = {
    "role": "system",
    "content": "You are a skilled technical blog writer. Write clear, informative, and engaging content with a consistent tone and style."
}

# Function to generate content
def generate_post(title, synopsis):
    messages = memory_messages[:] if ENABLE_MEMORY else []
    messages.insert(0, system_prompt)
    messages.append({"role": "user", "content": f"Write a blog post titled '{title}' based on this synopsis:\n\n{synopsis}"})
    
    response = client.chat.completions.create(
        messages=messages,
        model="gpt-4o",
        temperature=0.7
    )

    output = response.choices[0].message.content.strip()
    if ENABLE_MEMORY:
        memory_messages.append({"role": "assistant", "content": output})
    return output

# Generate content
for category, posts in content.items():
    for post in posts:
        title = post.get("Title")
        synopsis = post.get("Synopsis", "")
        slug = title.lower().replace(" ", "_").replace("?", "").replace("'", "")
        print(f"Generating: {title}")
        try:
            blog_content = generate_post(title, synopsis)
            output_path = Path(OUTPUT_DIR) / f"{slug}.md"
            with open(output_path, "w", encoding="utf-8") as out_file:
                out_file.write(blog_content)
            print(f"Saved to: {output_path}")
        except Exception as e:
            print(f"Error generating post for '{title}': {e}")

print("All content generation complete.")
