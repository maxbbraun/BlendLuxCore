from bpy.props import (
    PointerProperty, BoolProperty, FloatProperty,
    IntProperty, EnumProperty, FloatVectorProperty,
    StringProperty,
)
from bpy.types import PropertyGroup, Image
from .light import GAMMA_DESCRIPTION


class LuxCoreImagepipelineTonemapper(PropertyGroup):
    NAME = "Tonemapper"
    enabled = BoolProperty(name=NAME, default=True, description="Enable/disable " + NAME)

    FSTOP_DESC = "Camera aperture, lower values result in a brighter image"
    EXPOSURE_DESC = (
        "Camera exposure time in seconds. Lower values result in a darker image. "
        "Don't forget that you can enter math formulas here, e.g. 1/100"
    )
    SENSITIVITY_DESC = "Camera sensitivity to light (ISO), lower values lead to a darker image"

    REINHARD_PRESCALE_DESC = ""
    REINHARD_POSTSCALE_DESC = ""
    REINHARD_BURN_DESC = ""

    type_items = [
        ("TONEMAP_LINEAR", "Linear", "Brightness is controlled by the scale value", 0),
        ("TONEMAP_LUXLINEAR", "Camera Settings", "Use camera settings (ISO, f-stop and shuttertime)", 1),
        ("TONEMAP_REINHARD02", "Reinhard", "Non-linear tonemapper that adapts to the image brightness", 2),
    ]
    type = EnumProperty(name="Tonemapper Type", items=type_items, default="TONEMAP_LINEAR",
                        description="The tonemapper converts the image from HDR to LDR")

    # Settings for TONEMAP_LINEAR
    use_autolinear = BoolProperty(name="Auto Brightness", default=True,
                                  description="Auto-detect the optimal image brightness")
    linear_scale = FloatProperty(name="Gain", default=0.5, min=0, soft_min=0.00001, soft_max=100,
                                 description="Image brightness is multiplied with this value")

    # Settings for TONEMAP_LUXLINEAR (camera settings)
    fstop = FloatProperty(name="F-stop", default=2.8, min=0.01, description=FSTOP_DESC)
    exposure = FloatProperty(name="Shutter (s)", default=1 / 100, min=0, description=EXPOSURE_DESC)
    sensitivity = FloatProperty(name="ISO", default=100, min=0, soft_max=6400, description=SENSITIVITY_DESC)

    # Settings for TONEMAP_REINHARD02
    reinhard_prescale = FloatProperty(name="Pre", default=1, min=0, max=25,
                                      description=REINHARD_PRESCALE_DESC)
    reinhard_postscale = FloatProperty(name="Post", default=1.2, min=0, max=25,
                                       description=REINHARD_POSTSCALE_DESC)
    reinhard_burn = FloatProperty(name="Burn", default=6, min=0.01, max=25,
                                  description=REINHARD_BURN_DESC)

    def is_automatic(self):
        autolinear = (self.type == "TONEMAP_LINEAR" and self.use_autolinear)
        return autolinear or self.type == "TONEMAP_REINHARD02"


class LuxCoreImagepipelineBloom(PropertyGroup):
    NAME = "Bloom"
    enabled = BoolProperty(name=NAME, default=False, description="Enable/disable " + NAME)

    radius = FloatProperty(name="Radius", default=7, min=0.1, max=100, precision=1, subtype="PERCENTAGE",
                           description="Size of the bloom effect (percent of the image size)")
    weight = FloatProperty(name="Strength", default=25, min=0, max=100, precision=1, subtype="PERCENTAGE",
                           description="Strength of the bloom effect (a linear mix factor)")


class LuxCoreImagepipelineMist(PropertyGroup):
    NAME = "Mist"
    enabled = BoolProperty(name=NAME, default=False, description="Enable/disable " + NAME)

    EXCLUDE_BACKGROUND_DESC = "Disable mist over background parts of the image (where distance = infinity)"

    color = FloatVectorProperty(name="Color", default=(0.3, 0.4, 0.55), min=0, max=1, subtype="COLOR")
    amount = FloatProperty(name="Strength", default=30, min=0, max=100, precision=1, subtype="PERCENTAGE",
                           description="Strength of the mist overlay")
    start_distance = FloatProperty(name="Start", default=100, min=0, subtype="DISTANCE",
                                   description="Distance from the camera where the mist starts to be visible")
    end_distance = FloatProperty(name="End", default=1000, min=0, subtype="DISTANCE",
                                 description="Distance from the camera where the mist reaches full strength")
    exclude_background = BoolProperty(name="Exclude Background", default=True,
                                      description=EXCLUDE_BACKGROUND_DESC)


class LuxCoreImagepipelineVignetting(PropertyGroup):
    NAME = "Vignetting"
    enabled = BoolProperty(name=NAME, default=False, description="Enable/disable " + NAME)

    scale = FloatProperty(name="Strength", default=40, min=0, soft_max=60, max=100, precision=1,
                          subtype="PERCENTAGE", description="Strength of the vignette")


class LuxCoreImagepipelineColorAberration(PropertyGroup):
    NAME = "Color Aberration"
    enabled = BoolProperty(name=NAME, default=False, description="Enable/disable " + NAME)

    amount = FloatProperty(name="Strength", default=0.5, min=0, soft_max=10, max=100, precision=1,
                           subtype = "PERCENTAGE", description = "Strength of the color aberration effect")


class LuxCoreImagepipelineBackgroundImage(PropertyGroup):
    NAME = "Background Image"
    enabled = BoolProperty(name=NAME, default=False, description="Enable/disable " + NAME)

    image = PointerProperty(name="Image", type=Image)
    gamma = FloatProperty(name="Gamma", default=2.2, min=0, description=GAMMA_DESCRIPTION)


class LuxCoreImagepipelineCameraResponseFunc(PropertyGroup):
    NAME = "Analog Film Simulation"
    enabled = BoolProperty(name=NAME, default=False, description="Enable/disable " + NAME)

    # TODO: Support CRF file as Blender text block (similar to IES files)
    type_items = [
        ("PRESET", "Preset", "Choose a CRF profile from a list of built-in presets", 1),
        ("FILE", "File", "Choose a camera response function file (.crf)", 2),
    ]
    type = EnumProperty(name="Type", items=type_items, default="PRESET",
                        description="Source of the CRF data")

    file = StringProperty(name="", subtype="FILE_PATH",
                          description="Path to the external .crf file")
    # Internal, not shown to the user (set by operator "luxcore.select_crf")
    preset = StringProperty(name="")


class LuxCoreImagepipelineContourLines(PropertyGroup):
    NAME = "Irradiance Contour Lines"
    enabled = BoolProperty(name=NAME, default=False, description="Enable/disable " + NAME)

    ZERO_GRID_SIZE_DESC = (
        "Size of the black grid to draw on image where irradiance values are not avilable "
        "(-1 => no grid, 0 => all black, >0 => size of the black grid)"
    )

    scale = FloatProperty(name="Scale", default=179, min=0, soft_max=1000)
    contour_range = FloatProperty(name="Range", default=100, soft_max=1000,
                                  description="Max range of irradiance values (unit: lux), minimum is always 0")
    steps = IntProperty(name="Steps", default=8, min=0, soft_min=2, soft_max=50,
                        description="Number of steps to draw in interval range")
    zero_grid_size = IntProperty(name="Grid Size", default=8, min=-1, soft_max=20,
                                 description=ZERO_GRID_SIZE_DESC)


class LuxCoreImagepipeline(PropertyGroup):
    """
    Used (and initialized) in properties/camera.py
    The UI elements are located in ui/camera.py
    """
    transparent_film = BoolProperty(name="Transparent Film", default=False,
                                    description="Make the world background transparent")

    tonemapper = PointerProperty(type=LuxCoreImagepipelineTonemapper)
    bloom = PointerProperty(type=LuxCoreImagepipelineBloom)
    mist = PointerProperty(type=LuxCoreImagepipelineMist)
    vignetting = PointerProperty(type=LuxCoreImagepipelineVignetting)
    coloraberration = PointerProperty(type=LuxCoreImagepipelineColorAberration)
    backgroundimage = PointerProperty(type=LuxCoreImagepipelineBackgroundImage)
    camera_response_func = PointerProperty(type=LuxCoreImagepipelineCameraResponseFunc)
    contour_lines = PointerProperty(type=LuxCoreImagepipelineContourLines)
