
#!/usr/bin/env python3
"""
generate_from_yaml_prompt_driven.py

Generates blog posts from a YAML file using OpenAI's Chat API.
Formatting, headings, diagrams (e.g., Mermaid) and structure are handled entirely via prompt and system message.

Requires:
- openai
- pyyaml
- log_setup.py

Usage:
python generate_from_yaml_prompt_driven.py --config config_updated.yml --input blogs.yaml
"""

import os
import yaml
import argparse
from pathlib import Path
from openai import OpenAI
from openai import AuthenticationError, APIError, RateLimitError, Timeout
from log_setup import setup_logging, ContextualLoggerAdapter


def load_config(config_path):
    """Load YAML config file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def estimate_tokens(reading_time, tokens_per_minute, default_max_tokens):
    """Estimate token usage from reading time."""
    try:
        return min(int(reading_time * tokens_per_minute), default_max_tokens)
    except Exception:
        return default_max_tokens


def create_front_matter(post):
    """Create Markdown front matter."""
    front_matter = {
        "title": post.get("Title", "Untitled"),
        "tags": post.get("Tags", []),
        "reading_time": post.get("Estimated Reading Time", 6),
        "description": post.get("Description", ""),
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


def generate_post(post, config, memory_messages, logger, memory_enabled):
    """Generate content for a blog post."""
    title = post.get("Title")
    description = post.get("Description", "")
    synopsis = post.get("Synopsis", "")
    structure = post.get("Structure", "")
    diagram = post.get("Suggested Diagram/Image", "")
    reading_time_str = str(post.get("Estimated Reading Time", "6")).strip()
    reading_time = int(reading_time_str.split()[0])  # Extract number

    # Estimate max tokens
    try:
        minutes = int(str(reading_time).strip().split()[0])
    except:
        minutes = 6
    tokens = min(config.get("default_max_tokens", 3000), minutes * config.get("tokens_per_minute", 300))

    words_per_minute = config.get("words_per_minute", 250)
    word_count = minutes * words_per_minute

    prompt = config["content_prompt_template"].format(
        title=title or "No title provided.",
        description=description or "No description provided.",
        synopsis=synopsis or "No synopsis provided.",
        structure=structure or "No structure provided.",
        diagram=diagram or "No diagram provided.",    
        reading_time=reading_time or "No reading_time provided." ,
        tokens=tokens or "No max_tokens provided." ,
        word_count=word_count or "No word_count provided."
    )

    messages = memory_messages[:] if memory_enabled else []
    messages.insert(0, {"role": "system", "content": config["system_prompt"]})
    messages.append({"role": "user", "content": prompt})

    max_tokens = estimate_tokens(reading_time, config["tokens_per_minute"], config["default_max_tokens"])
    logger.info(f"📝 Generating: {title} ({reading_time} min, max_tokens={max_tokens})")
    logger.debug(f"📤 Prompt:{prompt}")

    client = OpenAI(api_key=config["api_key"])
    try:
        response = client.chat.completions.create(
            model=config["model"],
            temperature=config["temperature"],
            max_tokens=max_tokens,
            messages=messages,
            frequency_penalty=config.get("frequency_penalty", 0.0),
            presence_penalty=config.get("presence_penalty", 0.0)
        )
    except AuthenticationError as e:
        logger.error("❌ OpenAI Authentication failed. Check your API key.")
        raise SystemExit(1)
    except RateLimitError as e:
        logger.error("⚠️ Rate limit or quota exceeded. Check billing.")
        raise SystemExit(1)
    except Timeout:
        logger.error("⏱️ Request timed out.")
        raise
    except APIError as e:
        logger.error(f"❌ OpenAI API error: {str(e)}")
        raise

    result = response.choices[0].message.content.strip()
    usage = response.usage

    word_count = len(result.split())
    logger.info(f"📝 Words in generated content: {word_count}")

    logger.info(f"📊 Tokens used — prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens}, total: {usage.total_tokens}")
    logger.debug(f"📥 Response sample: {result[:30]}...")
    if memory_enabled:
        memory_messages.append({"role": "assistant", "content": result})
    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate blog content using OpenAI.")
    parser.add_argument("--config", default="config.yml", help="Path to config YAML file.")
    parser.add_argument("--input", default="blogs.yaml", help="Input blog metadata YAML.")
    parser.add_argument("--output", default="generated_content", help="Directory to write Markdown output.")
    parser.add_argument("--model", help="Override the model.")
    parser.add_argument("--temperature", type=float, help="Override temperature.")
    parser.add_argument("--max-tokens", type=int, help="Override max tokens.")
    parser.add_argument("--tokens-per-minute", type=int, help="Override tokens per minute.")
    parser.add_argument("--memory", dest="enable_memory", action="store_true", help="Enable memory between posts")
    parser.add_argument("--no-memory", dest="enable_memory", action="store_false", help="Disable memory between posts")
    parser.add_argument("--front-matter", dest="front_matter", action="store_true", help="Enable front matter")
    parser.add_argument("--no-front-matter", dest="front_matter", action="store_false", help="Disable front matter")
    parser.set_defaults(enable_memory=None, front_matter=None)

    args = parser.parse_args()

    config = load_config(args.config)
    config["model"] = args.model or config.get("default_model", "gpt-4o")
    config["temperature"] = args.temperature if args.temperature is not None else config.get("temperature", 0.7)
    config["default_max_tokens"] = args.max_tokens if args.max_tokens is not None else config.get("default_max_tokens", 1500)
    config["tokens_per_minute"] = args.tokens_per_minute if args.tokens_per_minute is not None else config.get("tokens_per_minute", 225)
    config["api_key"] = config.get("api_key") or os.getenv("OPENAI_API_KEY")
    memory_enabled = args.enable_memory if args.enable_memory is not None else config.get("enable_memory", False)
    front_matter_enabled = args.front_matter if args.front_matter is not None else config.get("enable_front_matter", False)

    if not config["api_key"]:
        raise ValueError("API key not found in config or environment.")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(name="docgen", to_console=True, to_file=True, file_path="logs/docgen.log", level="DEBUG", mode="verbose")
    logger = ContextualLoggerAdapter(logger)
    logger.info("🚀 Starting blog post generation")

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"❌ Input file not found: {input_path.resolve()}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        blog_data = yaml.safe_load(f)

    memory_messages = []

    try:
        for category, posts in blog_data.items():
            for post in posts:
                slug = post["Title"].lower().replace(" ", "_").replace("?", "").replace("'", "")
                try:
                    content = generate_post(post, config, memory_messages, logger, memory_enabled)
                    full_content = create_front_matter(post) + content if front_matter_enabled else content
                    output_path = output_dir / f"{slug}.md"
                    with open(output_path, "w", encoding="utf-8") as out_file:
                        out_file.write(full_content)
                    logger.info(f"✅ Saved: {output_path}")
                except Exception as e:
                    logger.exception(f"❌ Error generating post for '{post['Title']}': {e}")

        logger.info("🏁 All blog content generated.")

    except SystemExit:
        logger.warning("🛑 Script terminated due to critical error.")


if __name__ == "__main__":
    main()
