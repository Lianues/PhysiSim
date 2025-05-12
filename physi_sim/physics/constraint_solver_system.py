import math
from typing import List, Dict, Tuple, Any, Set

import numpy as np

from physi_sim.core.system import System
from physi_sim.core.entity_manager import EntityManager
from physi_sim.core.component import (
    TransformComponent,
    PhysicsBodyComponent,
    ForceAccumulatorComponent, # Needed for recording detailed forces
    ConnectionComponent,
    ConnectionType
)
from physi_sim.core.vector import Vector2D
from physi_sim.core.utils import EPSILON # For small number comparisons

class ConstraintSolverSystem(System):
    """
    Solves physics constraints using Lagrange multipliers (e.g., for rods).
    This system calculates the necessary accelerations to satisfy constraints.
    """
    def __init__(self, entity_manager: EntityManager,
                 baumgarte_pos_correction_factor: float = 0.2,
                 baumgarte_vel_correction_factor: float = 0.8): # Renamed and new defaults
        """
        Initializes the ConstraintSolverSystem.

        Args:
            entity_manager: The entity manager instance.
            baumgarte_pos_correction_factor: Dimensionless factor for Baumgarte position stabilization (e.g., 0.1-0.8). Effective alpha = factor/dt.
            baumgarte_vel_correction_factor: Dimensionless factor for Baumgarte velocity stabilization (e.g., 0.1-1.0). Effective beta = factor (or factor/dt).
        """
        super().__init__(entity_manager)
        self.baumgarte_pos_correction_factor = baumgarte_pos_correction_factor
        self.baumgarte_vel_correction_factor = baumgarte_vel_correction_factor
        # # print(f"ConstraintSolverSystem initialized with pos_factor={self.baumgarte_pos_correction_factor}, vel_factor={self.baumgarte_vel_correction_factor}")

    def _get_rotation_matrix(self, angle_rad: float) -> np.ndarray:
        """Helper to get a 2D rotation matrix."""
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return np.array([[cos_a, -sin_a], [sin_a, cos_a]])

    def solve_constraints_and_get_accelerations(
        self,
        dt: float,
        all_entity_ids_with_physics: List[str], # IDs of all entities with physics body (dynamic or fixed)
        external_forces_torques: Dict[str, Tuple[Vector2D, float]], # {entity_id: (F_ext, τ_ext)}
        apply_and_record_constraint_forces: bool = True # New parameter
    ) -> Dict[str, Tuple[Vector2D, float]]: # {entity_id: (constrained_accel, constrained_angular_accel)}
        """
        Identifies active constraints, builds and solves the global KKT system,
        and returns the resulting constrained accelerations for all involved entities.

        Args:
            dt: Time step.
            all_entity_ids_with_physics: List of all entity IDs that have a PhysicsBodyComponent.
                                         The system will determine which are dynamic vs fixed.
            external_forces_torques: A map of externally applied forces and torques
                                     for each entity.

        Returns:
            A dictionary mapping entity IDs to their constrained linear and angular accelerations.
            Entities not involved in any constraint or fixed will also be in this map
            (fixed with zero acceleration, unconstrained dynamic with F_ext/M acceleration).
        """
        active_constraints: List[ConnectionComponent] = []
        entity_data_map: Dict[str, Dict[str, Any]] = {} # Stores transform, physics_body
        constrained_bodies_set: Set[str] = set() # All bodies (dynamic or fixed) part of any active constraint

        # 1. Identify active constraints (rod or rope) and pre-fetch component data
        all_connections = self.entity_manager.get_all_independent_components_of_type(ConnectionComponent)

        for conn in all_connections:
            is_rod = conn.connection_type == ConnectionType.ROD
            is_rope = conn.connection_type == ConnectionType.ROPE
            is_revolute_joint = conn.connection_type == ConnectionType.REVOLUTE_JOINT
            
            if (is_rod or is_rope or is_revolute_joint) and not conn.is_broken:
                # Common logic for fetching entity data
                valid_connection = True
                temp_entity_data_to_add = {}
                temp_constrained_bodies_to_add = set()

                entities_to_check = []
                if is_rod or is_rope or is_revolute_joint: # All these are two-body connections
                    entities_to_check = [conn.source_entity_id, conn.target_entity_id]

                for entity_id in entities_to_check:
                    if entity_id not in entity_data_map:
                        transform = self.entity_manager.get_component(entity_id, TransformComponent)
                        physics_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)
                        if transform and physics_body:
                            temp_entity_data_to_add[entity_id] = {'transform': transform, 'physics': physics_body}
                            # For axis joint, the axis itself is fixed, but still part of the "constrained bodies" concept
                            temp_constrained_bodies_to_add.add(entity_id)
                        else:
                            print(f"Warning: Connection {conn.id} ({conn.connection_type.name}) involves entity {entity_id} missing Transform or PhysicsBody. Skipping constraint.")
                            valid_connection = False
                            break
                
                if not valid_connection:
                    continue

                # Add data if connection is valid so far
                for eid, data in temp_entity_data_to_add.items():
                    if eid not in entity_data_map: # Ensure not to overwrite if already processed via another connection
                         entity_data_map[eid] = data
                constrained_bodies_set.update(temp_constrained_bodies_to_add)

                # Constraint-specific activation logic & validation
                if is_rod:
                    active_constraints.append(conn)
                elif is_revolute_joint:
                    # print(f"[CSS_DEBUG] Found REVOLUTE_JOINT: {conn.id}, Source: {conn.source_entity_id}, Target: {conn.target_entity_id}")
                    # For REVOLUTE_JOINT, both source and target are typically dynamic, or one could be fixed.
                    # The constraint itself doesn't impose one being an "axis entity".
                    source_physics = entity_data_map[conn.source_entity_id]['physics']
                    target_physics = entity_data_map[conn.target_entity_id]['physics'] # Axis entity

                    if source_physics.is_fixed:
                        print(f"[CSS_DEBUG] Axis joint {conn.id} source entity {conn.source_entity_id} (dynamic part) IS FIXED. Skipping constraint.")
                        valid_connection = False
                    
                    # If both are fixed, it's also not a dynamic constraint we handle here.
                    if source_physics.is_fixed and target_physics.is_fixed:
                         print(f"[CSS_DEBUG] Axis joint {conn.id} connects two fixed bodies ({conn.source_entity_id} and {conn.target_entity_id}). Skipping.")
                         valid_connection = False
                    
                    if valid_connection:
                        # print(f"[CSS_DEBUG] Axis joint {conn.id} is considered for active_constraints. Source fixed: {source_physics.is_fixed}, Target (Axis) fixed: {target_physics.is_fixed}")
                        active_constraints.append(conn)
                    else:
                        print(f"[CSS_DEBUG] Axis joint {conn.id} IS INVALID and skipped.")
                elif is_rope: # Keep rope logic after axis joint, as it might share some initial checks
                    natural_length = conn.parameters.get("natural_length")
                    if natural_length is None:
                        print(f"Warning: Rope connection {conn.id} missing 'natural_length' parameter. Skipping constraint.")
                        continue

                    # Calculate current length
                    # This requires entity_data_map to be populated for conn.source_entity_id and conn.target_entity_id
                    # which should be guaranteed by the loop above if valid_connection is true.
                    data_a_rope = entity_data_map[conn.source_entity_id]
                    data_b_rope = entity_data_map[conn.target_entity_id]
                    r_a_rope = data_a_rope['transform'].position
                    theta_a_rope = data_a_rope['transform'].angle
                    p_a_local_rope = conn.connection_point_a
                    R_a_np_rope = self._get_rotation_matrix(theta_a_rope)
                    r_AP_local_np_rope = np.array([p_a_local_rope.x, p_a_local_rope.y])
                    r_AP_world_np_rope = R_a_np_rope @ r_AP_local_np_rope
                    P_A_world_rope = r_a_rope + Vector2D(r_AP_world_np_rope[0], r_AP_world_np_rope[1])

                    r_b_rope = data_b_rope['transform'].position
                    theta_b_rope = data_b_rope['transform'].angle
                    p_b_local_rope = conn.connection_point_b
                    R_b_np_rope = self._get_rotation_matrix(theta_b_rope)
                    r_BP_local_np_rope = np.array([p_b_local_rope.x, p_b_local_rope.y])
                    r_BP_world_np_rope = R_b_np_rope @ r_BP_local_np_rope
                    P_B_world_rope = r_b_rope + Vector2D(r_BP_world_np_rope[0], r_BP_world_np_rope[1])
                    
                    current_length_sq = (P_B_world_rope - P_A_world_rope).magnitude_squared()
                    current_length = math.sqrt(current_length_sq)

                    if current_length > natural_length + EPSILON:
                        active_constraints.append(conn)
                        # # print(f"[DEBUG_CONSTRAINTSOLVER] Rope {conn.id} activated. Current: {current_length:.3f}, Natural: {natural_length:.3f}")
                    # else:
                        # # print(f"[DEBUG_CONSTRAINTSOLVER] Rope {conn.id} NOT activated. Current: {current_length:.3f}, Natural: {natural_length:.3f}")


        # Initialize result map with unconstrained accelerations for all physics entities
        result_accelerations: Dict[str, Tuple[Vector2D, float]] = {}
        for entity_id in all_entity_ids_with_physics:
            # Ensure data is loaded if not already by constraint scan
            if entity_id not in entity_data_map:
                transform = self.entity_manager.get_component(entity_id, TransformComponent)
                physics_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)
                if transform and physics_body:
                     entity_data_map[entity_id] = {'transform': transform, 'physics': physics_body}
                else: # Should not happen if all_entity_ids_with_physics is correct
                    result_accelerations[entity_id] = (Vector2D(0, 0), 0.0) # Fallback
                    continue

            physics = entity_data_map[entity_id]['physics']
            if physics.is_fixed:
                result_accelerations[entity_id] = (Vector2D(0, 0), 0.0)
            else:
                force, torque = external_forces_torques.get(entity_id, (Vector2D(0, 0), 0.0))
                mass = physics.mass
                inertia = physics.moment_of_inertia
                accel = force / mass if mass > EPSILON else Vector2D(0, 0)
                angular_accel = torque / inertia if inertia > EPSILON else 0.0
                result_accelerations[entity_id] = (accel, angular_accel)

        if not active_constraints:
            # # print("[DEBUG_CONSTRAINTSOLVER] No active constraints found.")
            return result_accelerations # Return unconstrained accelerations
        
        # # print(f"[DEBUG_CONSTRAINTSOLVER] Found {len(active_constraints)} active constraints.")

        # 2. Identify unique DYNAMIC bodies involved in constraints for DoF allocation
        #    and create DoF mapping.
        ordered_dynamic_bodies = sorted(list(
            eid for eid in constrained_bodies_set if not entity_data_map[eid]['physics'].is_fixed
        ))

        if not ordered_dynamic_bodies:
            # All constrained bodies are fixed, no dynamic DoFs to solve for.
            # This implies constraints are between fixed points, which are either trivially satisfied or violated.
            # No constraint forces are generated in a dynamic sense.
            # # print("[DEBUG_CONSTRAINTSOLVER] All constrained bodies are fixed. No dynamic DoFs.")
            return result_accelerations # Accelerations are already set (0 for fixed, F/M for others)


        N_dynamic_bodies = len(ordered_dynamic_bodies)
        N_dof = N_dynamic_bodies * 3

        entity_to_dof_start_idx: Dict[str, int] = {
            entity_id: i * 3 for i, entity_id in enumerate(ordered_dynamic_bodies)
        }

        # 3. Build Global M, M_inv, F_ext, v_global (for dynamic bodies only)
        global_M_diag = np.zeros(N_dof)
        global_M_inv_diag = np.zeros(N_dof)
        v_global_list = []
        Global_F_ext_list = []

        for i, entity_id in enumerate(ordered_dynamic_bodies):
            physics = entity_data_map[entity_id]['physics']
            start_idx = i * 3 # This is also entity_to_dof_start_idx[entity_id]

            # Mass and Inertia for M and M_inv
            mass = physics.mass
            inertia = physics.moment_of_inertia
            
            global_M_diag[start_idx] = mass
            global_M_diag[start_idx+1] = mass
            global_M_diag[start_idx+2] = inertia

            global_M_inv_diag[start_idx] = 1.0 / mass if mass > EPSILON else 0.0
            global_M_inv_diag[start_idx+1] = 1.0 / mass if mass > EPSILON else 0.0
            global_M_inv_diag[start_idx+2] = 1.0 / inertia if inertia > EPSILON else 0.0

            # Current velocities for v_global
            v_global_list.extend([physics.velocity.x, physics.velocity.y, physics.angular_velocity])

            # External forces for F_ext
            force, torque = external_forces_torques.get(entity_id, (Vector2D(0, 0), 0.0))
            Global_F_ext_list.extend([force.x, force.y, torque])
        
        Global_M = np.diag(global_M_diag)
        Global_M_inv = np.diag(global_M_inv_diag)
        v_global_np = np.array(v_global_list)
        Global_F_ext_np = np.array(Global_F_ext_list)

        # 4. Build Global J and Global b_stabilized
        # N_scalar_constraints is the total number of scalar constraint equations
        N_scalar_constraints = 0
        for conn in active_constraints:
            if conn.connection_type == ConnectionType.ROD or conn.connection_type == ConnectionType.ROPE:
                N_scalar_constraints += 1
            elif conn.connection_type == ConnectionType.REVOLUTE_JOINT:
                N_scalar_constraints += 2 # 2 scalar constraints for a 2D revolute joint (dx=0, dy=0)
        
        Global_J = np.zeros((N_scalar_constraints, N_dof))
        Global_b_stabilized = np.zeros(N_scalar_constraints)
        
        current_row_idx = 0 # Tracks the current row in Global_J and Global_b_stabilized

        # Loop through active_constraints to populate Global_J and Global_b_stabilized
        for conn in active_constraints: # Removed i_constraint as we use current_row_idx
            id_a = conn.source_entity_id
            # For axis joint, id_b is the axis (fixed). For others, it's the second dynamic body.
            id_b = conn.target_entity_id
            data_a = entity_data_map[id_a]
            data_b = entity_data_map[id_b]
            
            is_a_fixed = data_a['physics'].is_fixed
            is_b_fixed = data_b['physics'].is_fixed

            # Get current state for bodies A and B
            r_a = data_a['transform'].position
            theta_a = data_a['transform'].angle
            v_a_eff = data_a['physics'].velocity if not is_a_fixed else Vector2D(0, 0)
            omega_a_eff = data_a['physics'].angular_velocity if not is_a_fixed else 0.0
            
            r_b = data_b['transform'].position
            theta_b = data_b['transform'].angle
            v_b_eff = data_b['physics'].velocity if not is_b_fixed else Vector2D(0, 0)
            omega_b_eff = data_b['physics'].angular_velocity if not is_b_fixed else 0.0

            p_a_local = conn.connection_point_a
            p_b_local = conn.connection_point_b
            
            if conn.connection_type == ConnectionType.ROD or conn.connection_type == ConnectionType.ROPE:
                L_param_name = "target_length" if conn.connection_type == ConnectionType.ROD else "natural_length"
                L = conn.parameters.get(L_param_name)
                if L is None:
                    print(f"Error: {conn.connection_type.name} {conn.id} missing '{L_param_name}'. Skipping.")
                    # Need to ensure current_row_idx is advanced if we skip, or handle this better.
                    # For now, assume valid parameters from creation. If not, this could lead to issues.
                    # A simple skip might misalign rows if not careful.
                    # Let's assume for now that if L is None, the constraint was already filtered or this is an error.
                    # To be safe, let's fill with zeros and advance.
                    if N_dof > 0: # Only if there are dynamic DoFs to map to
                         Global_J[current_row_idx, :] = 0
                    Global_b_stabilized[current_row_idx] = 0
                    current_row_idx += 1
                    continue


            # --- Common calculations for ROD, ROPE ---
            if conn.connection_type == ConnectionType.ROD or conn.connection_type == ConnectionType.ROPE:
                R_a_np = self._get_rotation_matrix(theta_a)
                R_b_np = self._get_rotation_matrix(theta_b)

                r_AP_local_np = np.array([p_a_local.x, p_a_local.y])
                r_AP_world_np = R_a_np @ r_AP_local_np
                P_A_world = r_a + Vector2D(r_AP_world_np[0], r_AP_world_np[1])

                r_BP_local_np = np.array([p_b_local.x, p_b_local.y])
                r_BP_world_np = R_b_np @ r_BP_local_np
                P_B_world = r_b + Vector2D(r_BP_world_np[0], r_BP_world_np[1])
                
                d_vec = P_B_world - P_A_world
                
                k_cross_r_AP_world = Vector2D(-r_AP_world_np[1], r_AP_world_np[0])
                k_cross_r_BP_world = Vector2D(-r_BP_world_np[1], r_BP_world_np[0])

                J_k_local_row_rodrope = np.zeros(6)
                J_k_local_row_rodrope[0] = -2 * d_vec.x
                J_k_local_row_rodrope[1] = -2 * d_vec.y
                J_k_local_row_rodrope[2] = -2 * d_vec.dot(k_cross_r_AP_world)
                J_k_local_row_rodrope[3] =  2 * d_vec.x
                J_k_local_row_rodrope[4] =  2 * d_vec.y
                J_k_local_row_rodrope[5] =  2 * d_vec.dot(k_cross_r_BP_world)

                if not is_a_fixed:
                    idx_a_start = entity_to_dof_start_idx[id_a]
                    Global_J[current_row_idx, idx_a_start : idx_a_start+3] = J_k_local_row_rodrope[0:3]
                if not is_b_fixed: # Should always be true for ROD/ROPE if it's dynamic
                    idx_b_start = entity_to_dof_start_idx[id_b]
                    Global_J[current_row_idx, idx_b_start : idx_b_start+3] = J_k_local_row_rodrope[3:6]

                v_rel_P_term1 = v_b_eff - v_a_eff
                v_rel_P_term2_A = k_cross_r_AP_world * omega_a_eff
                v_rel_P_term2_B = k_cross_r_BP_world * omega_b_eff
                v_rel_P = v_rel_P_term1 + (v_rel_P_term2_B - v_rel_P_term2_A)
                term_v_sq = v_rel_P.dot(v_rel_P)
                
                omega_sq_r_A_term = Vector2D(r_AP_world_np[0], r_AP_world_np[1]) * (omega_a_eff**2)
                omega_sq_r_B_term = Vector2D(r_BP_world_np[0], r_BP_world_np[1]) * (omega_b_eff**2)
                term_omega_sq_r = d_vec.dot(omega_sq_r_B_term - omega_sq_r_A_term)
                b_accel_k = -2 * (term_v_sq - term_omega_sq_r)
                C_pos_k = d_vec.dot(d_vec) - L**2
                Jv_k = Global_J[current_row_idx, :] @ v_global_np
                
                effective_alpha_pos = self.baumgarte_pos_correction_factor / dt if dt > EPSILON else self.baumgarte_pos_correction_factor * (1.0/0.016) # Avoid division by zero, use typical 1/dt
                effective_beta_vel = self.baumgarte_vel_correction_factor / dt if dt > EPSILON else self.baumgarte_vel_correction_factor * (1.0/0.016) # Also scale beta by 1/dt

                Global_b_stabilized[current_row_idx] = b_accel_k - effective_alpha_pos * C_pos_k - effective_beta_vel * Jv_k
                current_row_idx += 1

            elif conn.connection_type == ConnectionType.REVOLUTE_JOINT:
                # Constraint: P_A_world(q_A) - P_B_world(q_B) = 0
                # This means the connection points on body A and body B must coincide.
                # P_A_world = r_A + R_A * p_A_local
                # P_B_world = r_B + R_B * p_B_local
                
                id_A_dyn = conn.source_entity_id # Dynamic body
                id_B_axis = conn.target_entity_id # Axis (can be dynamic or fixed)

                data_A_dyn = entity_data_map[id_A_dyn]
                data_B_axis = entity_data_map[id_B_axis]

                is_B_axis_fixed = data_B_axis['physics'].is_fixed

                pos_A = data_A_dyn['transform'].position
                angle_A = data_A_dyn['transform'].angle
                # vel_A and omega_A will be taken from v_global_np for Jv calculation
                p_A_local = conn.connection_point_a

                pos_B = data_B_axis['transform'].position
                angle_B = data_B_axis['transform'].angle
                # vel_B and omega_B if dynamic, else 0
                omega_B_val = data_B_axis['physics'].angular_velocity if not is_B_axis_fixed else 0.0
                p_B_local = conn.connection_point_b # Usually (0,0) for axis entity

                # Calculate world offsets r_AP_world and r_BP_world
                R_A_np = self._get_rotation_matrix(angle_A)
                p_A_local_np = np.array([p_A_local.x, p_A_local.y])
                r_AP_world_np = R_A_np @ p_A_local_np
                r_AP_world = Vector2D(r_AP_world_np[0], r_AP_world_np[1])
                P_A_world = pos_A + r_AP_world

                R_B_np = self._get_rotation_matrix(angle_B)
                p_B_local_np = np.array([p_B_local.x, p_B_local.y])
                r_BP_world_np = R_B_np @ p_B_local_np
                r_BP_world = Vector2D(r_BP_world_np[0], r_BP_world_np[1])
                P_B_world = pos_B + r_BP_world

                # Jacobian for body A (dynamic)
                idx_A_start = entity_to_dof_start_idx[id_A_dyn]
                Global_J[current_row_idx, idx_A_start : idx_A_start+3] = [1, 0, -r_AP_world.y]
                Global_J[current_row_idx+1, idx_A_start : idx_A_start+3] = [0, 1, r_AP_world.x]
                
                # dJ/dt * v terms for body A (omega_A is from physics component, representing current state)
                current_omega_A = data_A_dyn['physics'].angular_velocity
                b_accel_A_x = current_omega_A**2 * r_AP_world.x
                b_accel_A_y = current_omega_A**2 * r_AP_world.y
                
                # Positional error C_pos = P_A_world - P_B_world
                C_pos_x = P_A_world.x - P_B_world.x
                C_pos_y = P_A_world.y - P_B_world.y
                
                # Jv for body A part (using v_global_np which contains current velocities)
                v_global_A_slice = v_global_np[idx_A_start : idx_A_start+3]
                Jv_A_x = Global_J[current_row_idx, idx_A_start : idx_A_start+3] @ v_global_A_slice
                Jv_A_y = Global_J[current_row_idx+1, idx_A_start : idx_A_start+3] @ v_global_A_slice

                b_accel_x_total = b_accel_A_x
                b_accel_y_total = b_accel_A_y
                Jv_x_total = Jv_A_x
                Jv_y_total = Jv_A_y

                if not is_B_axis_fixed:
                    # Axis B is dynamic, add its Jacobian and dJ/dt * v terms
                    idx_B_start = entity_to_dof_start_idx[id_B_axis]
                    Global_J[current_row_idx, idx_B_start : idx_B_start+3] = [-1, 0, r_BP_world.y]
                    Global_J[current_row_idx+1, idx_B_start : idx_B_start+3] = [0, -1, -r_BP_world.x]
                    
                    current_omega_B = data_B_axis['physics'].angular_velocity
                    b_accel_B_x = -(current_omega_B**2 * r_BP_world.x) # J_B part is -I, so d(J_B)/dt * v_B gives -(dI/dt * v_B) effectively
                    b_accel_B_y = -(current_omega_B**2 * r_BP_world.y)
                    b_accel_x_total += b_accel_B_x
                    b_accel_y_total += b_accel_B_y
                    
                    v_global_B_slice = v_global_np[idx_B_start : idx_B_start+3]
                    Jv_B_x = Global_J[current_row_idx, idx_B_start : idx_B_start+3] @ v_global_B_slice
                    Jv_B_y = Global_J[current_row_idx+1, idx_B_start : idx_B_start+3] @ v_global_B_slice
                    Jv_x_total += Jv_B_x
                    Jv_y_total += Jv_B_y
                effective_alpha_pos = self.baumgarte_pos_correction_factor / dt if dt > EPSILON else self.baumgarte_pos_correction_factor * (1.0/0.016)
                effective_beta_vel = self.baumgarte_vel_correction_factor / dt if dt > EPSILON else self.baumgarte_vel_correction_factor * (1.0/0.016)
                
                Global_b_stabilized[current_row_idx]   = b_accel_x_total - effective_alpha_pos * C_pos_x - effective_beta_vel * Jv_x_total
                Global_b_stabilized[current_row_idx+1] = b_accel_y_total - effective_alpha_pos * C_pos_y - effective_beta_vel * Jv_y_total
                
                current_row_idx += 2
            
            
            else: # Should not happen if active_constraints only contains valid types
                print(f"Error: Unknown or unhandled constraint type {conn.connection_type} for {conn.id} during Jacobian build. Skipping.")
                # How many rows to advance current_row_idx depends on the unknown constraint.
                # This indicates a logic error if reached.
                # For safety, if it's a recognized ConnectionComponent, assume 1 or 2 rows based on typical constraint counts.
                # However, this path should ideally not be taken.
                # If it's truly unknown, we might not know how many rows it *should* have taken.
                # Let's assume it's a single scalar constraint if we absolutely must guess.
                # current_row_idx += 1 # This is risky.
                pass # Or raise an error, as this means an unhandled constraint type made it this far.

        # # print(f"[DEBUG_CONSTRAINTSOLVER] Global_J and Global_b_stabilized populated.")
        # # print(f"[DEBUG_CONSTRAINTSOLVER] Global_J:\n{Global_J}")
        # # print(f"[DEBUG_CONSTRAINTSOLVER] Global_b_stabilized:\n{Global_b_stabilized}")

        # 5. Solve the global KKT system
        # [ Global_M   Global_J^T ] [ dv_dt_global ] = [ Global_F_ext        ]
        # [ Global_J    0         ] [ lambda_global] = [ Global_b_stabilized ]
        
        dv_dt_global_np = np.zeros(N_dof) # Initialize to zeros
        lambda_global_np = np.zeros(N_scalar_constraints) # Lambdas match scalar constraints

        if N_dof > 0 : # Only solve if there are dynamic degrees of freedom
            KKT_size = N_dof + N_scalar_constraints
            Global_KKT_matrix = np.zeros((KKT_size, KKT_size))
            
            # Top-left: Global_M (N_dof x N_dof)
            Global_KKT_matrix[0:N_dof, 0:N_dof] = Global_M
            # Top-right: Global_J^T (N_dof x N_scalar_constraints)
            Global_KKT_matrix[0:N_dof, N_dof:KKT_size] = Global_J.T
            # Bottom-left: Global_J (N_scalar_constraints x N_dof)
            Global_KKT_matrix[N_dof:KKT_size, 0:N_dof] = Global_J
            # Bottom-right block (N_scalar_constraints x N_scalar_constraints) is zero for ideal constraints

            Global_rhs = np.zeros(KKT_size)
            Global_rhs[0:N_dof] = Global_F_ext_np
            Global_rhs[N_dof:KKT_size] = Global_b_stabilized

            try:
                # # print(f"[DEBUG_CONSTRAINTSOLVER] Attempting to solve KKT system of size {KKT_size}x{KKT_size}")
                # # print(f"[DEBUG_CONSTRAINTSOLVER] KKT Matrix:\n{Global_KKT_matrix}")
                # # print(f"[DEBUG_CONSTRAINTSOLVER] RHS Vector:\n{Global_rhs}")
                # Use lstsq for more robustness against singular matrices
                solution_global, residuals, rank, s = np.linalg.lstsq(Global_KKT_matrix, Global_rhs, rcond=None)
                if rank < KKT_size:
                    print(f"Warning: KKT matrix is rank deficient (rank {rank} for size {KKT_size}). Solution may not be unique or exact.")

                dv_dt_global_np = solution_global[0:N_dof]
                lambda_global_np = solution_global[N_dof:KKT_size]
                # # print(f"[DEBUG_CONSTRAINTSOLVER] KKT system solved.")
                # # print(f"[DEBUG_CONSTRAINTSOLVER] dv_dt_global_np:\n{dv_dt_global_np}")
                # # print(f"[DEBUG_CONSTRAINTSOLVER] lambda_global_np:\n{lambda_global_np}")

            except np.linalg.LinAlgError as e:
                print(f"Error: Global KKT system solve failed: {e}")
                print(f"KKT Matrix (first few rows/cols if large):\n{Global_KKT_matrix[:min(10, KKT_size), :min(10, KKT_size)]}")
                print(f"RHS Vector:\n{Global_rhs}")
                # Fallback: use unconstrained accelerations (already in result_accelerations for dynamic bodies)
                # No need to modify dv_dt_global_np from zeros, lambda_global_np remains zeros.
                # The existing result_accelerations map will be returned.
                pass # result_accelerations already holds unconstrained values for dynamic bodies

            # 6. Distribute global dv/dt back to individual entities in result_accelerations
            for i, entity_id in enumerate(ordered_dynamic_bodies):
                start_idx = entity_to_dof_start_idx[entity_id] # Or simply i * 3
                accel = Vector2D(dv_dt_global_np[start_idx], dv_dt_global_np[start_idx+1])
                angular_accel = dv_dt_global_np[start_idx+2]
                result_accelerations[entity_id] = (accel, angular_accel)
        
        # else: N_dof is 0, all constrained bodies are fixed.
        # result_accelerations already contains 0 accel for fixed, and F/M for unconstrained dynamic.

        # 7. Record detailed constraint forces for visualization/debugging
        if apply_and_record_constraint_forces and N_scalar_constraints > 0 and np.any(lambda_global_np): # Check new flag
            # # print(f"[DEBUG_CONSTRAINTSOLVER] Recording detailed constraint forces. Lambdas: {lambda_global_np}")
            
            processed_lambda_idx = 0 # Tracks which lambda(s) we are processing from lambda_global_np
            for conn_k in active_constraints:
                id_a = conn_k.source_entity_id
                id_b = conn_k.target_entity_id # Axis for REVOLUTE_JOINT_AXIS, other body for ROD/ROPE
                data_a = entity_data_map[id_a]
                p_a_local = conn_k.connection_point_a
                
                if conn_k.connection_type == ConnectionType.ROD or conn_k.connection_type == ConnectionType.ROPE:
                    lambda_k_val = lambda_global_np[processed_lambda_idx]
                    lambda_k_val = -lambda_k_val # Sign convention
                    processed_lambda_idx += 1

                    if conn_k.connection_type == ConnectionType.ROPE and lambda_k_val > EPSILON:
                        lambda_k_val = 0.0
                    if abs(lambda_k_val) < EPSILON:
                        continue

                    data_b = entity_data_map[id_b] # Second dynamic body
                    p_b_local = conn_k.connection_point_b
                    
                    r_a = data_a['transform'].position; theta_a = data_a['transform'].angle
                    r_b = data_b['transform'].position; theta_b = data_b['transform'].angle
                    R_a_np_fc = self._get_rotation_matrix(theta_a)
                    R_b_np_fc = self._get_rotation_matrix(theta_b)
                    r_AP_local_np_fc = np.array([p_a_local.x, p_a_local.y])
                    r_AP_world_np_fc = R_a_np_fc @ r_AP_local_np_fc
                    P_A_world_fc = r_a + Vector2D(r_AP_world_np_fc[0], r_AP_world_np_fc[1])
                    r_BP_local_np_fc = np.array([p_b_local.x, p_b_local.y])
                    r_BP_world_np_fc = R_b_np_fc @ r_BP_local_np_fc
                    P_B_world_fc = r_b + Vector2D(r_BP_world_np_fc[0], r_BP_world_np_fc[1])
                    d_vec_fc = P_B_world_fc - P_A_world_fc
                    k_cross_r_AP_world_fc = Vector2D(-r_AP_world_np_fc[1], r_AP_world_np_fc[0])
                    k_cross_r_BP_world_fc = Vector2D(-r_BP_world_np_fc[1], r_BP_world_np_fc[0])

                    J_k_local_for_force_rodrope = np.zeros(6)
                    J_k_local_for_force_rodrope[0] = -2 * d_vec_fc.x
                    J_k_local_for_force_rodrope[1] = -2 * d_vec_fc.y
                    J_k_local_for_force_rodrope[2] = -2 * d_vec_fc.dot(k_cross_r_AP_world_fc)
                    J_k_local_for_force_rodrope[3] =  2 * d_vec_fc.x
                    J_k_local_for_force_rodrope[4] =  2 * d_vec_fc.y
                    J_k_local_for_force_rodrope[5] =  2 * d_vec_fc.dot(k_cross_r_BP_world_fc)
                    
                    f_k_gen = J_k_local_for_force_rodrope.T * lambda_k_val
                    force_label_prefix = "CRod" if conn_k.connection_type == ConnectionType.ROD else "RopeTension"

                    # print(f"[DEBUG_CSS_FORCE_REC] Rope/Rod: {conn_k.id.hex[:4]}, Lambda_k: {lambda_k_val:.4f}") # REMOVED
                    # print(f"  Entity A: {id_a.hex[:4]}, Fixed: {data_a['physics'].is_fixed}, Force: Vector2D({f_k_gen[0]:.4f}, {f_k_gen[1]:.4f})") # REMOVED
                    # print(f"  Entity B: {id_b.hex[:4]}, Fixed: {data_b['physics'].is_fixed}, Force: Vector2D({f_k_gen[3]:.4f}, {f_k_gen[4]:.4f})") # REMOVED

                    # Force on A
                    acc_a = self.entity_manager.get_component(id_a, ForceAccumulatorComponent)
                    if acc_a and not data_a['physics'].is_fixed:
                        acc_a.record_force_detail(
                            force_vector=Vector2D(f_k_gen[0], f_k_gen[1]),
                            application_point_local=p_a_local,
                            force_type_label=f"{force_label_prefix}_{conn_k.id.hex[:4]}_{id_a.hex[:4]}",
                            is_visualization_only=False) # MODIFIED: Apply this force
                        # Also add to net_force and net_torque
                        constraint_force_on_a = Vector2D(f_k_gen[0], f_k_gen[1])
                        constraint_torque_on_a = p_a_local.rotate(data_a['transform'].angle).cross(constraint_force_on_a)
                        acc_a.add_force(constraint_force_on_a)
                        acc_a.add_torque(constraint_torque_on_a)
                        # print(f"DEBUG_CSS: Applied constraint force {constraint_force_on_a} and torque {constraint_torque_on_a} to entity {id_a} from {force_label_prefix}")
                    # Force on B
                    acc_b = self.entity_manager.get_component(id_b, ForceAccumulatorComponent)
                    if acc_b and not data_b['physics'].is_fixed:
                        acc_b.record_force_detail(
                            force_vector=Vector2D(f_k_gen[3], f_k_gen[4]),
                            application_point_local=p_b_local,
                            force_type_label=f"{force_label_prefix}_{conn_k.id.hex[:4]}_{id_b.hex[:4]}",
                            is_visualization_only=False) # MODIFIED: Apply this force
                        # Also add to net_force and net_torque
                        constraint_force_on_b = Vector2D(f_k_gen[3], f_k_gen[4])
                        constraint_torque_on_b = p_b_local.rotate(data_b['transform'].angle).cross(constraint_force_on_b)
                        acc_b.add_force(constraint_force_on_b)
                        acc_b.add_torque(constraint_torque_on_b)
                        # print(f"DEBUG_CSS: Applied constraint force {constraint_force_on_b} and torque {constraint_torque_on_b} to entity {id_b} from {force_label_prefix}")

                elif conn_k.connection_type == ConnectionType.REVOLUTE_JOINT:
                    lambda_x = lambda_global_np[processed_lambda_idx]
                    lambda_y = lambda_global_np[processed_lambda_idx+1]
                    lambda_x = -lambda_x # Sign convention for reaction force
                    lambda_y = -lambda_y # Sign convention
                    processed_lambda_idx += 2

                    if abs(lambda_x) < EPSILON and abs(lambda_y) < EPSILON:
                        continue

                    pos_A = data_a['transform'].position
                    angle_A = data_a['transform'].angle
                    R_A_np_fc = self._get_rotation_matrix(angle_A)
                    p_A_local_np_fc = np.array([p_a_local.x, p_a_local.y])
                    pA_world_offset_np_fc = R_A_np_fc @ p_A_local_np_fc
                    pA_world_offset_fc = Vector2D(pA_world_offset_np_fc[0], pA_world_offset_np_fc[1])
                    
                    # J_A^T = [[1,               0              ],
                    #          [0,               1              ],
                    #          [-pA_world_offset_fc.y, pA_world_offset_fc.x]]
                    # f_gen_A = J_A^T * [lambda_x, lambda_y]^T
                    force_on_A_x = lambda_x
                    force_on_A_y = lambda_y
                    # torque_on_A = -lambda_x * pA_world_offset_fc.y + lambda_y * pA_world_offset_fc.x
                    
                    acc_a = self.entity_manager.get_component(id_a, ForceAccumulatorComponent)
                    if acc_a and not data_a['physics'].is_fixed: # Should always be dynamic
                        acc_a.record_force_detail(
                            force_vector=Vector2D(force_on_A_x, force_on_A_y),
                            application_point_local=p_a_local, # Force applied at anchor point on A
                            force_type_label=f"CRevolute_{conn_k.id.hex[:4]}_{id_a.hex[:4]}",
                            is_visualization_only=False # MODIFIED: Apply this force
                        )
                        # Also add to net_force and net_torque
                        constraint_force_on_A_rev = Vector2D(force_on_A_x, force_on_A_y)
                        # Torque for revolute joint constraint force is more complex if the force itself isn't just canceling net external forces.
                        # The lambda directly gives the constraint force. Its application point is p_a_local.
                        constraint_torque_on_A_rev = p_a_local.rotate(data_a['transform'].angle).cross(constraint_force_on_A_rev)
                        acc_a.add_force(constraint_force_on_A_rev)
                        acc_a.add_torque(constraint_torque_on_A_rev)
                        # print(f"DEBUG_CSS: Applied constraint force {constraint_force_on_A_rev} and torque {constraint_torque_on_A_rev} to entity {id_a} from CRevolute")
                    
                    # Force on B (the other body of the joint)
                    id_B_fc = conn_k.target_entity_id # Renamed for clarity
                    data_B_fc = entity_data_map[id_B_fc]
                    if not data_B_fc['physics'].is_fixed: # If body B is dynamic
                        acc_b_fc = self.entity_manager.get_component(id_B_fc, ForceAccumulatorComponent)
                        if acc_b_fc:
                            # Force on B is opposite to force on A (Newton's 3rd law for contact point)
                            force_on_B_x = -force_on_A_x
                            force_on_B_y = -force_on_A_y
                            p_B_local_fc = conn_k.connection_point_b # Anchor point on B

                            acc_b_fc.record_force_detail(
                                force_vector=Vector2D(force_on_B_x, force_on_B_y),
                                application_point_local=p_B_local_fc,
                                force_type_label=f"CRevolute_{conn_k.id.hex[:4]}_{id_B_fc.hex[:4]}",
                                is_visualization_only=False # MODIFIED: Apply this force
                            )
                            # Also add to net_force and net_torque
                            constraint_force_on_B_rev = Vector2D(force_on_B_x, force_on_B_y)
                            constraint_torque_on_B_rev = p_B_local_fc.rotate(data_B_fc['transform'].angle).cross(constraint_force_on_B_rev)
                            acc_b_fc.add_force(constraint_force_on_B_rev)
                            acc_b_fc.add_torque(constraint_torque_on_B_rev)
                            # print(f"DEBUG_CSS: Applied constraint force {constraint_force_on_B_rev} and torque {constraint_torque_on_B_rev} to entity {id_B_fc} from CRevolute")
        # else: No constraints or lambdas are zero, no forces to record.

        return result_accelerations


    def update(self, dt: float):
        """
        The main logic of this system is encapsulated in `solve_constraints_and_get_accelerations`,
        which is intended to be called by `PhysicsSystem`.
        This update method is present for System interface compliance but may not be used directly
        in the primary simulation loop if `PhysicsSystem` orchestrates the call.
        """
        pass