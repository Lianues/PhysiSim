from typing import TYPE_CHECKING

from physi_sim.core.system import System
from physi_sim.core.component import SpringComponent, TransformComponent, PhysicsBodyComponent, ForceAccumulatorComponent
from physi_sim.core.vector import Vector2D

if TYPE_CHECKING:
    from physi_sim.core.entity_manager import EntityManager


class SpringSystem(System):
    def __init__(self, entity_manager: 'EntityManager'):
        super().__init__(entity_manager)

    def update(self, dt: float) -> None:
        # Use get_all_independent_components_of_type to fetch SpringComponent instances
        spring_components = self.entity_manager.get_all_independent_components_of_type(SpringComponent)
        
        if not spring_components: # Check if the list is empty
            return
            
        for spring_comp in spring_components:
            entity_a_id = spring_comp.entity_a_id
            entity_b_id = spring_comp.entity_b_id

            # Check for entity existence first
            spring_identifier = spring_comp.id if hasattr(spring_comp, 'id') else f"between {entity_a_id} and {entity_b_id}"

            if entity_a_id not in self.entity_manager.entities:
                print(f"Warning: SpringSystem skipping spring {spring_identifier} because entity A (ID: {entity_a_id}) not found.")
                continue
            
            if entity_b_id not in self.entity_manager.entities:
                print(f"Warning: SpringSystem skipping spring {spring_identifier} because entity B (ID: {entity_b_id}) not found.")
                continue

            # Get necessary components from the entities
            transform_a = self.entity_manager.get_component(entity_a_id, TransformComponent)
            transform_b = self.entity_manager.get_component(entity_b_id, TransformComponent)
            physics_a = self.entity_manager.get_component(entity_a_id, PhysicsBodyComponent)
            physics_b = self.entity_manager.get_component(entity_b_id, PhysicsBodyComponent)
            force_acc_a = self.entity_manager.get_component(entity_a_id, ForceAccumulatorComponent)
            force_acc_b = self.entity_manager.get_component(entity_b_id, ForceAccumulatorComponent)

            if not all([transform_a, transform_b, physics_a, physics_b, force_acc_a, force_acc_b]):
                # One or more components are missing, skip this spring
                print(f"Warning: SpringSystem skipping spring {spring_identifier} due to missing required components on one or both entities.")
                continue

            # Calculate world anchor points considering entity rotation
            # r_world = R_body * r_local
            rotated_anchor_a = spring_comp.anchor_a.rotate(transform_a.angle)
            rotated_anchor_b = spring_comp.anchor_b.rotate(transform_b.angle)
            world_anchor_a = transform_a.position + rotated_anchor_a
            world_anchor_b = transform_b.position + rotated_anchor_b

            # Calculate spring's current length and direction
            current_vector = world_anchor_b - world_anchor_a
            current_length = current_vector.magnitude()
            
            direction_vector = Vector2D(0,0)
            # Use a small epsilon to avoid division by zero or near-zero
            epsilon = 1e-9 # Reverted epsilon back, though it wasn't the solution
            if current_length > epsilon:
                direction_vector = current_vector / current_length
            
            # Calculate spring force (Hooke's Law) - F = -k * displacement_vector
            displacement_scalar = current_length - spring_comp.rest_length # Positive if stretched, negative if compressed
            spring_force_scalar = spring_comp.stiffness_k * displacement_scalar # This is signed force magnitude (+ if stretched, - if compressed)

            force_on_b = direction_vector * (-spring_force_scalar) # Corrected direction
            force_on_a = -force_on_b # Newton's 3rd law ensures force on A is opposite

            # Calculate damping force (optional) - Changed Model
            if spring_comp.damping_c > 0:
                velocity_a = physics_a.velocity
                velocity_b = physics_b.velocity
                relative_velocity = velocity_b - velocity_a
                
                # New Damping Model: Oppose the full relative velocity vector
                # F_damping = -c * v_relative
                # F_damping = -c * v_relative
                damping_force_on_b = relative_velocity * (-spring_comp.damping_c)
                damping_force_on_a = -damping_force_on_b # Damping forces are also equal and opposite

                # Add damping forces to the total forces
                force_on_a += damping_force_on_a
                force_on_b += damping_force_on_b
            
            # Calculate and apply torques
            if not physics_a.is_fixed:
                # Torque on A: r_a x F_on_a
                # r_a is the vector from CoM of A to the anchor point on A (already rotated_anchor_a)
                if spring_comp.anchor_a.x != 0 or spring_comp.anchor_a.y != 0:
                    torque_on_a = rotated_anchor_a.x * force_on_a.y - rotated_anchor_a.y * force_on_a.x
                    force_acc_a.net_torque += torque_on_a
                force_acc_a.add_force(force_on_a)
                if hasattr(force_acc_a, 'record_force_detail'):
                    spring_id_label = f"Spring ({spring_comp.id if hasattr(spring_comp, 'id') else 'Unknown'})"
                    force_acc_a.record_force_detail(
                        force_vector=force_on_a,
                        application_point_local=spring_comp.anchor_a, # Use the local anchor point
                        force_type_label=spring_id_label
                    )

            if not physics_b.is_fixed:
                # Torque on B: r_b x F_on_b
                # r_b is the vector from CoM of B to the anchor point on B (already rotated_anchor_b)
                if spring_comp.anchor_b.x != 0 or spring_comp.anchor_b.y != 0:
                    torque_on_b = rotated_anchor_b.x * force_on_b.y - rotated_anchor_b.y * force_on_b.x
                    force_acc_b.net_torque += torque_on_b
                force_acc_b.add_force(force_on_b)
                if hasattr(force_acc_b, 'record_force_detail'):
                    spring_id_label = f"Spring ({spring_comp.id if hasattr(spring_comp, 'id') else 'Unknown'})"
                    force_acc_b.record_force_detail(
                        force_vector=force_on_b,
                        application_point_local=spring_comp.anchor_b, # Use the local anchor point
                        force_type_label=spring_id_label
                    )