from typing import TYPE_CHECKING
from physi_sim.core.system import System
from physi_sim.core.component import (
    TransformComponent,
    PhysicsBodyComponent,
    ConnectionComponent,
    ForceAccumulatorComponent,
    ConnectionType  # Changed from CONNECTION_TYPE_ROPE
)
from physi_sim.core.vector import Vector2D
import math # For math.isclose

if TYPE_CHECKING:
    from physi_sim.core.entity_manager import EntityManager, EntityID

class RopeSystem(System):
    """
    通过主动力法模拟轻绳行为的系统。
    绳索只在被拉伸时施加拉力。
    """
    def __init__(self, entity_manager: 'EntityManager'):
        """
        初始化 RopeSystem。

        Args:
            entity_manager: 实体管理器实例。
        """
        super().__init__(entity_manager)
        # Default stiffness and damping are no longer class members,
        # they will be fetched from ConnectionComponent.parameters
        # print(f"[DEBUG_ROPE_SYSTEM_INIT] RopeSystem initialized.") # Optional: keep for debugging if needed

    def update(self, dt: float) -> None:
        """
        更新所有绳索连接，计算并施加力。

        Args:
            dt: 时间步长。
        """
        if dt <= 1e-9: # Avoid issues with very small or zero dt
            return

        # Iterate over all ConnectionComponents
        connections = self.entity_manager.get_all_independent_components_of_type(ConnectionComponent) # Use get_all_independent_components_of_type
        # print(f"[DEBUG_ROPE_SYSTEM] Found {len(connections)} ConnectionComponents. Connections: {connections}") # Commented out to stop log spam

        # The logic for applying forces for ROPE connections is now handled by ConstraintSolverSystem.
        # This system might still be useful for other rope-specific logic not related to force calculation,
        # or it could be removed if ConstraintSolverSystem covers all ROPE behaviors.
        # For now, commenting out the force calculation part.
        # print(f"[DEBUG_ROPE_SYSTEM] RopeSystem.update called, but force calculation is deferred to ConstraintSolverSystem.")
        pass # Keep the method, but effectively disable its old force calculations.

        # for connection in connections: # Iterate directly over the list of components
        #     if connection.connection_type != ConnectionType.ROPE: # Process only rope connections
        #         continue
            
        #     connection_id = connection.id # Get id from component
        #     if connection.is_broken:
        #         # print(f"[DEBUG_ROPE_SYSTEM] Rope {connection_id[:8]} is broken. Skipping.")
        #         continue

        #     entity_a_id = connection.source_entity_id # Use source_entity_id
        #     entity_b_id = connection.target_entity_id # Use target_entity_id

        #     # Get components for entity A and entity B
        #     transform_a = self.entity_manager.get_component(entity_a_id, TransformComponent)
        #     physics_body_a = self.entity_manager.get_component(entity_a_id, PhysicsBodyComponent)
        #     force_accumulator_a = self.entity_manager.get_component(entity_a_id, ForceAccumulatorComponent)
            
        #     transform_b = self.entity_manager.get_component(entity_b_id, TransformComponent)
        #     physics_body_b = self.entity_manager.get_component(entity_b_id, PhysicsBodyComponent)
        #     force_accumulator_b = self.entity_manager.get_component(entity_b_id, ForceAccumulatorComponent)

        #     if not all([transform_a, physics_body_a, force_accumulator_a,
        #                 transform_b, physics_body_b, force_accumulator_b]):
        #         # print(f"[DEBUG_ROPE_SYSTEM] Warning: Missing components for rope {connection_id[:8]}. Skipping.")
        #         continue

        #     # Get rope parameters from ConnectionComponent
        #     # Using .get with a default value is safer if a parameter might be missing,
        #     # but for required parameters, direct access or a check might be better.
        #     natural_length = connection.parameters.get("natural_length")
        #     # stiffness = connection.parameters.get("rope_stiffness") # No longer used here
        #     # damping = connection.parameters.get("rope_damping", 0.0) # No longer used here

        #     if natural_length is None: # Removed stiffness check
        #         # print(f"[DEBUG_ROPE_SYSTEM] Rope {connection_id[:8]} missing natural_length. Skipping.")
        #         continue
            
        #     if natural_length < 0:
        #         # print(f"[DEBUG_ROPE_SYSTEM] Rope {connection_id[:8]} has invalid natural_length: {natural_length}. Skipping.")
        #         continue

        #     # Calculate world anchor points
        #     # Ensure anchor_a and anchor_b are Vector2D instances
        #     local_anchor_a = connection.connection_point_a if isinstance(connection.connection_point_a, Vector2D) else Vector2D(connection.connection_point_a[0], connection.connection_point_a[1])
        #     local_anchor_b = connection.connection_point_b if isinstance(connection.connection_point_b, Vector2D) else Vector2D(connection.connection_point_b[0], connection.connection_point_b[1])

        #     anchor_a_world = transform_a.position + local_anchor_a.rotate(transform_a.angle)
        #     anchor_b_world = transform_b.position + local_anchor_b.rotate(transform_b.angle)
            
        #     # Calculate current rope vector and length
        #     rope_vector = anchor_b_world - anchor_a_world
        #     current_length = rope_vector.magnitude()

        #     # Calculate length deviation
        #     delta_length = current_length - natural_length

        #     # Rope only applies force if stretched (delta_length > 0)
        #     if delta_length <= 0:
        #         # print(f"[DEBUG_ROPE_SYSTEM] Rope {connection_id[:8]} is slack or compressed (L={current_length:.2f}, L0={natural_length:.2f}). No force applied.")
        #         continue # Skip to the next connection

        #     # Calculate direction unit vector
        #     if math.isclose(current_length, 0.0):
        #         direction_vec = Vector2D(0, 0) # Avoid division by zero if somehow current_length is zero despite delta_length > 0
        #     else:
        #         direction_vec = rope_vector.normalize()

        #     # Calculate elastic force (tension) - This part is now handled by ConstraintSolverSystem
        #     # elastic_force_magnitude = stiffness * delta_length
        #     # elastic_force_vec = direction_vec * elastic_force_magnitude # Points from A to B if stretched

        #     # Calculate damping force (optional but recommended) - This part is now handled by ConstraintSolverSystem
        #     # damping_force_vec = Vector2D(0, 0)
        #     # if damping > 0.0 and not math.isclose(current_length, 0.0):
        #         # ... (damping calculation logic) ...

            
        #     # total_rope_force_on_B = -(elastic_force_vec + damping_force_vec) # Tension pulls B towards A

            # # Record forces - This part is now handled by ConstraintSolverSystem
            # if force_accumulator_b and not physics_body_b.is_fixed:
            #     # ... (record force logic) ...
            
            # if force_accumulator_a and not physics_body_a.is_fixed: # Check accumulator exists before record_force_detail for safety
            #     # ... (record force logic) ...
            
            # # Debug prints (only if force was applied, i.e., delta_length > 0)
            # if delta_length > 0: # This outer if delta_length > 0 ensures these prints only happen when rope is taut
            #     connection_id_str = str(connection_id)[:8]
            #     # print(f"[DEBUG_ROPE_FORCE] Rope ID: {connection_id_str} - CurrentL: {current_length:.2f}, NaturalL: {natural_length:.2f}, DeltaL: {delta_length:.2f}")
            #     # print(f"  ElasticF_Mag: {elastic_force_magnitude:.2f}, DampF_Vec: {damping_force_vec}")
            #     # print(f"  TotalForceOnB: {total_rope_force_on_B}, TotalForceOnA: {-total_rope_force_on_B}")
        
        # # print(f"[DEBUG_ROPE_SYSTEM] Finished processing rope connections.") # Optional