"""
Shape-to-Azure resource mapper.

Maps draw.io mxCell shape style identifiers to Azure resource types and
short names used throughout the generator.  Custom overrides can be
provided via a mapping.yaml file.
"""

import os
import re
from typing import Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ---------------------------------------------------------------------------
# Default built-in mapping: shape-key fragment → (azure_type, short_type)
# ---------------------------------------------------------------------------
DEFAULT_SHAPE_MAP: dict = {
    # Networking
    "mxgraph.azure.network.vnet":                  ("Microsoft.Network/virtualNetworks",        "vnet"),
    "mxgraph.azure.network.virtual_network":       ("Microsoft.Network/virtualNetworks",        "vnet"),
    "mxgraph.azure.networking.virtual_network":    ("Microsoft.Network/virtualNetworks",        "vnet"),
    "mxgraph.azure.network.subnet":                ("Microsoft.Network/virtualNetworks/subnets","subnet"),
    "mxgraph.azure.networking.subnet":             ("Microsoft.Network/virtualNetworks/subnets","subnet"),
    "mxgraph.azure.network.load_balancer":         ("Microsoft.Network/loadBalancers",          "lb"),
    "mxgraph.azure.networking.load_balancer":      ("Microsoft.Network/loadBalancers",          "lb"),
    "mxgraph.azure.network.application_gateway":   ("Microsoft.Network/applicationGateways",    "appgw"),
    "mxgraph.azure.networking.application_gateway":("Microsoft.Network/applicationGateways",    "appgw"),
    "mxgraph.azure.network.firewall":              ("Microsoft.Network/azureFirewalls",         "firewall"),
    "mxgraph.azure.networking.firewall":           ("Microsoft.Network/azureFirewalls",         "firewall"),
    "mxgraph.azure.network.vpn_gateway":           ("Microsoft.Network/virtualNetworkGateways", "vpngw"),
    "mxgraph.azure.networking.vpn_gateway":        ("Microsoft.Network/virtualNetworkGateways", "vpngw"),
    "mxgraph.azure.network.dns":                   ("Microsoft.Network/dnsZones",               "dns"),
    "mxgraph.azure.networking.dns":                ("Microsoft.Network/dnsZones",               "dns"),
    "mxgraph.azure.network.public_ip":             ("Microsoft.Network/publicIPAddresses",      "pip"),
    "mxgraph.azure.networking.public_ip_address":  ("Microsoft.Network/publicIPAddresses",      "pip"),
    "mxgraph.azure.network.nsg":                   ("Microsoft.Network/networkSecurityGroups",  "nsg"),
    "mxgraph.azure.networking.network_security_group": ("Microsoft.Network/networkSecurityGroups", "nsg"),
    "mxgraph.azure.network.private_endpoint":      ("Microsoft.Network/privateEndpoints",       "pe"),
    "mxgraph.azure.networking.private_endpoint":   ("Microsoft.Network/privateEndpoints",       "pe"),

    # Compute
    "mxgraph.azure.compute.vm":                    ("Microsoft.Compute/virtualMachines",        "vm"),
    "mxgraph.azure.compute.virtual_machine":       ("Microsoft.Compute/virtualMachines",        "vm"),
    "mxgraph.azure.compute.vmss":                  ("Microsoft.Compute/virtualMachineScaleSets","vmss"),
    "mxgraph.azure.compute.virtual_machine_scale_set": ("Microsoft.Compute/virtualMachineScaleSets","vmss"),
    "mxgraph.azure.compute.function":              ("Microsoft.Web/sites",                      "func"),
    "mxgraph.azure.compute.function_apps":         ("Microsoft.Web/sites",                      "func"),
    "mxgraph.azure.compute.app_service":           ("Microsoft.Web/sites",                      "app"),
    "mxgraph.azure.web.app_service":               ("Microsoft.Web/sites",                      "app"),
    "mxgraph.azure.compute.container_instance":    ("Microsoft.ContainerInstance/containerGroups","aci"),
    "mxgraph.azure.compute.kubernetes":            ("Microsoft.ContainerService/managedClusters","aks"),
    "mxgraph.azure.container.aks":                 ("Microsoft.ContainerService/managedClusters","aks"),
    "mxgraph.azure.compute.batch":                 ("Microsoft.Batch/batchAccounts",            "batch"),

    # Storage
    "mxgraph.azure.storage.storageaccount":        ("Microsoft.Storage/storageAccounts",        "storage"),
    "mxgraph.azure.storage.storage_account":       ("Microsoft.Storage/storageAccounts",        "storage"),
    "mxgraph.azure.storage.blob":                  ("Microsoft.Storage/storageAccounts",        "blob"),
    "mxgraph.azure.storage.data_lake":             ("Microsoft.Storage/storageAccounts",        "adls"),
    "mxgraph.azure.storage.file":                  ("Microsoft.Storage/storageAccounts",        "files"),
    "mxgraph.azure.storage.queue":                 ("Microsoft.Storage/storageAccounts",        "queue"),
    "mxgraph.azure.storage.table":                 ("Microsoft.Storage/storageAccounts",        "table"),

    # Databases
    "mxgraph.azure.databases.sql":                 ("Microsoft.Sql/servers",                    "sql"),
    "mxgraph.azure.databases.sql_database":        ("Microsoft.Sql/servers/databases",          "sqldb"),
    "mxgraph.azure.databases.cosmos_db":           ("Microsoft.DocumentDB/databaseAccounts",    "cosmos"),
    "mxgraph.azure.databases.cosmosdb":            ("Microsoft.DocumentDB/databaseAccounts",    "cosmos"),
    "mxgraph.azure.databases.mysql":               ("Microsoft.DBforMySQL/servers",             "mysql"),
    "mxgraph.azure.databases.postgresql":          ("Microsoft.DBforPostgreSQL/servers",        "psql"),
    "mxgraph.azure.databases.redis":               ("Microsoft.Cache/redis",                    "redis"),
    "mxgraph.azure.databases.synapse":             ("Microsoft.Synapse/workspaces",             "synapse"),

    # Security & Identity
    "mxgraph.azure.security.key_vault":            ("Microsoft.KeyVault/vaults",                "kv"),
    "mxgraph.azure.key_vault":                     ("Microsoft.KeyVault/vaults",                "kv"),
    "mxgraph.azure.identity.managed_identity":     ("Microsoft.ManagedIdentity/userAssignedIdentities", "mi"),
    "mxgraph.azure.security.managed_identity":     ("Microsoft.ManagedIdentity/userAssignedIdentities", "mi"),

    # Integration
    "mxgraph.azure.integration.api_management":    ("Microsoft.ApiManagement/service",          "apim"),
    "mxgraph.azure.integration.apim":              ("Microsoft.ApiManagement/service",          "apim"),
    "mxgraph.azure.integration.service_bus":       ("Microsoft.ServiceBus/namespaces",          "sb"),
    "mxgraph.azure.integration.event_hub":         ("Microsoft.EventHub/namespaces",            "eh"),
    "mxgraph.azure.integration.event_grid":        ("Microsoft.EventGrid/topics",               "eg"),
    "mxgraph.azure.integration.logic_app":         ("Microsoft.Logic/workflows",                "logic"),

    # Monitoring
    "mxgraph.azure.management.log_analytics":      ("Microsoft.OperationalInsights/workspaces", "law"),
    "mxgraph.azure.management.monitor":            ("Microsoft.Insights/components",            "appi"),
    "mxgraph.azure.management.application_insights":("Microsoft.Insights/components",           "appi"),

    # AI / Cognitive
    "mxgraph.azure.ai.cognitive_services":         ("Microsoft.CognitiveServices/accounts",     "cog"),
    "mxgraph.azure.ai.machine_learning":           ("Microsoft.MachineLearningServices/workspaces","mlws"),

    # CDN / Front Door
    "mxgraph.azure.network.cdn":                   ("Microsoft.Cdn/profiles",                   "cdn"),
    "mxgraph.azure.networking.front_door":         ("Microsoft.Network/frontDoors",              "fd"),
}


# Short labels that appear in draw.io cell labels and hint at resource type
LABEL_HINT_MAP: dict = {
    "vnet":             ("Microsoft.Network/virtualNetworks",        "vnet"),
    "subnet":           ("Microsoft.Network/virtualNetworks/subnets","subnet"),
    "vm":               ("Microsoft.Compute/virtualMachines",        "vm"),
    "virtual machine":  ("Microsoft.Compute/virtualMachines",        "vm"),
    "storage":          ("Microsoft.Storage/storageAccounts",        "storage"),
    "storage account":  ("Microsoft.Storage/storageAccounts",        "storage"),
    "blob":             ("Microsoft.Storage/storageAccounts",        "blob"),
    "sql":              ("Microsoft.Sql/servers",                    "sql"),
    "cosmos":           ("Microsoft.DocumentDB/databaseAccounts",    "cosmos"),
    "key vault":        ("Microsoft.KeyVault/vaults",                "kv"),
    "keyvault":         ("Microsoft.KeyVault/vaults",                "kv"),
    "apim":             ("Microsoft.ApiManagement/service",          "apim"),
    "api management":   ("Microsoft.ApiManagement/service",          "apim"),
    "app service":      ("Microsoft.Web/sites",                      "app"),
    "function":         ("Microsoft.Web/sites",                      "func"),
    "function app":     ("Microsoft.Web/sites",                      "func"),
    "aks":              ("Microsoft.ContainerService/managedClusters","aks"),
    "kubernetes":       ("Microsoft.ContainerService/managedClusters","aks"),
    "service bus":      ("Microsoft.ServiceBus/namespaces",          "sb"),
    "event hub":        ("Microsoft.EventHub/namespaces",            "eh"),
    "load balancer":    ("Microsoft.Network/loadBalancers",          "lb"),
    "application gateway": ("Microsoft.Network/applicationGateways", "appgw"),
    "firewall":         ("Microsoft.Network/azureFirewalls",         "firewall"),
    "log analytics":    ("Microsoft.OperationalInsights/workspaces", "law"),
    "application insights": ("Microsoft.Insights/components",        "appi"),
    "redis":            ("Microsoft.Cache/redis",                    "redis"),
    "front door":       ("Microsoft.Network/frontDoors",             "fd"),
    "cdn":              ("Microsoft.Cdn/profiles",                   "cdn"),
    "nsg":              ("Microsoft.Network/networkSecurityGroups",  "nsg"),
}


class ShapeToAzureMapper:
    """
    Maps draw.io shape style strings and cell labels to Azure resource types.

    Resolution order:
      1. Custom overrides from mapping.yaml
      2. Exact match in DEFAULT_SHAPE_MAP (normalised shape key)
      3. Partial/fragment match in DEFAULT_SHAPE_MAP
      4. Label-hint match in LABEL_HINT_MAP
      5. Falls back to a generic unknown resource
    """

    UNKNOWN = ("Microsoft.Resources/unknown", "unknown")

    def __init__(self, mapping_yaml_path: Optional[str] = None):
        self._shape_map: dict = dict(DEFAULT_SHAPE_MAP)
        self._label_map: dict = dict(LABEL_HINT_MAP)
        if mapping_yaml_path and os.path.isfile(mapping_yaml_path):
            self._load_yaml_overrides(mapping_yaml_path)

    # ------------------------------------------------------------------
    def _load_yaml_overrides(self, path: str) -> None:
        if not HAS_YAML:
            print(f"[WARN] PyYAML not installed – cannot load overrides from {path}")
            return
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        for key, val in data.get("shape_overrides", {}).items():
            self._shape_map[key.lower()] = (val["azure_type"], val["short_type"])
        for key, val in data.get("label_overrides", {}).items():
            self._label_map[key.lower()] = (val["azure_type"], val["short_type"])

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_shape_key(style: str) -> str:
        """Pull the shape= value out of a draw.io style string."""
        match = re.search(r"shape=([\w.]+)", style, re.IGNORECASE)
        return match.group(1).lower() if match else ""

    # ------------------------------------------------------------------
    def map(self, style: str, label: str = "") -> tuple:
        """
        Return (azure_type, short_type) for the given style / label.

        Parameters
        ----------
        style : str
            The raw mxCell style attribute value.
        label : str
            The cell's display label (value attribute).
        """
        shape_key = self._extract_shape_key(style)

        # 1. Exact shape match
        if shape_key in self._shape_map:
            return self._shape_map[shape_key]

        # 2. Fragment / substring match against known shape keys (only when shape key is non-empty)
        if shape_key:
            for known_key, mapping in self._shape_map.items():
                if known_key in shape_key or shape_key in known_key:
                    return mapping

        # 3. Label-based hint (case-insensitive)
        if label:
            label_lower = label.lower().strip()
            if label_lower in self._label_map:
                return self._label_map[label_lower]
            for hint, mapping in self._label_map.items():
                if hint in label_lower:
                    return mapping

        return self.UNKNOWN

    # ------------------------------------------------------------------
    def get_all_mappings(self) -> dict:
        """Return a copy of the current shape map."""
        return dict(self._shape_map)
