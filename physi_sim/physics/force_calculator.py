from typing import TYPE_CHECKING, Optional
from physi_sim.core.vector import Vector2D
from physi_sim.core.component import PhysicsBodyComponent, ForceAccumulatorComponent, SurfaceComponent, TransformComponent
# It's good practice for modules like this to not directly depend on global constants from utils
# but rather have them passed in if needed, or rely on systems to provide context.

if TYPE_CHECKING:
    from physi_sim.core.entity_manager import EntityManager, EntityID

class ForceCalculator:
    def __init__(self, gravity_vector: Vector2D): # ForceCalculator can be aware of gravity
        self.gravity_vector = gravity_vector

    def calculate_and_apply_support_force(self,
                                          entity_on_surface_id: 'EntityID',
                                          surface_entity_id: 'EntityID', # For context, not directly used yet
                                          contact_normal: Vector2D, # Normal pointing FROM surface TO entity_on_surface
                                          contact_point_local: Vector2D, # Contact point relative to entity_on_surface's CoM
                                          entity_manager: 'EntityManager') -> Optional[float]:
       print(f"DEBUG_FC_SUPPORT: Called for entity {entity_on_surface_id}, contact_point_local_in: {contact_point_local}") # DEBUG LOG
       applied_support_magnitude: Optional[float] = None
       phys_body = entity_manager.get_component(entity_on_surface_id, PhysicsBodyComponent)
       force_acc = entity_manager.get_component(entity_on_surface_id, ForceAccumulatorComponent)
       # surface_comp = entity_manager.get_component(surface_entity_id, SurfaceComponent) # For later use

       if not phys_body or not force_acc or phys_body.is_fixed:
            return applied_support_magnitude

       # Calculate the total force pushing the entity into the surface along the -contact_normal direction.
       # This should consider all forces currently accumulated on the object (e.g., gravity, spring forces, etc.)
       # that are not yet balanced by a support force from *this* specific contact.
       
       # force_acc.net_force at this point contains forces like gravity, spring forces, etc.
       # We want the component of this net_force that is pushing *into* the surface.
       # contact_normal points FROM surface TO entity.
       # So, force pushing into surface is along -contact_normal.
       
       total_force_on_entity = force_acc.net_force
       
       # The component of the total current force that is directed into the surface
       component_to_counteract = total_force_on_entity.dot(-contact_normal)

       # Add a small check: if the object is actually moving away from the surface along the normal,
       # it might not need a support force. This is often handled by the collision response itself
       # (impulse stops penetration). This function is more for sustained contact.
       # For now, we assume if there's contact and a force pushing in, support is needed.

       if component_to_counteract > 1e-6: # Check if there's a net force pushing the object into the surface
            support_force_magnitude = component_to_counteract
            support_force_vector = contact_normal * support_force_magnitude
            
            if hasattr(force_acc, 'add_force'):
                force_acc.add_force(support_force_vector)
                # Calculate and add torque due to support force
                entity_transform = entity_manager.get_component(entity_on_surface_id, TransformComponent)
                if not entity_transform:
                    print(f"ERROR_FC_SUPPORT: TransformComponent not found for entity {entity_on_surface_id} during torque calculation.")
                    torque_due_to_support = 0.0
                else:
                    lever_arm_world = contact_point_local.rotate(entity_transform.angle)
                    torque_due_to_support = lever_arm_world.cross(support_force_vector)
                
                if hasattr(force_acc, 'add_torque'):
                    force_acc.add_torque(torque_due_to_support)
                else: # Fallback
                    force_acc.net_torque += torque_due_to_support

                # Record the detailed force for visualization
                force_acc.record_force_detail(
                    force_vector=support_force_vector,
                    application_point_local=contact_point_local, # Use the provided local contact point
                    force_type_label=f"Support (from {str(surface_entity_id)})"
                )
                print(f"DEBUG_FC_SUPPORT: Recording support force for entity {entity_on_surface_id}. contact_point_local_used: {contact_point_local}, force: {support_force_vector}, torque: {torque_due_to_support}")
                print(f"DETAILED_LOG: SupportForce: entity={entity_on_surface_id}, force_vec={support_force_vector}, app_point_local={contact_point_local}, torque={torque_due_to_support}")
            else: # Fallback for add_force (should ideally not be needed if ForceAccumulatorComponent is consistent)
                force_acc.net_force += support_force_vector
                # Calculate and add torque due to support force (fallback for net_force)
                # Lever arm rotation should also happen in fallback
                entity_transform_fb = entity_manager.get_component(entity_on_surface_id, TransformComponent)
                if not entity_transform_fb:
                    print(f"ERROR_FC_SUPPORT_FB: TransformComponent not found for entity {entity_on_surface_id} during torque calculation.")
                    torque_due_to_support = 0.0
                else:
                    lever_arm_world_fb = contact_point_local.rotate(entity_transform_fb.angle)
                    torque_due_to_support = lever_arm_world_fb.cross(support_force_vector)
                force_acc.net_torque += torque_due_to_support # Assuming net_torque exists

                # Also record if using fallback, assuming record_force_detail is available
                if hasattr(force_acc, 'record_force_detail'):
                    force_acc.record_force_detail(
                        force_vector=support_force_vector,
                        application_point_local=contact_point_local, # Use the provided local contact point
                        force_type_label=f"Support (from {str(surface_entity_id)})"
                    )
                    print(f"DEBUG_FC_SUPPORT: Recording support force (fallback) for entity {entity_on_surface_id}. contact_point_local_used: {contact_point_local}, force: {support_force_vector}, torque: {torque_due_to_support}")
                    print(f"DETAILED_LOG: SupportForce (fallback): entity={entity_on_surface_id}, force_vec={support_force_vector}, app_point_local={contact_point_local}, torque={torque_due_to_support}")
            
            applied_support_magnitude = support_force_magnitude
            # print(f"DEBUG: Applied support force {support_force_vector} to entity {entity_on_surface_id} from surface {surface_entity_id}")
        
       return applied_support_magnitude


    def calculate_and_apply_friction_force(self,
                                           entity_on_surface_id: 'EntityID',
                                           surface_entity_id: 'EntityID',
                                           contact_normal: Vector2D, # Normal pointing FROM surface TO entity_on_surface
                                           support_force_magnitude: float,
                                           contact_point_local: Vector2D, # Contact point relative to entity_on_surface's CoM
                                           entity_manager: 'EntityManager',
                                           dt: float): # dt is needed for a simplified static friction model
        print(f"DEBUG_FC_FRICTION: Called for entity {entity_on_surface_id}, contact_point_local_in: {contact_point_local}, support_F_mag: {support_force_magnitude}, contact_norm: {contact_normal}") # DEBUG LOG

        phys_body_obj = entity_manager.get_component(entity_on_surface_id, PhysicsBodyComponent)
        force_acc_obj = entity_manager.get_component(entity_on_surface_id, ForceAccumulatorComponent)
        
        phys_body_surf = entity_manager.get_component(surface_entity_id, PhysicsBodyComponent) # For its friction coeffs
        surface_comp = entity_manager.get_component(surface_entity_id, SurfaceComponent)     # For overrides

        if not phys_body_obj or not force_acc_obj or phys_body_obj.is_fixed or support_force_magnitude <= 0:
            print(f"DEBUG_FC: Friction calc aborted. phys_body_obj={phys_body_obj is not None}, force_acc_obj={force_acc_obj is not None}, is_fixed={phys_body_obj.is_fixed if phys_body_obj else 'N/A'}, support_F_mag={support_force_magnitude}") # DEBUG LOG
            return

        # Determine friction coefficients
        # Priority: SurfaceComponent override -> Surface's PhysicsBodyComponent -> Object's PhysicsBodyComponent (less ideal)
        static_friction_coeff = 0.0
        dynamic_friction_coeff = 0.0

        if surface_comp and surface_comp.override_static_friction is not None:
            static_friction_coeff = surface_comp.override_static_friction
        elif phys_body_surf:
            static_friction_coeff = phys_body_surf.static_friction_coefficient
        else: # Fallback to object's own friction, or a default
            static_friction_coeff = phys_body_obj.static_friction_coefficient

        if surface_comp and surface_comp.override_dynamic_friction is not None:
            dynamic_friction_coeff = surface_comp.override_dynamic_friction
        elif phys_body_surf:
            dynamic_friction_coeff = phys_body_surf.dynamic_friction_coefficient
        else: # Fallback
            dynamic_friction_coeff = phys_body_obj.dynamic_friction_coefficient
        print(f"DEBUG_FC: Friction coeffs: static={static_friction_coeff}, dynamic={dynamic_friction_coeff}") # DEBUG LOG

        # Relative velocity calculation
        # Velocity of the contact point on obj relative to contact point on surf
        # For now, assume point contact and use CoM velocities
        vel_obj = phys_body_obj.velocity
        vel_surf = Vector2D(0,0) # Default if surface has no physics body or is fixed
        if phys_body_surf and not phys_body_surf.is_fixed:
            vel_surf = phys_body_surf.velocity
        
        relative_velocity = vel_obj - vel_surf
        
        # Tangential velocity vector
        velocity_along_normal_vec = contact_normal * relative_velocity.dot(contact_normal)
        tangential_velocity_vector = relative_velocity - velocity_along_normal_vec
        tangential_speed = tangential_velocity_vector.magnitude()
        print(f"DEBUG_FC: Relative vel: {relative_velocity}, Tangential vel vec: {tangential_velocity_vector}, Tangential speed: {tangential_speed}") # DEBUG LOG

        friction_force_vector = Vector2D(0,0)
        VELOCITY_THRESHOLD = 0.05 # Small speed to consider as "at rest" for static friction

        if tangential_speed < VELOCITY_THRESHOLD:
            # --- Static Friction ---
            print(f"DEBUG_FC: Attempting Static Friction (tangential_speed {tangential_speed} < threshold {VELOCITY_THRESHOLD})") # DEBUG LOG
            force_to_stop_tangential_motion_magnitude = (tangential_speed / dt) * phys_body_obj.mass if dt > 0 else float('inf')
            max_static_friction_magnitude = static_friction_coeff * support_force_magnitude
            print(f"DEBUG_FC: Static fric: force_to_stop_mag={force_to_stop_tangential_motion_magnitude}, max_static_mag={max_static_friction_magnitude}") # DEBUG LOG

            if force_to_stop_tangential_motion_magnitude < max_static_friction_magnitude:
                print(f"DEBUG_FC: Applying static friction (force to stop)") # DEBUG LOG
                if tangential_speed > 1e-6: # Avoid normalizing zero vector
                     friction_force_vector = -tangential_velocity_vector.normalize() * force_to_stop_tangential_motion_magnitude
                # else: it's already stopped tangentially, no static friction needed from this model
            else:
                print(f"DEBUG_FC: Static friction limit exceeded, applying dynamic friction instead.") # DEBUG LOG
                # Not enough static friction to hold, it will slide (becomes dynamic)
                if tangential_speed > 1e-6:
                    friction_force_vector = -tangential_velocity_vector.normalize() * (dynamic_friction_coeff * support_force_magnitude)
        else:
            # --- Dynamic (Kinetic) Friction ---
            print(f"DEBUG_FC: Applying dynamic friction (tangential_speed {tangential_speed} >= threshold {VELOCITY_THRESHOLD})") # DEBUG LOG
            dynamic_friction_magnitude = dynamic_friction_coeff * support_force_magnitude
            if tangential_speed > 1e-6: # Avoid normalizing zero vector
                friction_force_vector = -tangential_velocity_vector.normalize() * dynamic_friction_magnitude
        
        print(f"DEBUG_FC: Calculated friction_force_vector: {friction_force_vector}") # DEBUG LOG
        if friction_force_vector.magnitude_squared() > 1e-6: # Only apply if non-zero
            print(f"DEBUG_FC: Applying friction force: {friction_force_vector} to {entity_on_surface_id}") # DEBUG LOG
            if hasattr(force_acc_obj, 'add_force'):
                force_acc_obj.add_force(friction_force_vector)
                
                # Calculate and add torque due to friction
                entity_transform_friction = entity_manager.get_component(entity_on_surface_id, TransformComponent)
                if not entity_transform_friction:
                    print(f"ERROR_FC_FRICTION: TransformComponent not found for entity {entity_on_surface_id} during torque calculation.")
                    torque_due_to_friction = 0.0
                else:
                    lever_arm_world_friction = contact_point_local.rotate(entity_transform_friction.angle)
                    torque_due_to_friction = lever_arm_world_friction.cross(friction_force_vector)

                if hasattr(force_acc_obj, 'add_torque'):
                    force_acc_obj.add_torque(torque_due_to_friction)
                    print(f"DEBUG_FC: Applying torque_due_to_friction: {torque_due_to_friction} to {entity_on_surface_id} using local point {contact_point_local} (rotated lever: {lever_arm_world_friction if entity_transform_friction else 'N/A'})")
                else: # Fallback
                    force_acc_obj.net_torque += torque_due_to_friction
                                
                # Record the detailed force for visualization
                force_acc_obj.record_force_detail(
                    force_vector=friction_force_vector,
                    application_point_local=contact_point_local, # Use the provided local contact point
                    force_type_label=f"Friction (from {str(surface_entity_id)})"
                )
                print(f"DEBUG_FC_FRICTION: Recording friction force for entity {entity_on_surface_id}. contact_point_local_used: {contact_point_local}, force: {friction_force_vector}, torque: {torque_due_to_friction}")
                print(f"DETAILED_LOG: FrictionForce: entity={entity_on_surface_id}, force_vec={friction_force_vector}, app_point_local={contact_point_local}, torque={torque_due_to_friction}")
            else: # Fallback for add_force
                force_acc_obj.net_force += friction_force_vector
                # Also calculate and add torque in fallback if possible
                entity_transform_friction_fb = entity_manager.get_component(entity_on_surface_id, TransformComponent)
                if not entity_transform_friction_fb:
                    print(f"ERROR_FC_FRICTION_FB: TransformComponent not found for entity {entity_on_surface_id} during torque calculation.")
                    torque_due_to_friction = 0.0
                else:
                    lever_arm_world_friction_fb = contact_point_local.rotate(entity_transform_friction_fb.angle)
                    torque_due_to_friction = lever_arm_world_friction_fb.cross(friction_force_vector)
                force_acc_obj.net_torque += torque_due_to_friction
                print(f"DEBUG_FC: Applying torque_due_to_friction (fallback): {torque_due_to_friction} to {entity_on_surface_id} using local point {contact_point_local} (rotated lever: {lever_arm_world_friction_fb if entity_transform_friction_fb else 'N/A'})")
                # Also record if using fallback, assuming record_force_detail is available
                if hasattr(force_acc_obj, 'record_force_detail'):
                    force_acc_obj.record_force_detail(
                        force_vector=friction_force_vector,
                        application_point_local=contact_point_local, # Use the provided local contact point
                        force_type_label=f"Friction (from {str(surface_entity_id)})"
                    )
                    print(f"DEBUG_FC_FRICTION: Recording friction force (fallback) for entity {entity_on_surface_id}. contact_point_local_used: {contact_point_local}, force: {friction_force_vector}, torque: {torque_due_to_friction}")
                    print(f"DETAILED_LOG: FrictionForce (fallback): entity={entity_on_surface_id}, force_vec={friction_force_vector}, app_point_local={contact_point_local}, torque={torque_due_to_friction}")
            # print(f"Applied friction {friction_force_vector} to {entity_on_surface_id}, tang_speed: {tangential_speed}")