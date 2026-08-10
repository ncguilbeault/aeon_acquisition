"""Base classes for defining experiment configuration and data models."""

import sys
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, GetJsonSchemaHandler
from pydantic.alias_generators import to_camel, to_pascal
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

# Schema extension read by Bonsai.Sgen to resolve the fully qualified name of a generated type.
# Types whose namespace matches the target namespace of a generation pass are emitted into that
# pass; all others are referenced as external types, fully qualified.
SGEN_TYPENAME = "x-sgen-typename"

# Class attribute overriding the namespace a single type is generated into.
SGEN_NAMESPACE_ATTR = "__sgen_namespace__"

NAMESPACE_PREFIX = "Aeon"


def module_namespaces(module_name: str) -> tuple[str, ...]:
    """Returns every C# namespace the specified module declares, in declaration order.

    A module declares its namespaces through `SGEN_NAMESPACE`, as either a single namespace or a
    sequence of them. Otherwise a single namespace is derived from the final component of the
    module name, e.g. `...schema.video` maps to `Aeon.Video`.

    Declaring several namespaces lets one module generate types into more than one C# project.
    Each type still belongs to exactly one of them, and any type not declaring a namespace of its
    own belongs to the first.
    """
    declared = getattr(sys.modules[module_name], "SGEN_NAMESPACE", None)
    if declared is None:
        return (f"{NAMESPACE_PREFIX}.{to_pascal(module_name.rpartition('.')[2])}",)

    if isinstance(declared, str):
        return (declared,)

    namespaces = tuple(declared)
    if not namespaces:
        raise ValueError(f"{module_name} declares an empty SGEN_NAMESPACE.")
    return namespaces


def module_namespace(module_name: str) -> str:
    """Returns the C# namespace that models declared in the specified module belong to by default."""
    return module_namespaces(module_name)[0]


def sgen_namespace(cls: type) -> str:
    """Returns the C# namespace the specified class is generated into.

    A namespace declared by the class itself takes priority over the namespace of its module. A
    namespace declared by a base class applies to that base class alone, and is not inherited by
    the classes derived from it.
    """
    namespace = cls.__dict__.get(SGEN_NAMESPACE_ATTR)
    if namespace is None:
        namespace = module_namespace(cls.__module__)
    return namespace


def sgen_typename(cls: type) -> str:
    """Returns the fully qualified C# type name Bonsai.Sgen should emit for the specified class."""
    return f"{sgen_namespace(cls)}.{cls.__name__}"


class BaseSchema(BaseModel):
    """The base class for all experiment configuration and data models.

    A derived class is generated into the namespace of its module. To generate it into a
    different namespace, pass `sgen_namespace` when declaring the class:

        class Commutator(BaseSchema, sgen_namespace="Aeon.Tether.Commutator"):
            ...
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        arbitrary_types_allowed=True,
        field_title_generator=lambda n, _: to_pascal(n),
        populate_by_name=True,
        from_attributes=True,
    )

    def __init_subclass__(cls, sgen_namespace: str | None = None, **kwargs: Any) -> None:
        """Accepts the namespace declaration so that it reaches `__pydantic_init_subclass__`."""
        super().__init_subclass__(**kwargs)

    @classmethod
    def __pydantic_init_subclass__(
        cls, sgen_namespace: str | None = None, **kwargs: Any
    ) -> None:
        """Annotates the model with the C# type name Bonsai.Sgen should generate for it."""
        if sgen_namespace is not None:
            setattr(cls, SGEN_NAMESPACE_ATTR, sgen_namespace)

        extra = cls.model_config.get("json_schema_extra")
        if callable(extra):
            return

        extra = dict(extra or {})
        typename = extra.get(SGEN_TYPENAME)
        # A typename equal to the one on the base class was inherited through the merged model
        # config rather than declared here, so it is recomputed for the derived class.
        if typename is None or typename == getattr(cls, "__sgen_typename__", None):
            typename = sgen_typename(cls)

        extra[SGEN_TYPENAME] = typename
        cls.model_config["json_schema_extra"] = extra
        cls.__sgen_typename__ = typename


class SchemaEnum(StrEnum):
    """The base class for string enumerations used in experiment configuration models.

    A derived enumeration is generated into the namespace of its module. To generate it into a
    different namespace, declare `__sgen_namespace__` in the class body.
    """

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Annotates the enumeration with the C# type name Bonsai.Sgen should generate for it."""
        schema = handler(core_schema)
        schema[SGEN_TYPENAME] = sgen_typename(cls)
        return schema
