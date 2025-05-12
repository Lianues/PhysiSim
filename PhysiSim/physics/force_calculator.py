from typing import TYPE_CHECKING, Optional
from physi_sim.core.vector import Vector2D
from physi_sim.core.component import PhysicsBodyComponent, ForceAccumulatorComponent, SurfaceComponent, TransformComponent
from physi_sim.core.utils import EPSILON # Import EPSILON
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
      # # print(f"DEBUG_FC_SUPPORT: Called for entity {entity_on_surface_id}, contact_point_local_in: {contact_point_local}") # DEBUG LOG
      # print(f"LOG_FC_SUPPORT_ENTRY: Entity={entity_on_surface_id}, Surface={surface_entity_id}, Normal(S->E)={contact_normal}, CP_Local={contact_point_local}")
      # print(f"DEBUG_FC_PROCESS: Processing entities: entity_on_surface_id (A)={entity_on_surface_id}, surface_entity_id (B)={surface_entity_id}") # LOG
      
      # DEBUG LOG START: ForceCalculator.calculate_and_apply_support_force (REMOVED)
      # print(f"[DEBUG FC_Support] Called for entity_on_surface: {entity_on_surface_id} (potential ball) on surface: {surface_entity_id} (potential wall)")
      # print(f"  Contact Info: Normal (Surface->Entity)={contact_normal}, ContactPointLocal (on entity)={contact_point_local}")
      # DEBUG LOG END

      applied_support_magnitude: Optional[float] = None
      phys_body = entity_manager.get_component(entity_on_surface_id, PhysicsBodyComponent)
      force_acc = entity_manager.get_component(entity_on_surface_id, ForceAccumulatorComponent)
      # surface_comp = entity_manager.get_component(surface_entity_id, SurfaceComponent) # For later use

      if not phys_body or not force_acc or phys_body.is_fixed:
           # print(f"LOG_FC_SUPPORT_ABORT: Entity={entity_on_surface_id}, phys_body={phys_body is not None}, force_acc={force_acc is not None}, is_fixed={phys_body.is_fixed if phys_body else 'N/A'}")
           return applied_support_magnitude

      # Calculate the total force pushing the entity into the surface along the -contact_normal direction.
      # This should consider all forces currently accumulated on the object (e.g., gravity, spring forces, etc.)
      # that are not yet balanced by a support force from *this* specific contact.
      
      # force_acc.net_force at this point contains forces like gravity, spring forces, etc.
      # We want the component of this net_force that is pushing *into* the surface.
      # contact_normal points FROM surface TO entity.
      # So, force pushing into surface is along -contact_normal.
      
      total_force_on_entity = force_acc.net_force
      # print(f"DEBUG_FC_NET_FORCE: Entity A ({entity_on_surface_id}) force_accumulator.net_force before support calc: {total_force_on_entity}") # LOG
      # DEBUG LOG START: ForceCalculator.calculate_and_apply_support_force (REMOVED)
      # print(f"  Entity {entity_on_surface_id}: Current force_accumulator.net_force (before this support calc) = {total_force_on_entity}")
      # DEBUG LOG END
      # # print(f"FC_CALC_SUPPORT_DETAILS: Entity {entity_on_surface_id} - total_force_on_entity (from force_acc.net_force): {total_force_on_entity}")
      # # print(f"FC_CALC_SUPPORT_DETAILS: Entity {entity_on_surface_id} - contact_normal (Surface->Entity, as_param): {contact_normal}")
      
      # contact_normal points FROM surface TO entity (e.g., upwards (0, -Y_val) if Y is upwards positive).
      # total_force_on_entity is the sum of external forces like gravity (e.g., downwards (0, -mg)).
      
      # Calculate the projection of total_force_on_entity onto contact_normal.
      # If total_force_on_entity is primarily gravity (downwards) and contact_normal is upwards,
      # this projection will be negative. Its absolute value is the magnitude of force component
      # that needs to be counteracted by the support force.
      projection_on_normal = total_force_on_entity.dot(contact_normal)
      # print(f"LOG_FC_SUPPORT_CALC: Entity={entity_on_surface_id}, TotalForce={total_force_on_entity}, ProjOnNormal={projection_on_normal:.4f}")

      # Add a small check: if the object is actually moving away from the surface along the normal,
      # it might not need a support force. This is often handled by the collision response itself
      # (impulse stops penetration). This function is more for sustained contact.
      # For now, we assume if there's contact and a force pushing in, support is needed.

      # If projection_on_normal is negative, it means total_force_on_entity has a component
      # in the direction OPPOSITE to contact_normal (i.e., pushing INTO the surface).
      support_condition_met = projection_on_normal < -EPSILON
      # print(f"LOG_FC_SUPPORT_CONDITION: Entity={entity_on_surface_id}, Proj={projection_on_normal:.4f}, EPSILON={EPSILON}, ConditionMet={support_condition_met}")

      if support_condition_met:
           support_force_magnitude = -projection_on_normal # Magnitude of the force to counteract (must be positive)
           support_force_vector = contact_normal * support_force_magnitude # Support force acts along contact_normal
           # print(f"DEBUG_FC_CALC_FORCE: Calculated normal_force_vec (support_force_vector) for entity A ({entity_on_surface_id}): {support_force_vector}") # LOG
           # # print(f"FC_CALC_SUPPORT_DETAILS: Entity {entity_on_surface_id} - Support needed. Magnitude: {support_force_magnitude}, Vector: {support_force_vector}")
           
           # DEBUG LOG START: ForceCalculator.calculate_and_apply_support_force (REMOVED)
           # print(f"  Calculated Support Force for {entity_on_surface_id}: Vector={support_force_vector}, Magnitude={support_force_magnitude:.4f}")
           # DEBUG LOG END

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
               # print(f"DEBUG_FC_RECORD_DETAIL: Recorded ForceDetail to entity A ({entity_on_surface_id}): Vector={support_force_vector}, PointLocal={contact_point_local}, Label='Support (from {str(surface_entity_id)})'") # LOG
               # DEBUG LOG START: ForceCalculator.calculate_and_apply_support_force (REMOVED)
               # print(f"  Support force for {entity_on_surface_id} recorded to detailed_forces. Label: 'Support (from {str(surface_entity_id)})'")
               # DEBUG LOG END
               # print(f"LOG_FC_POST_RECORD_SUPPORT: TargetEntity={entity_on_surface_id}, detailed_forces_count={len(force_acc.detailed_forces)}, last_force_label='{force_acc.detailed_forces[-1].force_type_label if force_acc.detailed_forces else 'N/A'}'")
               # More detailed log for applied force info
               force_info_tuple = (support_force_vector, contact_point_local, f"Support (from {str(surface_entity_id)})", torque_due_to_support, entity_on_surface_id, surface_entity_id)
               # print(f"LOG_FORCE_APPLIED: Type=Support, Target={entity_on_surface_id}, Source={surface_entity_id}, ForceVec={support_force_vector}, AppPointLocal={contact_point_local}, Torque={torque_due_to_support:.4f}")

               # Apply reaction force to the surface entity if it's not fixed
               phys_body_surface = entity_manager.get_component(surface_entity_id, PhysicsBodyComponent)
               if phys_body_surface and not phys_body_surface.is_fixed:
                   force_acc_surface = entity_manager.get_component(surface_entity_id, ForceAccumulatorComponent)
                   surface_transform = entity_manager.get_component(surface_entity_id, TransformComponent)
                   if force_acc_surface and surface_transform:
                       reaction_force_on_surface = -support_force_vector
                       # Contact point is the same in world space. Convert to surface's local space.
                       # contact_point_world = entity_transform.position + contact_point_local.rotate(entity_transform.angle) # This is contact_point_local for entity_on_surface
                                               
                       # To get contact_point_world correctly if entity_transform was None
                       contact_point_world_for_reaction: Vector2D
                       if entity_transform: # Should exist if we reached here for a non-fixed body
                            contact_point_world_for_reaction = entity_transform.position + lever_arm_world # lever_arm_world is contact_point_local rotated
                       else: # Fallback, less accurate if torque was 0 due to missing transform
                            contact_point_world_for_reaction = phys_body.position + contact_point_local # Approximation

                       offset_world_surface = contact_point_world_for_reaction - surface_transform.position
                       app_point_local_surface = offset_world_surface.rotate(-surface_transform.angle)
                       
                       reaction_torque_on_surface = app_point_local_surface.rotate(surface_transform.angle).cross(reaction_force_on_surface)


                       force_acc_surface.add_force(reaction_force_on_surface)
                       force_acc_surface.add_torque(reaction_torque_on_surface)
                       force_acc_surface.record_force_detail(
                           force_vector=reaction_force_on_surface,
                           application_point_local=app_point_local_surface,
                           force_type_label=f"Pressure (from {str(entity_on_surface_id)})" # MODIFIED_LABEL
                       )
                       # print(f"LOG_FC_POST_RECORD_REACTION_SUPPORT: TargetEntity={surface_entity_id}, detailed_forces_count={len(force_acc_surface.detailed_forces)}, last_force_label='{force_acc_surface.detailed_forces[-1].force_type_label if force_acc_surface.detailed_forces else 'N/A'}'")
                       # print(f"LOG_REACTION_FORCE_APPLIED: Type=ReactionToSupport, Target={surface_entity_id}, Source={entity_on_surface_id}, ForceVec={reaction_force_on_surface}, AppPointLocal={app_point_local_surface}, Torque={reaction_torque_on_surface:.4f}")
               
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
                   force_info_tuple_fb = (support_force_vector, contact_point_local, f"Support (from {str(surface_entity_id)})", torque_due_to_support, entity_on_surface_id, surface_entity_id)
                   # print(f"LOG_FORCE_APPLIED_FB: Type=Support, Target(EntityOnSurface)={entity_on_surface_id}, Source(Surface)={surface_entity_id}, ForceVec={support_force_vector}, AppPointLocal={contact_point_local}, Torque={torque_due_to_support:.4f}")
                   # Apply reaction force to the surface entity if it's not fixed (FALLBACK PATH)
                   phys_body_surface_fb = entity_manager.get_component(surface_entity_id, PhysicsBodyComponent)
                   if phys_body_surface_fb and not phys_body_surface_fb.is_fixed:
                       force_acc_surface_fb = entity_manager.get_component(surface_entity_id, ForceAccumulatorComponent)
                       surface_transform_fb = entity_manager.get_component(surface_entity_id, TransformComponent)
                       if force_acc_surface_fb and surface_transform_fb:
                           reaction_force_on_surface_fb = -support_force_vector
                           contact_point_world_for_reaction_fb: Vector2D
                           if entity_transform_fb:
                                contact_point_world_for_reaction_fb = entity_transform_fb.position + lever_arm_world_fb
                           else: # Fallback, less accurate
                                contact_point_world_for_reaction_fb = phys_body.position + contact_point_local

                           offset_world_surface_fb = contact_point_world_for_reaction_fb - surface_transform_fb.position
                           app_point_local_surface_fb = offset_world_surface_fb.rotate(-surface_transform_fb.angle)
                           reaction_torque_on_surface_fb = app_point_local_surface_fb.rotate(surface_transform_fb.angle).cross(reaction_force_on_surface_fb)
                           
                           force_acc_surface_fb.net_force += reaction_force_on_surface_fb # Using net_force directly in fallback
                           force_acc_surface_fb.net_torque += reaction_torque_on_surface_fb
                           if hasattr(force_acc_surface_fb, 'record_force_detail'):
                               force_acc_surface_fb.record_force_detail(
                                   force_vector=reaction_force_on_surface_fb,
                                   application_point_local=app_point_local_surface_fb,
                                   force_type_label=f"Pressure_FB (from {str(entity_on_surface_id)})" # MODIFIED_LABEL
                               )
                           # print(f"LOG_REACTION_FORCE_APPLIED_FB: Type=ReactionToSupport_FB, Target(Surface)={surface_entity_id}, Source(EntityOnSurface)={entity_on_surface_id}, ForceVec={reaction_force_on_surface_fb}, AppPointLocal={app_point_local_surface_fb}, Torque={reaction_torque_on_surface_fb:.4f}")

           applied_support_magnitude = support_force_magnitude
           # # print(f"DEBUG: Applied support force {support_force_vector} to entity {entity_on_surface_id} from surface {surface_entity_id}")
       
      return applied_support_magnitude


    def calculate_and_apply_friction_force(self,
                                           entity_on_surface_id: 'EntityID',
                                           surface_entity_id: 'EntityID',
                                           contact_normal: Vector2D, # Normal pointing FROM surface TO entity_on_surface
                                           support_force_magnitude: float,
                                           contact_point_local: Vector2D, # Contact point relative to entity_on_surface's CoM
                                           entity_manager: 'EntityManager',
                                           dt: float): # dt is needed for a simplified static friction model
       # # print(f"DEBUG_FC_FRICTION: Called for entity {entity_on_surface_id}, contact_point_local_in: {contact_point_local}, support_F_mag: {support_force_magnitude}, contact_norm: {contact_normal}") # DEBUG LOG
       # print(f"LOG_FC_FRICTION_ENTRY: Entity={entity_on_surface_id}, Surface={surface_entity_id}, Normal(S->E)={contact_normal}, SupportMag={support_force_magnitude:.4f}, CP_Local={contact_point_local}, dt={dt}")

       phys_body_obj = entity_manager.get_component(entity_on_surface_id, PhysicsBodyComponent)
       force_acc_obj = entity_manager.get_component(entity_on_surface_id, ForceAccumulatorComponent)
       
       phys_body_surf = entity_manager.get_component(surface_entity_id, PhysicsBodyComponent) # For its friction coeffs
       surface_comp = entity_manager.get_component(surface_entity_id, SurfaceComponent)     # For overrides

       if not phys_body_obj or not force_acc_obj or phys_body_obj.is_fixed or support_force_magnitude <= EPSILON: # Changed to <= EPSILON
           # print(f"LOG_FC_FRICTION_ABORT: Entity={entity_on_surface_id}, phys_body={phys_body_obj is not None}, force_acc={force_acc_obj is not None}, is_fixed={phys_body_obj.is_fixed if phys_body_obj else 'N/A'}, support_F_mag={support_force_magnitude:.4f}")
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
       # # print(f"DEBUG_FC: Friction coeffs: static={static_friction_coeff}, dynamic={dynamic_friction_coeff}") # DEBUG LOG

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
       # # print(f"DEBUG_FC: Relative vel: {relative_velocity}, Tangential vel vec: {tangential_velocity_vector}, Tangential speed: {tangential_speed}") # DEBUG LOG

       friction_force_vector = Vector2D(0,0)
       VELOCITY_THRESHOLD = 0.05 # Small speed to consider as "at rest" for static friction
       friction_type = "None"

       if tangential_speed < VELOCITY_THRESHOLD:
           friction_type = "StaticAttempt"
           # --- Static Friction ---
           # # print(f"DEBUG_FC: Attempting Static Friction (tangential_speed {tangential_speed} < threshold {VELOCITY_THRESHOLD})") # DEBUG LOG
           force_to_stop_tangential_motion_magnitude = (tangential_speed / dt) * phys_body_obj.mass if dt > EPSILON else float('inf') # dt > EPSILON
           max_static_friction_magnitude = static_friction_coeff * support_force_magnitude
           # # print(f"DEBUG_FC: Static fric: force_to_stop_mag={force_to_stop_tangential_motion_magnitude}, max_static_mag={max_static_friction_magnitude}") # DEBUG LOG

           if force_to_stop_tangential_motion_magnitude < max_static_friction_magnitude:
               friction_type = "StaticApplied"
               # # print(f"DEBUG_FC: Applying static friction (force to stop)") # DEBUG LOG
               if tangential_speed > EPSILON: # Avoid normalizing zero vector, changed from 1e-6
                    friction_force_vector = -tangential_velocity_vector.normalize() * force_to_stop_tangential_motion_magnitude
               # else: it's already stopped tangentially, no static friction needed from this model
           else:
               friction_type = "StaticExceededToDynamic"
               # # print(f"DEBUG_FC: Static friction limit exceeded, applying dynamic friction instead.") # DEBUG LOG
               # Not enough static friction to hold, it will slide (becomes dynamic)
               if tangential_speed > EPSILON: # Changed from 1e-6
                   friction_force_vector = -tangential_velocity_vector.normalize() * (dynamic_friction_coeff * support_force_magnitude)
       else:
           friction_type = "DynamicApplied"
           # --- Dynamic (Kinetic) Friction ---
           # # print(f"DEBUG_FC: Applying dynamic friction (tangential_speed {tangential_speed} >= threshold {VELOCITY_THRESHOLD})") # DEBUG LOG
           dynamic_friction_magnitude = dynamic_friction_coeff * support_force_magnitude
           if tangential_speed > EPSILON: # Avoid normalizing zero vector, changed from 1e-6
               friction_force_vector = -tangential_velocity_vector.normalize() * dynamic_friction_magnitude
       
       # print(f"LOG_FC_FRICTION_CALC: Entity={entity_on_surface_id}, Type={friction_type}, TanSpeed={tangential_speed:.4f}, StaticCoeff={static_friction_coeff:.3f}, DynCoeff={dynamic_friction_coeff:.3f}, FricVec={friction_force_vector}")
       # # print(f"DEBUG_FC: Calculated friction_force_vector: {friction_force_vector}") # DEBUG LOG
       if friction_force_vector.magnitude_squared() > EPSILON * EPSILON: # Only apply if non-zero, changed from 1e-6
           # # print(f"DEBUG_FC: Applying friction force: {friction_force_vector} to {entity_on_surface_id}") # DEBUG LOG
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
                   # # print(f"DEBUG_FC: Applying torque_due_to_friction: {torque_due_to_friction} to {entity_on_surface_id} using local point {contact_point_local} (rotated lever: {lever_arm_world_friction if entity_transform_friction else 'N/A'})")
               else: # Fallback
                   force_acc_obj.net_torque += torque_due_to_friction
                               
               # Record the detailed force for visualization
               force_acc_obj.record_force_detail(
                   force_vector=friction_force_vector,
                   application_point_local=contact_point_local, # Use the provided local contact point
                   force_type_label=f"Friction (from {str(surface_entity_id)})"
               )
               # print(f"LOG_FC_POST_RECORD_FRICTION: TargetEntity={entity_on_surface_id}, detailed_forces_count={len(force_acc_obj.detailed_forces)}, last_force_label='{force_acc_obj.detailed_forces[-1].force_type_label if force_acc_obj.detailed_forces else 'N/A'}'")
               force_info_tuple_fric = (friction_force_vector, contact_point_local, f"Friction (from {str(surface_entity_id)})", torque_due_to_friction, entity_on_surface_id, surface_entity_id)
               # Ensure Target is entity_on_surface_id for this block
               # print(f"LOG_FORCE_APPLIED: Type=Friction, Target={entity_on_surface_id}, Source={surface_entity_id}, ForceVec={friction_force_vector}, AppPointLocal={contact_point_local}, Torque={torque_due_to_friction:.4f}")

               # Apply reaction friction force to the surface entity
               phys_body_surface_fric = entity_manager.get_component(surface_entity_id, PhysicsBodyComponent)
               if phys_body_surface_fric and not phys_body_surface_fric.is_fixed:
                   force_acc_surface_fric = entity_manager.get_component(surface_entity_id, ForceAccumulatorComponent)
                   surface_transform_fric = entity_manager.get_component(surface_entity_id, TransformComponent)
                   if force_acc_surface_fric and surface_transform_fric:
                       reaction_friction_force = -friction_force_vector
                       
                       # Calculate contact_point_world for reaction force application point
                       contact_point_world_for_reaction_fric: Vector2D
                       if entity_transform_friction: # Should exist
                           contact_point_world_for_reaction_fric = entity_transform_friction.position + lever_arm_world_friction # lever_arm_world_friction from friction torque calc
                       else: # Fallback
                           contact_point_world_for_reaction_fric = phys_body_obj.position + contact_point_local

                       offset_world_surface_fric = contact_point_world_for_reaction_fric - surface_transform_fric.position
                       app_point_local_surface_fric = offset_world_surface_fric.rotate(-surface_transform_fric.angle)
                       reaction_friction_torque = app_point_local_surface_fric.rotate(surface_transform_fric.angle).cross(reaction_friction_force)

                       # Ensure we are using force_acc_surface_fric for the surface entity
                       force_acc_surface_fric.add_force(reaction_friction_force)
                       force_acc_surface_fric.add_torque(reaction_friction_torque)
                       force_acc_surface_fric.record_force_detail( # This records to force_acc_surface_fric (for surface_entity_id)
                           force_vector=reaction_friction_force,
                           application_point_local=app_point_local_surface_fric,
                           force_type_label=f"Friction (by {str(entity_on_surface_id)})" # MODIFIED_LABEL
                       )
                       # Ensure TargetEntity is surface_entity_id for this block
                       # print(f"LOG_FC_POST_RECORD_REACTION_FRICTION: TargetEntity={surface_entity_id}, detailed_forces_count={len(force_acc_surface_fric.detailed_forces)}, last_force_label='{force_acc_surface_fric.detailed_forces[-1].force_type_label if force_acc_surface_fric.detailed_forces else 'N/A'}'")
                       # Ensure Target is surface_entity_id for this block
                       # print(f"LOG_REACTION_FORCE_APPLIED: Type=ReactionToFriction, Target={surface_entity_id}, Source={entity_on_surface_id}, ForceVec={reaction_friction_force}, AppPointLocal={app_point_local_surface_fric}, Torque={reaction_friction_torque:.4f}")

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
               # # print(f"DEBUG_FC: Applying torque_due_to_friction (fallback): {torque_due_to_friction} to {entity_on_surface_id} using local point {contact_point_local} (rotated lever: {lever_arm_world_friction_fb if entity_transform_friction_fb else 'N/A'})")
               # Also record if using fallback, assuming record_force_detail is available
               if hasattr(force_acc_obj, 'record_force_detail'):
                   force_acc_obj.record_force_detail(
                       force_vector=friction_force_vector,
                       application_point_local=contact_point_local, # Use the provided local contact point
                       force_type_label=f"Friction (from {str(surface_entity_id)})"
                   )
                   force_info_tuple_fric_fb = (friction_force_vector, contact_point_local, f"Friction (from {str(surface_entity_id)})", torque_due_to_friction, entity_on_surface_id, surface_entity_id)
                   # print(f"LOG_FORCE_APPLIED_FB: Type=Friction, Target={entity_on_surface_id}, Source={surface_entity_id}, ForceVec={friction_force_vector}, AppPointLocal={contact_point_local}, Torque={torque_due_to_friction:.4f}")
                   
                   # Apply reaction friction force to the surface entity (FALLBACK PATH)
                   phys_body_surface_fric_fb = entity_manager.get_component(surface_entity_id, PhysicsBodyComponent)
                   if phys_body_surface_fric_fb and not phys_body_surface_fric_fb.is_fixed:
                       force_acc_surface_fric_fb = entity_manager.get_component(surface_entity_id, ForceAccumulatorComponent)
                       surface_transform_fric_fb = entity_manager.get_component(surface_entity_id, TransformComponent)
                       if force_acc_surface_fric_fb and surface_transform_fric_fb:
                           reaction_friction_force_fb = -friction_force_vector
                           contact_point_world_for_reaction_fric_fb: Vector2D
                           if entity_transform_friction_fb:
                               contact_point_world_for_reaction_fric_fb = entity_transform_friction_fb.position + lever_arm_world_friction_fb
                           else: # Fallback
                               contact_point_world_for_reaction_fric_fb = phys_body_obj.position + contact_point_local
                               
                           offset_world_surface_fric_fb = contact_point_world_for_reaction_fric_fb - surface_transform_fric_fb.position
                           app_point_local_surface_fric_fb = offset_world_surface_fric_fb.rotate(-surface_transform_fric_fb.angle)
                           reaction_friction_torque_fb = app_point_local_surface_fric_fb.rotate(surface_transform_fric_fb.angle).cross(reaction_friction_force_fb)

                           force_acc_surface_fric_fb.net_force += reaction_friction_force_fb # Using net_force directly
                           force_acc_surface_fric_fb.net_torque += reaction_friction_torque_fb
                           if hasattr(force_acc_surface_fric_fb, 'record_force_detail'):
                               force_acc_surface_fric_fb.record_force_detail(
                                   force_vector=reaction_friction_force_fb,
                                   application_point_local=app_point_local_surface_fric_fb,
                                   force_type_label=f"Friction_FB (by {str(entity_on_surface_id)})" # MODIFIED_LABEL
                               )
                           # print(f"LOG_REACTION_FORCE_APPLIED_FB: Type=ReactionToFriction_FB, Target={surface_entity_id}, Source={entity_on_surface_id}, ForceVec={reaction_friction_force_fb}, AppPointLocal={app_point_local_surface_fric_fb}, Torque={reaction_friction_torque_fb:.4f}")
           # # print(f"Applied friction {friction_force_vector} to {entity_on_surface_id}, tang_speed: {tangential_speed}")