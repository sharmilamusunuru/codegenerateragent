"""
draw.io / .drawio / .xml diagram parser.

Extracts mxCell elements, detects Azure resource shapes/labels, and builds
an ArchitectureModel that the generator can consume.
"""

import os
import re
import xml.etree.ElementTree as ET
from typing import Optional

from model.architecture_model import ArchitectureModel, AzureResource, ResourceConnection
from mapping.shape_to_azure_mapper import ShapeToAzureMapper


class DrawIOParser:
    """
    Parses a draw.io file and returns an :class:`ArchitectureModel`.

    Supported file formats
    ----------------------
    - Uncompressed .drawio / .xml  (mxGraphModel root element)
    - Multi-page .drawio with ``<mxfile>`` wrapper
    """

    def __init__(self, mapper: Optional[ShapeToAzureMapper] = None):
        self.mapper = mapper or ShapeToAzureMapper()
        self._id_counter: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, file_path: str) -> ArchitectureModel:
        """
        Parse a draw.io file and return a populated :class:`ArchitectureModel`.

        Parameters
        ----------
        file_path : str
            Absolute or relative path to the .drawio / .xml file.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")

        tree = ET.parse(file_path)
        root = tree.getroot()

        model = ArchitectureModel(
            name=os.path.splitext(os.path.basename(file_path))[0],
            metadata={"source_file": file_path},
        )

        # Handle both <mxfile> wrapper and bare <mxGraphModel>
        graph_models = self._collect_graph_models(root)

        for gm in graph_models:
            self._process_graph_model(gm, model)

        model.resolve_dependencies()
        return model

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_graph_models(self, root: ET.Element) -> list:
        """Return all mxGraphModel elements in the document."""
        if root.tag == "mxGraphModel":
            return [root]
        if root.tag == "mxfile":
            return root.findall(".//mxGraphModel")
        # Fallback: search anywhere
        models = root.findall(".//mxGraphModel")
        return models if models else [root]

    def _process_graph_model(self, graph_model: ET.Element, model: ArchitectureModel) -> None:
        """Walk all mxCell elements and populate the model."""
        cells_raw: dict = {}   # id → element
        connections_raw: list = []

        for cell in graph_model.iter("mxCell"):
            cell_id = cell.get("id", "")
            style = cell.get("style", "")
            value = cell.get("value", "")
            source = cell.get("source")
            target = cell.get("target")

            # Skip default parent/background cells (id=0 or id=1 with no style)
            if cell_id in ("0", "1") and not style:
                continue

            if source is not None and target is not None:
                # This is a connector/edge
                connections_raw.append(cell)
            else:
                cells_raw[cell_id] = cell

        # Also collect userObject elements (draw.io stores labels there sometimes)
        for user_obj in graph_model.iter("UserObject"):
            obj_id = user_obj.get("id", "")
            if obj_id:
                cells_raw[obj_id] = user_obj

        # Build resources
        resource_id_map: dict = {}   # cell_id → resource_id (short slugified)

        for cell_id, cell in cells_raw.items():
            style = cell.get("style", "")
            value = cell.get("value", "") or ""

            # Skip purely geometric/container cells with no azure shape
            azure_type, short_type = self.mapper.map(style, value)
            if azure_type == "Microsoft.Resources/unknown":
                # Still record if the label provides enough info
                if not value.strip():
                    continue

            resource = self._build_resource(cell_id, style, value, azure_type, short_type, cell)
            model.add_resource(resource)
            resource_id_map[cell_id] = resource.resource_id

        # Build connections
        for edge in connections_raw:
            edge_id = edge.get("id", f"edge-{self._next_id()}")
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            label = edge.get("value", "")

            src_rid = resource_id_map.get(src, src)
            tgt_rid = resource_id_map.get(tgt, tgt)

            if src_rid and tgt_rid:
                conn = ResourceConnection(
                    connection_id=edge_id,
                    source_id=src_rid,
                    target_id=tgt_rid,
                    label=label,
                    connection_type=self._infer_connection_type(label),
                )
                model.add_connection(conn)

    def _build_resource(
        self,
        cell_id: str,
        style: str,
        value: str,
        azure_type: str,
        short_type: str,
        cell: ET.Element,
    ) -> AzureResource:
        """Construct an AzureResource from a parsed mxCell."""
        display_name = self._sanitise_label(value) or short_type
        resource_id = self._make_resource_id(short_type, display_name, cell_id)

        # Geometry
        geo = cell.find("mxGeometry")
        if geo is None:
            geo = cell.find(".//mxGeometry")
        position = {}
        if geo is not None:
            position = {
                "x": float(geo.get("x", 0)),
                "y": float(geo.get("y", 0)),
                "width": float(geo.get("width", 0)),
                "height": float(geo.get("height", 0)),
            }

        props = self._default_properties(short_type, display_name)
        tags = {"environment": "${environment}", "managedBy": "bicep-generator-agent"}

        return AzureResource(
            resource_id=resource_id,
            resource_type=azure_type,
            display_name=display_name,
            short_type=short_type,
            shape_style=style,
            properties=props,
            tags=tags,
            position=position,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _sanitise_label(label: str) -> str:
        """Strip HTML tags and normalise whitespace from a cell label."""
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", " ", label)
        # Collapse whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    @staticmethod
    def _make_resource_id(short_type: str, display_name: str, fallback: str) -> str:
        """Create a safe bicep-friendly resource identifier."""
        base = display_name if display_name else short_type
        slug = re.sub(r"[^a-zA-Z0-9]", "_", base).strip("_").lower()
        if not slug:
            slug = re.sub(r"[^a-zA-Z0-9]", "_", fallback).strip("_").lower()
        return f"{short_type}_{slug}"

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    @staticmethod
    def _infer_connection_type(label: str) -> str:
        label_lower = label.lower()
        if any(k in label_lower for k in ("peering", "vnet", "subnet", "network")):
            return "network"
        if any(k in label_lower for k in ("depend", "require", "use")):
            return "dependency"
        if any(k in label_lower for k in ("data", "flow", "stream", "event")):
            return "data-flow"
        return "generic"

    @staticmethod
    def _default_properties(short_type: str, name: str) -> dict:
        """Return safe-default properties for a given resource type."""
        defaults: dict = {
            "vnet": {
                "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
            },
            "subnet": {
                "addressPrefix": "10.0.0.0/24",
            },
            "vm": {
                "vmSize": "Standard_B2s",
                "osDisk": {"caching": "ReadWrite", "createOption": "FromImage"},
                "imageReference": {
                    "publisher": "Canonical",
                    "offer": "UbuntuServer",
                    "sku": "18.04-LTS",
                    "version": "latest",
                },
            },
            "storage": {
                "sku": {"name": "Standard_LRS"},
                "kind": "StorageV2",
                "minimumTlsVersion": "TLS1_2",
                "supportsHttpsTrafficOnly": True,
                "allowBlobPublicAccess": False,
            },
            "blob": {
                "sku": {"name": "Standard_LRS"},
                "kind": "BlobStorage",
                "minimumTlsVersion": "TLS1_2",
                "allowBlobPublicAccess": False,
            },
            "sql": {
                "administratorLogin": "sqladmin",
                "version": "12.0",
                "minimalTlsVersion": "1.2",
            },
            "sqldb": {
                "sku": {"name": "Basic", "tier": "Basic"},
                "collation": "SQL_Latin1_General_CP1_CI_AS",
            },
            "cosmos": {
                "databaseAccountOfferType": "Standard",
                "consistencyPolicy": {"defaultConsistencyLevel": "Session"},
                "locations": [{"locationName": "${location}", "failoverPriority": 0}],
            },
            "kv": {
                "sku": {"family": "A", "name": "standard"},
                "enableSoftDelete": True,
                "enablePurgeProtection": True,
                "enableRbacAuthorization": True,
            },
            "apim": {
                "sku": {"name": "Developer", "capacity": 1},
                "publisherEmail": "admin@example.com",
                "publisherName": "Admin",
            },
            "app": {
                "kind": "app",
                "httpsOnly": True,
                "identity": {"type": "SystemAssigned"},
            },
            "func": {
                "kind": "functionapp",
                "httpsOnly": True,
                "identity": {"type": "SystemAssigned"},
            },
            "aks": {
                "dnsPrefix": name[:10] if name else "aks",
                "agentPoolProfiles": [
                    {
                        "name": "agentpool",
                        "count": 3,
                        "vmSize": "Standard_DS2_v2",
                        "osType": "Linux",
                        "mode": "System",
                    }
                ],
                "identity": {"type": "SystemAssigned"},
            },
            "sb": {
                "sku": {"name": "Standard", "tier": "Standard"},
            },
            "eh": {
                "sku": {"name": "Standard", "tier": "Standard", "capacity": 1},
            },
            "lb": {
                "sku": {"name": "Standard"},
            },
            "appgw": {
                "sku": {"name": "WAF_v2", "tier": "WAF_v2", "capacity": 2},
                "webApplicationFirewallConfiguration": {
                    "enabled": True,
                    "firewallMode": "Prevention",
                    "ruleSetType": "OWASP",
                    "ruleSetVersion": "3.2",
                },
            },
            "law": {
                "sku": {"name": "PerGB2018"},
                "retentionInDays": 30,
            },
            "appi": {
                "applicationType": "web",
                "kind": "web",
            },
            "redis": {
                "sku": {"name": "Basic", "family": "C", "capacity": 0},
                "minimumTlsVersion": "1.2",
                "enableNonSslPort": False,
            },
        }
        return defaults.get(short_type, {})
