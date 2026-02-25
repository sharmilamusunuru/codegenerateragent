# bicep-generator-agent

> **Automated Azure Bicep Infrastructure-as-Code generator from draw.io architecture diagrams.**

Convert your draw.io (.drawio / .xml) cloud architecture diagrams into production-ready, modular Azure Bicep code — automatically.

---

## Features

- 🔍 **Parses** draw.io XML files and extracts Azure resource shapes, labels, and connections
- 🗺️ **Maps** 50+ Azure shape styles to their Bicep resource types
- 🏗️ **Generates** modular Bicep with `main.bicep`, per-resource-type modules, and a `parameters.json`
- 🔒 **Secure defaults**: private endpoints, managed identity, RBAC, minimum TLS 1.2
- 📝 **README.md** summarising inferred architecture decisions
- 📦 **Architecture JSON** export for downstream tooling
- ⚙️ **Custom mapping** overrides via `mapping.yaml`
- 🧩 **Plugin-ready** structure for future Terraform / CDK support

---

## Project Structure

```
bicep-generator-agent/
├── parser/
│   └── drawio_parser.py         # XML parser for draw.io files
├── mapping/
│   └── shape_to_azure_mapper.py # Shape style → Azure resource type mapping
├── model/
│   └── architecture_model.py    # Internal architecture JSON model
├── generator/
│   └── bicep_generator.py       # Jinja2-based Bicep code generator
├── templates/
│   ├── vnet.bicep.j2            # Virtual Network template
│   ├── vm.bicep.j2              # Virtual Machine template
│   ├── storage.bicep.j2         # Storage Account template
│   ├── sql.bicep.j2             # Azure SQL template
│   ├── keyvault.bicep.j2        # Key Vault template
│   ├── appservice.bicep.j2      # App Service / Function App template
│   ├── apim.bicep.j2            # API Management template
│   ├── aks.bicep.j2             # AKS template
│   └── generic.bicep.j2         # Generic placeholder template
├── tests/
│   ├── test_parser.py           # Parser unit tests
│   ├── test_mapper.py           # Mapper unit tests
│   └── test_generator.py        # Generator unit tests
├── examples/
│   └── sample-architecture.drawio  # Example 3-tier web app diagram
├── main.py                      # CLI entrypoint
├── mapping.yaml                 # Custom shape mapping overrides
└── requirements.txt
```

---

## Installation

```bash
cd bicep-generator-agent
pip install -r requirements.txt
```

---

## Usage

```bash
python main.py --input architecture.drawio --output ./bicep-output
```

### Full options

```
usage: bicep-generator-agent [-h] --input FILE [--output DIR]
                              [--prefix PREFIX] [--env {dev,staging,prod}]
                              [--location REGION] [--mapping YAML]
                              [--export-json] [--report]
                              [--templates-dir DIR]

options:
  --input  FILE       Path to the draw.io (.drawio or .xml) input file
  --output DIR        Output directory (default: ./bicep-output)
  --prefix PREFIX     Naming prefix for all Azure resources (default: myapp)
  --env               Deployment environment: dev | staging | prod
  --location REGION   Azure region (default: eastus)
  --mapping YAML      Path to custom mapping.yaml for shape overrides
  --report            Print summary report to stdout after generation
  --templates-dir DIR Directory containing .bicep.j2 templates
```

### Example with sample diagram

```bash
python main.py \
  --input examples/sample-architecture.drawio \
  --output ./bicep-output \
  --prefix webapp \
  --env dev \
  --location eastus \
  --report
```

---

## Generated Output

```
bicep-output/
├── main.bicep           # Orchestration file referencing all modules
├── parameters.json      # ARM/Bicep parameter file
├── architecture.json    # Machine-readable model export
├── README.md            # Inferred architecture summary
└── modules/
    ├── vnet.bicep
    ├── vm.bicep
    ├── storage.bicep
    ├── sql.bicep
    ├── kv.bicep
    └── apim.bicep
```

### main.bicep snippet

```bicep
targetScope = 'resourceGroup'

param location string = resourceGroup().location
param namingPrefix string = 'myapp'
param environment string = 'dev'

module vnet_module 'modules/vnet.bicep' = {
  name: 'vnet_module-${environment}'
  params: {
    location: location
    namingPrefix: namingPrefix
    environment: environment
    tags: tags
  }
}

module vm_module 'modules/vm.bicep' = {
  name: 'vm_module-${environment}'
  params: { ... }
  dependsOn: [ vnet_module ]
}
```

---

## Supported Azure Resources

| Shape Key Fragment | Azure Resource Type |
|--------------------|---------------------|
| `mxgraph.azure.network.vnet` | `Microsoft.Network/virtualNetworks` |
| `mxgraph.azure.compute.vm` | `Microsoft.Compute/virtualMachines` |
| `mxgraph.azure.storage.storageaccount` | `Microsoft.Storage/storageAccounts` |
| `mxgraph.azure.databases.sql` | `Microsoft.Sql/servers` |
| `mxgraph.azure.databases.cosmos_db` | `Microsoft.DocumentDB/databaseAccounts` |
| `mxgraph.azure.security.key_vault` | `Microsoft.KeyVault/vaults` |
| `mxgraph.azure.integration.api_management` | `Microsoft.ApiManagement/service` |
| `mxgraph.azure.compute.kubernetes` | `Microsoft.ContainerService/managedClusters` |
| `mxgraph.azure.compute.app_service` | `Microsoft.Web/sites` |
| `mxgraph.azure.compute.function` | `Microsoft.Web/sites` (functionapp) |
| `mxgraph.azure.integration.service_bus` | `Microsoft.ServiceBus/namespaces` |
| `mxgraph.azure.integration.event_hub` | `Microsoft.EventHub/namespaces` |
| `mxgraph.azure.management.log_analytics` | `Microsoft.OperationalInsights/workspaces` |
| *(50+ total — see `mapping/shape_to_azure_mapper.py`)* | |

Resources without a known shape can also be detected via **label hints** (e.g. a box labelled "Key Vault" will map correctly).

---

## Custom Shape Overrides

Edit `mapping.yaml` to add or override mappings:

```yaml
shape_overrides:
  mxgraph.company.mygateway:
    azure_type: Microsoft.Network/applicationGateways
    short_type: appgw

label_overrides:
  my custom service:
    azure_type: Microsoft.Web/sites
    short_type: app
```

Pass the file with `--mapping mapping.yaml`.

---

## Bicep Generation Rules

- **Modular design**: one `.bicep` module per resource type
- **Parameterised**: `location`, `namingPrefix`, `environment`, `tags` on every module
- **Azure naming conventions**: `${prefix}-${type}-${env}` pattern
- **Secure defaults**:
  - Minimum TLS 1.2 everywhere
  - `allowBlobPublicAccess: false` on storage
  - `publicNetworkAccess: Disabled` on SQL
  - `enableRbacAuthorization: true` on Key Vault
  - `SystemAssigned` managed identity on VM, App Service, APIM, AKS
- **Dependency inference**: `dependsOn` blocks generated from diagram connections

---

## Running Tests

```bash
cd bicep-generator-agent
python -m pytest tests/ -v
# or
python -m unittest discover -s tests
```

---

## Deploying Generated Bicep

```bash
# Create resource group
az group create --name my-rg --location eastus

# Deploy
az deployment group create \
  --resource-group my-rg \
  --template-file bicep-output/main.bicep \
  --parameters bicep-output/parameters.json

# Validate (requires Bicep CLI)
az bicep build --file bicep-output/main.bicep
```

---

## Architecture

```
draw.io file
     │
     ▼
DrawIOParser          (XML parsing, shape/label extraction)
     │
     ▼
ShapeToAzureMapper    (shape key → Azure resource type)
     │
     ▼
ArchitectureModel     (internal JSON model)
     │
     ▼
BicepGenerator        (Jinja2 template rendering)
     │
     ▼
Bicep output files    (main.bicep, modules/, parameters.json, README.md)
```
