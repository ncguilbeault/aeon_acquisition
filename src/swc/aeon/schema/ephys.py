from pydantic import Field

from swc.aeon.schema.base import BaseSchema, SchemaEnum

SGEN_NAMESPACE = "Aeon.Ephys"

class ReferenceSerialized(SchemaEnum):
    """Represents the configuration of a reference electrode for a Neuropixels v2 probe."""

    __sgen_namespace__ = "OpenEphys.Onix1"

    EXTERNAL = "External"
    TIP1 = "Tip1"
    TIP2 = "Tip2"
    TIP3 = "Tip3"
    TIP4 = "Tip4"
    GROUND = "Ground"

class NeuropixelsV2ProbeConfiguration(BaseSchema, sgen_namespace="OpenEphys.Onix1"):
    """Represents the configuration of a Neuropixels v2 probe."""

    invert_polarity: bool = Field(
        default=False, description="Whether to invert the polarity of the probe signal."
    )

    reference: ReferenceSerialized = Field(
        default=ReferenceSerialized.EXTERNAL,
        description="The reference electrode to use for the probe signal.",
    )

    gain_calibration_filename: str = Field(
        default="", description="The path to the gain calibration file."
    )

    probe_interface_filename: str = Field(
        default="", description="The path to the probe interface file."
    )

class ConfigureNeuropixelsV2PsbDecoder(BaseSchema, sgen_namespace="OpenEphys.Onix1"):
    """Configures the Neuropixels v2 probe signal decoder module."""

    enabled: bool = Field(
        default=True, description="Whether to enable the Neuropixels v2 decoder module."
    )

    probe_configuration: NeuropixelsV2ProbeConfiguration = Field(
        default_factory=NeuropixelsV2ProbeConfiguration,
        description="The configuration of the Neuropixels v2 probe.",
    )

class EphysConfiguration(BaseSchema):
    """Represents the configuration of the electrophysiology acquisition system."""

    neuropixels_v2_decoder: ConfigureNeuropixelsV2PsbDecoder = Field(
        default_factory=ConfigureNeuropixelsV2PsbDecoder,
        description="The configuration of the Neuropixels v2 decoder module.",
    )

