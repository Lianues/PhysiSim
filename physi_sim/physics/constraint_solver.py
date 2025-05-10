from typing import TYPE_CHECKING, Dict
from physi_sim.core.system import System
from physi_sim.core.component import TransformComponent, PhysicsBodyComponent, ConnectionComponent, ConnectionType
from physi_sim.core.vector import Vector2D
# from physi_sim.core.component import CONNECTION_TYPE_ROD # Replaced by ConnectionType Enum

if TYPE_CHECKING:
    from physi_sim.core.entity_manager import EntityManager, EntityID

class ConstraintSolver(System):
    def __init__(self, entity_manager: 'EntityManager', iterations: int = 30): # Increased iterations
        super().__init__(entity_manager)
        self.iterations = iterations
        print(f"[DEBUG_CS_INIT] ConstraintSolver initialized for PBD ROD constraints. Iterations: {self.iterations}")

    def _resolve_rod_constraint_pbd(self,
                                    entity_a_id: 'EntityID', trans_a: TransformComponent, phys_a: PhysicsBodyComponent,
                                    entity_b_id: 'EntityID', trans_b: TransformComponent, phys_b: PhysicsBodyComponent,
                                    conn_comp: ConnectionComponent, iteration_num: int): # dt not needed for position solve
        """
        PBD-based rod constraint resolution.
        This function is currently commented out as part of the transition to active force-based rods.
        """
        # print(f"[DEBUG_ROD_PBD] Iteration {iteration_num} - Processing Rod ID: {str(conn_comp.id)[:4]}, EntA: {str(entity_a_id)[:4]}, EntB: {str(entity_b_id)[:4]}")
        # print(f"[DEBUG_ROD_PBD]   Before - PosA: {trans_a.position}, AngA: {trans_a.angle:.2f}, PosB: {trans_b.position}, AngB: {trans_b.angle:.2f}")

        # if conn_comp.is_broken:
        #     print(f"[DEBUG_ROD_PBD]   Rod {str(conn_comp.id)[:4]} is broken. Skipping.")
        #     return

        # rod_length = conn_comp.parameters.get("fixed_length")
        # if rod_length is None or rod_length <= 0:
        #     print(f"[DEBUG_ROD_PBD]   Rod {str(conn_comp.id)[:4]} has invalid fixed_length ({rod_length}). Skipping.")
        #     return

        # r_a_local = conn_comp.connection_point_a
        # r_b_local = conn_comp.connection_point_b

        # r_a_world = r_a_local.rotate(trans_a.angle)
        # world_anchor_a = trans_a.position + r_a_world

        # r_b_world = r_b_local.rotate(trans_b.angle)
        # world_anchor_b = trans_b.position + r_b_world
        
        # delta_vector = world_anchor_b - world_anchor_a
        # current_distance = delta_vector.magnitude()
        
        # pbd_threshold = 1e-6
        # if abs(current_distance - rod_length) > pbd_threshold:
        #     correction_direction: Vector2D
        #     if current_distance < 1e-9:
        #         correction_direction = Vector2D(0, 1)
        #     else:
        #         correction_direction = delta_vector / current_distance

        #     delta_length_scalar = current_distance - rod_length
            
        #     inv_mass_a = 0.0
        #     inv_inertia_a = 0.0
        #     if not phys_a.is_fixed and phys_a.mass > 0:
        #         inv_mass_a = 1.0 / phys_a.mass
        #     if not phys_a.is_fixed and phys_a.moment_of_inertia > 0:
        #         inv_inertia_a = 1.0 / phys_a.moment_of_inertia
        #     # print(f"[DEBUG_ROD_PBD]   EntA ({str(entity_a_id)[:4]}): is_fixed={phys_a.is_fixed}, mass={phys_a.mass:.2f}, inv_mass={inv_mass_a:.2e}, inv_inertia={inv_inertia_a:.2e}")

        #     inv_mass_b = 0.0
        #     inv_inertia_b = 0.0
        #     if not phys_b.is_fixed and phys_b.mass > 0:
        #         inv_mass_b = 1.0 / phys_b.mass
        #     if not phys_b.is_fixed and phys_b.moment_of_inertia > 0:
        #         inv_inertia_b = 1.0 / phys_b.moment_of_inertia
        #     # print(f"[DEBUG_ROD_PBD]   EntB ({str(entity_b_id)[:4]}): is_fixed={phys_b.is_fixed}, mass={phys_b.mass:.2f}, inv_mass={inv_mass_b:.2e}, inv_inertia={inv_inertia_b:.2e}")

        #     w_a = 0.0
        #     if not phys_a.is_fixed:
        #         cross_r_a_n = r_a_world.cross(correction_direction)
        #         w_a = inv_mass_a + inv_inertia_a * cross_r_a_n * cross_r_a_n
            
        #     w_b = 0.0
        #     if not phys_b.is_fixed:
        #         cross_r_b_n = r_b_world.cross(correction_direction)
        #         w_b = inv_mass_b + inv_inertia_b * cross_r_b_n * cross_r_b_n
            
        #     total_generalized_inv_mass = w_a + w_b

        #     if total_generalized_inv_mass < 1e-9:
        #         # print(f"[DEBUG_ROD_PBD]   Rod {str(conn_comp.id)[:4]} total_generalized_inv_mass too small ({total_generalized_inv_mass:.2e}). Skipping correction.")
        #         return

        #     scaling_factor = -delta_length_scalar / total_generalized_inv_mass
            
        #     if not phys_a.is_fixed:
        #         delta_pos_a_com = scaling_factor * inv_mass_a * (-correction_direction)
        #         delta_angle_a = scaling_factor * inv_inertia_a * r_a_world.cross(-correction_direction)
        #         trans_a.position += delta_pos_a_com
        #         trans_a.angle += delta_angle_a
            
        #     if not phys_b.is_fixed:
        #         delta_pos_b_com = scaling_factor * inv_mass_b * correction_direction
        #         delta_angle_b = scaling_factor * inv_inertia_b * r_b_world.cross(correction_direction) # CORRECTED
        #         trans_b.position += delta_pos_b_com
        #         trans_b.angle += delta_angle_b
        #     # print(f"[DEBUG_ROD_PBD]   Applied correction. Rod ID: {str(conn_comp.id)[:4]}, DeltaL: {delta_length_scalar:.4f}, ScaleFactor: {scaling_factor:.3e}")
        #     # print(f"[DEBUG_ROD_PBD]   After - PosA: {trans_a.position}, AngA: {trans_a.angle:.2f}, PosB: {trans_b.position}, AngB: {trans_b.angle:.2f}")
        # else:
        #     # print(f"[DEBUG_ROD_PBD]   Rod {str(conn_comp.id)[:4]} already satisfied (current: {current_distance:.4f}, target: {rod_length:.4f}). No correction.")
        pass # Functionality removed


    def update(self, dt: float,
                 positions_at_timestep_start: Dict['EntityID', Vector2D], 
                 angles_at_timestep_start: Dict['EntityID', float]) -> None:
        print(f"[DEBUG_CS_PBD_UPDATE] PBD ConstraintSolver.update called. dt: {dt}, Iterations: {self.iterations}")
        if dt <= 1e-9:
            print(f"[DEBUG_CS_PBD_UPDATE] dt too small ({dt}). Skipping.")
            return

        involved_entities_for_velocity_update = set()

        for i in range(self.iterations):
            all_connections = self.entity_manager.get_all_independent_components_of_type(ConnectionComponent)
            if i == 0: # Log only on first iteration
                 print(f"[DEBUG_CS_PBD_UPDATE] Iteration {i}: Found {len(all_connections)} ConnectionComponents for PBD.")

            for conn_comp in all_connections:
                if conn_comp.connection_type == ConnectionType.ROD: # Only process RODs, use Enum
                    entity_a_id = conn_comp.source_entity_id
                    entity_b_id = conn_comp.target_entity_id

                    trans_a = self.entity_manager.get_component(entity_a_id, TransformComponent)
                    phys_a = self.entity_manager.get_component(entity_a_id, PhysicsBodyComponent)
                    trans_b = self.entity_manager.get_component(entity_b_id, TransformComponent)
                    phys_b = self.entity_manager.get_component(entity_b_id, PhysicsBodyComponent)

                    if not (trans_a and phys_a and trans_b and phys_b):
                        print(f"[DEBUG_CS_PBD_UPDATE] Rod {str(conn_comp.id)[:4]}: Missing components for entities {str(entity_a_id)[:4]} or {str(entity_b_id)[:4]}. Skipping.")
                        continue
                    
                    if not phys_a.is_fixed:
                        involved_entities_for_velocity_update.add(entity_a_id)
                    if not phys_b.is_fixed:
                        involved_entities_for_velocity_update.add(entity_b_id)

                    # self._resolve_rod_constraint_pbd(entity_a_id, trans_a, phys_a,
                    #                                  entity_b_id, trans_b, phys_b,
                    #                                  conn_comp, i)
                    pass # Rod PBD logic removed
        
        # After PBD iterations, update velocities
        print(f"[DEBUG_CS_PBD_UPDATE] Updating velocities for {len(involved_entities_for_velocity_update)} involved entities.")
        for entity_id in involved_entities_for_velocity_update:
            trans_corrected = self.entity_manager.get_component(entity_id, TransformComponent)
            phys_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)

            if trans_corrected and phys_body and not phys_body.is_fixed:
                pos_at_start = positions_at_timestep_start.get(entity_id)
                angle_at_start = angles_at_timestep_start.get(entity_id)

                if pos_at_start is not None:
                    delta_position = trans_corrected.position - pos_at_start
                    phys_body.velocity = delta_position / dt
                    print(f"[DEBUG_CS_PBD_VEL] Ent {str(entity_id)[:4]} Velo: {phys_body.velocity} (from deltaPos: {delta_position}, p_corr: {trans_corrected.position}, p_start: {pos_at_start})")


                if angle_at_start is not None:
                    delta_angle = trans_corrected.angle - angle_at_start
                    phys_body.angular_velocity = delta_angle / dt
                    print(f"[DEBUG_CS_PBD_VEL] Ent {str(entity_id)[:4]} AngVelo: {phys_body.angular_velocity:.3f} (from deltaAngle: {delta_angle:.3f})")

                # previous_acceleration is NOT reset here. PhysicsSystem handles it based on forces.
        
        print(f"[DEBUG_CS_PBD_UPDATE] Finished PBD constraint solve and velocity updates for this step.")
