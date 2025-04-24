#!/usr/bin/env python3
"""
md_yaml_converter.py

Converts between a Markdown table and a YAML list of dictionaries.

- Automatically detects conversion mode based on input file extension (.md or .yml/.yaml)
- Defaults output file to the same base name with the opposite extension
- Logs detailed progress and errors using a structured logging system

Requirements:
    pip install pyyaml colourlog python-json-logger tqdm

Usage:
    python md_yaml_converter.py --input blog.md
    python md_yaml_converter.py --input blog.yml --output converted.md
"""

import argparse
import os
import sys
import yaml

from log_setup import setup_logging, ContextualLoggerAdapter, set_log_context, log_exception

logger = setup_logging(name="md_yaml_converter", to_console=True, to_file=False, level="DEBUG", mode="verbose")
logger = ContextualLoggerAdapter(logger)


def markdown_to_yaml(md_path: str, yaml_path: str) -> None:
    """
    Convert a Markdown table to YAML.
    
    Args:
        md_path (str): Path to the input Markdown file.
        yaml_path (str): Path to the output YAML file.
    """
    logger.info(f"Converting Markdown to YAML: {md_path} -> {yaml_path}")
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        headers = [h.strip() for h in lines[0].strip('|').split('|')]
        records = []

        for line in lines[2:]:  # Skip header and separator
            fields = [field.strip() for field in line.strip('|').split('|')]
            record = dict(zip(headers, fields))
            records.append(record)

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(records, f, sort_keys=False, allow_unicode=True)

        logger.info(f"Successfully wrote {len(records)} records to YAML.")
    except Exception as exc:
        log_exception(logger, "Error converting Markdown to YAML.")
        raise exc


def yaml_to_markdown(yaml_path: str, md_path: str) -> None:
    """
    Convert a YAML list of dictionaries to a Markdown table.
    
    Args:
        yaml_path (str): Path to the input YAML file.
        md_path (str): Path to the output Markdown file.
    """
    logger.info(f"Converting YAML to Markdown: {yaml_path} -> {md_path}")
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            records = yaml.safe_load(f)

        if not records:
            logger.warning("YAML file is empty or malformed.")
            return

        headers = list(records[0].keys())
        rows = [headers] + [[str(r.get(h, '')) for h in headers] for r in records]

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('| ' + ' | '.join(headers) + ' |\n')
            f.write('|:' + ':|:'.join(['-' for _ in headers]) + ':|\n')
            for row in rows[1:]:
                f.write('| ' + ' | '.join(row) + ' |\n')

        logger.info(f"Successfully wrote Markdown table with {len(rows) - 1} rows.")
    except Exception as exc:
        log_exception(logger, "Error converting YAML to Markdown.")
        raise exc


def detect_mode_from_input(file_path: str) -> str:
    """
    Determine conversion mode from input file extension.

    Args:
        file_path (str): Path to input file.

    Returns:
        str: 'to-yaml' or 'to-md'
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.md', '.markdown']:
        return 'to-yaml'
    elif ext in ['.yml', '.yaml']:
        return 'to-md'
    else:
        logger.error("Unsupported input file type. Use .md, .yml, or .yaml.")
        sys.exit(1)


def default_output_filename(input_file: str, mode: str) -> str:
    """
    Generate default output file name by swapping extension.

    Args:
        input_file (str): Input file name.
        mode (str): 'to-yaml' or 'to-md'

    Returns:
        str: Suggested output file name.
    """
    base, _ = os.path.splitext(input_file)
    return f"{base}.yml" if mode == 'to-yaml' else f"{base}.md"


def main():
    parser = argparse.ArgumentParser(description="Convert Markdown table <-> YAML list.")
    parser.add_argument('--input', required=True, help="Input file path (.md or .yml/.yaml)")
    parser.add_argument('--output', help="Optional output file path")

    args = parser.parse_args()

    mode = detect_mode_from_input(args.input)
    output_file = args.output or default_output_filename(args.input, mode)

    set_log_context(input=args.input, output=output_file, mode=mode)

    if mode == 'to-yaml':
        markdown_to_yaml(args.input, output_file)
    else:
        yaml_to_markdown(args.input, output_file)


if __name__ == "__main__":
    main()
