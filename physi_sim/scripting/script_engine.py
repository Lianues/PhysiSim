import sys
import math # Example module to potentially allow
from typing import TYPE_CHECKING, Optional, Dict, Any, Tuple
from uuid import UUID # Assuming EntityID is UUID

# Import core types needed by SystemAPI or context building
from physi_sim.core.vector import Vector2D

if TYPE_CHECKING:
    from physi_sim.core.entity_manager import EntityManager
    # Import components potentially accessed by API
    from physi_sim.core.component import TransformComponent, PhysicsBodyComponent, ForceAccumulatorComponent

# --- System API for Scripts ---
class SystemAPI:
    """Provides a safe interface for scripts to interact with the simulation."""
    def __init__(self, entity_manager: 'EntityManager', script_engine: 'ScriptEngine'):
        self._entity_manager = entity_manager
        self._script_engine = script_engine # May need access to engine state/methods

    def log(self, message: Any):
        """Prints a message to the console."""
        print(f"[SCRIPT LOG] {message}")

    def get_entity_id_by_name(self, name: str) -> Optional[UUID]:
         """Finds the first entity with the given name."""
         # This requires EntityManager to have a way to search by name,
         # possibly by iterating through IdentifierComponents. Implement later if needed.
         self.log(f"Warning: get_entity_id_by_name('{name}') not fully implemented yet.")
         # Placeholder: Iterate through all entities with IdentifierComponent
         try:
             from physi_sim.core.component import IdentifierComponent # Late import
             entities_with_id = self._entity_manager.get_entities_with_components(IdentifierComponent)
             for eid in entities_with_id:
                 id_comp = self._entity_manager.get_component(eid, IdentifierComponent)
                 if id_comp and id_comp.name == name:
                     return eid
         except ImportError:
             pass # Component might not exist yet
         return None

    def get_position(self, entity_id: UUID) -> Optional[Tuple[float, float]]:
        """Gets the position (x, y) of an entity."""
        try:
            from physi_sim.core.component import TransformComponent # Late import
            trans_comp = self._entity_manager.get_component(entity_id, TransformComponent)
            if trans_comp:
                return (trans_comp.position.x, trans_comp.position.y)
        except ImportError:
             pass
        return None

    def set_position(self, entity_id: UUID, position_tuple: Tuple[float, float]):
         """Sets the position (x, y) of an entity."""
         try:
             from physi_sim.core.component import TransformComponent # Late import
             trans_comp = self._entity_manager.get_component(entity_id, TransformComponent)
             if trans_comp:
                 trans_comp.position = Vector2D(position_tuple[0], position_tuple[1])
             else:
                 self.log(f"Warning: Entity {entity_id} has no TransformComponent to set position.")
         except ImportError:
             pass
         except Exception as e:
             self.log(f"Error setting position for {entity_id}: {e}")


    def get_velocity(self, entity_id: UUID) -> Optional[Tuple[float, float]]:
        """Gets the velocity (vx, vy) of an entity."""
        try:
            from physi_sim.core.component import PhysicsBodyComponent # Late import
            phys_comp = self._entity_manager.get_component(entity_id, PhysicsBodyComponent)
            if phys_comp:
                return (phys_comp.velocity.x, phys_comp.velocity.y)
        except ImportError:
             pass
        return None

    def set_velocity(self, entity_id: UUID, velocity_tuple: Tuple[float, float]):
        """Sets the velocity (vx, vy) of an entity."""
        try:
            from physi_sim.core.component import PhysicsBodyComponent # Late import
            phys_comp = self._entity_manager.get_component(entity_id, PhysicsBodyComponent)
            if phys_comp:
                if not phys_comp.is_fixed:
                    phys_comp.velocity = Vector2D(velocity_tuple[0], velocity_tuple[1])
                else:
                    self.log(f"Warning: Cannot set velocity for fixed entity {entity_id}.")
            else:
                 self.log(f"Warning: Entity {entity_id} has no PhysicsBodyComponent to set velocity.")
        except ImportError:
             pass
        except Exception as e:
             self.log(f"Error setting velocity for {entity_id}: {e}")


    def apply_force(self, entity_id: UUID, force_tuple: Tuple[float, float]):
        """Applies a force (fx, fy) to an entity for the current frame."""
        try:
            from physi_sim.core.component import ForceAccumulatorComponent # Late import
            force_acc = self._entity_manager.get_component(entity_id, ForceAccumulatorComponent)
            if force_acc:
                force_vector = Vector2D(force_tuple[0], force_tuple[1])
                if hasattr(force_acc, 'add_force'):
                     force_acc.add_force(force_vector)
                else:
                     force_acc.net_force += force_vector # Fallback
            else:
                 self.log(f"Warning: Entity {entity_id} has no ForceAccumulatorComponent to apply force.")
        except ImportError:
             pass
        except Exception as e:
             self.log(f"Error applying force for {entity_id}: {e}")

    # Add more API methods as needed: apply_impulse, get_mass, destroy_entity, create_entity etc.

# --- Script Engine ---
class ScriptEngine:
    def __init__(self, entity_manager: 'EntityManager'):
        self.entity_manager = entity_manager
        # Create a single API instance to be shared by all script contexts
        self.system_api = SystemAPI(entity_manager, self)

        # Define allowed builtins and modules for safety
        self._allowed_builtins = {
            'print': print, # Allow print for debugging
            'abs': abs, 'min': min, 'max': max, 'round': round, 'len': len,
            'str': str, 'int': int, 'float': float, 'bool': bool, 'list': list, 'dict': dict, 'tuple': tuple,
            'True': True, 'False': False, 'None': None,
            # Math functions can be useful
            'math': math,
            'Vector2D': Vector2D, # Allow creating Vector2D instances
        }
        # Potentially restrict math module further if needed

    def build_script_context(self,
                             entity_id: Optional[UUID] = None,
                             extra_context: Optional[dict] = None) -> dict:
        """Builds the global context dictionary for script execution."""

        context = {}
        # Start with allowed builtins only
        context['__builtins__'] = self._allowed_builtins

        # Add core simulation info
        context['time'] = extra_context.get('time', 0.0) if extra_context else 0.0
        context['dt'] = extra_context.get('dt', 0.016) if extra_context else 0.016

        # Add the System API
        context['system_api'] = self.system_api

        # Add info about the current entity, if applicable
        context['current_entity_id'] = entity_id

        # Add access to the entity's persistent variables
        script_variables = {}
        if entity_id:
            try:
                from physi_sim.core.component import ScriptExecutionComponent # Late import
                script_comp = self.entity_manager.get_component(entity_id, ScriptExecutionComponent)
                if script_comp:
                    # Provide a reference to the script_variables dict
                    script_variables = script_comp.script_variables
            except ImportError:
                pass # Component might not exist yet
            except Exception as e:
                print(f"Error getting script variables for {entity_id}: {e}")
        context['variables'] = script_variables # Always provide the dict, even if empty

        # Add any other extra context provided
        if extra_context:
            context.update(extra_context)

        return context

    def execute_script(self, script_string: str, context: dict):
        """Executes the script string within the given context."""
        if not script_string:
            return
        try:
            # Execute the script. Pass the context as both globals and locals
            # for simplicity, but restrict globals mainly via __builtins__.
            exec(script_string, context, context)
        except Exception as e:
            entity_info = f" for entity {context.get('current_entity_id')}" if context.get('current_entity_id') else ""
            print(f"--- SCRIPT ERROR{entity_info} ---")
            print(f"Error: {e}")
            # Consider logging the traceback too for easier debugging
            import traceback
            traceback.print_exc()
            print(f"Script Content:\n{script_string}")
            print("--------------------------")
            # Optionally re-raise, or just log and continue