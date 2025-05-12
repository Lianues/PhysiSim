import math # Added for SAT
from typing import TYPE_CHECKING, List, Tuple, Optional, TypedDict, Union, Set # Add TypedDict, Union and Set
from physi_sim.core.system import System
from physi_sim.core.component import TransformComponent, GeometryComponent, PhysicsBodyComponent, ShapeType # Import ShapeType
from physi_sim.core.vector import Vector2D # For distance calculation
from physi_sim.core.utils import GRAVITY_ACCELERATION, EPSILON # Import the constant and EPSILON
from physi_sim.core.component import SurfaceComponent # Added for ForceCalculator integration
from .force_calculator import ForceCalculator
class ContactPointInfo(TypedDict):
    point: Vector2D  # World-space contact point position
    normal: Vector2D  # From second object to first object
    penetration_depth: float

if TYPE_CHECKING:
    from physi_sim.core.entity_manager import EntityManager, EntityID

class CollisionSystem(System):
    def __init__(self, entity_manager: 'EntityManager'):
        super().__init__(entity_manager)
        self.force_calculator = ForceCalculator(gravity_vector=GRAVITY_ACCELERATION) # Pass gravity
        self.disabled_collision_pairs: Set[Tuple['EntityID', 'EntityID']] = set()

    def disable_collision_pair(self, entity_id_a: 'EntityID', entity_id_b: 'EntityID') -> None:
        """Disables collision detection between two entities."""
        # Ensure consistent ordering of entity IDs in the tuple
        pair = tuple(sorted((entity_id_a, entity_id_b)))
        self.disabled_collision_pairs.add(pair)
        # print(f"Collision disabled between {entity_id_a} and {entity_id_b}")

    def enable_collision_pair(self, entity_id_a: 'EntityID', entity_id_b: 'EntityID') -> None:
        """Enables collision detection between two entities."""
        pair = tuple(sorted((entity_id_a, entity_id_b)))
        if pair in self.disabled_collision_pairs:
            self.disabled_collision_pairs.remove(pair)
            # print(f"Collision enabled between {entity_id_a} and {entity_id_b}")

    def is_collision_disabled(self, entity_id_a: 'EntityID', entity_id_b: 'EntityID') -> bool:
        """Checks if collision is disabled between two entities."""
        pair = tuple(sorted((entity_id_a, entity_id_b)))
        return pair in self.disabled_collision_pairs

    def _check_circle_circle_collision(self,
                                       transform_a: TransformComponent, geometry_a: GeometryComponent,
                                       transform_b: TransformComponent, geometry_b: GeometryComponent) -> bool:
        # Assuming geometry_a.shape_type == ShapeType.CIRCLE and geometry_b.shape_type == ShapeType.CIRCLE
        pos_a = transform_a.position
        radius_a = geometry_a.parameters.get("radius", 0)
        pos_b = transform_b.position
        radius_b = geometry_b.parameters.get("radius", 0)

        distance_sq = (pos_a.x - pos_b.x)**2 + (pos_a.y - pos_b.y)**2
        radii_sum_sq = (radius_a + radius_b)**2
        return distance_sq < radii_sum_sq

    def _check_aabb_aabb_collision(self,
                                   trans_a: TransformComponent, geom_a: GeometryComponent,
                                   trans_b: TransformComponent, geom_b: GeometryComponent) -> Tuple[bool, Optional[Vector2D], Optional[float]]:
        # Assuming geom_a.shape_type == ShapeType.RECTANGLE and geom_b.shape_type == ShapeType.RECTANGLE
        # And TransformComponent.position is the CENTER of the AABB.
        
        center_a = trans_a.position
        width_a = geom_a.parameters.get("width", 0)
        height_a = geom_a.parameters.get("height", 0)
        half_width_a = width_a / 2
        half_height_a = height_a / 2

        center_b = trans_b.position
        width_b = geom_b.parameters.get("width", 0)
        height_b = geom_b.parameters.get("height", 0)
        half_width_b = width_b / 2
        half_height_b = height_b / 2

        # Calculate distance between centers
        dist_x = center_a.x - center_b.x
        dist_y = center_a.y - center_b.y

        # Calculate sum of half-widths/heights
        sum_half_widths = half_width_a + half_width_b
        sum_half_heights = half_height_a + half_height_b

        # Check for overlap
        overlap_x = sum_half_widths - abs(dist_x)
        overlap_y = sum_half_heights - abs(dist_y)

        if overlap_x > 0 and overlap_y > 0:
            # Collision detected
            penetration_depth: float
            normal: Vector2D

            # Determine axis of minimum penetration
            if overlap_x < overlap_y:
                penetration_depth = overlap_x
                if dist_x > 0: # A is to the right of B
                    normal = Vector2D(1, 0) # Normal points from B to A along X
                else: # A is to the left of B
                    normal = Vector2D(-1, 0) # Normal points from B to A along X
            else:
                penetration_depth = overlap_y
                if dist_y > 0: # A is below B (assuming Y down is positive)
                    normal = Vector2D(0, 1) # Normal points from B to A along Y
                else: # A is above B
                    normal = Vector2D(0, -1) # Normal points from B to A along Y
            return True, normal, penetration_depth
        
        return False, None, None

    def _check_circle_aabb_collision(self,
                                     trans_circle: TransformComponent, geom_circle: GeometryComponent,
                                     trans_aabb: TransformComponent, geom_aabb: GeometryComponent
                                     ) -> Tuple[bool, Optional[Vector2D], Optional[float]]:
        
        circle_center = trans_circle.position # Circle position is its center
        radius = geom_circle.parameters.get("radius", 0)

        aabb_center = trans_aabb.position # AABB position is its center
        aabb_width = geom_aabb.parameters.get("width", 0)
        aabb_height = geom_aabb.parameters.get("height", 0)
        aabb_half_width = aabb_width / 2
        aabb_half_height = aabb_height / 2
        
        aabb_left = aabb_center.x - aabb_half_width
        aabb_right = aabb_center.x + aabb_half_width
        aabb_top = aabb_center.y - aabb_half_height
        aabb_bottom = aabb_center.y + aabb_half_height

        # Find the closest point on the AABB to the circle's center
        closest_x = max(aabb_left, min(circle_center.x, aabb_right))
        closest_y = max(aabb_top, min(circle_center.y, aabb_bottom))
        
        closest_point_on_aabb = Vector2D(closest_x, closest_y)
        
        distance_vector = circle_center - closest_point_on_aabb
        distance_squared = distance_vector.magnitude_squared()

        if distance_squared < radius * radius:
            # Collision detected
            if distance_squared == 0: # Circle center is exactly on the closest_point (e.g. inside AABB)
                # This case needs careful handling for normal.
                # One way: find vector from AABB center to circle center.
                # aabb_center is already defined
                normal = circle_center - aabb_center
                if normal.magnitude_squared() == 0: # If circle center is AABB center
                    normal = Vector2D(0, -1) # Default normal (e.g. push upwards)
                else:
                    normal = normal.normalize()
                # Penetration is harder to define perfectly here, could be radius or distance to an edge.
                # For simplicity when inside, penetration can be radius.
                penetration = radius
            else:
                distance = distance_vector.magnitude()
                normal = distance_vector / distance # Normalize
                penetration = radius - distance
            
            # Normal should point from AABB surface towards circle center for impulse application
            return True, normal, penetration

        return False, None, None

    # SAT Helper methods
    def _get_rotated_vertices(self, entity_id: 'EntityID') -> List[Vector2D]:
        """
        Calculates the world-space vertices of an entity with a geometric shape,
        considering its position and rotation.
        Supports RECTANGLE and POLYGON shapes.
        Position is assumed to be the center of the shape.
        """
        transform = self.entity_manager.get_component(entity_id, TransformComponent)
        geometry = self.entity_manager.get_component(entity_id, GeometryComponent)

        if not transform or not geometry:
            return []

        pos = transform.position
        angle = transform.angle # radians
        local_vertices: List[Vector2D] = []

        if geometry.shape_type == ShapeType.RECTANGLE:
            width = geometry.parameters.get("width", 0.0)
            height = geometry.parameters.get("height", 0.0)
            if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
                # Log error or handle appropriately if parameters are not floats
                return [] # Or raise error
            
            half_width = width / 2
            half_height = height / 2
            local_vertices = [
                Vector2D(-half_width, -half_height), # Top-left
                Vector2D( half_width, -half_height), # Top-right
                Vector2D( half_width,  half_height), # Bottom-right
                Vector2D(-half_width,  half_height)  # Bottom-left
            ]
        elif geometry.shape_type == ShapeType.POLYGON:
            # Ensure 'vertices' exists and is a list of Vector2D
            raw_vertices = geometry.parameters.get("vertices")
            if isinstance(raw_vertices, list) and all(isinstance(v, Vector2D) for v in raw_vertices):
                local_vertices = raw_vertices
            else:
                # Log error or handle appropriately
                return [] # Or raise error
        else:
            # Unsupported shape type for vertex calculation
            return []

        if not local_vertices:
            return []

        # Rotate and translate vertices
        rotated_vertices = [v.rotate(angle) + pos for v in local_vertices]
        return rotated_vertices

    def _get_axes(self, vertices: List[Vector2D]) -> List[Vector2D]:
        """
        Calculates the perpendicular axes (normals) for the edges of a polygon.
        For a rectangle, only two unique axes are needed.
        Vertices should be ordered (e.g., clockwise or counter-clockwise).
        """
        axes = []
        if not vertices or len(vertices) < 2:
            return []

        for i in range(len(vertices)):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % len(vertices)] # Wrap around for the last edge
            edge = p2 - p1
            # Normal is perpendicular to the edge. Ensure it's normalized.
            normal = edge.perpendicular().normalize()
            # Avoid adding duplicate axes (e.g. for parallel edges of a rectangle)
            # This simple check works if normals are consistently calculated (e.g. always pointing "outward")
            # A more robust way for general polygons might involve checking dot products close to -1.
            is_duplicate = False
            for existing_axis in axes:
                if abs(normal.dot(existing_axis) - 1.0) < 1e-6 or \
                   abs(normal.dot(existing_axis) + 1.0) < 1e-6: # Check for parallel or anti-parallel
                    is_duplicate = True
                    break
            if not is_duplicate:
                axes.append(normal)
        return axes

    def _project_shape_onto_axis(self, vertices: List[Vector2D], axis: Vector2D) -> Tuple[float, float]:
        """
        Projects a shape (defined by its vertices) onto a given axis.
        Returns the min and max scalar values of the projection.
        """
        if not vertices:
            return 0.0, 0.0 # Or raise error

        # Ensure axis is normalized for correct projection magnitudes
        # (though dot product itself doesn't strictly require normalized axis for comparison,
        # penetration depth calculation benefits from it if axis is the collision normal)
        # For SAT, axis is already normalized when generated by _get_axes.
        # axis_normalized = axis.normalize() # Not strictly needed if axis is already normal

        min_proj = vertices[0].dot(axis)
        max_proj = min_proj
        for i in range(1, len(vertices)):
            projection = vertices[i].dot(axis)
            if projection < min_proj:
                min_proj = projection
            if projection > max_proj:
                max_proj = projection
        return min_proj, max_proj

    def _interval_overlap(self, min_a: float, max_a: float, min_b: float, max_b: float) -> Optional[float]:
        """
        Checks if two 1D intervals [min_a, max_a] and [min_b, max_b] overlap.
        Returns the amount of overlap (penetration depth) if they do, otherwise None.
        Overlap is always positive.
        """
        # The distance between the interval centers
        # dist_centers = abs((min_a + max_a) / 2 - (min_b + max_b) / 2)
        # Sum of half-lengths
        # sum_half_lengths = (max_a - min_a) / 2 + (max_b - min_b) / 2
        # if dist_centers < sum_half_lengths:
        #    return sum_half_lengths - dist_centers
        # else:
        #    return None
        
        # Simpler way:
        overlap = max(0, min(max_a, max_b) - max(min_a, min_b))
        return overlap if overlap > 0 else None


    def _check_rectangle_rectangle_collision_sat(self,
                                             entity_a_id: 'EntityID',
                                             entity_b_id: 'EntityID'
                                             ) -> Tuple[bool, Optional[List[ContactPointInfo]]]:
        """
        Checks for collision between two (potentially rotated) rectangles using SAT.
        Returns (is_colliding, contact_manifold).
        Each contact point in the manifold contains point, normal (from B to A), and penetration_depth.
        """
        vertices_a = self._get_rotated_vertices(entity_a_id)
        vertices_b = self._get_rotated_vertices(entity_b_id)

        if not vertices_a or not vertices_b:
            return False, None # Entities might not be rectangles or valid

        axes_a = self._get_axes(vertices_a)
        axes_b = self._get_axes(vertices_b)
        
        all_axes = axes_a + axes_b
        if not all_axes:
            return False, None

        min_penetration = float('inf')
        collision_normal_internal: Optional[Vector2D] = None # Renamed to avoid confusion with ContactPointInfo.normal
        
        # The following loop determines the Minimum Translation Vector (MTV)
        # The MTV's direction is the collision_normal_internal, and its magnitude is min_penetration.
        for axis in all_axes:
            min_a, max_a = self._project_shape_onto_axis(vertices_a, axis)
            min_b, max_b = self._project_shape_onto_axis(vertices_b, axis)

            # Check for separation along this axis
            if max_a < min_b or max_b < min_a:
                return False, None # Separating axis found

            # Calculate overlap
            overlap_val = min(max_a, max_b) - max(min_a, min_b)

            # If this is the smallest overlap so far, store it
            if overlap_val < min_penetration:
                min_penetration = overlap_val
                collision_normal_internal = axis
                
                # Ensure the normal points from B to A.
                # Project the vector from B's center to A's center onto the current axis.
                # If the projection is in the opposite direction of the axis, flip the axis.
                trans_a = self.entity_manager.get_component(entity_a_id, TransformComponent)
                trans_b = self.entity_manager.get_component(entity_b_id, TransformComponent)
                if trans_a and trans_b: # Should always be true if entities are valid
                    center_to_center_vec = trans_a.position - trans_b.position
                    if center_to_center_vec.dot(collision_normal_internal) < 0:
                        collision_normal_internal = -collision_normal_internal
        
        if collision_normal_internal is None or min_penetration == float('inf'):
            # This case should ideally be caught by the separation check,
            # but as a safeguard if all_axes was empty or other edge cases.
            return False, None

        # collision_normal_internal should already be normalized from _get_axes
        # min_penetration is the depth of penetration along this normal.

        # Find contact points (as Vector2D) using the refined logic
        contact_point_vectors = self._find_contact_points_rect_rect(
            vertices_a, vertices_b, collision_normal_internal, min_penetration
        )

        if not contact_point_vectors: # Should not happen with the new _find_contact_points_rect_rect
            return False, None

        # Construct the contact manifold
        contact_manifold: List[ContactPointInfo] = []
        for cp_vec in contact_point_vectors:
            contact_manifold.append({
                "point": cp_vec,
                "normal": collision_normal_internal, # Normal from B to A
                "penetration_depth": min_penetration
            })
        
        return True, contact_manifold
    def _check_polygon_polygon_collision_sat(self,
                                             entity_a_id: 'EntityID',
                                             entity_b_id: 'EntityID'
                                             ) -> Tuple[bool, Optional[List[ContactPointInfo]]]:
        """
        Checks for collision between two (potentially rotated) polygons using SAT.
        Returns (is_colliding, contact_manifold).
        Each contact point in the manifold contains point, normal (from B to A), and penetration_depth.
        """
        # # print(f"DEBUG_SAT: _check_polygon_polygon_collision_sat called for A: {entity_a_id}, B: {entity_b_id}") # DEBUG LOG - Commented out
        geom_a = self.entity_manager.get_component(entity_a_id, GeometryComponent)
        geom_b = self.entity_manager.get_component(entity_b_id, GeometryComponent)

        if not geom_a or geom_a.shape_type not in [ShapeType.POLYGON, ShapeType.RECTANGLE]:
            # This function handles POLYGON-POLYGON and RECTANGLE-POLYGON (and RECT-RECT if called this way)
            # # print(f"DEBUG: _check_polygon_polygon_collision_sat called with invalid shape A: {entity_a_id}, type {geom_a.shape_type if geom_a else 'N/A'}")
            return False, None
        if not geom_b or geom_b.shape_type not in [ShapeType.POLYGON, ShapeType.RECTANGLE]:
            # # print(f"DEBUG: _check_polygon_polygon_collision_sat called with invalid shape B: {entity_b_id}, type {geom_b.shape_type if geom_b else 'N/A'}")
            return False, None

        vertices_a = self._get_rotated_vertices(entity_a_id)
        vertices_b = self._get_rotated_vertices(entity_b_id)
        # # print(f"DEBUG_SAT: entity_a_id={entity_a_id}, vertices_a={str(vertices_a)[:200]}") # DEBUG LOG - Truncate for brevity - Commented out
        # # print(f"DEBUG_SAT: entity_b_id={entity_b_id}, vertices_b={str(vertices_b)[:200]}") # DEBUG LOG - Truncate for brevity - Commented out

        if not vertices_a or not vertices_b:
            # # print(f"DEBUG: Could not get vertices for polygon collision: A empty: {not vertices_a}, B empty: {not vertices_b}")
            return False, None # Entities might not be valid polygons or error in vertex retrieval

        axes_a = self._get_axes(vertices_a)
        axes_b = self._get_axes(vertices_b)
        
        all_axes = axes_a + axes_b
        if not all_axes:
            # # print("DEBUG: No axes found for polygon collision.")
            return False, None

        min_penetration = float('inf')
        collision_normal_internal: Optional[Vector2D] = None
        
        for axis in all_axes:
            if axis.magnitude_squared() < EPSILON * EPSILON: # Skip zero axes if any
                continue
            min_a, max_a = self._project_shape_onto_axis(vertices_a, axis)
            min_b, max_b = self._project_shape_onto_axis(vertices_b, axis)

            if max_a < min_b - EPSILON or max_b < min_a - EPSILON: # Added EPSILON for robustness
                return False, None # Separating axis found

            overlap_val = min(max_a, max_b) - max(min_a, min_b)

            if overlap_val < min_penetration:
                min_penetration = overlap_val
                collision_normal_internal = axis
                
                trans_a = self.entity_manager.get_component(entity_a_id, TransformComponent)
                trans_b = self.entity_manager.get_component(entity_b_id, TransformComponent)
                if trans_a and trans_b:
                    center_to_center_vec = trans_a.position - trans_b.position # Vector from B's center to A's center
                    
                    # Log before flipping attempt
                    # print(f"LOG_SAT_PRE_FLIP: A={str(entity_a_id)[:8]}, B={str(entity_b_id)[:8]}")
                    # print(f"  center_A={trans_a.position}, center_B={trans_b.position}")
                    # print(f"  center_B_to_A_vec={center_to_center_vec}")
                    # print(f"  initial_MTV_axis(collision_normal_internal)={collision_normal_internal}")
                    dot_product = center_to_center_vec.dot(collision_normal_internal)
                    # print(f"  dot_product (center_B_to_A_vec . initial_MTV_axis)={dot_product:.4f}")

                    if dot_product < 0: # If MTV axis is opposite to B->A vector, flip MTV axis
                        collision_normal_internal = -collision_normal_internal
                        # print(f"  MTV_axis FLIPPED. New collision_normal_internal (B->A)={collision_normal_internal}")
                    # else:
                        # print(f"  MTV_axis NOT FLIPPED. collision_normal_internal (B->A) remains={collision_normal_internal}")
                # else: # Should not happen if trans_a and trans_b are valid
                #     # print(f"LOG_SAT_PRE_FLIP: Missing transform for A or B. A:{trans_a is not None}, B:{trans_b is not None}")

        if collision_normal_internal is None or min_penetration == float('inf') or min_penetration < 0: # min_penetration should be positive
            # # print(f"DEBUG: Polygon collision check failed: normal_internal is None or invalid penetration ({min_penetration})")
            return False, None

        # Ensure collision_normal_internal is normalized (it should be from _get_axes)
        if abs(collision_normal_internal.magnitude_squared() - 1.0) > EPSILON:
             collision_normal_internal = collision_normal_internal.normalize()
        # # print(f"DEBUG_SAT: Pre-contact find: entity_a_id={entity_a_id}, entity_b_id={entity_b_id}, collision_normal_internal={collision_normal_internal}, min_penetration={min_penetration}") # DEBUG LOG - Commented out


        # Find contact points (as Vector2D)
        phys_a = self.entity_manager.get_component(entity_a_id, PhysicsBodyComponent)
        phys_b = self.entity_manager.get_component(entity_b_id, PhysicsBodyComponent)

        is_fixed_a = phys_a.is_fixed if phys_a else False
        is_fixed_b = phys_b.is_fixed if phys_b else False
        
        contact_points_on_A_surface = self._find_contact_points_polygon_polygon(
            vertices_a, vertices_b, collision_normal_internal, min_penetration, is_fixed_a, is_fixed_b
        )

        if not contact_points_on_A_surface:
            # print(f"DEBUG_SAT: _find_contact_points_polygon_polygon for {entity_a_id} vs {entity_b_id} returned no points. Treating as no collision.")
            return False, None

        # Ensure we have exactly one contact point as per the new design objective for this function's output
        if len(contact_points_on_A_surface) != 1:
            # print(f"DEBUG_SAT: WARNING - _find_contact_points_polygon_polygon returned {len(contact_points_on_A_surface)} points, expected 1. Using the first one.")
            # Potentially log this as an issue or refine _find_contact_points_polygon_polygon further
            # if multiple points are still possible in some edge cases.
            # For now, take the first one if multiple, though ideally it should be one.
            if not contact_points_on_A_surface: # Should be caught above, but defensive
                 return False, None


        # The single representative contact point in world space.
        # This point is on the surface of A, as calculated by the clipping logic.
        representative_contact_point_world = contact_points_on_A_surface[0]

        contact_manifold: List[ContactPointInfo] = [{
            "point": representative_contact_point_world,
            "normal": collision_normal_internal, # Normal from B to A
            "penetration_depth": min_penetration
        }]
        
        # print(f"DEBUG_SAT: Polygon-Polygon Collision. Entity A: {entity_a_id}, Entity B: {entity_b_id}")
        # print(f"DEBUG_SAT:   Normal (B->A): {collision_normal_internal}, Penetration: {min_penetration}")
        # print(f"DEBUG_SAT:   Contact Point (World on A's surface): {representative_contact_point_world}")
        return True, contact_manifold

    def _get_polygon_edges_with_outward_normals(self, vertices: List[Vector2D]) -> List[Tuple[Vector2D, Vector2D, Vector2D]]:
        """
        Helper to get edges and their outward normals for a polygon.
        Assumes CCW vertex order for Y-down system results in outward normals.
        Returns a list of tuples: (vertex1, vertex2, outward_normal_of_edge).
        """
        edges = []
        num_vertices = len(vertices)
        if num_vertices < 2:
            return []
        for i in range(num_vertices):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % num_vertices]
            edge_vector = p2 - p1
            # For CCW vertices (Y-down): (dx, dy) -> outward normal (dy, -dx)
            # Ensure it's normalized.
            outward_normal = Vector2D(edge_vector.y, -edge_vector.x).normalize()
            edges.append((p1, p2, outward_normal))
        return edges

    def _project_point_onto_line(self, point: Vector2D, line_p1: Vector2D, line_p2: Vector2D) -> Vector2D:
        """Projects a point onto the infinite line defined by line_p1 and line_p2."""
        line_vec = line_p2 - line_p1
        if line_vec.magnitude_squared() < EPSILON * EPSILON:
            return line_p1 # Line is a point
        t = (point - line_p1).dot(line_vec) / line_vec.magnitude_squared()
        return line_p1 + line_vec * t

    def _find_best_matching_edge(self,
                                 vertices: List[Vector2D],
                                 target_normal_direction: Vector2D
                                 ) -> Optional[Tuple[Vector2D, Vector2D, Vector2D]]:
        """
        Finds the edge on the polygon whose outward normal is most aligned with target_normal_direction.
        Returns (edge_v1, edge_v2, edge_outward_normal) or None.
        """
        if not vertices or len(vertices) < 2:
            return None

        best_edge_v1: Optional[Vector2D] = None
        best_edge_v2: Optional[Vector2D] = None
        best_edge_normal: Optional[Vector2D] = None
        max_dot = -float('inf')

        edges = self._get_polygon_edges_with_outward_normals(vertices)
        if not edges:
            return None

        for v1, v2, edge_out_normal in edges:
            dot_val = edge_out_normal.dot(target_normal_direction)
            if dot_val > max_dot:
                max_dot = dot_val
                best_edge_v1 = v1
                best_edge_v2 = v2
                best_edge_normal = edge_out_normal
        
        if best_edge_v1 and best_edge_v2 and best_edge_normal:
            return best_edge_v1, best_edge_v2, best_edge_normal
        return None

    def _clip_line_segment_to_line_segment_region(self,
                                              incident_v1: Vector2D, incident_v2: Vector2D,
                                              ref_v1: Vector2D, ref_v2: Vector2D
                                              ) -> Optional[Tuple[Vector2D, Vector2D]]:
        """
        Clips the incident_segment (incident_v1, incident_v2) against the 'support region'
        of the reference_segment (ref_v1, ref_v2). The support region is defined by two
        lines perpendicular to the reference segment, passing through its endpoints.
        Uses a Cyrus-Beck-like approach by parameterizing the incident segment and finding
        intersection parameters with the two clipping lines.
        Returns the clipped segment (cp1, cp2) or None if no overlap or segment is outside.
        """
        # print(f"DEBUG_CLIP: Start clipping incident seg ({incident_v1}, {incident_v2}) against ref seg ({ref_v1}, {ref_v2})")
        # # print(f"DETAILED_LOG: _clip_line_segment_to_line_segment_region:") # Removed
        # # print(f"DETAILED_LOG:   incident_v1: {incident_v1}, incident_v2: {incident_v2}") # Removed
        # # print(f"DETAILED_LOG:   ref_v1: {ref_v1}, ref_v2: {ref_v2}") # Removed

        ref_edge_vec = ref_v2 - ref_v1
        incident_edge_vec = incident_v2 - incident_v1

        if ref_edge_vec.magnitude_squared() < EPSILON * EPSILON:
            # print(f"DEBUG_CLIP: Reference edge is a point ({ref_v1}). Cannot form clipping region.")
            # If incident segment itself is also a point and matches ref_v1, it's a point contact.
            if incident_edge_vec.magnitude_squared() < EPSILON * EPSILON and \
               (incident_v1 - ref_v1).magnitude_squared() < EPSILON * EPSILON:
                return ref_v1, ref_v1
            return None

        # Normals of the two clipping lines (perpendicular to ref_edge_vec)
        # These normals point "outside" the valid region if we consider the ref_edge_vec direction.
        # Let's define normals that point "inward" to the support region of the reference edge.
        # Clip line 1: Passes through ref_v1, normal is ref_edge_vec.normalize()
        # Clip line 2: Passes through ref_v2, normal is -ref_edge_vec.normalize()

        clip_line_normal1 = ref_edge_vec.normalize()
        clip_line_normal2 = -ref_edge_vec.normalize()

        # Parameter t for the incident segment: P(t) = incident_v1 + t * incident_edge_vec, for t in [0, 1]
        t_enter = 0.0  # Max of t_enters
        t_leave = 1.0  # Min of t_leaves

        # Clip against Line 1 (at ref_v1, normal along ref_edge_vec)
        # N = clip_line_normal1, P0 = ref_v1, S = incident_v1, D = incident_edge_vec
        # We want (P(t) - P0) . N >= 0  =>  (S + tD - P0) . N >= 0
        # (S - P0) . N + t (D . N) >= 0
        # t (D . N) >= -(S - P0) . N
        # t (D . N) >= (P0 - S) . N
        
        # Numerator for t: (P0 - S) . N
        # Denominator for t: D . N
        
        # Denominator for line 1
        denom1 = incident_edge_vec.dot(clip_line_normal1)
        # Numerator for line 1
        num1 = (ref_v1 - incident_v1).dot(clip_line_normal1)

        if abs(denom1) < EPSILON: # Incident segment is parallel to clip line 1
            if num1 < -EPSILON: # Incident segment is outside and parallel (P0-S).N < 0 means S is on the "wrong" side
                # print(f"DEBUG_CLIP: Parallel to clip line 1 and outside (num1={num1}). No clip.")
                return None
            # else: parallel and inside or on the line, no change to t_enter/t_leave from this line
        else:
            t = num1 / denom1
            if denom1 > 0: # Line enters from outside to inside (D.N > 0)
                t_enter = max(t_enter, t)
                # print(f"DEBUG_CLIP: ClipLine1 (enter): t={t:.3f}, t_enter={t_enter:.3f} (denom1={denom1:.3f}, num1={num1:.3f})")
                # # print(f"DETAILED_LOG:   ClipLine1 (enter): t_raw={t}, current t_enter={t_enter}") # Removed
            else: # Line leaves from inside to outside (D.N < 0)
                t_leave = min(t_leave, t)
                # print(f"DEBUG_CLIP: ClipLine1 (leave): t={t:.3f}, t_leave={t_leave:.3f} (denom1={denom1:.3f}, num1={num1:.3f})")
                # # print(f"DETAILED_LOG:   ClipLine1 (leave): t_raw={t}, current t_leave={t_leave}") # Removed

        if t_enter > t_leave + EPSILON: # +EPSILON for robustness with floating point comparisons
            # print(f"DEBUG_CLIP: t_enter ({t_enter:.3f}) > t_leave ({t_leave:.3f}) after clip line 1. No clip.")
            return None

        # Clip against Line 2 (at ref_v2, normal against ref_edge_vec)
        # N = clip_line_normal2, P0 = ref_v2
        denom2 = incident_edge_vec.dot(clip_line_normal2)
        num2 = (ref_v2 - incident_v1).dot(clip_line_normal2)

        if abs(denom2) < EPSILON: # Incident segment is parallel to clip line 2
            if num2 < -EPSILON: # Incident segment is outside and parallel
                # print(f"DEBUG_CLIP: Parallel to clip line 2 and outside (num2={num2}). No clip.")
                return None
        else:
            t = num2 / denom2
            if denom2 > 0: # Line enters from outside to inside
                t_enter = max(t_enter, t)
                # print(f"DEBUG_CLIP: ClipLine2 (enter): t={t:.3f}, t_enter={t_enter:.3f} (denom2={denom2:.3f}, num2={num2:.3f})")
                # # print(f"DETAILED_LOG:   ClipLine2 (enter): t_raw={t}, current t_enter={t_enter}") # Removed
            else: # Line leaves from inside to outside
                t_leave = min(t_leave, t)
                # print(f"DEBUG_CLIP: ClipLine2 (leave): t={t:.3f}, t_leave={t_leave:.3f} (denom2={denom2:.3f}, num2={num2:.3f})")
                # # print(f"DETAILED_LOG:   ClipLine2 (leave): t_raw={t}, current t_leave={t_leave}") # Removed
        
        if t_enter > t_leave + EPSILON:
            # print(f"DEBUG_CLIP: t_enter ({t_enter:.3f}) > t_leave ({t_leave:.3f}) after clip line 2. No clip.")
            return None

        # Ensure t_enter and t_leave are within [0,1] range of the original incident segment
        final_t_start = max(0.0, t_enter)
        final_t_end = min(1.0, t_leave)
        
        # print(f"DEBUG_CLIP: Original t_range: [0,1]. Clipped t_range before [0,1] clamp: [{t_enter:.3f}, {t_leave:.3f}]")
        # print(f"DEBUG_CLIP: Final t_range after [0,1] clamp: [{final_t_start:.3f}, {final_t_end:.3f}]")
        # # print(f"DETAILED_LOG:   t_enter_final: {final_t_start}, t_leave_final: {final_t_end}") # Removed


        if final_t_start > final_t_end + EPSILON : # Segment is completely outside or reduced to less than a point
            # print(f"DEBUG_CLIP: Final t_start ({final_t_start:.3f}) > final_t_end ({final_t_end:.3f}). No valid clipped segment.")
            return None
        
        # If the segment is extremely short (effectively a point)
        if abs(final_t_start - final_t_end) < EPSILON:
             # Check if this point is within the original [0,1] range of the incident segment
            if 0.0 - EPSILON <= final_t_start <= 1.0 + EPSILON:
                clipped_point = incident_v1 + incident_edge_vec * final_t_start
                # print(f"DEBUG_CLIP: Clipped segment is a point: {clipped_point}")
                # # print(f"DETAILED_LOG:   Clipped result is a point: {clipped_point}") # Removed
                return clipped_point, clipped_point
            else: # Point is outside original segment
                # print(f"DEBUG_CLIP: Clipped point {final_t_start:.3f} is outside original segment [0,1]. No clip.")
                return None


        clipped_v1 = incident_v1 + incident_edge_vec * final_t_start
        clipped_v2 = incident_v1 + incident_edge_vec * final_t_end
        
        # print(f"DEBUG_CLIP: Successfully clipped segment: ({clipped_v1} -> {clipped_v2})")
        # # print(f"DETAILED_LOG:   Clipped result segment: v1={clipped_v1}, v2={clipped_v2}") # Removed
        return clipped_v1, clipped_v2


    def _find_contact_points_polygon_polygon(self,
                                           vertices_a: List[Vector2D], # Vertices of polygon A (reference)
                                           vertices_b: List[Vector2D], # Vertices of polygon B (incident)
                                           collision_normal: Vector2D, # Collision normal, from B to A
                                           penetration: float,
                                           is_fixed_a: bool, # Added: True if entity A is fixed
                                           is_fixed_b: bool  # Added: True if entity B is fixed
                                           ) -> List[Vector2D]:
        """
        Finds contact points for a polygon-polygon collision.
        A is treated as the reference polygon, B as the incident polygon.
        The collision_normal points from B to A.
        This implementation uses edge clipping to find a contact manifold (line segment)
        and returns its midpoint as the single representative contact point.
        """
        # print(f"DEBUG_CONTACT_MANIFOLD: ======== Start _find_contact_points_polygon_polygon ========")
        # # print(f"DETAILED_LOG: _find_contact_points_polygon_polygon called with:") # Removed
        # # print(f"DETAILED_LOG:   vertices_a (count: {len(vertices_a)}): {vertices_a}") # Removed
        # # print(f"DETAILED_LOG:   vertices_b (count: {len(vertices_b)}): {vertices_b}") # Removed
        # # print(f"DETAILED_LOG:   collision_normal (B->A): {collision_normal}") # Removed
        # # print(f"DETAILED_LOG:   penetration: {penetration}") # Removed
        # # print(f"DETAILED_LOG:   is_fixed_a: {is_fixed_a}, is_fixed_b: {is_fixed_b}") # Removed
        # print(f"DEBUG_CONTACT_MANIFOLD:   Poly A Vertices ({len(vertices_a)}): {str(vertices_a)}")
        # print(f"DEBUG_CONTACT_MANIFOLD:   Poly B Vertices ({len(vertices_b)}): {str(vertices_b)}") # Keeping original for context if needed
        # print(f"DEBUG_CONTACT_MANIFOLD:   Collision Normal (B->A): {collision_normal}, Penetration: {penetration}") # Keeping original

        if not vertices_a or not vertices_b:
            # print("DEBUG_CONTACT_MANIFOLD:   Error: Empty vertices list provided.")
            return []
        
        # --- Enhanced Feature Recognition Logic ---
        # The previous ground contact heuristic has been removed as it caused issues with partial overlaps.
        # The general SAT + feature finding logic below should handle these cases more robustly.
        # print(f"LOG_CONTACT_GEN:   Skipping specialized ground contact heuristic. Using general polygon-polygon logic.")

        # Step a: Find deepest penetrating vertices of B (incident body)
        # Reference edge on A: its outward normal is most anti-parallel to collision_normal (B->A).
        # So, edge_normal_a.dot(collision_normal) is minimized (closest to -1).
        # Or, edge_normal_a.dot(-collision_normal) is maximized (closest to +1).
        # Target normal for A's edge: -collision_normal (points from A towards B, or into A if collision_normal is B->A)
        
        ref_edge_info_A = self._find_best_matching_edge(vertices_a, -collision_normal)
        if not ref_edge_info_A:
            # print("DEBUG_CONTACT_MANIFOLD:   Error: Could not find reference edge on Polygon A.")
            # Fallback to a simple point (e.g., center of B pushed back)
            center_b = sum(vertices_b, Vector2D(0,0)) / len(vertices_b) if vertices_b else Vector2D(0,0)
            return [center_b - collision_normal * penetration]
        
        ref_edge_v1_a, ref_edge_v2_a, ref_edge_normal_a = ref_edge_info_A
        # print(f"DEBUG_CONTACT_MANIFOLD:   Reference Edge A: ({ref_edge_v1_a} -> {ref_edge_v2_a}), Normal_A_out: {ref_edge_normal_a}")
        # # print(f"DETAILED_LOG:   Selected Reference Edge A (v1, v2, normal_out): {ref_edge_info_A}") # Removed

        # --- PRIORITY: Vertex-Face Contact Check (based on deepest penetrating point of B relative to A's reference face) ---
        # ref_edge_normal_a is the outward normal of A's reference edge.
        # We want to find vertices of B that are "deepest" into A's half-space defined by this reference edge.
        min_signed_dist_to_A_face = float('inf')
        deepest_vertices_b_list: List[Vector2D] = []
        if not vertices_b: # Should be caught earlier
            # print("DEBUG_CONTACT_MANIFOLD:   Error: vertices_b is empty before primary vertex-face check.")
            return [(ref_edge_v1_a + ref_edge_v2_a) * 0.5]

        for v_b_candidate in vertices_b:
            # Calculate signed distance from v_b_candidate to the plane of A's reference edge.
            # A negative distance indicates penetration into A's material (if ref_edge_normal_a points outward from A).
            dist_to_ref_plane = (v_b_candidate - ref_edge_v1_a).dot(ref_edge_normal_a)
            if abs(dist_to_ref_plane - min_signed_dist_to_A_face) < EPSILON: # Allow for multiple vertices at the same depth
                deepest_vertices_b_list.append(v_b_candidate)
            elif dist_to_ref_plane < min_signed_dist_to_A_face:
                min_signed_dist_to_A_face = dist_to_ref_plane
                deepest_vertices_b_list = [v_b_candidate]
        
        # print(f"DEBUG_CONTACT_MANIFOLD:   Primary V-F Check: Min signed dist to A's ref face: {min_signed_dist_to_A_face:.4f}, Num deepest B vertices: {len(deepest_vertices_b_list)}")

        is_point_feature_contact = False
        incident_feature_point_b: Optional[Vector2D] = None

        if len(deepest_vertices_b_list) == 1:
            is_point_feature_contact = True
            incident_feature_point_b = deepest_vertices_b_list[0]
            # print(f"DEBUG_CONTACT_MANIFOLD:   Primary V-F Check: Single deepest vertex B: {incident_feature_point_b}")
        elif len(deepest_vertices_b_list) == 2:
            v1_b, v2_b = deepest_vertices_b_list[0], deepest_vertices_b_list[1]
            # Consider them a "point feature" if they are very close (e.g., a very short edge)
            # This threshold might need tuning.
            vertex_cluster_threshold_sq = (EPSILON * 20)**2 # Increased threshold slightly
            if (v1_b - v2_b).magnitude_squared() < vertex_cluster_threshold_sq:
                is_point_feature_contact = True
                incident_feature_point_b = (v1_b + v2_b) * 0.5
                # print(f"DEBUG_CONTACT_MANIFOLD:   Primary V-F Check: Two very close deepest B vertices, using midpoint: {incident_feature_point_b}")
            # else:
                # print(f"DEBUG_CONTACT_MANIFOLD:   Primary V-F Check: Two deepest B vertices are not close enough to be a single point feature.")
        # else: # More than 2 deepest vertices, likely a face.
             # print(f"DEBUG_CONTACT_MANIFOLD:   Primary V-F Check: {len(deepest_vertices_b_list)} deepest B vertices, not a point feature.")


        if is_point_feature_contact and incident_feature_point_b:
            # print(f"DEBUG_CONTACT_MANIFOLD:   Prioritizing Vertex-Face contact based on deepest point(s) of B. Incident Feature B: {incident_feature_point_b}")
            
            projected_contact_on_A_line = self._project_point_onto_line(incident_feature_point_b, ref_edge_v1_a, ref_edge_v2_a)
            
            ref_edge_segment_vec = ref_edge_v2_a - ref_edge_v1_a
            if ref_edge_segment_vec.magnitude_squared() < EPSILON * EPSILON:
                final_contact_point_on_A = ref_edge_v1_a
            else:
                t = (projected_contact_on_A_line - ref_edge_v1_a).dot(ref_edge_segment_vec) / ref_edge_segment_vec.magnitude_squared()
                clamped_t = max(0.0, min(1.0, t))
                final_contact_point_on_A = ref_edge_v1_a + ref_edge_segment_vec * clamped_t
            
            # print(f"DEBUG_CONTACT_MANIFOLD:   Vertex-Face contact point (on A's surface): {final_contact_point_on_A}")
            # print(f"DEBUG_CONTACT_MANIFOLD: ======== End _find_contact_points_polygon_polygon (Priority Vertex-Face) ========")
            return [final_contact_point_on_A]

        # --- If not a clear Vertex-Face, proceed to find incident edge and then clip ---
        # print(f"DEBUG_CONTACT_MANIFOLD:   No clear single-point V-F contact. Proceeding to find incident edge for B.")
        # 1b. Determine Incident Edge on Polygon B
        # Incident edge on B: its outward normal is most parallel to collision_normal (B->A).
        # So, edge_normal_b.dot(collision_normal) is maximized (closest to +1).
        inc_edge_info_B = self._find_best_matching_edge(vertices_b, collision_normal)
        if not inc_edge_info_B:
            # print("DEBUG_CONTACT_MANIFOLD:   Error: Could not find incident edge on Polygon B (after V-F check).")
            # Fallback, though primary V-F should have caught pure vertex contacts.
            # This might happen if V-F was borderline and then no good edge found.
            if deepest_vertices_b_list: # Use average of deepest if available
                 center_b = sum(deepest_vertices_b_list, Vector2D(0,0)) / len(deepest_vertices_b_list)
                 return [center_b - collision_normal * penetration] # Push back along normal
            center_b_fallback = sum(vertices_b, Vector2D(0,0)) / len(vertices_b) if vertices_b else Vector2D(0,0)
            return [center_b_fallback - collision_normal * penetration]


        inc_edge_v1_b, inc_edge_v2_b, inc_edge_normal_b = inc_edge_info_B # inc_edge_normal_b is outward normal of B's edge
        # print(f"DEBUG_CONTACT_MANIFOLD:   Selected Incident Edge B for clipping: ({inc_edge_v1_b} -> {inc_edge_v2_b}), Normal_B_out: {inc_edge_normal_b}")
        
        # --- Edge-Edge Contact (Clipping) Logic --- (This was the previous V-F check location, now it's just edge-edge)
        # print(f"DEBUG_CONTACT_MANIFOLD:   Proceeding with Edge-Edge (clipping) logic using selected incident edge B.")
        
        clipped_incident_segment = self._clip_line_segment_to_line_segment_region(
            inc_edge_v1_b, inc_edge_v2_b,
            ref_edge_v1_a, ref_edge_v2_a
        )

        if not clipped_incident_segment:
            # print("DEBUG_CONTACT_MANIFOLD:   Clipping failed or resulted in no segment. Attempting vertex-based fallback.")
            # Fallback: project the most penetrating vertex of B onto reference edge A.
            # Find vertex of B "deepest" along collision_normal (B->A).
            # This means its projection on collision_normal is minimal.
            min_proj_val_b = float('inf')
            deepest_vertex_b: Optional[Vector2D] = None
            if not vertices_b:
                 # print("DEBUG_CONTACT_MANIFOLD:   Error: vertices_b is empty in fallback.")
                 return [(ref_edge_v1_a + ref_edge_v2_a) * 0.5] # Last resort

            for v_b_candidate in vertices_b:
                proj = v_b_candidate.dot(collision_normal)
                if proj < min_proj_val_b:
                    min_proj_val_b = proj
                    deepest_vertex_b = v_b_candidate
            
            if deepest_vertex_b:
                # Project this deepest vertex of B onto the reference edge A's line segment
                projected_contact = self._project_point_onto_line(deepest_vertex_b, ref_edge_v1_a, ref_edge_v2_a)
                # Clamp to the reference edge segment
                ref_edge_segment_vec = ref_edge_v2_a - ref_edge_v1_a
                if ref_edge_segment_vec.magnitude_squared() < EPSILON * EPSILON: # Ref edge is a point
                    final_contact_point_on_A = ref_edge_v1_a
                else:
                    t = (projected_contact - ref_edge_v1_a).dot(ref_edge_segment_vec) / ref_edge_segment_vec.magnitude_squared()
                    clamped_t = max(0.0, min(1.0, t))
                    final_contact_point_on_A = ref_edge_v1_a + ref_edge_segment_vec * clamped_t
                
                # print(f"DEBUG_CONTACT_MANIFOLD:   Fallback: Deepest B vertex {deepest_vertex_b} projected to Ref Edge A as {final_contact_point_on_A}")
                # # print(f"DETAILED_LOG:   Fallback contact point: {final_contact_point_on_A}") # Removed
                # print(f"DEBUG_CONTACT_MANIFOLD: ======== End _find_contact_points_polygon_polygon (Fallback) ========")
                return [final_contact_point_on_A]
            # else:
                # print("DEBUG_CONTACT_MANIFOLD:   Fallback failed: no deepest vertex found on B. Using midpoint of reference edge A.")
                fallback_point = (ref_edge_v1_a + ref_edge_v2_a) * 0.5
                # # print(f"DETAILED_LOG:   Fallback (no deepest B vertex) contact point: {fallback_point}") # Removed
                return [fallback_point]

        clip_p1, clip_p2 = clipped_incident_segment # These are on incident body B
        
        # Helper to project a point onto a line segment and clamp it
        def project_and_clamp_to_segment(point_to_project: Vector2D, seg_v1: Vector2D, seg_v2: Vector2D) -> Vector2D:
            projected_on_line = self._project_point_onto_line(point_to_project, seg_v1, seg_v2)
            seg_vec = seg_v2 - seg_v1
            
            # Check if segment is a point
            seg_len_sq = seg_vec.magnitude_squared()
            if seg_len_sq < EPSILON * EPSILON:
                return seg_v1

            t = (projected_on_line - seg_v1).dot(seg_vec) / seg_len_sq
            clamped_t = max(0.0, min(1.0, t))
            return seg_v1 + seg_vec * clamped_t

        # Project both endpoints of the (potentially point-like) clipped incident segment
        # onto the reference edge A's segment (projection + clamping)
        final_proj_clip_p1_on_A = project_and_clamp_to_segment(clip_p1, ref_edge_v1_a, ref_edge_v2_a)
        final_proj_clip_p2_on_A = project_and_clamp_to_segment(clip_p2, ref_edge_v1_a, ref_edge_v2_a)
        
        # The final contact point is the midpoint of this segment on A's surface
        final_contact_point_on_A = (final_proj_clip_p1_on_A + final_proj_clip_p2_on_A) * 0.5
        
        # print(f"DEBUG_CONTACT_MANIFOLD:   Clipped incident segment on B: ({clip_p1} -> {clip_p2})")
        # print(f"DEBUG_CONTACT_MANIFOLD:   Clipped P1 on B projected-clamped to A: {final_proj_clip_p1_on_A}")
        # print(f"DEBUG_CONTACT_MANIFOLD:   Clipped P2 on B projected-clamped to A: {final_proj_clip_p2_on_A}")
        # print(f"DEBUG_CONTACT_MANIFOLD:   Final Contact Point (Midpoint on A's surface): {final_contact_point_on_A}")
        # # print(f"DETAILED_LOG:   Clipped incident segment (on B): p1={clip_p1}, p2={clip_p2}") # Removed
        # # print(f"DETAILED_LOG:   Projected clipped segment on A: p1_proj={final_proj_clip_p1_on_A}, p2_proj={final_proj_clip_p2_on_A}") # Removed
        # # print(f"DETAILED_LOG:   Final representative contact_point_world: {final_contact_point_on_A}") # Removed
        # print(f"DEBUG_CONTACT_MANIFOLD: ======== End _find_contact_points_polygon_polygon (Success) ========")
        return [final_contact_point_on_A]
    def _find_contact_points_polygon_circle(self,
                                            polygon_vertices: List[Vector2D],
                                            polygon_center: Vector2D, # For reference, might not be needed if vertices are world
                                            circle_center: Vector2D,
                                            circle_radius: float,
                                            normal: Vector2D, # Normal from Polygon to Circle
                                            penetration: float) -> List[Vector2D]:
        """
        Finds contact point(s) for a polygon-circle collision. (Placeholder)
        Normal points from the Polygon towards the Circle.
        Returns a list containing one contact point.
        """
        # Placeholder: Contact point on circle surface along the normal from polygon.
        # contact_on_circle = circle_center - normal * circle_radius
        # The corresponding point on the polygon's surface would be:
        # contact_on_polygon = contact_on_circle + normal * penetration
        # contact_on_polygon = circle_center - normal * (circle_radius - penetration)
        
        # More robust: Find the point on the polygon's perimeter closest to the circle's center.
        min_dist_sq_to_edge = float('inf')
        contact_point_on_polygon_edge = polygon_vertices[0] if polygon_vertices else circle_center # Fallback

        if not polygon_vertices: # Should not happen if polygon is valid
            # Fallback: if no polygon vertices, use a point on circle based on normal
            return [circle_center - normal * (circle_radius - penetration)]

        for i in range(len(polygon_vertices)):
            p1 = polygon_vertices[i]
            p2 = polygon_vertices[(i + 1) % len(polygon_vertices)]
            edge_vec = p2 - p1
            len_sq = edge_vec.magnitude_squared()

            if len_sq == 0: # Edge is a point
                # Distance from circle_center to p1
                closest_point_on_segment = p1
            else:
                # Project circle_center onto the line defined by p1 and edge_vec
                t = (circle_center - p1).dot(edge_vec) / len_sq
                t = max(0, min(1, t)) # Clamp t to be between 0 and 1 for segment
                closest_point_on_segment = p1 + edge_vec * t
            
            dist_sq = (circle_center - closest_point_on_segment).magnitude_squared()

            if dist_sq < min_dist_sq_to_edge:
                min_dist_sq_to_edge = dist_sq
                contact_point_on_polygon_edge = closest_point_on_segment
        
        # This contact_point_on_polygon_edge is the feature on the polygon (vertex or edge point)
        # that is closest to the circle's center. This is our contact point on the polygon.
        return [contact_point_on_polygon_edge]

    def _check_polygon_circle_collision(self,
                                        entity_polygon_id: 'EntityID',
                                        entity_circle_id: 'EntityID'
                                        ) -> Tuple[bool, Optional[List[ContactPointInfo]]]:
        """
        Checks for collision between a polygon and a circle using SAT.
        The normal in ContactPointInfo will point from the polygon to the circle.
        """
        polygon_transform = self.entity_manager.get_component(entity_polygon_id, TransformComponent)
        polygon_geometry = self.entity_manager.get_component(entity_polygon_id, GeometryComponent)
        circle_transform = self.entity_manager.get_component(entity_circle_id, TransformComponent)
        circle_geometry = self.entity_manager.get_component(entity_circle_id, GeometryComponent)

        if not polygon_transform or not polygon_geometry or \
           polygon_geometry.shape_type not in [ShapeType.POLYGON, ShapeType.RECTANGLE] or \
           not circle_transform or not circle_geometry or circle_geometry.shape_type != ShapeType.CIRCLE:
            # # print(f"DEBUG PC: Invalid shapes. Poly: {polygon_geometry.shape_type if polygon_geometry else 'N/A'}, Circle: {circle_geometry.shape_type if circle_geometry else 'N/A'}")
            return False, None

        polygon_vertices = self._get_rotated_vertices(entity_polygon_id)
        if not polygon_vertices:
            # # print(f"DEBUG PC: No polygon vertices for {entity_polygon_id}")
            return False, None

        circle_center = circle_transform.position
        circle_radius = circle_geometry.parameters.get("radius", 0)
        if circle_radius <= 0:
            # # print(f"DEBUG PC: Circle {entity_circle_id} has invalid radius {circle_radius}")
            return False, None


        min_penetration = float('inf')
        collision_normal_internal: Optional[Vector2D] = None

        # 1. Axes from polygon edges
        polygon_axes = self._get_axes(polygon_vertices)
        all_axes = list(polygon_axes)

        # 2. Axis from circle center to closest polygon vertex
        closest_vertex_to_circle: Optional[Vector2D] = None
        min_dist_sq_vertex_circle = float('inf')

        if not polygon_vertices: # Should be caught earlier, but as a safeguard
             return False, None

        for vertex in polygon_vertices:
            dist_sq = (vertex - circle_center).magnitude_squared()
            if dist_sq < min_dist_sq_vertex_circle:
                min_dist_sq_vertex_circle = dist_sq
                closest_vertex_to_circle = vertex
        
        if closest_vertex_to_circle: # Should always be true if polygon_vertices is not empty
            axis_from_circle_to_vertex = closest_vertex_to_circle - circle_center
            if axis_from_circle_to_vertex.magnitude_squared() > EPSILON * EPSILON:
                 all_axes.append(axis_from_circle_to_vertex.normalize())
            # else: circle center is on a vertex. Polygon axes should handle this.

        if not all_axes:
            # # print(f"DEBUG PC: No axes generated for polygon {entity_polygon_id} and circle {entity_circle_id}")
            return False, None

        for axis in all_axes:
            if axis.magnitude_squared() < EPSILON * EPSILON:
                continue

            # Project polygon
            min_poly, max_poly = self._project_shape_onto_axis(polygon_vertices, axis)
            
            # Project circle
            center_proj_circle = circle_center.dot(axis)
            min_circle = center_proj_circle - circle_radius
            max_circle = center_proj_circle + circle_radius

            # Check for separation
            if max_poly < min_circle - EPSILON or max_circle < min_poly - EPSILON:
                return False, None # Separating axis found

            overlap_val = min(max_poly, max_circle) - max(min_poly, min_circle)

            if overlap_val < min_penetration:
                min_penetration = overlap_val
                collision_normal_internal = axis
                
                # Ensure normal points from polygon to circle
                # Vector from polygon center (approx) to circle center
                # For polygon, using its transform.position as its center.
                vec_poly_to_circle = circle_center - polygon_transform.position 
                if vec_poly_to_circle.dot(collision_normal_internal) < 0:
                    collision_normal_internal = -collision_normal_internal
        
        if collision_normal_internal is None or min_penetration == float('inf') or min_penetration < -EPSILON: # Allow very small negative due to float errors before correction
            # # print(f"DEBUG PC: Collision check failed. Normal: {collision_normal_internal}, Penetration: {min_penetration}")
            return False, None
        
        if abs(collision_normal_internal.magnitude_squared() - 1.0) > EPSILON: # Ensure normalization
            collision_normal_internal = collision_normal_internal.normalize()
        
        min_penetration = max(0, min_penetration) # Ensure penetration is not negative

        contact_point_vectors = self._find_contact_points_polygon_circle(
            polygon_vertices, polygon_transform.position, circle_center, circle_radius,
            collision_normal_internal, min_penetration
        )

        if not contact_point_vectors:
            # # print(f"DEBUG PC: No contact points found for {entity_polygon_id} and {entity_circle_id}")
            return False, None

        contact_manifold: List[ContactPointInfo] = []
        for cp_vec in contact_point_vectors:
            contact_manifold.append({
                "point": cp_vec, # This point is on the polygon surface
                "normal": collision_normal_internal, # Normal from polygon to circle
                "penetration_depth": min_penetration
            })
        
        # # print(f"DEBUG: Polygon-Circle Collision DETECTED between poly {entity_polygon_id} and circle {entity_circle_id}. Normal: {collision_normal_internal}, Depth: {min_penetration}, Points: {len(contact_point_vectors)}")
        return True, contact_manifold

    def _find_contact_points_rect_rect(self,
                                      vertices_a: List[Vector2D], # Vertices of rectangle A (reference)
                                      vertices_b: List[Vector2D], # Vertices of rectangle B (incident)
                                      normal: Vector2D,      # Collision normal, from B to A
                                      penetration: float) -> List[Vector2D]:
        """
        Finds contact points for a rectangle-rectangle collision.
        A is treated as the reference polygon, B as the incident polygon.
        The normal points from B to A.
        Implements logic to distinguish between edge-edge and vertex-edge contacts.
        """

        def get_edges_with_normals(vertices: List[Vector2D]) -> List[Tuple[Vector2D, Vector2D, Vector2D, Vector2D]]:
            # Returns list of (p1, p2, edge_vector, outward_normal)
            # Assumes vertices are ordered (e.g., counter-clockwise for Y-down coordinate system)
            # such that edge.perpendicular().normalize() points outward.
            # The current _get_rotated_vertices produces: TL, TR, BR, BL.
            # For Y-down, this is CCW. Example: Top edge from TL to TR (e.g. (-1,-1) to (1,-1)) is (2,0).
            # (2,0).perpendicular() = (0,2). Normalized (0,1). This points DOWN (inward for top edge if Y is down).
            # So, we need to adjust the normal calculation or vertex order assumption.
            # Let's assume vertices_a and vertices_b are ordered CCW (Y-down).
            # Edge p1->p2. Outward normal is (p2.y - p1.y, p1.x - p2.x).normalize()
            edges = []
            num_vertices = len(vertices)
            if num_vertices < 2:
                return []
            for i in range(num_vertices):
                p1 = vertices[i]
                p2 = vertices[(i + 1) % num_vertices]
                edge_vector = p2 - p1
                # For CCW vertices (Y-down): (dx, dy) -> outward normal (dy, -dx)
                outward_normal = Vector2D(edge_vector.y, -edge_vector.x).normalize()
                edges.append((p1, p2, edge_vector, outward_normal))
            return edges

        edges_a = get_edges_with_normals(vertices_a)
        edges_b = get_edges_with_normals(vertices_b)

        # 1. Find reference edge on A: edge whose outward normal is most anti-parallel to `normal` (from B to A).
        #    So, edge_normal_a.dot(normal) is minimized (closest to -1).
        min_dot_ref = float('inf')
        ref_edge_info_a = None # (v1, v2, edge_vec, edge_normal_a)
        for edge_a_tuple in edges_a: # Renamed to avoid conflict with outer scope 'edge_a' if any
            dot_val = edge_a_tuple[3].dot(normal)
            if dot_val < min_dot_ref:
                min_dot_ref = dot_val
                ref_edge_info_a = edge_a_tuple
        
        if not ref_edge_info_a: return [(vertices_a[0] + vertices_a[1] + vertices_a[2] + vertices_a[3]) * 0.25]

        # 2. Find incident edge or vertex on B.
        #    Incident edge: outward normal most parallel to `normal`.
        #    Incident vertex: vertex furthest along `normal`.

        # Check for Edge-Edge contact first
        # An edge-edge contact occurs if the collision normal is nearly parallel to the face normals
        # of both rectangles (one parallel, one anti-parallel).
        # ref_edge_info_a[3] is outward normal of A's ref edge. normal is B->A.
        # So, ref_edge_info_a[3] should be anti-parallel to normal. ref_edge_info_a[3].dot(normal) ~ -1.
        
        # Find incident edge on B (edge whose normal is most aligned with collision normal)
        max_dot_inc_edge = -float('inf')
        inc_edge_info_b = None
        for edge_b_tuple in edges_b:
            dot_val = edge_b_tuple[3].dot(normal) # edge_b_tuple[3] is outward normal of B's edge
            if dot_val > max_dot_inc_edge:
                max_dot_inc_edge = dot_val
                inc_edge_info_b = edge_b_tuple

        # Alignment threshold (cosine of angle). e.g. for angles up to ~10-15 degrees.
        # cos(15 deg) ~ 0.965. cos(10 deg) ~ 0.984
        alignment_dot_product_threshold = 0.98

        is_edge_edge = False
        if inc_edge_info_b and \
           min_dot_ref < (-alignment_dot_product_threshold + EPSILON) and \
           max_dot_inc_edge > (alignment_dot_product_threshold - EPSILON):
            is_edge_edge = True

        contact_points_on_a = []

        if is_edge_edge:
            # Edge-Edge Contact: "计算两个矩形在接触法线方向上的重叠区域...取这条线段的中点"
            # This implies finding the overlapping segment of the two edges when projected onto
            # an axis perpendicular to the collision normal, and then finding its midpoint.
            # Then project this midpoint back onto A's surface.

            # Simpler interpretation for "取这条线段的中点":
            # Use the midpoint of the *incident edge* of B, and then project it onto A's surface.
            inc_v1_b, inc_v2_b = inc_edge_info_b[0], inc_edge_info_b[1]
            mid_point_incident_edge_b = (inc_v1_b + inc_v2_b) * 0.5
            
            # The contact point on A's surface is this midpoint pushed back along the normal
            # by the penetration depth.
            contact_point = mid_point_incident_edge_b - normal * penetration
            contact_points_on_a.append(contact_point)
            
            # For a more robust two-point contact manifold in edge-edge:
            # Clip incident edge of B against reference edge of A.
            # For now, single midpoint as requested.

        else:
            # Vertex-Edge Contact (or Vertex-Vertex as a special case)
            # Find incident vertex on B: vertex of B furthest along `normal`.
            incident_vertex_b = None
            max_proj_val_b = -float('inf')
            for v_b in vertices_b:
                proj = v_b.dot(normal) # Project v_b onto collision normal
                if proj > max_proj_val_b:
                    max_proj_val_b = proj
                    incident_vertex_b = v_b
            
            if not incident_vertex_b: # Should not happen
                 return [(vertices_a[0] + vertices_a[1] + vertices_a[2] + vertices_a[3]) * 0.25] # Fallback

            # The reference edge on A is (ref_edge_info_a[0], ref_edge_info_a[1])
            ref_v1_a, ref_v2_a = ref_edge_info_a[0], ref_edge_info_a[1]
            ref_edge_vec_a = ref_v2_a - ref_v1_a

            # Project incident_vertex_b onto the line of the reference edge of A.
            # The contact point on A is this projection, clamped to the segment.
            if ref_edge_vec_a.magnitude_squared() < EPSILON * EPSILON: # Reference edge is a point
                # Effectively vertex-vertex: incident_vertex_b vs ref_v1_a
                # Contact point on A is ref_v1_a.
                # Or, more consistently with penetration: incident_vertex_b - normal * penetration
                contact_points_on_a.append(incident_vertex_b - normal * penetration)
            else:
                # t = dot(incident_vertex_b - ref_v1_a, ref_edge_vec_a) / ||ref_edge_vec_a||^2
                t_numerator = (incident_vertex_b - ref_v1_a).dot(ref_edge_vec_a)
                t_denominator = ref_edge_vec_a.magnitude_squared()
                t = t_numerator / t_denominator
                
                clamped_t = max(0.0, min(1.0, t)) # Clamp to segment [0,1]
                
                projected_point_on_ref_segment_a = ref_v1_a + ref_edge_vec_a * clamped_t
                contact_points_on_a.append(projected_point_on_ref_segment_a)
        
        if not contact_points_on_a: # Should be populated by now
            # Fallback to the old primary candidate logic if somehow empty
            max_proj_b_fallback = -float('inf')
            incident_vertex_b_fallback = None
            for v_b_fb in vertices_b:
                proj_fb = v_b_fb.dot(normal)
                if proj_fb > max_proj_b_fallback:
                    max_proj_b_fallback = proj_fb
                    incident_vertex_b_fallback = v_b_fb
            if incident_vertex_b_fallback:
                contact_points_on_a.append(incident_vertex_b_fallback - normal * penetration)
            else: # Ultimate fallback
                contact_points_on_a.append((vertices_a[0] + vertices_a[1] + vertices_a[2] + vertices_a[3]) * 0.25)

        return contact_points_on_a


    def _find_contact_points_rect_circle(self,
                                         rect_vertices: List[Vector2D],
                                         rect_center: Vector2D, # Added for easier reference
                                         circle_center: Vector2D,
                                         circle_radius: float,
                                         normal: Vector2D, # Normal from Rectangle to Circle
                                         penetration: float) -> List[Vector2D]:
        """
        Finds contact point(s) for a rectangle-circle collision.
        Normal points from the rectangle towards the circle.
        Returns a list containing one contact point.
        """
        # The contact point on the circle is: circle_center - normal * circle_radius
        # The contact point on the rectangle is: circle_center - normal * (circle_radius - penetration)
        # Or, equivalently, it's the point on the rectangle closest to the circle's center.

        # Find the closest point on the rectangle's perimeter to the circle's center.
        closest_point_on_rect = circle_center # Start with circle center
        
        # Clamp circle_center to the AABB of the rectangle (if it were axis-aligned)
        # This is more complex for a rotated rectangle.
        # We need to find the closest point on the OBB (Oriented Bounding Box).

        # Method 1: Using the normal (from rect to circle)
        # The point on the circle's surface in the direction of contact is:
        # contact_on_circle_surface = circle_center - normal * circle_radius
        # The point on the rectangle's surface is:
        # contact_on_rect_surface = circle_center - normal * (circle_radius - penetration)
        # This point `contact_on_rect_surface` is where the circle *would* touch the rectangle
        # if it just grazed it.
        # Since there's penetration, the circle center has moved `penetration` deeper.
        
        # The actual contact point for impulse calculation is often taken on one of the surfaces.
        # Let's take the point on the rectangle's surface.
        
        # A robust way: find the point on the perimeter of the rectangle closest to the circle center.
        min_dist_sq_to_edge = float('inf')
        contact_point_on_rect_edge = rect_vertices[0] # Initialize

        for i in range(len(rect_vertices)):
            p1 = rect_vertices[i]
            p2 = rect_vertices[(i + 1) % len(rect_vertices)]
            edge_vec = p2 - p1
            len_sq = edge_vec.magnitude_squared()

            if len_sq == 0: # Should not happen for a valid rect
                # Closest point to p1
                t = 0
            else:
                # Project circle_center onto the line defined by p1 and edge_vec
                # t = dot(circle_center - p1, edge_vec) / len_sq
                t = (circle_center - p1).dot(edge_vec) / len_sq
                t = max(0, min(1, t)) # Clamp t to be between 0 and 1 for segment

            closest_point_on_segment = p1 + edge_vec * t
            dist_sq = (circle_center - closest_point_on_segment).magnitude_squared()

            if dist_sq < min_dist_sq_to_edge:
                min_dist_sq_to_edge = dist_sq
                contact_point_on_rect_edge = closest_point_on_segment
        
        # This `contact_point_on_rect_edge` is the feature on the rectangle that is closest.
        # This should be the contact point.
        # The normal (from rect to circle) should pass through `circle_center` and `contact_point_on_rect_edge`
        # if the collision is with an edge, or point from `contact_point_on_rect_edge` (a vertex) to `circle_center`.

        # The SAT normal might be one of the rect's face normals or from circle center to a rect vertex.
        # If normal is a face normal of the rectangle:
        #   contact_point = circle_center - normal * circle_radius (this is on circle)
        #   To get it on the rectangle: project circle_center onto the face line, then adjust.
        #   Or, use `contact_on_rect_surface` as calculated above.
        
        # If normal is from rect vertex to circle center:
        #   The rect vertex IS the contact point on the rectangle.

        # The `contact_point_on_rect_edge` found by finding the closest point on perimeter to circle center
        # seems like the most reliable single contact point on the rectangle.
        
        # Let's verify the normal direction: normal is from Rectangle to Circle.
        # So, `circle_center - normal * circle_radius` is a point on the circle surface.
        # The point on the rectangle surface that this point on the circle is touching is
        # `(circle_center - normal * circle_radius) + normal * penetration`
        #  `= circle_center - normal * (circle_radius - penetration)`
        # This seems correct and consistent with SAT.
        
        # Let's use the calculated `contact_point_on_rect_edge`. This is the point on the rectangle.
        return [contact_point_on_rect_edge]


    def _check_rectangle_circle_collision_sat(self,
                                           rect_entity_id: 'EntityID',
                                           circle_entity_id: 'EntityID'
                                           ) -> Tuple[bool, Optional[List[ContactPointInfo]]]:
        """
        Checks for collision between a (potentially rotated) rectangle and a circle using SAT.
        Returns (is_colliding, contact_manifold).
        Each contact point in the manifold contains point, normal (from rect to circle), and penetration_depth.
        """
        rect_transform = self.entity_manager.get_component(rect_entity_id, TransformComponent)
        rect_geometry = self.entity_manager.get_component(rect_entity_id, GeometryComponent)
        circle_transform = self.entity_manager.get_component(circle_entity_id, TransformComponent)
        circle_geometry = self.entity_manager.get_component(circle_entity_id, GeometryComponent)

        if not rect_transform or not rect_geometry or rect_geometry.shape_type != ShapeType.RECTANGLE or \
           not circle_transform or not circle_geometry or circle_geometry.shape_type != ShapeType.CIRCLE:
            return False, None

        rect_vertices = self._get_rotated_vertices(rect_entity_id)
        if not rect_vertices:
            return False, None

        circle_center = circle_transform.position
        circle_radius = circle_geometry.parameters.get("radius", 0)

        min_penetration = float('inf')
        collision_normal_internal: Optional[Vector2D] = None # Renamed

        rect_axes = self._get_axes(rect_vertices)
        all_axes = list(rect_axes) # Start with rectangle's axes

        # Add axis from circle center to closest rectangle vertex
        closest_vertex_to_circle: Optional[Vector2D] = None
        min_dist_sq = float('inf')
        for vertex in rect_vertices:
            dist_sq = (vertex - circle_center).magnitude_squared()
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_vertex_to_circle = vertex
        
        if closest_vertex_to_circle: # Should always be true if rect_vertices is not empty
            axis_from_circle_to_vertex = closest_vertex_to_circle - circle_center
            if axis_from_circle_to_vertex.magnitude_squared() > EPSILON * EPSILON: # Avoid normalizing zero vector
                 all_axes.append(axis_from_circle_to_vertex.normalize())
            # If circle center is exactly on a vertex, this axis might be zero.
            # The rect_axes should handle this separation if it's a separating axis.

        if not all_axes: # Should not happen if rect_vertices is valid
            return False, None

        for axis in all_axes:
            # Ensure axis is valid (e.g. not a zero vector if one slipped through)
            if axis.magnitude_squared() < EPSILON * EPSILON:
                continue

            # Project rectangle onto axis
            min_rect, max_rect = self._project_shape_onto_axis(rect_vertices, axis)
            
            # Project circle onto axis
            center_proj_circle = circle_center.dot(axis)
            min_circle = center_proj_circle - circle_radius
            max_circle = center_proj_circle + circle_radius

            # Check for separation
            if max_rect < min_circle or max_circle < min_rect:
                return False, None # Separating axis found

            # Calculate overlap
            overlap_val = min(max_rect, max_circle) - max(min_rect, min_circle)

            if overlap_val < min_penetration:
                min_penetration = overlap_val
                collision_normal_internal = axis
                
                # Ensure the normal points from the rectangle towards the circle.
                # The SAT axis can point in either direction.
                # We define the normal from rect to circle.
                # If (circle_center - rect_center) dot normal < 0, flip normal.
                vec_rect_to_circle = circle_center - rect_transform.position
                if vec_rect_to_circle.dot(collision_normal_internal) < 0:
                    collision_normal_internal = -collision_normal_internal
        
        if collision_normal_internal is None or min_penetration == float('inf'):
             return False, None # No collision detected or error

        # collision_normal_internal should be normalized.

        # Find contact points (as Vector2D)
        # _find_contact_points_rect_circle expects normal from rect to circle.
        contact_point_vectors = self._find_contact_points_rect_circle(
            rect_vertices, rect_transform.position, circle_center, circle_radius,
            collision_normal_internal, min_penetration
        )

        if not contact_point_vectors: # Should not happen
            return False, None

        # Construct the contact manifold
        contact_manifold: List[ContactPointInfo] = []
        for cp_vec in contact_point_vectors:
            contact_manifold.append({
                "point": cp_vec,
                "normal": collision_normal_internal, # Normal from rect to circle
                "penetration_depth": min_penetration
            })
        
        return True, contact_manifold
    def _handle_collision_response(self,
                                 eid_a: 'EntityID', eid_b: 'EntityID',
                                 trans_a: TransformComponent, trans_b: TransformComponent,
                                 phys_a: PhysicsBodyComponent, phys_b: PhysicsBodyComponent,
                                 contact_info: ContactPointInfo,
                                 dt: float) -> None:
        """
        Handles the physics response (impulse, positional correction, friction, support)
        for a collision between two entities.
        Assumes contact_info.normal points from B to A.
        """
        # # print(f"DEBUG_HCR: _handle_collision_response for A: {eid_a}, B: {eid_b}") # DEBUG LOG
        # # print(f"DEBUG_HCR:   trans_a.position: {trans_a.position}, trans_b.position: {trans_b.position}") # DEBUG LOG - ADDED
        contact_point_world = contact_info["point"]
        collision_normal_b_to_a = contact_info["normal"] # Expected: From B to A
        penetration = contact_info["penetration_depth"]
        # print(f"LOG_HCR_ENTRY: Entities A={eid_a}, B={eid_b}. CPWorld={contact_point_world}, Normal(B->A)={collision_normal_b_to_a}, Pen={penetration:.4f}")
        # # print(f"DEBUG_HCR:   r_a: {r_a}, r_b: {r_b}") # DEBUG LOG - Commented out

        # This check should ideally be done before calling, but as a safeguard:
        if phys_a.is_fixed and phys_b.is_fixed:
            return
        
        # --- Impulse Response ---
        center_a = trans_a.position
        center_b = trans_b.position
        r_a = contact_point_world - center_a
        r_b = contact_point_world - center_b
        # # print(f"DEBUG_HCR:   r_a: {r_a}, r_b: {r_b}") # DEBUG LOG # Already commented above, ensuring it's off
        v_linear_a = phys_a.velocity
        v_linear_b = phys_b.velocity
        angular_velocity_a = getattr(phys_a, 'angular_velocity', 0.0)
        angular_velocity_b = getattr(phys_b, 'angular_velocity', 0.0)

        # Velocity of contact point on A and B
        velocity_a_contact = v_linear_a + Vector2D(-angular_velocity_a * r_a.y, angular_velocity_a * r_a.x)
        velocity_b_contact = v_linear_b + Vector2D(-angular_velocity_b * r_b.y, angular_velocity_b * r_b.x)
        
        # Relative velocity of contact points. Normal is B to A.
        # We want v_contact_a - v_contact_b projected onto normal_b_to_a
        relative_velocity_contact = velocity_a_contact - velocity_b_contact
        relative_velocity_normal = relative_velocity_contact.dot(collision_normal_b_to_a)

        # Only apply impulse if objects are approaching (relative_velocity_normal < 0)
        # or if they are interpenetrating and need separation impulse
        if relative_velocity_normal < -EPSILON or penetration > EPSILON:
            restitution = min(phys_a.restitution, phys_b.restitution)
            
            inv_mass_a = 1.0 / phys_a.mass if phys_a.mass > 0 and not phys_a.is_fixed else 0.0
            inv_mass_b = 1.0 / phys_b.mass if phys_b.mass > 0 and not phys_b.is_fixed else 0.0

            moment_of_inertia_a = getattr(phys_a, 'moment_of_inertia', float('inf'))
            moment_of_inertia_b = getattr(phys_b, 'moment_of_inertia', float('inf'))

            inv_inertia_a = 1.0 / moment_of_inertia_a if moment_of_inertia_a > 0 and moment_of_inertia_a != float('inf') and not phys_a.is_fixed else 0.0
            inv_inertia_b = 1.0 / moment_of_inertia_b if moment_of_inertia_b > 0 and moment_of_inertia_b != float('inf') and not phys_b.is_fixed else 0.0
            
            # Term for angular impulse calculation: (r x n)^2 / I
            # Ensure r_a and r_b are non-zero for cross product calculations if objects are not points
            term_a_ang = (r_a.cross(collision_normal_b_to_a)**2) * inv_inertia_a if inv_inertia_a > 0 else 0.0
            term_b_ang = (r_b.cross(collision_normal_b_to_a)**2) * inv_inertia_b if inv_inertia_b > 0 else 0.0
            
            denominator = inv_mass_a + inv_mass_b + term_a_ang + term_b_ang

            j_scalar = 0.0
            if abs(denominator) > EPSILON:
                # Standard impulse formula. If relative_velocity_normal is negative (approaching), j_scalar is positive.
                j_scalar = -(1.0 + restitution) * relative_velocity_normal / denominator
            # # print(f"DEBUG_HCR:   j_linear: {j_scalar}") # DEBUG LOG - Commented out
            
            # Apply impulse if significant
            if abs(j_scalar) > EPSILON:
                # Impulse on A is along collision_normal_b_to_a (pushing A away from B along the normal from B to A)
                impulse_vector_on_a = collision_normal_b_to_a * j_scalar

                if not phys_a.is_fixed:
                    delta_linear_velocity_a_val = impulse_vector_on_a * inv_mass_a
                    delta_angular_velocity_a_val = 0.0
                    if inv_inertia_a > 0:
                        delta_angular_velocity_a_val = r_a.cross(impulse_vector_on_a) * inv_inertia_a
                    # # print(f"DEBUG_HCR:   To A: dLinVel={delta_linear_velocity_a_val}, dAngVel={delta_angular_velocity_a_val}") # DEBUG LOG - Commented out
                    phys_a.velocity += delta_linear_velocity_a_val
                    if inv_inertia_a > 0:
                        setattr(phys_a, 'angular_velocity', angular_velocity_a + delta_angular_velocity_a_val)
                
                if not phys_b.is_fixed:
                    # Impulse on B is opposite to impulse on A
                    delta_linear_velocity_b_val = -impulse_vector_on_a * inv_mass_b
                    delta_angular_velocity_b_val = 0.0
                    if inv_inertia_b > 0:
                         # Impulse on B is -impulse_vector_on_a. Angular impulse on B is r_b x (-impulse_vector_on_a) * inv_inertia_b
                        delta_angular_velocity_b_val = -r_b.cross(impulse_vector_on_a) * inv_inertia_b
                    # # print(f"DEBUG_HCR:   To B: dLinVel={delta_linear_velocity_b_val}, dAngVel={delta_angular_velocity_b_val}") # DEBUG LOG - Commented out
                    phys_b.velocity += delta_linear_velocity_b_val
                    if inv_inertia_b > 0:
                        setattr(phys_b, 'angular_velocity', angular_velocity_b + delta_angular_velocity_b_val)

        # --- Positional Correction ---
        if penetration > EPSILON:
            inv_mass_a_pc = 1.0 / phys_a.mass if phys_a.mass > 0 and not phys_a.is_fixed else 0.0
            inv_mass_b_pc = 1.0 / phys_b.mass if phys_b.mass > 0 and not phys_b.is_fixed else 0.0
            total_inv_mass_for_pc = inv_mass_a_pc + inv_mass_b_pc

            if total_inv_mass_for_pc > EPSILON:
                correction_factor = 0.3 # Reduced from 0.6 to observe effect on flickering
                # # print(f"DETAILED_LOG: Positional Correction: Using correction_factor = {correction_factor}")
                # collision_normal_b_to_a points from B to A.
                # A moves along collision_normal_b_to_a to separate.
                # B moves along -collision_normal_b_to_a to separate.
                
                correction_magnitude_per_inv_mass = (penetration / total_inv_mass_for_pc) * correction_factor
                
                correction_delta_a = collision_normal_b_to_a * (correction_magnitude_per_inv_mass * inv_mass_a_pc)
                correction_delta_b = -collision_normal_b_to_a * (correction_magnitude_per_inv_mass * inv_mass_b_pc)

                if not phys_a.is_fixed:
                    trans_a.position += correction_delta_a
                if not phys_b.is_fixed:
                    trans_b.position += correction_delta_b
        
        # --- Support Force and Friction ---
        # Normal for support force points from surface to object.
        # collision_normal_b_to_a points from B to A.

        # Case 1: B is a potential surface for A.
        # Support normal for A is collision_normal_b_to_a (points from B to A).
        # This case covers: B is fixed, or B has SurfaceComponent, or B is simply below A (dynamic-dynamic stacking).
        if not phys_a.is_fixed: # Object A must be dynamic to receive support
            can_B_support_A = phys_b.is_fixed or \
                              self.entity_manager.has_component(eid_b, SurfaceComponent) or \
                              (not phys_b.is_fixed and collision_normal_b_to_a.dot(Vector2D(0,1)) > 0.707) # B is generally below A, so normal B->A (support normal for A) points UP. (Assuming Y-up world)

            if can_B_support_A:
                vel_a_current = phys_a.velocity
                vel_b_current = phys_b.velocity
                rel_vel_normal_current = (vel_a_current - vel_b_current).dot(collision_normal_b_to_a)
                # # print(f"DEBUG_HCR: Support Check A on B (B is surface-like): rel_vel_normal_current={rel_vel_normal_current}, penetration={penetration}")
                
                # Support condition: objects are penetrating or touching.
                # The ForceCalculator will determine if a support force is actually needed based on net forces.
                support_condition_met_A_on_B = penetration >= -EPSILON # Allow for minor floating point inaccuracies
                # print(f"LOG_HCR_SUPPORT_CHECK: A_on_B: Pen={penetration:.4f}, RelVelNorm={rel_vel_normal_current:.4f}, ConditionMet={support_condition_met_A_on_B}")

                if support_condition_met_A_on_B:
                    # # print(f"DEBUG_HCR: Support Condition Met for A on B.")
                    offset_world_a = contact_point_world - trans_a.position
                    contact_point_local_a = offset_world_a.rotate(-trans_a.angle)
                    # angle_deg_a = math.degrees(trans_a.angle)
                    # # print(f"DETAILED_LOG: HCR_A_on_B: CP_world={contact_point_world}, trans_a_pos={trans_a.position}, trans_a_angle_rad={trans_a.angle:.4f}, trans_a_angle_deg={angle_deg_a:.2f}, offset_world_a={offset_world_a}, contact_point_local_a={contact_point_local_a}")
                    # print(f"DEBUG_FC_CALL: Calling ForceCalculator for support: A={eid_a} (receiver) on B={eid_b} (surface-like)") # LOG
                    applied_support = self.force_calculator.calculate_and_apply_support_force(
                        eid_a, eid_b, collision_normal_b_to_a, contact_point_local_a, self.entity_manager
                    )
                    # # print(f"DEBUG_HCR: Support for A on B - applied_support_magnitude: {applied_support}")
                    if applied_support is not None and applied_support > 0:
                        # # print(f"DEBUG_HCR: Calling Friction for A on B with support: {applied_support}")
                        # print(f"DEBUG_FC_CALL: Calling ForceCalculator for friction: A={eid_a} (receiver) on B={eid_b} (surface-like)") # LOG
                        self.force_calculator.calculate_and_apply_friction_force(
                            eid_a, eid_b, collision_normal_b_to_a, applied_support, contact_point_local_a, self.entity_manager, dt
                        )
        
        # Case 2: A is a potential surface for B.
        # Support normal for B is -collision_normal_b_to_a (points from A to B).
        # This case covers: A is fixed, or A has SurfaceComponent, or A is simply below B (dynamic-dynamic stacking).
        if not phys_b.is_fixed: # Object B must be dynamic to receive support
            can_A_support_B = phys_a.is_fixed or \
                              self.entity_manager.has_component(eid_a, SurfaceComponent) or \
                              (not phys_a.is_fixed and (-collision_normal_b_to_a).dot(Vector2D(0,1)) > 0.707) # A is generally below B, so normal A->B (support normal for B) points UP. (Assuming Y-up world)
           
            if can_A_support_B:
                # normal_a_to_b is the normal FROM surface A TO object B.
                # collision_normal_b_to_a is B->A.
                # If B is on top of A, SAT's B->A normal points UPWARDS (e.g., (0, -1) if Y is down positive, or (0,1) if Y is up positive).
                # The support force on B from A should also be UPWARDS (opposite to gravity on B).
                # ForceCalculator expects normal FROM SURFACE (A) TO ENTITY_ON_SURFACE (B).
                # collision_normal_b_to_a is B->A.
                # So, normal_a_to_b must be -collision_normal_b_to_a.
                normal_a_to_b = -collision_normal_b_to_a
                # # print(f"DEBUG_HCR_NORMAL_FIX: For A supporting B: collision_normal_b_to_a (B->A) = {collision_normal_b_to_a}, Corrected normal_a_to_b (A->B, for FC) set to {normal_a_to_b}")
                vel_a_current = phys_a.velocity
                vel_b_current = phys_b.velocity
                rel_vel_normal_current = (vel_b_current - vel_a_current).dot(normal_a_to_b)
                # # print(f"DEBUG_HCR: Support Check B on A (A is surface-like): rel_vel_normal_current={rel_vel_normal_current}, penetration={penetration}")

                # Support condition: objects are penetrating or touching.
                # The ForceCalculator will determine if a support force is actually needed based on net forces.
                support_condition_met_B_on_A = penetration >= -EPSILON # Allow for minor floating point inaccuracies
                # print(f"LOG_HCR_SUPPORT_CHECK: B_on_A: Pen={penetration:.4f}, RelVelNorm={rel_vel_normal_current:.4f}, ConditionMet={support_condition_met_B_on_A}")
                
                if support_condition_met_B_on_A:
                    # # print(f"DEBUG_HCR: Support Condition Met for B on A.")
                    offset_world_b = contact_point_world - trans_b.position
                    contact_point_local_b = offset_world_b.rotate(-trans_b.angle)
                    # angle_deg_b = math.degrees(trans_b.angle)
                    # # print(f"DETAILED_LOG: HCR_B_on_A: CP_world={contact_point_world}, trans_b_pos={trans_b.position}, trans_b_angle_rad={trans_b.angle:.4f}, trans_b_angle_deg={angle_deg_b:.2f}, offset_world_b={offset_world_b}, contact_point_local_b={contact_point_local_b}")
                    
                    # Calculate the normal for ForceCalculator directly from -collision_normal_b_to_a
                    # This ensures we are using the freshest, correctly negated value.
                    normal_for_fc_BonA = -collision_normal_b_to_a
                    # print(f"LOG_HCR_PRE_FC_BonA: eid_b={eid_b}, eid_a={eid_a}, CALC_normal_for_fc(A->B)={normal_for_fc_BonA}")

                    applied_support = self.force_calculator.calculate_and_apply_support_force(
                        eid_b, eid_a, normal_for_fc_BonA, contact_point_local_b, self.entity_manager
                    )
                    # # print(f"DEBUG_HCR: Support for B on A - applied_support_magnitude: {applied_support}")
                    if applied_support is not None and applied_support > 0:
                        # # print(f"DEBUG_HCR: Calling Friction for B on A with support: {applied_support}")
                        # Pass the same freshly calculated normal to friction calculation
                        # print(f"LOG_HCR_PRE_FC_FRICTION_BonA: eid_b={eid_b}, eid_a={eid_a}, CALC_normal_for_fc_friction(A->B)={normal_for_fc_BonA}")
                        self.force_calculator.calculate_and_apply_friction_force(
                            eid_b, eid_a, normal_for_fc_BonA, applied_support, contact_point_local_b, self.entity_manager, dt
                        )

    def update(self, dt: float) -> None:
        # Get all relevant entities
        entities_with_physics = self.entity_manager.get_entities_with_components(
            TransformComponent, GeometryComponent, PhysicsBodyComponent
        )

        # Convert to list for indexed access if needed, or prepare for pairwise iteration
        # For O(n^2) broadphase, iterate through all unique pairs
        # We only want to check non-fixed bodies against others for dynamic collision response later
        # But for now, let's check all pairs that have the required components.

        # To avoid duplicate checks (A-B vs B-A) and self-collision (A-A)
        # we can convert the set of entity IDs to a list.
        entity_ids: List[EntityID] = list(entities_with_physics) # Ensure EntityID is defined or imported

        potential_colliders: List[Tuple[EntityID, TransformComponent, GeometryComponent, PhysicsBodyComponent]] = []
        for eid in entity_ids:
            transform = self.entity_manager.get_component(eid, TransformComponent)
            geometry = self.entity_manager.get_component(eid, GeometryComponent)
            physics = self.entity_manager.get_component(eid, PhysicsBodyComponent)
            if transform and geometry and physics: # and not physics.is_fixed (optional for now)
                potential_colliders.append((eid, transform, geometry, physics))

        num_colliders = len(potential_colliders)
        for i in range(num_colliders):
            eid_a, trans_a, geom_a, phys_a = potential_colliders[i]

            for j in range(i + 1, num_colliders):
                eid_b, trans_b, geom_b, phys_b = potential_colliders[j]

                # Skip if collision is disabled for this pair
                if self.is_collision_disabled(eid_a, eid_b):
                    continue

                # Skip if both are fixed (or one is fixed, depending on desired interaction)
                # if phys_a.is_fixed and phys_b.is_fixed:
                # continue

                collided = False
                # Simple dispatch based on shape types
                type_a = geom_a.shape_type
                type_b = geom_b.shape_type

                collided_result: Optional[Tuple[bool, Optional[List[ContactPointInfo]]]] = None
                # The normal in ContactPointInfo should consistently be from object B to object A
                # for the generic response handler below.

                # Order entities for consistent normal direction if needed (e.g., polygon always first if mixed with circle)
                # For Polygon vs Circle, _check_polygon_circle_collision expects (polygon_id, circle_id)
                # and its normal is defined from Polygon to Circle.

                if (type_a == ShapeType.POLYGON or type_a == ShapeType.RECTANGLE) and \
                   (type_b == ShapeType.POLYGON or type_b == ShapeType.RECTANGLE):
                    # Handles Poly-Poly, Poly-Rect, Rect-Poly, Rect-Rect
                    # _check_polygon_polygon_collision_sat normal is from B to A.
                    collided_result = self._check_polygon_polygon_collision_sat(eid_a, eid_b)
                
                elif type_a == ShapeType.CIRCLE and type_b == ShapeType.CIRCLE:
                    # Specific handling for Circle-Circle to generate ContactPointInfo
                    if self._check_circle_circle_collision(trans_a, geom_a, trans_b, geom_b):
                        center_a = trans_a.position
                        center_b = trans_b.position
                        radius_a = geom_a.parameters.get("radius", 0)
                        radius_b = geom_b.parameters.get("radius", 0)
                        
                        # Normal from B to A for response consistency
                        n_b_to_a = center_a - center_b
                        dist_sq = n_b_to_a.magnitude_squared()
                        
                        if dist_sq < EPSILON * EPSILON :
                            n_b_to_a = Vector2D(0, -1) # Default if centers coincide
                            dist = 0.0
                        else:
                            dist = math.sqrt(dist_sq)
                            n_b_to_a = n_b_to_a / dist # Normalize
                        
                        penetration = (radius_a + radius_b) - dist
                        if penetration > -EPSILON: # Collision or touching
                            penetration = max(0, penetration)
                            # Contact point on A's surface, along the normal from B's center towards A's center
                            contact_pt_on_a = center_a - n_b_to_a * radius_a
                            
                            cc_contact_manifold: List[ContactPointInfo] = [{
                                "point": contact_pt_on_a, # Point on A
                                "normal": n_b_to_a,       # Normal from B to A
                                "penetration_depth": penetration
                            }]
                            collided_result = (True, cc_contact_manifold)
                        else:
                            collided_result = (False, None) # No collision
                    else:
                        collided_result = (False, None) # No collision

                elif type_a == ShapeType.CIRCLE and (type_b == ShapeType.POLYGON or type_b == ShapeType.RECTANGLE):
                    # A is Circle, B is Polygon/Rectangle.
                    # _check_polygon_circle_collision(poly_id, circle_id) normal is from Poly to Circle.
                    # Here, B is Poly, A is Circle. So call with (eid_b, eid_a).
                    # Normal will be from B(Poly) to A(Circle). This is the desired B->A.
                    collided_result = self._check_polygon_circle_collision(eid_b, eid_a)

                elif (type_a == ShapeType.POLYGON or type_a == ShapeType.RECTANGLE) and type_b == ShapeType.CIRCLE:
                    # A is Polygon/Rectangle, B is Circle.
                    # _check_polygon_circle_collision(poly_id, circle_id) normal is from Poly to Circle.
                    # Here, A is Poly, B is Circle. So call with (eid_a, eid_b).
                    # Normal will be from A(Poly) to B(Circle).
                    # We need to flip it for the generic handler (B->A).
                    temp_collided_result = self._check_polygon_circle_collision(eid_a, eid_b)
                    if temp_collided_result and temp_collided_result[0] and temp_collided_result[1]:
                        flipped_manifold: List[ContactPointInfo] = []
                        for info in temp_collided_result[1]:
                            flipped_manifold.append({
                                "point": info["point"], # Contact point is on polygon A's surface
                                "normal": -info["normal"], # Flip normal to be B(Circle) -> A(Poly)
                                "penetration_depth": info["penetration_depth"]
                            })
                        collided_result = (True, flipped_manifold)
                    else:
                        collided_result = temp_collided_result
                
                # --- Generic Collision Response Section ---
                if collided_result and collided_result[0] and collided_result[1]:
                    # print(f"DEBUG_COLLISION: Collision detected between {eid_a} and {eid_b}") # LOG
                    contact_manifold_to_use = collided_result[1]
                    
                    # DEBUG LOG START: Collision detected and contact info (REMOVED)
                    # print(f"[DEBUG CollisionSystem.update] Collision detected between {eid_a} ({type_a}) and {eid_b} ({type_b}).")
                    # if contact_manifold_to_use:
                    #     for c_info_idx, c_info in enumerate(contact_manifold_to_use):
                    #         print(f"  Contact {c_info_idx + 1}: Point={c_info['point']}, Normal(B->A)={c_info['normal']}, Depth={c_info['penetration_depth']:.4f}")
                    # DEBUG LOG END

                    if phys_a.is_fixed and phys_b.is_fixed:
                        continue # Skip response if both are fixed
                    
                    if not contact_manifold_to_use:
                        continue

                    # For now, we assume SAT methods provide one primary contact point.
                    # If multiple contact points were generated (e.g. for edge-edge),
                    # this loop would process them, but _handle_collision_response needs to be adapted
                    # or called per contact point, or average/select one.
                    # Current SAT contact finders for poly/rect return one point.
                    for contact_info in contact_manifold_to_use: # Typically one iteration for now
                        # print(f"LOG_CS_UPDATE: Calling _handle_collision_response for A={eid_a}, B={eid_b} with contact_info: Normal(B->A)={contact_info['normal']}, Pen={contact_info['penetration_depth']:.4f}") # Detailed log before HCR
                        self._handle_collision_response(
                            eid_a, eid_b,
                            trans_a, trans_b,
                            phys_a, phys_b,
                            contact_info, # Contains point, normal (B->A), penetration
                            dt
                        )
                        # If handling multiple contact points, might need to average impulses or apply sequentially.
                        # For now, break after the first contact point is processed for simplicity,
                        # matching previous behavior where only one contact was handled.
                        break
                # --- End of Generic Collision Response ---