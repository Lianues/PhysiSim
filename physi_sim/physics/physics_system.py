import math # Added for angle normalization
import uuid # Added to define uuid
from typing import TYPE_CHECKING, Dict, Tuple, List
from physi_sim.core.system import System
from physi_sim.core.vector import Vector2D
from physi_sim.core.utils import GRAVITY_ACCELERATION, EPSILON # Import the constant and EPSILON
from physi_sim.core.component import (
    TransformComponent, PhysicsBodyComponent, ForceAccumulatorComponent,
    GeometryComponent, ShapeType # Added GeometryComponent and ShapeType
)
# Import the new ConstraintSolverSystem
from physi_sim.physics.constraint_solver_system import ConstraintSolverSystem


if TYPE_CHECKING:
    from physi_sim.core.entity_manager import EntityManager

class PhysicsSystem(System):
    def __init__(self, entity_manager: 'EntityManager', gravity: Vector2D = GRAVITY_ACCELERATION):
        super().__init__(entity_manager)
        self.gravity = gravity
        self.gravity_enabled = True # Default to enabled
        # Initialize the ConstraintSolverSystem with new factor-based Baumgarte parameters
        # These factors are dimensionless. Effective alpha/beta will be calculated using dt in the solver.
        # Defaults based on common practice (e.g., Box2D's Baumgarte factor is around 0.2 for position)
        # Increasing these factors for potentially "stiffer" constraints as per user feedback.
        baumgarte_pos_factor = 0.8  # Increased from 0.2
        baumgarte_vel_factor = 1.0  # Increased from 0.8
                                    # ConstraintSolverSystem will calculate effective_alpha = pos_factor/dt
                                    # and effective_beta = vel_factor/dt.
        self.constraint_solver = ConstraintSolverSystem(
            entity_manager,
            baumgarte_pos_correction_factor=baumgarte_pos_factor,
            baumgarte_vel_correction_factor=baumgarte_vel_factor
        )
        print(f"PhysicsSystem: ConstraintSolver initialized with Baumgarte factors: pos_factor={baumgarte_pos_factor}, vel_factor={baumgarte_vel_factor}")


    def _collect_external_forces_and_ids(self) -> Tuple[List[uuid.UUID], Dict[uuid.UUID, Tuple[Vector2D, float]]]:
        """Helper to collect external forces and list of physics entity IDs."""
        entities_with_physics = self.entity_manager.get_entities_with_components(
            TransformComponent, PhysicsBodyComponent, ForceAccumulatorComponent
        )
        external_forces_torques_map: Dict[uuid.UUID, Tuple[Vector2D, float]] = {}
        all_entity_ids_with_physics_list: List[uuid.UUID] = []

        for entity_id in entities_with_physics:
            all_entity_ids_with_physics_list.append(entity_id)
            force_accumulator = self.entity_manager.get_component(entity_id, ForceAccumulatorComponent)
            if force_accumulator:
                external_forces_torques_map[entity_id] = (
                    force_accumulator.net_force,
                    force_accumulator.net_torque
                )
            else:
                external_forces_torques_map[entity_id] = (Vector2D(0, 0), 0.0)
        return all_entity_ids_with_physics_list, external_forces_torques_map

    def update_constraints_and_apply_forces(self, dt: float) -> None:
        """
        Solves constraints and applies the resulting constraint forces to ForceAccumulators.
        This step is intended to run BEFORE collision detection and response.
        """
        all_entity_ids_list, external_forces_map = self._collect_external_forces_and_ids()

        if not all_entity_ids_list:
            return

        # This call will now internally add constraint forces to ForceAccumulators
        # We ignore the returned accelerations here as we only care about the force application side effect.
        _ = self.constraint_solver.solve_constraints_and_get_accelerations(
            dt,
            all_entity_ids_list,
            external_forces_map
        )
        # print(f"DEBUG_PHYSYS_CONSTRAINTS_APPLIED: Constraint forces applied to accumulators.")

    def update_integrate_state(self, dt: float) -> None:
        """
        Performs the final physics integration step using all accumulated forces
        (external, constraint, contact).
        This step is intended to run AFTER collision detection and response.
        """
        all_entity_ids_list, external_forces_map_final = self._collect_external_forces_and_ids()
        
        if not all_entity_ids_list:
            return

        # Get final constrained accelerations based on ALL forces (external, constraint, contact)
        # For this call, we do NOT want to re-apply or re-record constraint forces,
        # as they should have been handled by update_constraints_and_apply_forces().
        # We only need the resulting accelerations for integration.
        constrained_accel_map_final = self.constraint_solver.solve_constraints_and_get_accelerations(
            dt,
            all_entity_ids_list,
            external_forces_map_final, # This map now contains all forces
            apply_and_record_constraint_forces=False # Pass False here
        )
        
        # Integrate physics state using these final accelerations
        for entity_id in all_entity_ids_list: # Iterate using the list that was used for map creation
            transform = self.entity_manager.get_component(entity_id, TransformComponent)
            physics_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)

            if not (transform and physics_body):
                print(f"Warning: Entity {entity_id} missing Transform or PhysicsBody during final integration. Skipping.")
                continue

            if physics_body.is_fixed:
                physics_body.velocity = Vector2D(0, 0)
                physics_body.angular_velocity = 0.0
                physics_body.previous_acceleration = Vector2D(0, 0)
                continue

            v_old_linear = physics_body.velocity
            a_old_linear = physics_body.previous_acceleration

            transform.position = transform.position + (v_old_linear * dt) + (a_old_linear * (0.5 * dt * dt))

            accel_data = constrained_accel_map_final.get(entity_id)
            if accel_data:
                a_new_linear, a_new_angular = accel_data
            else:
                # Fallback if entity somehow missed in final accel map (should not happen)
                print(f"Warning: Entity {entity_id} not found in final constrained_accel_map. Using its current net_force/M.")
                current_force_acc = self.entity_manager.get_component(entity_id, ForceAccumulatorComponent)
                if current_force_acc:
                     ext_force_final, ext_torque_final = current_force_acc.net_force, current_force_acc.net_torque
                else: # Should definitely not happen if it's in all_entity_ids_list
                     ext_force_final, ext_torque_final = Vector2D(0,0), 0.0

                a_new_linear = ext_force_final / physics_body.mass if physics_body.mass > EPSILON else Vector2D(0, 0)
                a_new_angular = ext_torque_final / physics_body.moment_of_inertia if physics_body.moment_of_inertia > EPSILON else 0.0


            physics_body.velocity = v_old_linear + (a_old_linear + a_new_linear) * (0.5 * dt)
            physics_body.previous_acceleration = a_new_linear

            if physics_body.moment_of_inertia > EPSILON:
                physics_body.angular_velocity += a_new_angular * dt
                transform.angle += physics_body.angular_velocity * dt
                transform.angle = (transform.angle + math.pi) % (2 * math.pi) - math.pi
            else:
                transform.angle += physics_body.angular_velocity * dt
                transform.angle = (transform.angle + math.pi) % (2 * math.pi) - math.pi

    def toggle_gravity(self, enabled: bool) -> None:
        """Enables or disables gravity for the system."""
        self.gravity_enabled = enabled

    def update(self, dt: float) -> None: # Original update method
        # Get all entities that have physics properties
        entities_with_physics = self.entity_manager.get_entities_with_components(
            TransformComponent, PhysicsBodyComponent, ForceAccumulatorComponent
        )

        if not entities_with_physics:
            return

        # 1. Collect external forces and torques from ForceAccumulatorComponents
        #    These are forces accumulated by other systems (gravity, springs, user input, etc.)
        external_forces_torques_map: Dict[uuid.UUID, Tuple[Vector2D, float]] = {}
        all_entity_ids_with_physics_list: List[uuid.UUID] = [] # For ConstraintSolverSystem

        for entity_id in entities_with_physics:
            all_entity_ids_with_physics_list.append(entity_id)
            force_accumulator = self.entity_manager.get_component(entity_id, ForceAccumulatorComponent)
            # Ensure force_accumulator exists, though get_entities_with_components should guarantee it
            if force_accumulator:
                external_forces_torques_map[entity_id] = (
                    force_accumulator.net_force,
                    force_accumulator.net_torque
                )
            else: # Should ideally not happen
                external_forces_torques_map[entity_id] = (Vector2D(0, 0), 0.0)


        # 2. Call the ConstraintSolverSystem to get constrained accelerations
        #    The solver will handle identifying dynamic vs fixed bodies internally.
        constrained_accel_map = self.constraint_solver.solve_constraints_and_get_accelerations(
            dt,
            all_entity_ids_with_physics_list, # Pass all relevant entity IDs
            external_forces_torques_map
        )
        # # print(f"[DEBUG_PHYSYS] Constrained Accel Map: {constrained_accel_map}")


        # 3. Integrate physics state using constrained accelerations
        for entity_id in entities_with_physics:
            transform = self.entity_manager.get_component(entity_id, TransformComponent)
            physics_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)
            
            # Should always have transform and physics_body due to the initial query
            if not (transform and physics_body):
                # This check is more of a safeguard.
                print(f"Warning: Entity {entity_id} missing Transform or PhysicsBody during integration step. Skipping.")
                continue

            if physics_body.is_fixed:
                # Ensure fixed bodies remain static and their accelerations are zero.
                # The constraint solver should also return zero acceleration for fixed bodies.
                physics_body.velocity = Vector2D(0, 0)
                physics_body.angular_velocity = 0.0
                physics_body.previous_acceleration = Vector2D(0, 0) # Reset for consistency
                # Forces on fixed bodies are handled by constraint solver for reaction forces (visualization)
                # but they don't cause motion. ForceAccumulators are cleared externally.
                continue

            # --- Velocity Verlet Integration (or similar) using constrained accelerations ---
            v_old_linear = physics_body.velocity
            a_old_linear = physics_body.previous_acceleration # Linear acceleration from *last* full step

            # 3.1 Update position using previous step's linear acceleration
            # p_new = p_old + v_old * dt + 0.5 * a_old * dt^2
            # No change needed here, uses a_old_linear
            transform.position = transform.position + (v_old_linear * dt) + (a_old_linear * (0.5 * dt * dt))

            # 3.2 Get new_linear_acceleration and new_angular_acceleration for the *current* frame
            #     These come from the constraint_solver's results.
            accel_data = constrained_accel_map.get(entity_id)
            if accel_data:
                a_new_linear, a_new_angular = accel_data
                # # print(f"[DEBUG_PHYSYS_INTEGRATE] Entity {str(entity_id)[:8]}: Constrained a_new_linear={a_new_linear}, a_new_angular={a_new_angular:.4f}")
            else:
                # This case should ideally be covered by constraint_solver returning accelerations
                # for all entities passed to it (either constrained or unconstrained based on F_ext).
                # If an entity was somehow missed, fallback to unconstrained based on its F_ext.
                print(f"Warning: Entity {entity_id} not found in constrained_accel_map. Using F_ext/M.")
                ext_force, ext_torque = external_forces_torques_map.get(entity_id, (Vector2D(0, 0), 0.0))
                a_new_linear = ext_force / physics_body.mass if physics_body.mass > EPSILON else Vector2D(0, 0)
                a_new_angular = ext_torque / physics_body.moment_of_inertia if physics_body.moment_of_inertia > EPSILON else 0.0

            # 3.3 Update linear velocity using the average of old and new linear acceleration
            # v_new = v_old + 0.5 * (a_old_linear + a_new_linear) * dt
            physics_body.velocity = v_old_linear + (a_old_linear + a_new_linear) * (0.5 * dt)

            # 3.4 Store the new linear acceleration for the *next* step's a_old_linear
            physics_body.previous_acceleration = a_new_linear
            
            # --- Rotational Dynamics ---
            # Using a_new_angular from the constraint solver.
            # Simplified Euler integration for angular part for now.
            # More sophisticated rotational Verlet could be:
            # angle_new = angle_old + omega_old * dt + 0.5 * alpha_old * dt^2
            # omega_new = omega_old + 0.5 * (alpha_old + alpha_new) * dt
            # Need to store previous_angular_acceleration if doing that.
            # For now, direct Euler update with current angular acceleration:
            if physics_body.moment_of_inertia > EPSILON:
                physics_body.angular_velocity += a_new_angular * dt
                transform.angle += physics_body.angular_velocity * dt
                transform.angle = (transform.angle + math.pi) % (2 * math.pi) - math.pi
            else: # Fixed angular velocity if no inertia (or effectively infinite inertia)
                transform.angle += physics_body.angular_velocity * dt # Still apply existing ang_vel
                transform.angle = (transform.angle + math.pi) % (2 * math.pi) - math.pi

            # # print(f"[DEBUG_PHYSYS_OUTPUT] Entity {str(entity_id)[:8]}: pos={transform.position}, vel={physics_body.velocity}, angle={transform.angle:.2f}, ang_vel={physics_body.angular_velocity:.2f}, prev_accel={physics_body.previous_acceleration}")

        # ForceAccumulators are cleared by the main simulation loop after all systems that might read them
        # (like rendering detailed forces) have run.
        # The ConstraintSolverSystem has already used the F_external values.
        # The PhysicsSystem uses the *results* (accelerations) from the ConstraintSolverSystem.

    def calculate_and_set_inertia(self, entity_id: uuid.UUID):
        """
        Calculates and sets the moment of inertia for an entity if it has a
        PhysicsBodyComponent with auto_calculate_inertia set to True.
        Currently supports RECTANGLE, CIRCLE, and POLYGON.
        The polygon's vertices in GeometryComponent are assumed to be relative to its centroid.
        """
        physics_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)
        geometry = self.entity_manager.get_component(entity_id, GeometryComponent)

        if not physics_body or not geometry or not physics_body.auto_calculate_inertia:
            return

        mass = physics_body.mass
        new_inertia = float('inf') # Default for fixed or issues

        if mass <= 0: # Fixed objects or zero mass objects have infinite inertia effectively
            physics_body.moment_of_inertia = float('inf')
            # # print(f"Entity {entity_id} has mass <= 0, setting inertia to infinity.")
            return

        if geometry.shape_type == ShapeType.RECTANGLE:
            width = geometry.parameters.get("width", 0)
            height = geometry.parameters.get("height", 0)
            if width > 0 and height > 0:
                new_inertia = (1.0 / 12.0) * mass * (width**2 + height**2)
        elif geometry.shape_type == ShapeType.CIRCLE:
            radius = geometry.parameters.get("radius", 0)
            if radius > 0:
                new_inertia = 0.5 * mass * radius**2
        elif geometry.shape_type == ShapeType.POLYGON:
            vertices = geometry.parameters.get("vertices")
            if vertices and len(vertices) >= 3:
                # Formula for moment of inertia of a polygon with vertices (xi, yi)
                # relative to the origin (which should be the centroid for this formula to be correct for I_centroid)
                # I = (mass / 6) * sum[(xi*yi+1 - xi+1*yi) * (xi^2 + xi*xi+1 + xi+1^2 + yi^2 + yi*yi+1 + yi+1^2)]
                # This formula is complex. A simpler approach for lamina (2D shape) is using Green's theorem
                # or decomposing into triangles.
                # For a polygon with vertices (x_i, y_i) relative to the centroid:
                # I_z = sum over triangles ( (m_triangle / 3) * ( (v0.x^2 + v0.y^2) + (v1.x^2 + v1.y^2) + (v2.x^2 + v2.y^2) ) )
                # No, that's not right.
                # A common formula for a polygon (lamina) with vertices (x_i, y_i) for inertia about origin:
                # I_origin = (density / 12) * sum_{i=0 to N-1} (x_i * y_{i+1} - x_{i+1} * y_i) * ( (x_i^2 + x_i*x_{i+1} + x_{i+1}^2) + (y_i^2 + y_i*y_{i+1} + y_{i+1}^2) )
                # If vertices are relative to centroid, this I_origin is I_centroid.
                # Density = mass / area. Area can be calculated using Shoelace formula.

                # 1. Calculate Area using Shoelace formula
                area = 0.0
                for i in range(len(vertices)):
                    v1 = vertices[i]
                    v2 = vertices[(i + 1) % len(vertices)] # Next vertex, wraps around
                    area += (v1.x * v2.y - v2.x * v1.y)
                area = abs(area) / 2.0

                if area < EPSILON: # Avoid division by zero for degenerate polygons
                    new_inertia = float('inf') # Or a very large number
                else:
                    density = mass / area
                    
                    # 2. Calculate moment of inertia using the formula for lamina about origin
                    # (origin is centroid here)
                    # J = sum (x_i * y_{i+1} - x_{i+1} * y_i) * (x_i^2 + x_i*x_{i+1} + x_{i+1}^2 + y_i^2 + y_i*y_{i+1} + y_{i+1}^2)
                    # I = (density / 12) * J
                    sum_val = 0.0
                    for i in range(len(vertices)):
                        p1 = vertices[i]
                        p2 = vertices[(i + 1) % len(vertices)]
                        
                        term1 = p1.x * p2.y - p2.x * p1.y
                        term2 = (p1.x**2 + p1.x * p2.x + p2.x**2) + \
                                (p1.y**2 + p1.y * p2.y + p2.y**2)
                        sum_val += term1 * term2
                    
                    new_inertia = abs(density * sum_val / 12.0)

        if new_inertia == float('inf') or new_inertia < EPSILON: # Ensure positive inertia
             physics_body.moment_of_inertia = 1.0 # Fallback to a small default if calculation fails or mass is zero
             print(f"Warning: Calculated inertia for entity {entity_id} is invalid ({new_inertia}). Setting to 1.0. Mass: {mass}, Shape: {geometry.shape_type}")
        else:
            physics_body.moment_of_inertia = new_inertia
        
        # # print(f"Calculated and set inertia for entity {entity_id}: {physics_body.moment_of_inertia:.4f} (Mass: {mass}, Shape: {geometry.shape_type})")