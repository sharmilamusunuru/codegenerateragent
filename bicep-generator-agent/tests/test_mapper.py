"""
Unit tests for the shape-to-Azure mapper.
"""

import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mapping.shape_to_azure_mapper import ShapeToAzureMapper


class TestShapeToAzureMapperDefaults(unittest.TestCase):
    def setUp(self):
        self.mapper = ShapeToAzureMapper()

    # ── Shape key matching ────────────────────────────────────────────
    def test_vnet_shape_exact(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.network.vnet;fillColor=#dae8fc;"
        )
        self.assertEqual(azure_type, "Microsoft.Network/virtualNetworks")
        self.assertEqual(short_type, "vnet")

    def test_vm_shape_exact(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.compute.vm;align=center;"
        )
        self.assertEqual(azure_type, "Microsoft.Compute/virtualMachines")
        self.assertEqual(short_type, "vm")

    def test_storage_shape_exact(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.storage.storageaccount;"
        )
        self.assertEqual(azure_type, "Microsoft.Storage/storageAccounts")
        self.assertEqual(short_type, "storage")

    def test_sql_shape_exact(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.databases.sql;"
        )
        self.assertEqual(azure_type, "Microsoft.Sql/servers")
        self.assertEqual(short_type, "sql")

    def test_keyvault_shape_exact(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.security.key_vault;"
        )
        self.assertEqual(azure_type, "Microsoft.KeyVault/vaults")
        self.assertEqual(short_type, "kv")

    def test_apim_shape_exact(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.integration.api_management;"
        )
        self.assertEqual(azure_type, "Microsoft.ApiManagement/service")
        self.assertEqual(short_type, "apim")

    def test_aks_shape_exact(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.compute.kubernetes;"
        )
        self.assertEqual(azure_type, "Microsoft.ContainerService/managedClusters")
        self.assertEqual(short_type, "aks")

    def test_appservice_shape_exact(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.compute.app_service;"
        )
        self.assertEqual(azure_type, "Microsoft.Web/sites")
        self.assertEqual(short_type, "app")

    def test_function_shape_exact(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.compute.function;"
        )
        self.assertEqual(azure_type, "Microsoft.Web/sites")
        self.assertEqual(short_type, "func")

    def test_cosmos_shape_exact(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.databases.cosmos_db;"
        )
        self.assertEqual(azure_type, "Microsoft.DocumentDB/databaseAccounts")
        self.assertEqual(short_type, "cosmos")

    # ── Label-hint matching ───────────────────────────────────────────
    def test_label_hint_key_vault(self):
        azure_type, short_type = self.mapper.map("rounded=1;", label="Key Vault")
        self.assertEqual(azure_type, "Microsoft.KeyVault/vaults")
        self.assertEqual(short_type, "kv")

    def test_label_hint_storage(self):
        azure_type, short_type = self.mapper.map("rounded=1;", label="storage account")
        self.assertEqual(azure_type, "Microsoft.Storage/storageAccounts")
        self.assertEqual(short_type, "storage")

    def test_label_hint_vm_case_insensitive(self):
        azure_type, short_type = self.mapper.map("rounded=1;", label="Virtual Machine")
        self.assertEqual(azure_type, "Microsoft.Compute/virtualMachines")
        self.assertEqual(short_type, "vm")

    def test_label_hint_partial(self):
        # "my aks cluster" should still hit the "aks" hint
        azure_type, short_type = self.mapper.map("rounded=1;", label="My AKS cluster")
        self.assertEqual(short_type, "aks")

    # ── Unknown fallback ──────────────────────────────────────────────
    def test_unknown_style_no_label(self):
        azure_type, short_type = self.mapper.map("rounded=1;fillColor=#fff;")
        self.assertEqual(azure_type, "Microsoft.Resources/unknown")
        self.assertEqual(short_type, "unknown")

    def test_unknown_empty_style(self):
        azure_type, short_type = self.mapper.map("")
        self.assertEqual(short_type, "unknown")

    # ── Shape key extraction ──────────────────────────────────────────
    def test_extract_shape_key(self):
        key = ShapeToAzureMapper._extract_shape_key(
            "sketch=0;html=1;shape=mxgraph.azure.network.vnet;align=center;"
        )
        self.assertEqual(key, "mxgraph.azure.network.vnet")

    def test_extract_shape_key_missing(self):
        key = ShapeToAzureMapper._extract_shape_key("rounded=1;fillColor=#fff;")
        self.assertEqual(key, "")

    # ── get_all_mappings ──────────────────────────────────────────────
    def test_get_all_mappings_returns_dict(self):
        result = self.mapper.get_all_mappings()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 10)


class TestShapeToAzureMapperYamlOverrides(unittest.TestCase):
    YAML_CONTENT = """\
shape_overrides:
  mxgraph.custom.my_resource:
    azure_type: Microsoft.Custom/myResources
    short_type: custom

label_overrides:
  my custom service:
    azure_type: Microsoft.Custom/services
    short_type: myservice
"""

    def _make_yaml(self) -> str:
        fd, path = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, "w") as fh:
            fh.write(self.YAML_CONTENT)
        return path

    def test_shape_override_applied(self):
        path = self._make_yaml()
        try:
            mapper = ShapeToAzureMapper(mapping_yaml_path=path)
            azure_type, short_type = mapper.map(
                "shape=mxgraph.custom.my_resource;"
            )
            self.assertEqual(azure_type, "Microsoft.Custom/myResources")
            self.assertEqual(short_type, "custom")
        finally:
            os.unlink(path)

    def test_label_override_applied(self):
        path = self._make_yaml()
        try:
            mapper = ShapeToAzureMapper(mapping_yaml_path=path)
            azure_type, short_type = mapper.map("", label="My Custom Service")
            self.assertEqual(short_type, "myservice")
        finally:
            os.unlink(path)

    def test_nonexistent_yaml_ignored(self):
        # Should not raise even if the yaml file doesn't exist
        mapper = ShapeToAzureMapper(mapping_yaml_path="/nonexistent/file.yaml")
        self.assertIsNotNone(mapper)

    def test_builtin_still_works_after_override(self):
        path = self._make_yaml()
        try:
            mapper = ShapeToAzureMapper(mapping_yaml_path=path)
            azure_type, short_type = mapper.map("shape=mxgraph.azure.compute.vm;")
            self.assertEqual(short_type, "vm")
        finally:
            os.unlink(path)


class TestShapeFragmentMatching(unittest.TestCase):
    """Test that fragment / substring matching works for variations."""

    def setUp(self):
        self.mapper = ShapeToAzureMapper()

    def test_networking_variant_vnet(self):
        # mxgraph.azure.networking.virtual_network (alternative namespace)
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.networking.virtual_network;"
        )
        self.assertEqual(short_type, "vnet")

    def test_load_balancer(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.network.load_balancer;"
        )
        self.assertEqual(short_type, "lb")

    def test_nsg(self):
        azure_type, short_type = self.mapper.map(
            "shape=mxgraph.azure.networking.network_security_group;"
        )
        self.assertEqual(short_type, "nsg")


if __name__ == "__main__":
    unittest.main()
