import uuid
from uuid import UUID # Added for ConnectionComponent
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any # Added Any for ConnectionComponent
from enum import Enum, auto # Added for ShapeType

from .vector import Vector2D # For TransformComponent


@dataclass
class ForceDetail:
    """Stores details of a single force for visualization and analysis."""
    force_vector: Vector2D  # Force vector in world coordinates
    application_point_local: Vector2D  # Application point relative to the body's center of mass
    force_type_label: str  # e.g., "Gravity", "Spring (ID:X)"
    is_visualization_only: bool = False # True if this force is only for rendering and not for physics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "force_vector": self.force_vector.to_dict(),
            "application_point_local": self.application_point_local.to_dict(),
            "force_type_label": self.force_type_label,
            "is_visualization_only": self.is_visualization_only,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ForceDetail':
        # Vector2D.from_dict will handle potential errors for vector fields
        force_vector_data = data.get("force_vector", {})
        application_point_local_data = data.get("application_point_local", {})

        force_vector = Vector2D.from_dict(force_vector_data) if isinstance(force_vector_data, dict) else Vector2D(0,0)
        application_point_local = Vector2D.from_dict(application_point_local_data) if isinstance(application_point_local_data, dict) else Vector2D(0,0)
        
        return cls(
            force_vector=force_vector,
            application_point_local=application_point_local,
            force_type_label=data.get("force_type_label", ""),
            is_visualization_only=data.get("is_visualization_only", False)
        )


class Component:
    """
    Base class for all components in the Entity-Component-System (ECS) architecture.
    Components are primarily data containers that define the properties of entities.
    """
    pass

@dataclass
class IdentifierComponent(Component):
    """
    Stores identifying information for an entity, such as a unique ID, name, and tags.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "Entity"
    type_tags: List[str] = field(default_factory=list)

@dataclass
class TransformComponent(Component):
    """
    Represents the position, angle, and scale of an entity in 2D space.
    """
    position: Vector2D = field(default_factory=lambda: Vector2D(0.0, 0.0))
    angle: float = 0.0  # In radians
    scale: Vector2D = field(default_factory=lambda: Vector2D(1.0, 1.0))

class ShapeType(Enum):
    RECTANGLE = auto()
    CIRCLE = auto()
    POLYGON = auto() # Added for general polygon support

@dataclass
class GeometryComponent(Component):
    """
    Defines the geometric shape of an entity.
    - For RECTANGLE: parameters={"width": float, "height": float}
    - For CIRCLE: parameters={"radius": float}
    - For POLYGON: parameters={"vertices": List[Vector2D]} (local coordinates, CCW order recommended)
    """
    shape_type: ShapeType
    parameters: Dict[str, Any] # Value can be float or List[Vector2D] for POLYGON
    is_solid: bool = True
    is_boundary_only: bool = False

    def __post_init__(self):
        if not isinstance(self.shape_type, ShapeType):
            raise ValueError(f"Unsupported shape_type: {self.shape_type}. Must be an instance of ShapeType.")
        
        if self.shape_type == ShapeType.RECTANGLE:
            if not ("width" in self.parameters and "height" in self.parameters and \
                    isinstance(self.parameters["width"], (int, float)) and \
                    isinstance(self.parameters["height"], (int, float))):
                raise ValueError(f"Missing or invalid 'width'/'height' in parameters for RECTANGLE: {self.parameters}")
        elif self.shape_type == ShapeType.CIRCLE:
            if not ("radius" in self.parameters and isinstance(self.parameters["radius"], (int, float))):
                raise ValueError(f"Missing or invalid 'radius' in parameters for CIRCLE: {self.parameters}")
        elif self.shape_type == ShapeType.POLYGON:
            if "vertices" not in self.parameters:
                raise ValueError(f"Missing 'vertices' in parameters for POLYGON: {self.parameters}")
            vertices = self.parameters["vertices"]
            if not isinstance(vertices, list) or len(vertices) < 3:
                raise ValueError("POLYGON 'vertices' must be a list of at least 3 Vector2D points.")
            for v in vertices:
                if not isinstance(v, Vector2D):
                    raise ValueError("All items in POLYGON 'vertices' must be Vector2D instances.")

    def get_local_snap_points(self) -> List[Vector2D]:
        """
        Calculates and returns a list of local coordinate snap points for the shape.
        """
        snap_points = [Vector2D(0, 0)]  # Center of mass is always a snap point

        if self.shape_type == ShapeType.RECTANGLE:
            width = self.parameters.get("width", 0)
            height = self.parameters.get("height", 0)
            half_width = width / 2
            half_height = height / 2

            # Vertices
            snap_points.append(Vector2D(half_width, half_height))
            snap_points.append(Vector2D(-half_width, half_height))
            snap_points.append(Vector2D(half_width, -half_height))
            snap_points.append(Vector2D(-half_width, -half_height))

            # Midpoints of edges
            snap_points.append(Vector2D(0, half_height))
            snap_points.append(Vector2D(0, -half_height))
            snap_points.append(Vector2D(half_width, 0))
            snap_points.append(Vector2D(-half_width, 0))

        elif self.shape_type == ShapeType.CIRCLE:
            radius = self.parameters.get("radius", 0)
            # Points on the circumference (0, 90, 180, 270 degrees)
            snap_points.append(Vector2D(radius, 0))
            snap_points.append(Vector2D(0, radius))
            snap_points.append(Vector2D(-radius, 0))
            snap_points.append(Vector2D(0, -radius))
            # For a more complete circle representation, could add points at 45, 135, 225, 315 degrees
            # import math
            # for angle_deg in [45, 135, 225, 315]:
            #     angle_rad = math.radians(angle_deg)
            #     snap_points.append(Vector2D(radius * math.cos(angle_rad), radius * math.sin(angle_rad)))
        elif self.shape_type == ShapeType.POLYGON:
            # The center (0,0) which is usually the geometric center/CoM is already added.
            local_vertices = self.parameters.get("vertices", [])
            
            # Add all vertices
            for v in local_vertices:
                if isinstance(v, Vector2D):
                    snap_points.append(v)
            
            # Add midpoints of edges
            num_vertices = len(local_vertices)
            if num_vertices >= 2: # Need at least 2 vertices to form an edge
                for i in range(num_vertices):
                    p1 = local_vertices[i]
                    p2 = local_vertices[(i + 1) % num_vertices] # Wrap around for the last edge
                    if isinstance(p1, Vector2D) and isinstance(p2, Vector2D):
                        mid_point = (p1 + p2) * 0.5
                        snap_points.append(mid_point)
            
            # Geometric center (parameters["center"]) is usually (0,0) in local coords for polygons
            # defined relative to their center. If it's explicitly stored and different, it could be added.
            # For now, the initial Vector2D(0,0) covers the typical case.


        return snap_points

@dataclass
class RenderComponent(Component):
    """
    Contains rendering information for an entity, such as colors, stroke, and visibility.
    """
    fill_color: Tuple[int, int, int, int] = (128, 128, 128, 255)  # RGBA: Grey, Opaque
    stroke_color: Tuple[int, int, int, int] = (0, 0, 0, 255)    # RGBA: Black, Opaque
    stroke_width: float = 1.0
    visible: bool = True # Renamed from visibility to visible for consistency
    z_order: int = 0

# It's good practice to have all component definitions discoverable.
# If TestRenderComponent was meant to be a standard component, it should be here.
# For now, assuming it's a temporary test component managed in main_window.py for the test script.

@dataclass
class PhysicsBodyComponent(Component):
    """
    Represents the physical properties of an entity for dynamics simulation.
    """
    mass: float = 1.0
    moment_of_inertia: float = 1.0  # Simplified, or for future use
    velocity: Vector2D = field(default_factory=lambda: Vector2D(0.0, 0.0))
    angular_velocity: float = 0.0
    is_fixed: bool = False
    restitution: float = 0.5  # Coefficient of restitution (bounciness)
    static_friction_coefficient: float = 0.6
    dynamic_friction_coefficient: float = 0.4
    auto_calculate_inertia: bool = False # If true, moment_of_inertia is calculated from shape and mass
    # Store acceleration from the previous step for Verlet integration
    previous_acceleration: Vector2D = field(default_factory=lambda: Vector2D(0.0, 0.0)) # Removed init=False

    def __post_init__(self):
        # print(f"DEBUG: PhysicsBodyComponent initialized. Mass: {self.mass}, Fixed: {self.is_fixed}") # Reduced debug noise
        # A simple check for mass. If mass is non-positive,
        # it could imply the body is fixed or has infinite mass.
        # For now, we'll just allow positive mass.
        # More complex handling (e.g., setting is_fixed = True if mass <= 0) can be added.
        if self.mass <= 0:
            # For simplicity, we are not automatically setting is_fixed = True here,
            # but it's a common practice.
            # print(f"Warning: PhysicsBodyComponent created with non-positive mass ({self.mass}). Consider making it fixed.")
            pass # Or raise ValueError("Mass must be positive")
        if not self.auto_calculate_inertia and self.moment_of_inertia <= 0:
            raise ValueError("Moment of inertia must be positive if not auto-calculated.")
        elif self.auto_calculate_inertia and self.moment_of_inertia <= 0:
            # If auto-calculating, a placeholder non-positive value is acceptable
            # as it will be overwritten. Setting to a default like 1.0 if mass > 0
            # or inf if mass <=0 might be done by the calculation logic.
            # For now, just allow it to pass validation here.
            pass


@dataclass
class ForceAccumulatorComponent(Component):
    """
    Accumulates forces and torques acting on an entity over a simulation step.
    Also stores individual force details for analysis.
    """
    net_force: Vector2D = field(default_factory=lambda: Vector2D(0.0, 0.0))
    net_torque: float = 0.0
    detailed_forces: List[ForceDetail] = field(default_factory=list) # New field

    def __post_init__(self): # Log added
        # print(f"DEBUG: ForceAccumulatorComponent initialized.") # Keep or remove debug as needed
        pass # Original print was removed in provided file, keeping it minimal

    def clear_forces(self) -> None:
        """Resets the net force to zero and clears detailed force records."""
        self.net_force = Vector2D(0.0, 0.0)
        self.detailed_forces.clear() # Clear detailed forces when net force is cleared

    def clear_torques(self) -> None:
        """Resets the net torque to zero."""
        self.net_torque = 0.0

    def clear_all(self) -> None:
        """Clears all accumulated forces, torques, and detailed force records."""
        self.clear_forces() # This will also clear detailed_forces
        self.clear_torques()

    def add_force(self, force: Vector2D) -> None:
        """
        Adds a force to the accumulator. This force is assumed to act at the center of mass
        for net force calculation. For detailed force visualization, use record_force_detail.
        """
        self.net_force += force

    def add_torque(self, torque: float) -> None:
        """Adds a torque to the accumulator."""
        self.net_torque += torque

    def record_force_detail(self, force_vector: Vector2D, application_point_local: Vector2D, force_type_label: str, is_visualization_only: bool = False) -> None:
        """
        Records an individual force component for visualization and analysis.
        This method does NOT directly add to net_force or net_torque.
        The system applying the force is responsible for also calling add_force and add_torque if necessary.
        """
        self.detailed_forces.append(ForceDetail(force_vector, application_point_local, force_type_label, is_visualization_only))
@dataclass
class SurfaceComponent(Component):
    """
    Marks an entity as a surface and can override some of its physics properties
    when interacting as a surface.
    """
    override_static_friction: Optional[float] = None
    override_dynamic_friction: Optional[float] = None
    override_restitution: Optional[float] = None
    # Add a simple flag to indicate if it's a one-way platform (e.g. can fall through from below)
    is_one_way: bool = False 
    one_way_normal: Optional[Vector2D] = None # e.g., Vector2D(0, -1) means can only pass upwards through it

# Define connection types as constants for clarity
# CONNECTION_TYPE_ROD = "ROD" # Replaced by Enum
# CONNECTION_TYPE_SPRING = "SPRING" # Replaced by Enum
# CONNECTION_TYPE_ROPE = "ROPE"     # Replaced by Enum

class ConnectionType(Enum):
    ROD = auto()
    SPRING = auto()
    ROPE = auto()
    REVOLUTE_JOINT = auto() # Generic revolute joint between two bodies
    # REVOLUTE_JOINT_AXIS = auto() # DEPRECATED - use REVOLUTE_JOINT with one body potentially being a fixed "world" anchor if needed, or a dynamic axis entity.

@dataclass
class ConnectionComponent(Component):
    source_entity_id: UUID # The entity this component instance is primarily associated with, or one end of the connection
    target_entity_id: UUID # The other entity in the connection
    id: UUID = field(default_factory=uuid.uuid4) # Unique ID for the connection instance
    connection_type: ConnectionType = ConnectionType.ROD # Use Enum
    parameters: Dict[str, Any] = field(default_factory=dict) # e.g., ROD: {"target_length": 100.0}, ROPE: {"natural_length": 50.0}
    
    # Local offset from entity's origin (e.g., center of mass)
    connection_point_a: Vector2D = field(default_factory=lambda: Vector2D(0,0))
    # Local offset from target_entity's origin
    connection_point_b: Vector2D = field(default_factory=lambda: Vector2D(0,0))
    
    break_threshold: Optional[float] = None # Force or impulse magnitude to break
    is_broken: bool = False # State of the connection

    def __post_init__(self):
        if not isinstance(self.id, UUID): # Ensure ID is a UUID instance
            try:
                self.id = UUID(self.id) if isinstance(self.id, str) else uuid.uuid4()
            except ValueError:
                self.id = uuid.uuid4()


        if self.connection_type == ConnectionType.ROD:
            if "target_length" not in self.parameters:
                raise ValueError(f"ROD connection (ID: {self.id}) requires 'target_length' parameter.")
            if not isinstance(self.parameters["target_length"], (int, float)) or self.parameters["target_length"] <= 0:
                raise ValueError(f"ROD connection (ID: {self.id}) 'target_length' must be a positive number, got {self.parameters['target_length']}.")
            
            # Ensure old parameter is not lingering, though creation logic should handle this.
            if "fixed_length" in self.parameters:
                del self.parameters["fixed_length"]

        elif self.connection_type == ConnectionType.ROPE:
            if "natural_length" not in self.parameters:
                raise ValueError(f"ROPE connection (ID: {self.id}) requires 'natural_length' parameter.")
            if not isinstance(self.parameters["natural_length"], (int, float)) or self.parameters["natural_length"] < 0:
                raise ValueError(f"ROPE connection (ID: {self.id}) 'natural_length' must be a non-negative number, got {self.parameters['natural_length']}.")
@dataclass
class ScriptExecutionComponent(Component):
    """Holds scripts to be executed at different lifecycle points or events."""
    on_create: Optional[str] = None
    on_update: Optional[str] = None
    on_collision: Optional[str] = None # Collision context (other entity, point, normal) needed later
    custom_event_listeners: Dict[str, str] = field(default_factory=dict)
    # Persistent state for this entity's scripts
    script_variables: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SpringComponent(Component):
    """
    Represents a spring connection between two entities.
    """
    id: UUID # Added for independent component management
    entity_a_id: UUID
    entity_b_id: UUID
    rest_length: float
    stiffness_k: float
    damping_c: float = 0.0
    anchor_a: Vector2D = field(default_factory=lambda: Vector2D(0.0, 0.0))
    anchor_b: Vector2D = field(default_factory=lambda: Vector2D(0.0, 0.0))

    # __init__ will be implicitly created by dataclass.
    # If we need custom __init__ logic beyond what dataclass provides,
    # we would define it here. For now, ensuring 'id' is a parameter.
    # No explicit __init__ needed if all fields are to be constructor arguments.
    # However, to ensure 'id' is handled correctly and to potentially add
    # other initialization logic later, it's better to define __init__
    # or rely on dataclass's default behavior if 'id' is simply another field.
    # For independent components, 'id' is crucial.

    # Let's assume the dataclass will handle the 'id' in its generated __init__
    # If EntityManager.create_independent_component passes 'id' as a kwarg,
    # it should work.

    def __post_init__(self):
        if self.stiffness_k <= 0:
            raise ValueError("Spring stiffness (k) must be positive.")
        if self.damping_c < 0:
            raise ValueError("Spring damping (c) must be non-negative.")
        if self.rest_length < 0: # Though usually positive, 0 could be valid in some contexts
            raise ValueError("Spring rest length must be non-negative.")