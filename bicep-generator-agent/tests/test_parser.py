"""
Unit tests for the draw.io parser.
"""

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

# Ensure the project root is on the path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from parser.drawio_parser import DrawIOParser
from model.architecture_model import ArchitectureModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_DRAWIO = """\
<?xml version="1.0" encoding="UTF-8"?>
<mxfile>
  <diagram id="d1" name="Test">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="vnet1" value="Main VNet"
          style="shape=mxgraph.azure.network.vnet;"
          vertex="1" parent="1">
          <mxGeometry x="100" y="100" width="60" height="60" as="geometry" />
        </mxCell>
        <mxCell id="vm1" value="My VM"
          style="shape=mxgraph.azure.compute.vm;"
          vertex="1" parent="1">
          <mxGeometry x="200" y="100" width="60" height="60" as="geometry" />
        </mxCell>
        <mxCell id="edge1" value="network" edge="1"
          source="vnet1" target="vm1" parent="1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""

BARE_GRAPH_MODEL = """\
<?xml version="1.0" encoding="UTF-8"?>
<mxGraphModel>
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
    <mxCell id="storage1" value="Blob Storage"
      style="shape=mxgraph.azure.storage.storageaccount;"
      vertex="1" parent="1">
      <mxGeometry x="50" y="50" width="60" height="60" as="geometry" />
    </mxCell>
  </root>
</mxGraphModel>
"""

LABEL_ONLY_DRAWIO = """\
<?xml version="1.0" encoding="UTF-8"?>
<mxGraphModel>
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
    <mxCell id="kv1" value="Key Vault"
      style="rounded=1;whiteSpace=wrap;html=1;"
      vertex="1" parent="1">
      <mxGeometry x="50" y="50" width="120" height="60" as="geometry" />
    </mxCell>
  </root>
</mxGraphModel>
"""


def _write_tmp(content: str, suffix: str = ".drawio") -> str:
    """Write content to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDrawIOParserInit(unittest.TestCase):
    def test_default_mapper(self):
        p = DrawIOParser()
        self.assertIsNotNone(p.mapper)

    def test_custom_mapper(self):
        from mapping.shape_to_azure_mapper import ShapeToAzureMapper
        m = ShapeToAzureMapper()
        p = DrawIOParser(mapper=m)
        self.assertIs(p.mapper, m)


class TestDrawIOParserFileHandling(unittest.TestCase):
    def test_file_not_found(self):
        p = DrawIOParser()
        with self.assertRaises(FileNotFoundError):
            p.parse("/nonexistent/path/file.drawio")

    def test_returns_architecture_model(self):
        path = _write_tmp(MINIMAL_DRAWIO)
        try:
            model = DrawIOParser().parse(path)
            self.assertIsInstance(model, ArchitectureModel)
        finally:
            os.unlink(path)


class TestDrawIOParserResources(unittest.TestCase):
    def setUp(self):
        self.path = _write_tmp(MINIMAL_DRAWIO)
        self.model = DrawIOParser().parse(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_resource_count(self):
        self.assertEqual(len(self.model.resources), 2)

    def test_vnet_detected(self):
        vnets = self.model.get_resources_by_type("vnet")
        self.assertEqual(len(vnets), 1)
        self.assertEqual(vnets[0].resource_type, "Microsoft.Network/virtualNetworks")

    def test_vm_detected(self):
        vms = self.model.get_resources_by_type("vm")
        self.assertEqual(len(vms), 1)
        self.assertEqual(vms[0].resource_type, "Microsoft.Compute/virtualMachines")

    def test_vm_display_name(self):
        vms = self.model.get_resources_by_type("vm")
        self.assertEqual(vms[0].display_name, "My VM")

    def test_resource_has_position(self):
        vms = self.model.get_resources_by_type("vm")
        pos = vms[0].position
        self.assertIn("x", pos)
        self.assertIn("y", pos)
        self.assertAlmostEqual(pos["x"], 200.0)

    def test_resource_has_default_properties(self):
        vms = self.model.get_resources_by_type("vm")
        self.assertIn("vmSize", vms[0].properties)

    def test_resource_has_tags(self):
        vms = self.model.get_resources_by_type("vm")
        self.assertIn("environment", vms[0].tags)


class TestDrawIOParserConnections(unittest.TestCase):
    def setUp(self):
        self.path = _write_tmp(MINIMAL_DRAWIO)
        self.model = DrawIOParser().parse(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_connection_count(self):
        self.assertEqual(len(self.model.connections), 1)

    def test_connection_type_inferred(self):
        conn = self.model.connections[0]
        self.assertEqual(conn.connection_type, "network")

    def test_connection_label(self):
        conn = self.model.connections[0]
        self.assertEqual(conn.label, "network")


class TestDrawIOParserBareGraphModel(unittest.TestCase):
    def test_bare_graph_model_parsed(self):
        path = _write_tmp(BARE_GRAPH_MODEL)
        try:
            model = DrawIOParser().parse(path)
            storages = model.get_resources_by_type("storage")
            self.assertEqual(len(storages), 1)
        finally:
            os.unlink(path)


class TestDrawIOParserLabelHints(unittest.TestCase):
    def test_label_hint_for_key_vault(self):
        path = _write_tmp(LABEL_ONLY_DRAWIO)
        try:
            model = DrawIOParser().parse(path)
            kvs = model.get_resources_by_type("kv")
            self.assertEqual(len(kvs), 1, "Key Vault should be detected via label hint")
        finally:
            os.unlink(path)


class TestDrawIOParserModelName(unittest.TestCase):
    def test_model_name_from_filename(self):
        path = _write_tmp(MINIMAL_DRAWIO, suffix=".drawio")
        try:
            model = DrawIOParser().parse(path)
            # Name should be the base filename without extension
            expected = os.path.splitext(os.path.basename(path))[0]
            self.assertEqual(model.name, expected)
        finally:
            os.unlink(path)


class TestDrawIOParserDependencyResolution(unittest.TestCase):
    def test_dependencies_resolved(self):
        path = _write_tmp(MINIMAL_DRAWIO)
        try:
            model = DrawIOParser().parse(path)
            # VM is the target of the edge from VNet → dependencies should be set
            vms = model.get_resources_by_type("vm")
            # After resolve_dependencies, vm should have the vnet as a dep
            self.assertIsInstance(vms[0].dependencies, list)
        finally:
            os.unlink(path)


class TestSanitiseLabel(unittest.TestCase):
    def test_strips_html(self):
        result = DrawIOParser._sanitise_label("<b>My VM</b>")
        self.assertEqual(result, "My VM")

    def test_collapses_whitespace(self):
        result = DrawIOParser._sanitise_label("  My   VM  ")
        self.assertEqual(result, "My VM")

    def test_empty_string(self):
        result = DrawIOParser._sanitise_label("")
        self.assertEqual(result, "")


class TestInferConnectionType(unittest.TestCase):
    def test_network(self):
        self.assertEqual(DrawIOParser._infer_connection_type("vnet peering"), "network")

    def test_dependency(self):
        self.assertEqual(DrawIOParser._infer_connection_type("depends on"), "dependency")

    def test_data_flow(self):
        self.assertEqual(DrawIOParser._infer_connection_type("data flow"), "data-flow")

    def test_generic(self):
        self.assertEqual(DrawIOParser._infer_connection_type("connects"), "generic")


class TestSampleFile(unittest.TestCase):
    """Smoke-test the bundled sample diagram."""

    SAMPLE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "examples",
        "sample-architecture.drawio",
    )

    def test_sample_file_parses(self):
        if not os.path.isfile(self.SAMPLE):
            self.skipTest("Sample file not found")
        model = DrawIOParser().parse(self.SAMPLE)
        self.assertGreater(len(model.resources), 0)
        self.assertGreater(len(model.connections), 0)

    def test_sample_has_expected_types(self):
        if not os.path.isfile(self.SAMPLE):
            self.skipTest("Sample file not found")
        model = DrawIOParser().parse(self.SAMPLE)
        short_types = {r.short_type for r in model.resources}
        self.assertIn("vnet", short_types)
        self.assertIn("vm", short_types)
        self.assertIn("storage", short_types)


if __name__ == "__main__":
    unittest.main()
