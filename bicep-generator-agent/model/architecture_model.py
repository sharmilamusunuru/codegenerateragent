"""
Architecture model for representing Azure resources parsed from draw.io diagrams.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import json


@dataclass
class AzureResource:
    """Represents a single Azure resource extracted from a diagram."""

    resource_id: str
    resource_type: str          # e.g. Microsoft.Network/virtualNetworks
    display_name: str           # label from the diagram
    short_type: str             # e.g. vnet, vm, storage
    shape_style: str            # raw mxCell style string
    properties: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)
    dependencies: list = field(default_factory=list)
    position: dict = field(default_factory=dict)   # x, y, width, height

    def to_dict(self) -> dict:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "display_name": self.display_name,
            "short_type": self.short_type,
            "shape_style": self.shape_style,
            "properties": self.properties,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "position": self.position,
        }


@dataclass
class ResourceConnection:
    """Represents a connection/relationship between two resources."""

    connection_id: str
    source_id: str
    target_id: str
    label: str = ""
    connection_type: str = "generic"   # e.g. network, dependency, data-flow

    def to_dict(self) -> dict:
        return {
            "connection_id": self.connection_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "label": self.label,
            "connection_type": self.connection_type,
        }


@dataclass
class ArchitectureModel:
    """Top-level model representing the full architecture."""

    name: str = "azure-architecture"
    resources: list = field(default_factory=list)
    connections: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_resource(self, resource: AzureResource) -> None:
        self.resources.append(resource)

    def add_connection(self, connection: ResourceConnection) -> None:
        self.connections.append(connection)

    def get_resource_by_id(self, resource_id: str) -> Optional[AzureResource]:
        for r in self.resources:
            if r.resource_id == resource_id:
                return r
        return None

    def get_resources_by_type(self, short_type: str) -> list:
        return [r for r in self.resources if r.short_type == short_type]

    def resolve_dependencies(self) -> None:
        """Infer dependencies from connections between resources."""
        resource_map = {r.resource_id: r for r in self.resources}
        for conn in self.connections:
            target = resource_map.get(conn.target_id)
            source = resource_map.get(conn.source_id)
            if target and source:
                dep_name = f"{source.short_type}-{source.resource_id}"
                if dep_name not in target.dependencies:
                    target.dependencies.append(dep_name)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "metadata": self.metadata,
            "resources": [r.to_dict() for r in self.resources],
            "connections": [c.to_dict() for c in self.connections],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
