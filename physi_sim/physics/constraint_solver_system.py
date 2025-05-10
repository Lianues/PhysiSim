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
    def __init__(self, entity_manager: EntityManager, baumgarte_alpha: float = 20.0, baumgarte_beta: float = 2.0):
        """
        Initializes the ConstraintSolverSystem.

        Args:
            entity_manager: The entity manager instance.
            baumgarte_alpha: Proportional gain for Baumgarte stabilization (position error).
            baumgarte_beta: Derivative gain for Baumgarte stabilization (velocity error).
        """
        super().__init__(entity_manager)
        self.baumgarte_alpha = baumgarte_alpha
        self.baumgarte_beta = baumgarte_beta
        # print(f"ConstraintSolverSystem initialized with alpha={self.baumgarte_alpha}, beta={self.baumgarte_beta}")

    def _get_rotation_matrix(self, angle_rad: float) -> np.ndarray:
        """Helper to get a 2D rotation matrix."""
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return np.array([[cos_a, -sin_a], [sin_a, cos_a]])

    def solve_constraints_and_get_accelerations(
        self,
        dt: float,
        all_entity_ids_with_physics: List[str], # IDs of all entities with physics body (dynamic or fixed)
        external_forces_torques: Dict[str, Tuple[Vector2D, float]] # {entity_id: (F_ext, τ_ext)}
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
            
            if (is_rod or is_rope) and not conn.is_broken:
                # Common logic for fetching entity data
                valid_connection = True
                temp_entity_data_to_add = {}
                temp_constrained_bodies_to_add = set()

                for entity_id in [conn.source_entity_id, conn.target_entity_id]:
                    if entity_id not in entity_data_map:
                        transform = self.entity_manager.get_component(entity_id, TransformComponent)
                        physics_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)
                        if transform and physics_body:
                            temp_entity_data_to_add[entity_id] = {'transform': transform, 'physics': physics_body}
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

                # Constraint-specific activation logic
                if is_rod:
                    active_constraints.append(conn)
                elif is_rope:
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
                        # print(f"[DEBUG_CONSTRAINTSOLVER] Rope {conn.id} activated. Current: {current_length:.3f}, Natural: {natural_length:.3f}")
                    # else:
                        # print(f"[DEBUG_CONSTRAINTSOLVER] Rope {conn.id} NOT activated. Current: {current_length:.3f}, Natural: {natural_length:.3f}")


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
            # print("[DEBUG_CONSTRAINTSOLVER] No active rod or rope constraints found.")
            return result_accelerations # Return unconstrained accelerations

        # print(f"[DEBUG_CONSTRAINTSOLVER] Found {len(active_constraints)} active constraints (rod/rope).")

        # 2. Identify unique DYNAMIC bodies involved in constraints for DoF allocation
        #    and create DoF mapping.
        ordered_dynamic_bodies = sorted(list(
            eid for eid in constrained_bodies_set if not entity_data_map[eid]['physics'].is_fixed
        ))

        if not ordered_dynamic_bodies:
            # All constrained bodies are fixed, no dynamic DoFs to solve for.
            # This implies constraints are between fixed points, which are either trivially satisfied or violated.
            # No constraint forces are generated in a dynamic sense.
            # print("[DEBUG_CONSTRAINTSOLVER] All constrained bodies are fixed. No dynamic DoFs.")
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

        # 4. Build Global J (N_constraints x N_dof) and Global b_stabilized (N_constraints x 1)
        N_constraints = len(active_constraints)
        Global_J = np.zeros((N_constraints, N_dof))
        Global_b_stabilized = np.zeros(N_constraints)

        # Loop through active_constraints to populate Global_J and Global_b_stabilized
        for i_constraint, conn in enumerate(active_constraints):
            id_a = conn.source_entity_id
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
            
            if conn.connection_type == ConnectionType.ROD:
                L = conn.parameters.get("target_length")
                if L is None: # Should not happen if validation is done during creation
                    print(f"Error: Rod {conn.id} missing 'target_length'. Skipping.")
                    Global_b_stabilized[i_constraint] = 0 # Avoid issues
                    continue
            elif conn.connection_type == ConnectionType.ROPE:
                L = conn.parameters.get("natural_length")
                if L is None: # Should not happen if validation is done during creation
                    print(f"Error: Rope {conn.id} missing 'natural_length'. Skipping.")
                    Global_b_stabilized[i_constraint] = 0 # Avoid issues
                    continue
            else: # Should not happen as active_constraints only contains ROD/ROPE
                print(f"Error: Unknown constraint type {conn.connection_type} for {conn.id}. Skipping.")
                Global_b_stabilized[i_constraint] = 0
                continue


            # Rotation matrices (as numpy arrays)
            R_a_np = self._get_rotation_matrix(theta_a)
            R_b_np = self._get_rotation_matrix(theta_b)

            # World connection points (r_AP_world, r_BP_world) and vector d
            r_AP_local_np = np.array([p_a_local.x, p_a_local.y])
            r_AP_world_np = R_a_np @ r_AP_local_np
            P_A_world = r_a + Vector2D(r_AP_world_np[0], r_AP_world_np[1])

            r_BP_local_np = np.array([p_b_local.x, p_b_local.y])
            r_BP_world_np = R_b_np @ r_BP_local_np
            P_B_world = r_b + Vector2D(r_BP_world_np[0], r_BP_world_np[1])
            
            d_vec = P_B_world - P_A_world # Vector2D

            # Local Jacobian components J_k_local (1x6 for the pair A,B)
            # J_k_local = [J_Ax, J_Ay, J_Atheta, J_Bx, J_By, J_Btheta]
            J_k_local_row = np.zeros(6)
            
            # r_AP_world_vec = Vector2D(r_AP_world_np[0], r_AP_world_np[1]) # Not needed directly for J, but for b_accel
            # r_BP_world_vec = Vector2D(r_BP_world_np[0], r_BP_world_np[1])
            
            k_cross_r_AP_world = Vector2D(-r_AP_world_np[1], r_AP_world_np[0]) # k_hat x r_AP_world
            k_cross_r_BP_world = Vector2D(-r_BP_world_np[1], r_BP_world_np[0]) # k_hat x r_BP_world

            J_k_local_row[0] = -2 * d_vec.x
            J_k_local_row[1] = -2 * d_vec.y
            J_k_local_row[2] = -2 * d_vec.dot(k_cross_r_AP_world)
            J_k_local_row[3] =  2 * d_vec.x
            J_k_local_row[4] =  2 * d_vec.y
            J_k_local_row[5] =  2 * d_vec.dot(k_cross_r_BP_world)

            # Populate Global_J
            if not is_a_fixed:
                idx_a_start = entity_to_dof_start_idx[id_a]
                Global_J[i_constraint, idx_a_start : idx_a_start+3] = J_k_local_row[0:3]
            if not is_b_fixed:
                idx_b_start = entity_to_dof_start_idx[id_b]
                Global_J[i_constraint, idx_b_start : idx_b_start+3] = J_k_local_row[3:6]

            # Calculate b_accel for this constraint
            # v_rel_P = (v_B_eff - v_A_eff) + (ω_B_eff * k_hat × r_BP_world - ω_A_eff * k_hat × r_AP_world)
            v_rel_P_term1 = v_b_eff - v_a_eff
            v_rel_P_term2_A = k_cross_r_AP_world * omega_a_eff
            v_rel_P_term2_B = k_cross_r_BP_world * omega_b_eff
            v_rel_P = v_rel_P_term1 + (v_rel_P_term2_B - v_rel_P_term2_A)
            
            term_v_sq = v_rel_P.dot(v_rel_P)
            
            # d · (ω_B^2 r_BP_world - ω_A^2 r_AP_world)
            omega_sq_r_A_term = Vector2D(r_AP_world_np[0], r_AP_world_np[1]) * (omega_a_eff**2)
            omega_sq_r_B_term = Vector2D(r_BP_world_np[0], r_BP_world_np[1]) * (omega_b_eff**2)
            term_omega_sq_r = d_vec.dot(omega_sq_r_B_term - omega_sq_r_A_term)
            
            b_accel_k = -2 * (term_v_sq - term_omega_sq_r)

            # Baumgarte Stabilization terms for this constraint
            C_pos_k = d_vec.dot(d_vec) - L**2
            
            # Jv_k = J_k_global_row @ v_global_np
            # J_k_global_row is Global_J[i_constraint,:]
            Jv_k = Global_J[i_constraint, :] @ v_global_np
            
            Global_b_stabilized[i_constraint] = b_accel_k - self.baumgarte_alpha * C_pos_k - self.baumgarte_beta * Jv_k

        # print(f"[DEBUG_CONSTRAINTSOLVER] Global_J and Global_b_stabilized populated.")
        # print(f"[DEBUG_CONSTRAINTSOLVER] Global_J:\n{Global_J}")
        # print(f"[DEBUG_CONSTRAINTSOLVER] Global_b_stabilized:\n{Global_b_stabilized}")

        # 5. Solve the global KKT system
        # [ Global_M   Global_J^T ] [ dv_dt_global ] = [ Global_F_ext        ]
        # [ Global_J    0         ] [ lambda_global] = [ Global_b_stabilized ]
        
        dv_dt_global_np = np.zeros(N_dof) # Initialize to zeros
        lambda_global_np = np.zeros(N_constraints) # Initialize to zeros

        if N_dof > 0 : # Only solve if there are dynamic degrees of freedom
            KKT_size = N_dof + N_constraints
            Global_KKT_matrix = np.zeros((KKT_size, KKT_size))
            
            # Top-left: Global_M (N_dof x N_dof)
            Global_KKT_matrix[0:N_dof, 0:N_dof] = Global_M
            # Top-right: Global_J^T (N_dof x N_constraints)
            Global_KKT_matrix[0:N_dof, N_dof:KKT_size] = Global_J.T
            # Bottom-left: Global_J (N_constraints x N_dof)
            Global_KKT_matrix[N_dof:KKT_size, 0:N_dof] = Global_J
            # Bottom-right block (N_constraints x N_constraints) is zero for ideal constraints

            Global_rhs = np.zeros(KKT_size)
            Global_rhs[0:N_dof] = Global_F_ext_np
            Global_rhs[N_dof:KKT_size] = Global_b_stabilized

            try:
                # print(f"[DEBUG_CONSTRAINTSOLVER] Attempting to solve KKT system of size {KKT_size}x{KKT_size}")
                # print(f"[DEBUG_CONSTRAINTSOLVER] KKT Matrix:\n{Global_KKT_matrix}")
                # print(f"[DEBUG_CONSTRAINTSOLVER] RHS Vector:\n{Global_rhs}")
                solution_global = np.linalg.solve(Global_KKT_matrix, Global_rhs)
                dv_dt_global_np = solution_global[0:N_dof]
                lambda_global_np = solution_global[N_dof:KKT_size]
                # print(f"[DEBUG_CONSTRAINTSOLVER] KKT system solved.")
                # print(f"[DEBUG_CONSTRAINTSOLVER] dv_dt_global_np:\n{dv_dt_global_np}")
                # print(f"[DEBUG_CONSTRAINTSOLVER] lambda_global_np:\n{lambda_global_np}")

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
        if N_constraints > 0 and np.any(lambda_global_np): # Only if there are lambdas to process
            # print(f"[DEBUG_CONSTRAINTSOLVER] Recording detailed constraint forces. Lambdas: {lambda_global_np}")
            for k_constraint_idx, conn_k in enumerate(active_constraints):
                lambda_k_val = lambda_global_np[k_constraint_idx]
                lambda_k_val = -lambda_k_val # 全局符号反转 (恢复)
                
                # After flipping lambda_k_val, for a rope:
                # - If original lambda was positive (tension), flipped lambda_k_val is now negative. This is the valid tension case.
                # - If original lambda was negative (compression, not possible for rope), flipped lambda_k_val is now positive. Rope should be slack.
                if conn_k.connection_type == ConnectionType.ROPE and lambda_k_val > EPSILON: # Check if flipped lambda indicates original compression
                    # print(f"[DEBUG_CONSTRAINTSOLVER] Rope {conn_k.id} (flipped lambda_k_val {lambda_k_val:.4f} > 0) wants to push. Setting to 0 (slack).")
                    lambda_k_val = 0.0 # Rope cannot push, so set its force to zero.

                if abs(lambda_k_val) < EPSILON: # Skip if lambda is negligible (or was set to 0 for slack rope)
                    continue

                id_a = conn_k.source_entity_id
                id_b = conn_k.target_entity_id
                data_a = entity_data_map[id_a]
                data_b = entity_data_map[id_b]
                p_a_local = conn_k.connection_point_a
                p_b_local = conn_k.connection_point_b

                # Recompute J_k_local (1x6) for this constraint
                # This is needed because Global_J might only contain parts for dynamic bodies,
                # but for force calculation, we need the full local Jacobian.
                # (Code for P_A_world, P_B_world, d_vec, r_AP_world_np, r_BP_world_np, k_cross_r_AP_world, k_cross_r_BP_world)
                # This re-calculation is a bit redundant if values were cached during Global_J build.
                # For now, explicit re-calculation for clarity:
                r_a = data_a['transform'].position; theta_a = data_a['transform'].angle
                r_b = data_b['transform'].position; theta_b = data_b['transform'].angle
                R_a_np_fc = self._get_rotation_matrix(theta_a) # Suffix _fc for force calculation
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

                J_k_local_for_force = np.zeros(6)
                J_k_local_for_force[0] = -2 * d_vec_fc.x
                J_k_local_for_force[1] = -2 * d_vec_fc.y
                J_k_local_for_force[2] = -2 * d_vec_fc.dot(k_cross_r_AP_world_fc)
                J_k_local_for_force[3] =  2 * d_vec_fc.x
                J_k_local_for_force[4] =  2 * d_vec_fc.y
                J_k_local_for_force[5] =  2 * d_vec_fc.dot(k_cross_r_BP_world_fc)

                # Generalized force from this constraint: f_k_gen = J_k_local^T * lambda_k
                f_k_gen = J_k_local_for_force.T * lambda_k_val

                # Force on A from this constraint k
                force_on_A_k = Vector2D(f_k_gen[0], f_k_gen[1])
                # Torque on A: tau_A_k = f_k_gen[2] (not directly used by record_force_detail for linear force)
                acc_a = self.entity_manager.get_component(id_a, ForceAccumulatorComponent)
                if acc_a:
                    force_label_prefix = "CRod" if conn_k.connection_type == ConnectionType.ROD else "RopeTension"
                    acc_a.record_force_detail(
                        force_vector=force_on_A_k,
                        application_point_local=p_a_local,
                        force_type_label=f"{force_label_prefix}_{conn_k.id.hex[:4]}_{id_a.hex[:4]}",
                        is_visualization_only=True
                    )

                # Force on B from this constraint k
                force_on_B_k = Vector2D(f_k_gen[3], f_k_gen[4])
                # Torque on B: tau_B_k = f_k_gen[5]
                acc_b = self.entity_manager.get_component(id_b, ForceAccumulatorComponent)
                if acc_b:
                    force_label_prefix_b = "CRod" if conn_k.connection_type == ConnectionType.ROD else "RopeTension"
                    acc_b.record_force_detail(
                        force_vector=force_on_B_k,
                        application_point_local=p_b_local,
                        force_type_label=f"{force_label_prefix_b}_{conn_k.id.hex[:4]}_{id_b.hex[:4]}",
                        is_visualization_only=True
                    )
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