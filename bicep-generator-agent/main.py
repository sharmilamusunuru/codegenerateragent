#!/usr/bin/env python3
"""
bicep-generator-agent CLI

Converts draw.io architecture diagrams into modular Azure Bicep IaC.

Usage
-----
    python main.py --input architecture.drawio --output ./bicep-output

    python main.py --input arch.xml --output ./out \
        --prefix myapp --env prod --location westeurope \
        --mapping custom-mapping.yaml
"""

import argparse
import json
import os
import sys

# ---------------------------------------------------------------------------
# Ensure project root is on the path so local packages resolve correctly
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from parser.drawio_parser import DrawIOParser
from mapping.shape_to_azure_mapper import ShapeToAzureMapper
from generator.bicep_generator import BicepGenerator


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bicep-generator-agent",
        description="Convert draw.io diagrams to modular Azure Bicep IaC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--input", "-i",
        required=True,
        metavar="FILE",
        help="Path to the draw.io (.drawio or .xml) input file",
    )
    p.add_argument(
        "--output", "-o",
        default="./bicep-output",
        metavar="DIR",
        help="Output directory for generated Bicep files (default: ./bicep-output)",
    )
    p.add_argument(
        "--prefix", "-p",
        default="myapp",
        metavar="PREFIX",
        help="Naming prefix applied to all Azure resources (default: myapp)",
    )
    p.add_argument(
        "--env", "-e",
        default="dev",
        choices=["dev", "staging", "prod"],
        help="Deployment environment (default: dev)",
    )
    p.add_argument(
        "--location", "-l",
        default="eastus",
        metavar="REGION",
        help="Azure region (default: eastus)",
    )
    p.add_argument(
        "--mapping", "-m",
        default=None,
        metavar="YAML",
        help="Path to custom mapping.yaml for shape overrides",
    )
    p.add_argument(
        "--export-json",
        action="store_true",
        help="Write architecture.json model export (always included in output dir)",
    )
    p.add_argument(
        "--report",
        action="store_true",
        help="Print the generation summary report to stdout after completion",
    )
    p.add_argument(
        "--templates-dir",
        default=os.path.join(_HERE, "templates"),
        metavar="DIR",
        help="Directory containing Jinja2 .bicep.j2 templates",
    )
    return p


def main(argv: list = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    input_file = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output)
    templates_dir = os.path.abspath(args.templates_dir)
    mapping_yaml = os.path.abspath(args.mapping) if args.mapping else None

    print(f"\n🔍  Parsing diagram: {input_file}")

    # 1. Parse
    try:
        mapper = ShapeToAzureMapper(mapping_yaml_path=mapping_yaml)
        parser_obj = DrawIOParser(mapper=mapper)
        model = parser_obj.parse(input_file)
    except FileNotFoundError as exc:
        print(f"❌  Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"❌  Parsing failed: {exc}", file=sys.stderr)
        raise

    print(
        f"✅  Parsed {len(model.resources)} resource(s) and "
        f"{len(model.connections)} connection(s)"
    )

    if not model.resources:
        print(
            "⚠️  No Azure resources detected in the diagram.  "
            "Ensure cells use recognised Azure shape styles or labels.",
            file=sys.stderr,
        )
        return 2

    # 2. Generate
    print(f"\n🔧  Generating Bicep in: {output_dir}")

    generator = BicepGenerator(
        output_dir=output_dir,
        templates_dir=templates_dir,
        naming_prefix=args.prefix,
        environment=args.env,
        location=args.location,
    )

    try:
        report = generator.generate(model)
    except Exception as exc:
        print(f"❌  Generation failed: {exc}", file=sys.stderr)
        raise

    print(f"\n✅  Generation complete!")
    print(f"   Resources  : {len(report['resources'])}")
    print(f"   Warnings   : {len(report['warnings'])}")
    print(f"   Output dir : {output_dir}")

    # 3. Optional report to stdout
    if args.report:
        print("\n── Summary Report ────────────────────────────────────────────")
        print(json.dumps(report, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
