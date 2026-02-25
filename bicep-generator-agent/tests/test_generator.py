"""
Unit tests for the Bicep generator.
"""

import json
import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model.architecture_model import ArchitectureModel, AzureResource, ResourceConnection
from generator.bicep_generator import BicepGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_model() -> ArchitectureModel:
    model = ArchitectureModel(name="test-arch")
    model.add_resource(AzureResource(
        resource_id="vnet_main_vnet",
        resource_type="Microsoft.Network/virtualNetworks",
        display_name="Main VNet",
        short_type="vnet",
        shape_style="shape=mxgraph.azure.network.vnet;",
        properties={"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
        tags={"environment": "dev"},
    ))
    model.add_resource(AzureResource(
        resource_id="vm_my_vm",
        resource_type="Microsoft.Compute/virtualMachines",
        display_name="My VM",
        short_type="vm",
        shape_style="shape=mxgraph.azure.compute.vm;",
        properties={"vmSize": "Standard_B2s"},
        tags={"environment": "dev"},
    ))
    model.add_resource(AzureResource(
        resource_id="storage_blob",
        resource_type="Microsoft.Storage/storageAccounts",
        display_name="Blob Storage",
        short_type="storage",
        shape_style="shape=mxgraph.azure.storage.storageaccount;",
        properties={"sku": {"name": "Standard_LRS"}},
        tags={"environment": "dev"},
    ))
    model.add_connection(ResourceConnection(
        connection_id="edge1",
        source_id="vnet_main_vnet",
        target_id="vm_my_vm",
        label="network",
        connection_type="network",
    ))
    return model


def _make_generator(output_dir: str) -> BicepGenerator:
    templates_dir = os.path.join(_ROOT, "templates")
    return BicepGenerator(
        output_dir=output_dir,
        templates_dir=templates_dir,
        naming_prefix="test",
        environment="dev",
        location="eastus",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBicepGeneratorOutputFiles(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        model = _make_model()
        self.generator = _make_generator(self.tmp_dir)
        self.report = self.generator.generate(model)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_main_bicep_created(self):
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "main.bicep")))

    def test_parameters_json_created(self):
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "parameters.json")))

    def test_architecture_json_created(self):
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "architecture.json")))

    def test_readme_created(self):
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "README.md")))

    def test_modules_dir_created(self):
        self.assertTrue(os.path.isdir(os.path.join(self.tmp_dir, "modules")))

    def test_vnet_module_created(self):
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "modules", "vnet.bicep")))

    def test_vm_module_created(self):
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "modules", "vm.bicep")))

    def test_storage_module_created(self):
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "modules", "storage.bicep")))


class TestBicepGeneratorMainBicepContent(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        model = _make_model()
        gen = _make_generator(self.tmp_dir)
        gen.generate(model)
        with open(os.path.join(self.tmp_dir, "main.bicep"), "r") as fh:
            self.content = fh.read()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_target_scope(self):
        self.assertIn("targetScope", self.content)

    def test_module_vnet_referenced(self):
        self.assertIn("vnet_module", self.content)

    def test_module_vm_referenced(self):
        self.assertIn("vm_module", self.content)

    def test_module_storage_referenced(self):
        self.assertIn("storage_module", self.content)

    def test_location_param(self):
        self.assertIn("param location", self.content)

    def test_naming_prefix_param(self):
        self.assertIn("param namingPrefix", self.content)

    def test_environment_param(self):
        self.assertIn("param environment", self.content)


class TestBicepGeneratorParametersJson(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        model = _make_model()
        gen = _make_generator(self.tmp_dir)
        gen.generate(model)
        with open(os.path.join(self.tmp_dir, "parameters.json"), "r") as fh:
            self.params = json.load(fh)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_schema_present(self):
        self.assertIn("$schema", self.params)

    def test_content_version(self):
        self.assertEqual(self.params["contentVersion"], "1.0.0.0")

    def test_location_parameter(self):
        self.assertIn("location", self.params["parameters"])
        self.assertEqual(self.params["parameters"]["location"]["value"], "eastus")

    def test_naming_prefix_parameter(self):
        self.assertIn("namingPrefix", self.params["parameters"])
        self.assertEqual(self.params["parameters"]["namingPrefix"]["value"], "test")

    def test_environment_parameter(self):
        self.assertIn("environment", self.params["parameters"])
        self.assertEqual(self.params["parameters"]["environment"]["value"], "dev")


class TestBicepGeneratorArchitectureJson(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.model = _make_model()
        gen = _make_generator(self.tmp_dir)
        gen.generate(self.model)
        with open(os.path.join(self.tmp_dir, "architecture.json"), "r") as fh:
            self.arch = json.load(fh)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_has_resources(self):
        self.assertIn("resources", self.arch)
        self.assertEqual(len(self.arch["resources"]), 3)

    def test_has_connections(self):
        self.assertIn("connections", self.arch)
        self.assertEqual(len(self.arch["connections"]), 1)

    def test_model_name(self):
        self.assertEqual(self.arch["name"], "test-arch")


class TestBicepGeneratorReport(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        model = _make_model()
        gen = _make_generator(self.tmp_dir)
        self.report = gen.generate(model)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_report_has_resources(self):
        self.assertIn("resources", self.report)
        self.assertEqual(len(self.report["resources"]), 3)

    def test_report_has_warnings(self):
        self.assertIn("warnings", self.report)

    def test_report_has_generated_at(self):
        self.assertIn("generated_at", self.report)

    def test_report_naming_prefix(self):
        self.assertEqual(self.report["naming_prefix"], "test")

    def test_report_environment(self):
        self.assertEqual(self.report["environment"], "dev")


class TestBicepGeneratorReadme(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        model = _make_model()
        gen = _make_generator(self.tmp_dir)
        gen.generate(model)
        with open(os.path.join(self.tmp_dir, "README.md"), "r") as fh:
            self.readme = fh.read()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_title_present(self):
        self.assertIn("# Generated Azure Architecture", self.readme)

    def test_deployment_section(self):
        self.assertIn("## Deployment", self.readme)

    def test_resource_types_section(self):
        self.assertIn("## Resource Types", self.readme)

    def test_azure_types_listed(self):
        self.assertIn("Microsoft.Network/virtualNetworks", self.readme)
        self.assertIn("Microsoft.Compute/virtualMachines", self.readme)


if __name__ == "__main__":
    unittest.main()
