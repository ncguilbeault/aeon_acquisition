"""Generates Bonsai serialization classes from the schema models declared in this package.

Every model is annotated with the fully qualified C# type name it maps to, via the
`x-sgen-typename` schema extension. All models are emitted into a single JSON schema document,
which Bonsai.Sgen is then run over once per target namespace. Each pass generates the types
belonging to that namespace and references types from the other namespaces as external types,
so a model may be referenced across C# projects without being duplicated in them.

A namespace is a generation target if a module of this package declares it, through the
module-level `SGEN_NAMESPACE`. Any other namespace belongs to a C# package outside this
repository, and its types are referenced but never generated. Models mapping onto such a type
declare the namespace on the class itself.
"""

import argparse
import importlib
import json
import pkgutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from pydantic.json_schema import models_json_schema

import swc.aeon.schema
from swc.aeon.schema.base import SGEN_TYPENAME, BaseSchema, module_namespaces

ROOT = Path(__file__).parents[4]
SCHEMA_PATH = ROOT / "schemas" / "aeon.json"
PROJECT_ROOT = ROOT / "src"

# Modules which declare no schema models of their own.
EXCLUDED_MODULES = frozenset({"base", "generate"})

# Namespace assigned to the document root so that no pass ever matches it and emits a type for it.
CONTAINER_NAMESPACE = "Bonsai.Sgen.Container"


def discover_modules() -> list[str]:
    """Returns the name of every module of the `swc.aeon.schema` package declaring models."""
    package = swc.aeon.schema
    names = []
    for info in pkgutil.iter_modules(package.__path__, f"{package.__name__}."):
        if info.name.rpartition(".")[2] in EXCLUDED_MODULES:
            continue

        importlib.import_module(info.name)
        names.append(info.name)

    return names


def discover_models(module_names: list[str]) -> list[type[BaseSchema]]:
    """Returns every schema model declared by the specified modules."""
    models = []
    for module_name in module_names:
        module = sys.modules[module_name]
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, BaseSchema)
                and value.__module__ == module_name
            ):
                models.append(value)

    return models


def build_schema(models: list[type[BaseSchema]]) -> dict:
    """Returns a single JSON schema document holding a definition for every specified model."""
    _, schema = models_json_schema(
        [(model, "validation") for model in models], ref_template="#/$defs/{model}"
    )
    schema[SGEN_TYPENAME] = f"{CONTAINER_NAMESPACE}.Root"
    return schema


def group_by_namespace(schema: dict) -> dict[str, list[str]]:
    """Returns the names of the types in the specified schema, grouped by C# namespace."""
    namespaces = defaultdict(list)
    unannotated = []
    for key, definition in schema.get("$defs", {}).items():
        typename = definition.get(SGEN_TYPENAME)
        if typename is None:
            unannotated.append(key)
            continue

        namespace, _, name = typename.rpartition(".")
        namespaces[namespace].append(name)

    if unannotated:
        raise ValueError(
            f"No {SGEN_TYPENAME} annotation on: {', '.join(sorted(unannotated))}. "
            "Types without a namespace would be generated into every C# project. "
            "Derive them from BaseSchema or SchemaEnum, or annotate them explicitly."
        )

    return dict(namespaces)


def sgen_command(namespace: str, serializer: str | None) -> list[str]:
    """Returns the Bonsai.Sgen invocation generating the classes for the specified namespace."""
    command = [
        "dotnet",
        "bonsai.sgen",
        str(SCHEMA_PATH.relative_to(ROOT)),
        "--namespace",
        namespace,
        "--output",
        str((PROJECT_ROOT / namespace).relative_to(ROOT)),
        "--name",
        f"{namespace}.Generated.cs",
    ]
    if serializer is not None:
        command += ["--serializer", serializer]
    return command


def main() -> int:
    """Writes the schema document and regenerates the C# classes for every namespace in it."""
    parser = argparse.ArgumentParser(description=__doc__.partition("\n")[0])
    parser.add_argument(
        "--serializer",
        choices=["json", "yaml"],
        help="Serializer data annotations to include in the generated classes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write the schema and print the generation commands without running them.",
    )
    args = parser.parse_args()

    module_names = discover_modules()
    targets = {
        namespace
        for module_name in module_names
        for namespace in module_namespaces(module_name)
    }
    schema = build_schema(discover_models(module_names))
    namespaces = group_by_namespace(schema)

    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Wrote {len(schema['$defs'])} type definitions to {SCHEMA_PATH.relative_to(ROOT)}")

    for namespace in sorted(targets - namespaces.keys()):
        print(f"{namespace}: declared but no type belongs to it")

    for namespace, names in sorted(namespaces.items()):
        if namespace not in targets:
            print(f"{namespace}: referenced as external types ({', '.join(sorted(names))})")
            continue

        project = PROJECT_ROOT / namespace
        if not project.is_dir():
            raise FileNotFoundError(
                f"No project folder for namespace {namespace} at {project.relative_to(ROOT)}."
            )

        command = sgen_command(namespace, args.serializer)
        print(f"{namespace}: {', '.join(sorted(names))}")
        if args.dry_run:
            print(f"  {' '.join(command)}")
            continue

        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode != 0:
            return result.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
