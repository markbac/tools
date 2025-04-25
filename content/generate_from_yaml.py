
#!/usr/bin/env python3
"""
generate_content_from_yaml.py

Generates blog content from a structured YAML file using OpenAI's Chat API.
- Supports memory context for thematic continuity
- Loads configuration from YAML
- CLI overrides for model, temperature, max_tokens, tokens_per_minute
- Logs API requests and responses
- Outputs Markdown with front matter and diagram placeholders

Requires:
- openai
- pyyaml
- log_setup.py (your logging module)

Install dependencies:
pip install openai pyyaml colourlog
"""

import os
import yaml
import argparse
from pathlib import Path
from openai import OpenAI
from log_setup import setup_logging, ContextualLoggerAdapter


def load_config(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def estimate_tokens(reading_time, tokens_per_minute, default_max_tokens):
    try:
        return min(int(reading_time * tokens_per_minute), default_max_tokens)
    except Exception:
        return default_max_tokens


def create_front_matter(post):
    front_matter = {
        "title": post.get("Title", "Untitled"),
        "tags": post.get("Tags", []),
        "reading_time": post.get("Estimated Reading Time", 6),
        "description": post.get("Short Description", ""),
        "draft": False
    }

    image = post.get("Suggested Diagram/Image")
    if image:
        front_matter["image"] = image

    fm_lines = ["---"]
    for key, value in front_matter.items():
        if isinstance(value, list):
            value = "[" + ", ".join(f"'{v}'" for v in value) + "]"
        fm_lines.append(f"{key}: {value}")
    fm_lines.append("---\n")
    return "\n".join(fm_lines)


def insert_diagram_placeholder(content, placeholder_text):
    if placeholder_text:
        return f"![{placeholder_text}](images/placeholder.png)\n\n" + content
    return content


def generate_post(title, synopsis, reading_time, config, memory_messages, logger):
    prompt = config["content_prompt_template"].format(title=title, synopsis=synopsis)
    messages = memory_messages[:] if memory_messages else []
    messages.insert(0, {"role": "system", "content": config["system_prompt"]})
    messages.append({"role": "user", "content": prompt})

    max_tokens = estimate_tokens(reading_time, config["tokens_per_minute"], config["default_max_tokens"])
    logger.info(f"📝 Generating: {title} ({reading_time} min, max_tokens={max_tokens})")
    logger.debug(f"📤 Prompt: {prompt}")

    client = OpenAI(api_key=config["api_key"])
    response = client.chat.completions.create(
        model=config["model"],
        temperature=config["temperature"],
        max_tokens=max_tokens,
        messages=messages
    )

    result = response.choices[0].message.content.strip()
    logger.debug(f"📥 Response for '{title}': {result[:300]}...")
    memory_messages.append({"role": "assistant", "content": result})
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate blog content using OpenAI.")
    parser.add_argument("--config", default="config.yml", help="Path to config YAML file.")
    parser.add_argument("--input", default="out.yml", help="Input blog metadata YAML.")
    parser.add_argument("--output", default="generated_content", help="Directory to write Markdown output.")
    parser.add_argument("--model", help="Override the model.")
    parser.add_argument("--temperature", type=float, help="Override temperature.")
    parser.add_argument("--max-tokens", type=int, help="Override max tokens.")
    parser.add_argument("--tokens-per-minute", type=int, help="Override tokens per minute.")
    args = parser.parse_args()

    config = load_config(args.config)
    config["model"] = args.model or config.get("default_model", "gpt-4o")
    config["temperature"] = args.temperature if args.temperature is not None else config.get("temperature", 0.7)
    config["default_max_tokens"] = args.max_tokens if args.max_tokens is not None else config.get("default_max_tokens", 1500)
    config["tokens_per_minute"] = args.tokens_per_minute if args.tokens_per_minute is not None else config.get("tokens_per_minute", 225)
    config["api_key"] = config.get("api_key") or os.getenv("OPENAI_API_KEY")
    if not config["api_key"]:
        raise ValueError("API key not found in config or environment.")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(name="docgen", to_console=True, to_file=True, file_path="logs/docgen.log", level="INFO", mode="verbose")
    logger = ContextualLoggerAdapter(logger)
    logger.info("🚀 Starting blog post generation")

    with open(args.input, "r", encoding="utf-8") as f:
        blog_data = yaml.safe_load(f)

    memory_messages = []

    for category, posts in blog_data.items():
        for post in posts:
            title = post.get("Title")
            synopsis = post.get("Synopsis", "")
            reading_time = post.get("Estimated Reading Time", 6)
            diagram_note = post.get("Suggested Diagram/Image", "")
            slug = title.lower().replace(" ", "_").replace("?", "").replace("'", "")

            try:
                article = generate_post(title, synopsis, reading_time, config, memory_messages, logger)
                front_matter = create_front_matter(post)
                article_with_diagram = insert_diagram_placeholder(article, diagram_note)

                output_path = output_dir / f"{slug}.md"
                with open(output_path, "w", encoding="utf-8") as out_file:
                    out_file.write(front_matter + article_with_diagram)
                logger.info(f"✅ Saved: {output_path}")
            except Exception as e:
                logger.exception(f"❌ Error generating post for '{title}': {e}")

    logger.info("🏁 All blog content generated.")


if __name__ == "__main__":
    main()
