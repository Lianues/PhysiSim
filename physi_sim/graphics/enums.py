from enum import Enum, auto

class ToolAttachmentMode(Enum):
    CENTER_OF_MASS = auto()
    FREE_POSITION = auto()

class ForceAnalysisDisplayMode(Enum): # Also moving this here to consolidate UI enums
    OBJECT = auto()
    CENTER_OF_MASS = auto()