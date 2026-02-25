"""
Bicep code generator.

Takes an :class:`ArchitectureModel` and renders modular Azure Bicep output:
  - modules/<short_type>.bicep   (one per unique resource type)
  - main.bicep                   (orchestrates all modules)
  - parameters.json              (parameter file)
  - architecture.json            (raw model export)
  - README.md                    (inferred architecture summary)
"""

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

try:
    from jinja2 import Environment, FileSystemLoader, TemplateNotFound
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

from model.architecture_model import ArchitectureModel, AzureResource


# ---------------------------------------------------------------------------
# Template selection: map short_type → template filename
# ---------------------------------------------------------------------------
TEMPLATE_MAP: dict = {
    "vnet":     "vnet.bicep.j2",
    "subnet":   "vnet.bicep.j2",     # subnets are part of the VNet module
    "vm":       "vm.bicep.j2",
    "vmss":     "vm.bicep.j2",
    "storage":  "storage.bicep.j2",
    "blob":     "storage.bicep.j2",
    "adls":     "storage.bicep.j2",
    "files":    "storage.bicep.j2",
    "queue":    "storage.bicep.j2",
    "table":    "storage.bicep.j2",
    "sql":      "sql.bicep.j2",
    "sqldb":    "sql.bicep.j2",
    "kv":       "keyvault.bicep.j2",
    "app":      "appservice.bicep.j2",
    "func":     "appservice.bicep.j2",
    "apim":     "apim.bicep.j2",
    "aks":      "aks.bicep.j2",
}

GENERIC_TEMPLATE = "generic.bicep.j2"


class BicepGenerator:
    """
    Generates modular Bicep infrastructure code from an :class:`ArchitectureModel`.

    Parameters
    ----------
    output_dir : str
        Root directory where generated files will be written.
    templates_dir : str
        Directory containing Jinja2 ``.bicep.j2`` templates.
    naming_prefix : str
        Prefix applied to all Azure resource names.
    environment : str
        Deployment environment tag (dev / staging / prod).
    location : str
        Default Azure region.
    """

    def __init__(
        self,
        output_dir: str,
        templates_dir: str,
        naming_prefix: str = "myapp",
        environment: str = "dev",
        location: str = "eastus",
    ):
        self.output_dir = output_dir
        self.templates_dir = templates_dir
        self.naming_prefix = naming_prefix
        self.environment = environment
        self.location = location
        self._jinja_env: Optional[object] = None
        if HAS_JINJA2:
            self._jinja_env = Environment(
                loader=FileSystemLoader(templates_dir),
                trim_blocks=True,
                lstrip_blocks=True,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, model: ArchitectureModel) -> dict:
        """
        Generate all Bicep artefacts and write them to ``output_dir``.

        Returns
        -------
        dict
            A summary report of decisions made during generation.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        modules_dir = os.path.join(self.output_dir, "modules")
        os.makedirs(modules_dir, exist_ok=True)

        report: dict = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "naming_prefix": self.naming_prefix,
            "environment": self.environment,
            "location": self.location,
            "resources": [],
            "warnings": [],
            "inferred_assumptions": [],
        }

        # Group resources by short_type (one module per type)
        type_groups: dict = defaultdict(list)
        for resource in model.resources:
            type_groups[resource.short_type].append(resource)

        module_refs: list = []   # (module_name, module_path, params)

        for short_type, resources in type_groups.items():
            module_name = f"{short_type}_module"
            module_file = f"modules/{short_type}.bicep"
            module_path = os.path.join(modules_dir, f"{short_type}.bicep")

            bicep_content = self._render_module(short_type, resources, report)
            self._write_file(module_path, bicep_content)

            params = self._module_params(short_type, resources)
            module_refs.append((module_name, module_file, params, short_type, resources))

            for r in resources:
                report["resources"].append(
                    {
                        "resource_id": r.resource_id,
                        "display_name": r.display_name,
                        "azure_type": r.resource_type,
                        "short_type": short_type,
                        "module": module_file,
                        "dependencies": r.dependencies,
                    }
                )

        # main.bicep
        main_content = self._render_main(module_refs)
        self._write_file(os.path.join(self.output_dir, "main.bicep"), main_content)

        # parameters.json
        params_content = self._render_parameters()
        self._write_file(
            os.path.join(self.output_dir, "parameters.json"), params_content
        )

        # architecture.json export
        arch_json = model.to_json()
        self._write_file(
            os.path.join(self.output_dir, "architecture.json"), arch_json
        )

        # README.md
        readme = self._render_readme(model, report)
        self._write_file(os.path.join(self.output_dir, "README.md"), readme)

        return report

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _render_module(
        self,
        short_type: str,
        resources: list,
        report: dict,
    ) -> str:
        """Render a Bicep module file for a group of resources of the same type."""
        template_file = TEMPLATE_MAP.get(short_type, GENERIC_TEMPLATE)

        if not HAS_JINJA2:
            report["warnings"].append(
                "Jinja2 not installed – falling back to raw template copy."
            )
            return self._raw_template_fallback(template_file, short_type, resources)

        try:
            tmpl = self._jinja_env.get_template(template_file)
        except TemplateNotFound:
            report["warnings"].append(
                f"Template '{template_file}' not found; using generic template."
            )
            try:
                tmpl = self._jinja_env.get_template(GENERIC_TEMPLATE)
            except TemplateNotFound:
                return self._minimal_placeholder(short_type, resources)

        ctx = {
            "short_type": short_type,
            "resources": resources,
            "resource_type": resources[0].resource_type if resources else "",
            "display_name": resources[0].display_name if resources else "",
            "naming_prefix": self.naming_prefix,
            "environment": self.environment,
            "location": self.location,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return tmpl.render(**ctx)

    def _render_main(self, module_refs: list) -> str:
        """Render the main.bicep orchestration file."""
        lines = [
            "// ============================================================",
            "// main.bicep – generated by bicep-generator-agent",
            f"// Generated at: {datetime.now(timezone.utc).isoformat()}",
            "// ============================================================",
            "",
            "targetScope = 'resourceGroup'",
            "",
            "// ── Parameters ────────────────────────────────────────────────",
            "param location string = resourceGroup().location",
            "",
            "@description('Naming prefix applied to all resources')",
            "param namingPrefix string = 'myapp'",
            "",
            "@description('Deployment environment')",
            "@allowed(['dev','staging','prod'])",
            "param environment string = 'dev'",
            "",
            "param tags object = {",
            "  environment: environment",
            "  managedBy: 'bicep-generator-agent'",
            "}",
            "",
            "// ── Modules ───────────────────────────────────────────────────",
        ]

        for module_name, module_file, params, short_type, resources in module_refs:
            # Build dependsOn by collecting unique dependencies across resources in group
            dep_set = set()
            for r in resources:
                for dep in r.dependencies:
                    # dep format: "{short_type}-{resource_id}" from resolve_dependencies
                    dep_type = dep.split("-")[0]
                    dep_module = f"{dep_type}_module"
                    if dep_module != module_name:
                        dep_set.add(dep_module)

            lines.append(f"module {module_name} '{module_file}' = {{")
            lines.append(f"  name: '{module_name}-${{environment}}'")
            lines.append("  params: {")
            lines.append("    location: location")
            lines.append("    namingPrefix: namingPrefix")
            lines.append("    environment: environment")
            lines.append("    tags: tags")
            for pk, pv in params.items():
                lines.append(f"    {pk}: {pv}")
            lines.append("  }")
            if dep_set:
                lines.append("  dependsOn: [")
                for dep in sorted(dep_set):
                    lines.append(f"    {dep}")
                lines.append("  ]")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def _render_parameters(self) -> str:
        """Render a parameters.json file."""
        params = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "location": {"value": self.location},
                "namingPrefix": {"value": self.naming_prefix},
                "environment": {"value": self.environment},
                "tags": {
                    "value": {
                        "environment": self.environment,
                        "managedBy": "bicep-generator-agent",
                    }
                },
            },
        }
        return json.dumps(params, indent=2)

    def _render_readme(self, model: ArchitectureModel, report: dict) -> str:
        """Render a README.md summarising the generated architecture."""
        resource_count = len(model.resources)
        connection_count = len(model.connections)
        resource_types = sorted({r.resource_type for r in model.resources})

        lines = [
            "# Generated Azure Architecture",
            "",
            f"> Generated by **bicep-generator-agent** on {report['generated_at']}  ",
            f"> Source: `{model.metadata.get('source_file', 'unknown')}`",
            "",
            "## Overview",
            "",
            f"- **Resources detected:** {resource_count}",
            f"- **Connections detected:** {connection_count}",
            f"- **Target environment:** `{self.environment}`",
            f"- **Naming prefix:** `{self.naming_prefix}`",
            f"- **Default location:** `{self.location}`",
            "",
            "## Resource Types",
            "",
        ]
        for rt in resource_types:
            lines.append(f"- `{rt}`")

        lines += [
            "",
            "## Resources",
            "",
            "| Name | Type | Module |",
            "|------|------|--------|",
        ]
        for r in report["resources"]:
            lines.append(
                f"| {r['display_name']} | `{r['azure_type']}` | `{r['module']}` |"
            )

        lines += [
            "",
            "## Deployment",
            "",
            "```bash",
            "# Deploy to a resource group",
            "az deployment group create \\",
            f"  --resource-group <your-rg> \\",
            f"  --template-file main.bicep \\",
            f"  --parameters parameters.json",
            "```",
            "",
            "## Inferred Assumptions",
            "",
        ]
        assumptions = report.get("inferred_assumptions") or [
            "Default SKUs / sizes applied where not specified in the diagram.",
            "SystemAssigned managed identity enabled on supported resources.",
            "Minimum TLS version set to 1.2 for all applicable resources.",
            "Public network access disabled on databases and Key Vault.",
            "Storage accounts use Deny-by-default network ACLs.",
        ]
        for a in assumptions:
            lines.append(f"- {a}")

        if report.get("warnings"):
            lines += ["", "## Warnings", ""]
            for w in report["warnings"]:
                lines.append(f"- ⚠️  {w}")

        lines += ["", "## File Structure", "", "```"]
        lines.append(".")
        lines.append("├── main.bicep")
        lines.append("├── parameters.json")
        lines.append("├── architecture.json")
        lines.append("├── README.md")
        lines.append("└── modules/")
        for r in report["resources"]:
            module_base = os.path.basename(r["module"])
            lines.append(f"    └── {module_base}")
        lines.append("```")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _module_params(short_type: str, resources: list) -> dict:
        """Return extra params to pass to a module beyond the standard ones."""
        params: dict = {}
        if short_type in ("app", "func"):
            params["appKind"] = f"'{resources[0].properties.get('kind', 'app')}'"
        return params

    def _raw_template_fallback(
        self, template_file: str, short_type: str, resources: list
    ) -> str:
        """Return raw template content when Jinja2 is unavailable."""
        template_path = os.path.join(self.templates_dir, template_file)
        if os.path.isfile(template_path):
            with open(template_path, "r", encoding="utf-8") as fh:
                return fh.read()
        return self._minimal_placeholder(short_type, resources)

    @staticmethod
    def _minimal_placeholder(short_type: str, resources: list) -> str:
        """Last-resort placeholder Bicep content."""
        names = ", ".join(r.display_name for r in resources)
        return (
            f"// Module: {short_type}\n"
            f"// Resources: {names}\n"
            f"// TODO: Implement Bicep for {short_type}\n\n"
            f"param location string = resourceGroup().location\n"
            f"param namingPrefix string\n"
            f"param environment string\n"
            f"param tags object = {{}}\n"
        )

    @staticmethod
    def _write_file(path: str, content: str) -> None:
        """Write content to a file, creating parent directories as needed."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"  [+] {path}")
