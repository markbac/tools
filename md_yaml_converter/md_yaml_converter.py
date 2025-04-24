#!/usr/bin/env python3
"""
md_yaml_converter.py

Converts between a Markdown table and a YAML (or JSON) list of dictionaries.
Includes validation, support for lists/multiline fields, dry-run mode,
and unit-testable structure.

Requirements:
    pip install pyyaml colourlog python-json-logger tqdm

Usage:
    python md_yaml_converter.py --input input.md
    python md_yaml_converter.py --input input.yml --output output.md
    python md_yaml_converter.py --input input.yml --dry-run
"""

import argparse
import os
import sys
import yaml
import json
from typing import List

from log_setup import setup_logging, ContextualLoggerAdapter, set_log_context, log_exception

logger = setup_logging(name="md_yaml_converter", to_console=True, to_file=False, level="DEBUG", mode="verbose")
logger = ContextualLoggerAdapter(logger)

def validate_markdown_table(lines: List[str]) -> bool:
    """Validate the structure of a Markdown table, checking header consistency with each row."""
    if len(lines) < 3:
        logger.error("Markdown table too short to be valid.")
        return False

    headers = lines[0].strip('|').split('|')
    for i, line in enumerate(lines[2:], start=3):
        fields = line.strip('|').split('|')
        if len(fields) != len(headers):
            logger.warning(f"Row {i} has {len(fields)} fields but expected {len(headers)}: {fields}")
    return True

def markdown_to_yaml(md_path: str, output_path: str, output_format: str, dry_run: bool = False) -> None:
    """Convert a Markdown table to YAML or JSON format.

    Args:
        md_path (str): Path to the input Markdown file.
        output_path (str): Path to the output YAML or JSON file.
        output_format (str): Either 'yaml' or 'json'.
        dry_run (bool): If True, only parses and logs, does not write.
    """
    logger.info(f"Converting Markdown to {output_format.upper()}: {md_path} -> {output_path}")
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        if not validate_markdown_table(lines):
            return

        headers = [h.strip() for h in lines[0].strip('|').split('|')]
        records = []

        for line in lines[2:]:
            fields = [field.strip() for field in line.strip('|').split('|')]
            record = dict(zip(headers, [parse_markdown_field(field) for field in fields]))
            records.append(record)

        if dry_run:
            logger.info(f"Dry run: parsed {len(records)} records. Nothing written.")
            return

        with open(output_path, 'w', encoding='utf-8') as f:
            if output_format == 'yaml':
                yaml.dump(records, f, sort_keys=False, allow_unicode=True)
            elif output_format == 'json':
                json.dump(records, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Wrote {len(records)} records to {output_path}")
    except Exception as exc:
        log_exception(logger, "Failed Markdown to YAML/JSON conversion.")
        raise exc

def parse_markdown_field(value: str):
    """Convert bullet-style Markdown content to list if applicable, otherwise return the value.

    Args:
        value (str): Cell content from a Markdown table.

    Returns:
        Union[str, list]: Parsed value.
    """
    if value.startswith('- '):
        return [line.lstrip('- ').strip() for line in value.split('\\n') if line.strip()]
    return value

def yaml_to_markdown(input_path: str, output_path: str, dry_run: bool = False) -> None:
    """Convert a YAML list of dicts to a Markdown table.

    Args:
        input_path (str): Path to the YAML input file.
        output_path (str): Path to the Markdown output file.
        dry_run (bool): If True, only logs parsed result.
    """
    logger.info(f"Converting YAML to Markdown: {input_path} -> {output_path}")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            records = yaml.safe_load(f)

        if not records:
            logger.warning("YAML file is empty or malformed.")
            return

        headers = list(records[0].keys())
        rows = [headers] + [[format_markdown_cell(r.get(h, '')) for h in headers] for r in records]

        if dry_run:
            logger.info(f"Dry run: Would convert {len(records)} rows to Markdown. Nothing written.")
            return

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('| ' + ' | '.join(headers) + ' |\n')
            f.write('|:' + ':|:'.join(['-' for _ in headers]) + ':|\n')
            for row in rows[1:]:
                f.write('| ' + ' | '.join(row) + ' |\n')

        logger.info(f"✅ Wrote Markdown table with {len(rows) - 1} rows.")
    except Exception as exc:
        log_exception(logger, "Failed YAML to Markdown conversion.")
        raise exc

def format_markdown_cell(value) -> str:
    """Format a cell's value for Markdown output, handling lists.

    Args:
        value: Original value from YAML (could be str, list, etc.)

    Returns:
        str: Markdown-safe cell content.
    """
    if isinstance(value, list):
        return '\\n'.join(f"- {v}" for v in value)
    return str(value)

def detect_mode(file_path: str) -> str:
    """Detect conversion mode from input file extension.

    Args:
        file_path (str): Path to the input file.

    Returns:
        str: 'to-yaml' or 'to-md'.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.md', '.markdown']:
        return 'to-yaml'
    elif ext in ['.yml', '.yaml']:
        return 'to-md'
    else:
        logger.error("Unsupported file extension.")
        sys.exit(1)

def default_output_filename(input_file: str, mode: str, output_format: str = 'yaml') -> str:
    """Generate a default output filename based on input file and mode.

    Args:
        input_file (str): Original input file.
        mode (str): Conversion mode.
        output_format (str): Output format (yaml or json).

    Returns:
        str: Suggested output filename.
    """
    base, _ = os.path.splitext(input_file)
    return f"{base}.{output_format}" if mode == 'to-yaml' else f"{base}.md"

def main():
    """Main CLI entrypoint that parses args and runs the converter."""
    parser = argparse.ArgumentParser(description="Convert Markdown <-> YAML/JSON with logging and validation")
    parser.add_argument('--input', required=True, help="Input file path (.md or .yml/.yaml)")
    parser.add_argument('--output', help="Optional output file path")
    parser.add_argument('--format', choices=['yaml', 'json'], default='yaml', help="Output format when converting from Markdown")
    parser.add_argument('--dry-run', action='store_true', help="Run conversion but don't write any output")

    args = parser.parse_args()
    mode = detect_mode(args.input)
    output_file = args.output or default_output_filename(args.input, mode, args.format)

    set_log_context(input=args.input, output=output_file, mode=mode)

    if mode == 'to-yaml':
        markdown_to_yaml(args.input, output_file, args.format, dry_run=args.dry_run)
    else:
        yaml_to_markdown(args.input, output_file, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
