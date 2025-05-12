import json
from typing import Dict, Any, List, Type, Union, Optional, get_type_hints, cast
from uuid import UUID
import uuid # For generating UUIDs in tests if needed
import inspect
import dataclasses
from enum import Enum # Added to handle Enum serialization

from physi_sim.core.entity_manager import EntityManager
from physi_sim.core.component import Component
from physi_sim.core.vector import Vector2D
# Import the components_module to access actual component classes for registration
import physi_sim.core.component as components_module # Renamed for clarity
from physi_sim.core.component import IdentifierComponent, TransformComponent, SpringComponent # Added for preset handling and independent components


# List of known independent component types.
# In the future, EntityManager might provide a way to get all registered independent component types.
KNOWN_INDEPENDENT_COMPONENT_TYPES: List[Type[Component]] = [
    SpringComponent,
    components_module.ConnectionComponent # Added ConnectionComponent
]


class SceneSerializer:
    """
    Handles serialization of scene data to JSON and deserialization from JSON.
    """

    COMPONENT_REGISTRY: Dict[str, Type[Component]] = {}

    @classmethod
    def register_component(cls, component_class: Type[Component]):
        """Registers a component class for deserialization."""
        if not inspect.isclass(component_class) or not issubclass(component_class, Component):
            # print(f"Warning: Attempted to register non-component class: {component_class}")
            return
        cls.COMPONENT_REGISTRY[component_class.__name__] = component_class
        # print(f"DEBUG: Registered component {component_class.__name__}")

    @classmethod
    def unregister_all_components(cls):
        """Clears the component registry. Useful for testing or re-initialization."""
        cls.COMPONENT_REGISTRY.clear()

    @staticmethod
    def _component_to_dict(component: Component) -> Dict[str, Any]:
        """Converts a component instance to a dictionary suitable for JSON serialization."""
        data = {}
        if dataclasses.is_dataclass(component):
            for field_info in dataclasses.fields(component):
                attr_name = field_info.name
                value = getattr(component, attr_name)
                
                if isinstance(value, Vector2D):
                    data[attr_name] = value.to_dict()
                elif isinstance(value, UUID):
                    # Ensure ConnectionComponent's target_entity_id is stringified even if already UUID
                    # This also handles any other direct UUID attributes.
                    if component.__class__.__name__ == 'ConnectionComponent' and attr_name == 'target_entity_id':
                        print(f"DEBUG: Explicitly stringifying ConnectionComponent.target_entity_id: {value}")
                    else:
                         print(f"DEBUG: Stringifying UUID attribute {type(component).__name__}.{attr_name}: {value}")
                    data[attr_name] = str(value)
                elif isinstance(value, Enum): # Handle Enum types
                    data[attr_name] = value.name # Serialize as the enum member's name
                elif isinstance(value, list):
                    data[attr_name] = [
                        item.to_dict() if isinstance(item, Vector2D) else
                        item.to_dict() if isinstance(item, components_module.ForceDetail) else # Handle ForceDetail in list
                        str(item) if isinstance(item, UUID) else
                        item.name if isinstance(item, Enum) else # Handle Enum in list
                        # Add more complex item type handling if needed
                        item
                        for item in value
                    ]
                elif isinstance(value, dict):
                    processed_dict = {}
                    for k, v_item in value.items():
                        key_str = str(k) # JSON keys must be strings
                        if isinstance(v_item, Vector2D):
                            processed_dict[key_str] = v_item.to_dict()
                        elif isinstance(v_item, UUID):
                            processed_dict[key_str] = str(v_item)
                        elif isinstance(v_item, Enum): # Handle Enum in dict values
                            processed_dict[key_str] = v_item.name
                        # Add more complex value type handling if needed
                        else:
                            processed_dict[key_str] = v_item
                    data[attr_name] = processed_dict
                elif isinstance(value, (int, float, str, bool, tuple)) or value is None:
                    data[attr_name] = value
                else:
                    # Fallback for other types. Consider if specific handling is needed.
                    value_type_name = type(value).__name__
                    print(f"DEBUG: Fallback serialization for {type(component).__name__}.{attr_name} "
                          f"(Type: {value_type_name}, Value: {repr(value)})")
                    # Explicitly check if it's a UUID here just in case it slipped through
                    if isinstance(value, UUID):
                         print(f"ERROR: UUID object reached fallback serialization for {type(component).__name__}.{attr_name}!")
                         data[attr_name] = str(value)
                    else:
                         try:
                             # Attempt str() conversion, but log potential issues
                             data[attr_name] = str(value)
                             print(f"DEBUG: Fallback converted {value_type_name} to string: {data[attr_name]}")
                         except Exception as e_str:
                              print(f"ERROR: Fallback str() conversion failed for {type(component).__name__}.{attr_name} "
                                    f"(Type: {value_type_name}): {e_str}")
                              data[attr_name] = f"SerializationError: Could not convert {value_type_name}"
        else: 
            # Fallback for non-dataclass components (should be avoided for consistency)
            for attr_name, value in component.__dict__.items():
                if attr_name.startswith('_'): continue # Skip private/protected

                if isinstance(value, Vector2D): data[attr_name] = value.to_dict()
                elif isinstance(value, UUID): data[attr_name] = str(value)
                elif isinstance(value, (int, float, str, bool, list, dict, tuple)) or value is None:
                    data[attr_name] = value
                else:
                    print(f"Warning (non-dataclass): Attribute '{attr_name}' type '{type(value).__name__}' may not be serializable. Converting to string.")
                    data[attr_name] = str(value)
        return {
            "type": component.__class__.__name__,
            "data": data
        }

    @staticmethod
    def _reconstruct_value(value_from_json: Any, target_type_hint: Optional[Type]) -> Any:
        """
        Recursively reconstructs a value from its JSON representation based on a type hint.
        """
        if target_type_hint is None: # No type hint, return as is
            return value_from_json
        
        # Attempt to get the actual class for Enum types if target_type_hint is an Enum itself
        # This is important because get_type_hints might return the Enum class directly.
        if inspect.isclass(target_type_hint) and issubclass(target_type_hint, Enum):
            if isinstance(value_from_json, str): # Enum was serialized as its name
                try:
                    return target_type_hint[value_from_json] # Access member by name
                except KeyError:
                    print(f"Warning: Enum member '{value_from_json}' not found in {target_type_hint}. Using raw value.")
                    return value_from_json # Fallback to raw value if name not found
            elif isinstance(value_from_json, target_type_hint): # Already correct type
                return value_from_json


        origin_type = getattr(target_type_hint, '__origin__', None)
        args_types = getattr(target_type_hint, '__args__', tuple())

        if origin_type is Union: # Handles Optional[T] as Union[T, NoneType]
            if value_from_json is None and type(None) in args_types:
                return None
            # Try to reconstruct with the first non-NoneType arg.
            non_none_args = [arg for arg in args_types if arg is not type(None)]
            if not non_none_args: return value_from_json 
            return SceneSerializer._reconstruct_value(value_from_json, non_none_args[0])

        if target_type_hint == Vector2D and isinstance(value_from_json, dict) and 'x' in value_from_json and 'y' in value_from_json:
            try: return Vector2D.from_dict(value_from_json)
            except (ValueError, TypeError) as e: print(f"Warning: Vector2D.from_dict failed for {value_from_json}: {e}"); return value_from_json
        
        if target_type_hint == UUID and isinstance(value_from_json, str):
            try: return UUID(value_from_json)
            except ValueError as e: print(f"Warning: UUID(str) failed for '{value_from_json}': {e}"); return value_from_json

        if target_type_hint == components_module.ForceDetail and isinstance(value_from_json, dict):
            try:
                return components_module.ForceDetail.from_dict(value_from_json)
            except Exception as e: # Catch any error during ForceDetail.from_dict
                print(f"Warning: ForceDetail.from_dict failed for {value_from_json}: {e}")
                return value_from_json # Fallback to returning the dict if reconstruction fails

        if origin_type in (list, List) and args_types and isinstance(value_from_json, list):
            item_type_hint = args_types[0]
            return [SceneSerializer._reconstruct_value(item, item_type_hint) for item in value_from_json]

        if origin_type in (dict, Dict) and len(args_types) == 2 and isinstance(value_from_json, dict):
            # Key type hint args_types[0] is usually str for JSON, so we focus on value type hint.
            val_type_hint = args_types[1]
            # Reconstruct keys if needed, though typically JSON keys are strings.
            # For simplicity, assume keys are strings or directly usable.
            # If keys need reconstruction (e.g. int keys stored as str in JSON), that needs more logic.
            return {k: SceneSerializer._reconstruct_value(v, val_type_hint) for k, v in value_from_json.items()}
            
        # Check if value_from_json is already an instance of the target_type_hint's origin or the hint itself.
        # This handles cases where target_type_hint might be a subscripted generic (e.g., List[int]).
        # We should check against the origin type (e.g., list) or the type itself if not generic.
        check_type = origin_type if origin_type is not None else target_type_hint
        try:
            # Only attempt isinstance if check_type is a valid type for it (not a generic alias like List[int])
            # For basic types or non-generic types, target_type_hint can be used directly.
            # For subscripted generics, origin_type (e.g. list, dict) should be used.
            if inspect.isclass(check_type) and isinstance(value_from_json, check_type):
                return value_from_json
        except TypeError:
            # This can happen if check_type is still something like typing.Union, which isn't a class.
            # In such cases, we might rely on later specific type checks or direct conversion attempts.
            pass # Fall through to other reconstruction logic
        
        try: # Attempt direct conversion for basic types like int("10"), float("3.14")
            # Ensure target_type_hint is a class and not a subscripted generic for direct conversion
            if inspect.isclass(target_type_hint) and \
               target_type_hint in (int, float, str, bool) and \
               not isinstance(value_from_json, target_type_hint):
                 return target_type_hint(value_from_json)
        except (ValueError, TypeError):
            pass 

        return value_from_json # Fallback


    @staticmethod
    def _dict_to_component(component_json_data: Dict[str, Any], entity_manager: EntityManager) -> Optional[Component]:
        """Converts a dictionary (from JSON) to a component instance."""
        component_type_name = component_json_data.get("type")
        if not component_type_name:
            print(f"Warning: Component data missing 'type': {component_json_data}"); return None

        component_class = SceneSerializer.COMPONENT_REGISTRY.get(component_type_name)
        if not component_class:
            print(f"Warning: Unknown component type '{component_type_name}'. Ensure it's registered. Skipping."); return None

        raw_data_from_json = component_json_data.get("data", {})
        processed_data_for_constructor = {}
        
        field_annotations = {}
        if dataclasses.is_dataclass(component_class):
            try:
                component_module_globals = inspect.getmodule(component_class).__dict__ if inspect.getmodule(component_class) else {}
                component_module_globals.update(globals()) 
                field_annotations = get_type_hints(component_class, globalns=component_module_globals, localns=locals())
            except Exception as e: 
                print(f"Warning: get_type_hints failed for {component_type_name}: {e}. Using dataclasses.fields as fallback.")
                field_annotations = {f.name: f.type for f in dataclasses.fields(component_class)}


        for attr_name, value_from_json in raw_data_from_json.items():
            target_type_hint = field_annotations.get(attr_name)
            processed_data_for_constructor[attr_name] = SceneSerializer._reconstruct_value(value_from_json, target_type_hint)
        
        try:
            if hasattr(component_class, 'from_dict'):
                sig = inspect.signature(component_class.from_dict)
                if 'entity_manager' in sig.parameters:
                    instance = component_class.from_dict(processed_data_for_constructor, entity_manager=entity_manager)
                else:
                    instance = component_class.from_dict(processed_data_for_constructor)
            elif dataclasses.is_dataclass(component_class):
                try:
                    instance = component_class(**processed_data_for_constructor)
                except TypeError as te:
                    print(f"TypeError during dataclass direct instantiation for {component_type_name}: {te}. "
                          f"Data: {processed_data_for_constructor}. Attempting fallback.")
                    try:
                        temp_instance = component_class() 
                        for attr, val_to_set in processed_data_for_constructor.items():
                            if hasattr(temp_instance, attr):
                                setattr(temp_instance, attr, val_to_set)
                        instance = temp_instance
                    except Exception as e_fallback:
                         print(f"Error in dataclass fallback for {component_type_name}: {e_fallback}. Not created.")
                         return None
            else: # Non-dataclass, no from_dict
                print(f"Warning: {component_type_name} not dataclass and no from_dict. Basic init.")
                instance = component_class() 
                for attr, val_to_set in processed_data_for_constructor.items():
                    if hasattr(instance, attr): setattr(instance, attr, val_to_set)
            return instance
        except Exception as e:
            print(f"Critical error instantiating '{component_type_name}': {e}, Data: {processed_data_for_constructor}")
            return None


    def serialize_scene_to_json_string(
        self,
        entity_manager: EntityManager,
        include_time: bool = False,
        current_time: Optional[float] = None
    ) -> str:
        """
        Serializes all entities and their components from an EntityManager into a JSON string.
        Optionally includes simulation time.
        Also serializes independent components.
        """
        scene_data_content: Dict[str, Any] = {
            "entities": [],
            "independent_components": {}
        }
        # print(f"DEBUG: Serializing scene. EntityManager instance: {entity_manager}")
        
        # Serialize entities
        # print(f"DEBUG: All entity IDs in EntityManager: {list(entity_manager.entities)}")
        # if entity_manager.entities:
        #     first_entity_id = list(entity_manager.entities)[0]
        #     print(f"DEBUG: Components for first entity ({first_entity_id}): {entity_manager.get_all_components_for_entity(first_entity_id)}")
        # else:
        #     print("DEBUG: EntityManager has no entities.")
        for entity_id in entity_manager.entities:
            entity_id_str = str(entity_id)
            entity_data = {"id": entity_id_str, "components": []}
            components_for_entity = entity_manager.get_all_components_for_entity(entity_id)
            if components_for_entity:
                for component_instance in components_for_entity.values():
                    entity_data["components"].append(self._component_to_dict(component_instance))
            scene_data_content["entities"].append(entity_data)

        # Serialize independent components
        for component_type in KNOWN_INDEPENDENT_COMPONENT_TYPES:
            try:
                independent_components_of_type = entity_manager.get_all_independent_components_of_type(component_type)
            except AttributeError:
                print(f"Warning: EntityManager does not have 'get_all_independent_components_of_type' method. Skipping independent {component_type.__name__}.")
                continue
            except Exception as e:
                print(f"Error fetching independent components of type {component_type.__name__}: {e}")
                continue

            if independent_components_of_type:
                serialized_components = []
                for comp_instance in independent_components_of_type:
                    serialized_components.append(self._component_to_dict(comp_instance))
                scene_data_content["independent_components"][component_type.__name__] = serialized_components
        
        output_json_object: Dict[str, Any] = {}
        if include_time and current_time is not None:
            output_json_object["simulation_time"] = current_time
        
        # Add entities and independent_components under a main key if time is included,
        # or directly if not, to maintain backward compatibility for old files not expecting a top-level structure.
        # However, for clarity and future-proofing, it's better to always have a consistent structure.
        # Let's decide to *always* have the entity/component data nested, even if time is not present.
        # This makes deserialization more straightforward.
        # If simulation_time is not included, the top level of JSON will be scene_data_content directly.
        # If simulation_time IS included, scene_data_content will be nested.
        # The requirement is: `{"simulation_time": current_time, "entities": ..., "independent_components": ...}`
        # So, if include_time is true, simulation_time is at top level, and entities/independent_components are also at top level.

        if include_time and current_time is not None:
            # Merge scene_data_content into output_json_object
            # output_json_object["scene_content"] = scene_data_content # Original thought
            output_json_object.update(scene_data_content) # Correctly merges keys
        else:
            # If not including time, the scene_data_content is the root object
            output_json_object = scene_data_content
            
        return json.dumps(output_json_object, indent=2)


    def deserialize_json_string_to_scene(self, json_string: str, entity_manager: EntityManager) -> Dict[str, Any]:
        """
        Deserializes a JSON string into entities and components in the given EntityManager.
        Returns a dictionary containing the status and potentially the loaded simulation time.
        Example return: {"status": "success", "simulation_time": 123.45}
                        {"status": "success", "simulation_time": 0.0} (if no time in file)
                        {"status": "error", "message": "details"}
        """
        try:
            loaded_json_data = json.loads(json_string)
        except json.JSONDecodeError as e:
            # Consider returning an error structure instead of raising, for consistency
            return {"status": "error", "message": f"Invalid JSON format: {e}", "simulation_time": 0.0}

        loaded_simulation_time = 0.0
        scene_content_data = {} # This will hold entities and independent_components

        if not isinstance(loaded_json_data, dict):
             return {"status": "error", "message": "Invalid scene data: Root must be a dictionary.", "simulation_time": 0.0}

        if "simulation_time" in loaded_json_data:
            loaded_simulation_time = loaded_json_data.get("simulation_time", 0.0)
            # If simulation_time is present, entities and independent_components are expected at the same level
            scene_content_data = loaded_json_data
        else:
            # This is an older format file, or a file saved without time.
            # The loaded_json_data itself contains entities and independent_components.
            scene_content_data = loaded_json_data
            loaded_simulation_time = 0.0 # Explicitly set if not found

        if "entities" not in scene_content_data:
            return {"status": "error", "message": "Invalid scene data: Must contain 'entities' key.", "simulation_time": loaded_simulation_time}
        
        entities_data = scene_content_data.get("entities", [])
        if not isinstance(entities_data, list):
            return {"status": "error", "message": "Invalid scene data: 'entities' must be a list.", "simulation_time": loaded_simulation_time}

        for entity_data_dict in entities_data:
            if not isinstance(entity_data_dict, dict):
                print(f"Warning: Skipping invalid entity data (not dict): {entity_data_dict}"); continue
            entity_id_from_json = entity_data_dict.get("id")
            if entity_id_from_json is None:
                print(f"Warning: Entity data missing 'id'. Skipping: {entity_data_dict}"); continue

            try:
                entity_uuid_to_process = uuid.UUID(entity_id_from_json)
                entity_manager.create_entity(entity_uuid_to_process)
            except ValueError:
                print(f"Warning: Invalid UUID string '{entity_id_from_json}' in JSON for entity id. Skipping entity.")
                continue
            
            components_json_list = entity_data_dict.get("components", [])
            if not isinstance(components_json_list, list):
                print(f"Warning: Components for entity '{entity_id_from_json}' not a list. Skipping."); continue

            for component_json_item_dict in components_json_list:
                if not isinstance(component_json_item_dict, dict):
                    print(f"Warning: Invalid component data (not dict) for '{entity_id_from_json}': {component_json_item_dict}"); continue
                
                component_instance = self._dict_to_component(component_json_item_dict, entity_manager)
                if component_instance:
                    try:
                        entity_manager.add_component(entity_uuid_to_process, component_instance)
                    except Exception as e:
                        print(f"Error adding component '{type(component_instance).__name__}' to entity '{entity_id_from_json}': {e}")
        
        independent_components_data = scene_content_data.get("independent_components")
        if isinstance(independent_components_data, dict):
            for component_type_name, components_list in independent_components_data.items():
                component_class = self.COMPONENT_REGISTRY.get(component_type_name)
                if not component_class:
                    print(f"Warning: Unknown independent component type '{component_type_name}' in JSON. Skipping.")
                    continue
                
                if not isinstance(components_list, list):
                    print(f"Warning: Independent component data for '{component_type_name}' is not a list. Skipping.")
                    continue

                for component_json_item_dict in components_list:
                    if not isinstance(component_json_item_dict, dict):
                        print(f"Warning: Invalid independent component data (not dict) for '{component_type_name}': {component_json_item_dict}. Skipping.")
                        continue
                    
                    component_instance = self._dict_to_component(component_json_item_dict, entity_manager)
                    if component_instance:
                        try:
                            entity_manager.add_independent_component(component_instance)
                        except AttributeError:
                             print(f"Warning: EntityManager does not have 'add_independent_component' method. Cannot add independent {type(component_instance).__name__}.")
                        except Exception as e_add_indie:
                            print(f"Error adding independent component '{type(component_instance).__name__}' (ID: {getattr(component_instance, 'id', 'N/A')}) to EntityManager: {e_add_indie}")
        elif independent_components_data is not None:
            print(f"Warning: 'independent_components' key exists in JSON but is not a dictionary. Skipping independent components. Value: {independent_components_data}")
        
        return {"status": "success", "simulation_time": loaded_simulation_time}

    def serialize_entity_to_preset_dict(self, entity_manager: EntityManager, entity_id: Union[str, UUID]) -> Dict[str, Any]:
        """
        Serializes a single entity and its components into a dictionary suitable for a preset.
        """
        if isinstance(entity_id, str):
            try:
                entity_uuid = UUID(entity_id) # Convert string ID to UUID
            except ValueError:
                print(f"Warning: Invalid UUID string '{entity_id}' for preset serialization.")
                return {}
        elif isinstance(entity_id, UUID):
            entity_uuid = entity_id # Already a UUID object
        else:
            print(f"Warning: Invalid entity_id type '{type(entity_id)}' for preset serialization. Expected str or UUID.")
            return {}

        if entity_uuid not in entity_manager.entities:
            # Or raise an error, or return an empty dict with an error message
            print(f"Warning: Entity '{entity_uuid}' not found for preset serialization.")
            return {}

        components_data = []
        components_for_entity = entity_manager.get_all_components_for_entity(entity_uuid) # Use UUID
        if components_for_entity:
            for component_instance in components_for_entity.values(): # Iterate over values (instances)
                comp_type_name = component_instance.__class__.__name__
                print(f"DEBUG: Serializing component type: {comp_type_name} for preset") # Log before call
                try:
                    component_dict = self._component_to_dict(component_instance)
                    # print(f"DEBUG: Serialized {comp_type_name} data: {component_dict}") # Optional: Log serialized data
                    components_data.append(component_dict)
                except Exception as e_comp_serialize:
                    # Log the specific exception during the component serialization
                    print(f"ERROR: Exception during _component_to_dict for {comp_type_name}: {e_comp_serialize}")
                    # Optionally append an error marker or re-raise, but logging might be enough for now
                    components_data.append({"type": comp_type_name, "error": f"Serialization failed: {e_comp_serialize}"})
                    # If we want the whole preset saving to fail immediately, re-raise the exception:
                    # raise e_comp_serialize

        preset_dict = {
            "entity_id_placeholder": "preset_entity_id", # This will be replaced on load
            "components": components_data
        }
        return preset_dict

    def deserialize_preset_dict_to_entity(
        self,
        preset_data: Dict[str, Any],
        entity_manager: EntityManager,
        new_entity_id: UUID, # Changed type hint from str to UUID
        target_position: Optional[Vector2D] = None,
        name_override: Optional[str] = None
    ) -> UUID: # Also changed return type hint to UUID for consistency
        """
        Deserializes a preset dictionary to create a new entity with components.
        Returns the ID of the newly created entity.
        """
        if not isinstance(preset_data, dict) or "components" not in preset_data:
            print(f"Warning: Invalid preset data format. Missing 'components'. Preset: {preset_data}")
            raise ValueError("Invalid preset data format.")

        components_json_list = preset_data.get("components", [])
        if not isinstance(components_json_list, list):
            print(f"Warning: Components in preset data is not a list. Preset: {preset_data}")
            raise ValueError("Preset components must be a list.")

        # Ensure the entity exists (or create it if EntityManager handles it this way)
        # For this implementation, we assume new_entity_id is fresh and needs to be "created"
        # by adding components to it. If EntityManager requires explicit creation, adjust here.
        # entity_manager.create_entity(new_entity_id) # If needed

        for component_json_item_dict in components_json_list:
            if not isinstance(component_json_item_dict, dict):
                print(f"Warning: Invalid component data (not dict) in preset for '{new_entity_id}': {component_json_item_dict}"); continue
            
            component_instance = self._dict_to_component(component_json_item_dict, entity_manager)
            if component_instance:
                # Special handling for TransformComponent position
                if isinstance(component_instance, TransformComponent):
                    if target_position is not None:
                        component_instance.position = target_position
                
                # Special handling for IdentifierComponent name
                if isinstance(component_instance, IdentifierComponent) and name_override:
                    component_instance.name = name_override
                    # Potentially update the ID as well if the preset's ID was meant to be a template
                    # component_instance.id = new_entity_id
                    # However, IdentifierComponent.id is usually the entity_id itself.
                    # Let's assume the 'id' field in IdentifierComponent should match new_entity_id
                    # if it exists as a field in the component.
                    if hasattr(component_instance, 'id'):
                         # If IdentifierComponent has an 'id' field, it should store the entity's UUID
                         # Ensure it's the UUID object, not a string representation of it, if types matter strictly.
                         # However, new_entity_id is already a UUID object here.
                         component_instance.id = new_entity_id
 
 
                try:
                    entity_manager.add_component(new_entity_id, component_instance) # new_entity_id is now a UUID object
                except Exception as e:
                    print(f"Error adding component '{type(component_instance).__name__}' to entity '{new_entity_id}' from preset: {e}")
        
        return new_entity_id # Returning the UUID object

    def serialize_object_group_to_preset_data(
        self,
        entity_ids: List[UUID],
        connection_ids: List[UUID],
        entity_manager: EntityManager,
        group_anchor_world_pos: Vector2D
    ) -> Dict[str, Any]:
        """
        Serializes a group of selected entities and their relevant connections into a dictionary
        suitable for a composite preset.
        Entities' positions are stored relative to the group_anchor_world_pos.
        Entity IDs within the preset are local to the preset.
        """
        preset_data: Dict[str, Any] = {
            "preset_type": "group", # Indicates a group preset
            "entities": [],
            "connections": []
        }
        
        local_id_map: Dict[UUID, int] = {entity_id: i for i, entity_id in enumerate(entity_ids)}
        
        # Serialize entities
        for original_entity_id in entity_ids:
            if original_entity_id not in entity_manager.entities:
                print(f"Warning: Entity '{original_entity_id}' not found in EntityManager during group preset serialization. Skipping.")
                continue

            local_entity_id = local_id_map[original_entity_id]
            entity_preset_data = {
                "local_id": local_entity_id,
                "components": []
            }
            
            components_for_entity = entity_manager.get_all_components_for_entity(original_entity_id)
            if components_for_entity:
                for component_instance in components_for_entity.values():
                    # Skip serializing ConnectionComponents and SpringComponents here as they are handled separately
                    if isinstance(component_instance, (components_module.ConnectionComponent, components_module.SpringComponent)):
                        continue

                    component_dict = self._component_to_dict(component_instance)

                    if isinstance(component_instance, TransformComponent):
                        if 'data' in component_dict and isinstance(component_dict['data'], dict) and \
                           'position' in component_dict['data'] and isinstance(component_dict['data']['position'], dict) and \
                           'x' in component_dict['data']['position'] and 'y' in component_dict['data']['position']:
                            
                            original_world_pos = Vector2D(
                                component_dict['data']['position']['x'],
                                component_dict['data']['position']['y']
                            )
                            relative_pos = original_world_pos - group_anchor_world_pos
                            component_dict['data']['position'] = relative_pos.to_dict()
                        else:
                            print(f"Warning: Could not find or parse position for TransformComponent of entity {original_entity_id} during group preset serialization.")
                    
                    entity_preset_data["components"].append(component_dict)
            
            preset_data["entities"].append(entity_preset_data)

        # Serialize connections (Springs and Rods/Ropes)
        all_connections_from_em: List[Union[components_module.ConnectionComponent, components_module.SpringComponent]] = []
        all_connections_from_em.extend(entity_manager.get_all_independent_components_of_type(components_module.ConnectionComponent))
        all_connections_from_em.extend(entity_manager.get_all_independent_components_of_type(components_module.SpringComponent))
        
        # DEBUG: Print all available connection component IDs from EntityManager
        print(f"DEBUG_SERIALIZER: All Connection/Spring IDs in EntityManager at serialization time ({len(all_connections_from_em)} total):")
        available_em_conn_ids = set()
        for comp_instance_debug in all_connections_from_em:
            if hasattr(comp_instance_debug, 'id') and isinstance(comp_instance_debug.id, UUID):
                print(f"  - EM Stored {type(comp_instance_debug).__name__} ID: {comp_instance_debug.id}")
                available_em_conn_ids.add(comp_instance_debug.id)
            else:
                print(f"  - EM Stored Component instance has no valid 'id': {comp_instance_debug}")
        
        print(f"DEBUG_SERIALIZER: Selected connection_ids to find ({len(connection_ids)} total):")
        for sel_id in connection_ids:
            print(f"  - Selected ID: {sel_id}")


        for conn_id_to_find in connection_ids: # conn_id_to_find is a UUID
            conn_comp_instance_to_serialize: Optional[Union[components_module.ConnectionComponent, components_module.SpringComponent]] = None
            
            for comp_instance_from_em in all_connections_from_em:
                if hasattr(comp_instance_from_em, 'id') and comp_instance_from_em.id == conn_id_to_find:
                    conn_comp_instance_to_serialize = comp_instance_from_em
                    break
            
            if not conn_comp_instance_to_serialize:
                print(f"Warning: Connection or Spring Component with ID '{conn_id_to_find}' not found in EntityManager. Skipping for preset.")
                if conn_id_to_find not in available_em_conn_ids:
                    print(f"  Further Info: The ID {conn_id_to_find} was NOT in the set of ConnectionComponent or SpringComponent IDs printed from EntityManager.")
                continue

            is_spring = isinstance(conn_comp_instance_to_serialize, components_module.SpringComponent)
            
            if is_spring:
                spring_instance = cast(components_module.SpringComponent, conn_comp_instance_to_serialize)
                entity_one_uuid = spring_instance.entity_a_id
                entity_two_uuid = spring_instance.entity_b_id
                id_field_for_remap_one = 'entity_a_id'
                id_field_for_remap_two = 'entity_b_id'
            else: # Is ConnectionComponent
                conn_instance_typed = cast(components_module.ConnectionComponent, conn_comp_instance_to_serialize)
                entity_one_uuid = conn_instance_typed.source_entity_id
                entity_two_uuid = conn_instance_typed.target_entity_id
                id_field_for_remap_one = 'source_entity_id'
                id_field_for_remap_two = 'target_entity_id'

            if entity_one_uuid not in local_id_map or entity_two_uuid not in local_id_map:
                print(f"Warning: Component (ID: {conn_id_to_find}, Type: {type(conn_comp_instance_to_serialize).__name__}) links to one or more entities "
                      f"not in the selected group ({entity_one_uuid}, {entity_two_uuid}). Skipping.")
                continue

            conn_serialized_data_full = self._component_to_dict(conn_comp_instance_to_serialize)
            
            if 'data' in conn_serialized_data_full and isinstance(conn_serialized_data_full['data'], dict):
                conn_data_to_modify = conn_serialized_data_full['data']
                
                original_entity_one_uuid_str = conn_data_to_modify.get(id_field_for_remap_one)
                original_entity_two_uuid_str = conn_data_to_modify.get(id_field_for_remap_two)

                if original_entity_one_uuid_str and original_entity_two_uuid_str:
                    try:
                        conn_data_to_modify[id_field_for_remap_one] = local_id_map[UUID(original_entity_one_uuid_str)]
                        conn_data_to_modify[id_field_for_remap_two] = local_id_map[UUID(original_entity_two_uuid_str)]
                        
                        # Add original component type to distinguish during deserialization
                        conn_data_to_modify['original_component_type'] = conn_comp_instance_to_serialize.__class__.__name__
                        
                        preset_data["connections"].append(conn_data_to_modify)
                    except ValueError:
                        print(f"Warning: Could not parse UUIDs for Component (ID: {conn_comp_instance_to_serialize.id}, "
                              f"Type: {type(conn_comp_instance_to_serialize).__name__}). Skipping.")
                    except KeyError as e:
                        print(f"Warning: Entity ID from Component {conn_comp_instance_to_serialize.id} "
                              f"(Type: {type(conn_comp_instance_to_serialize).__name__}) not in local_id_map: {e}. Skipping.")
                else:
                    print(f"Warning: Component (ID: {conn_comp_instance_to_serialize.id}, Type: {type(conn_comp_instance_to_serialize).__name__}) "
                          f"missing '{id_field_for_remap_one}' or '{id_field_for_remap_two}' in serialized data. Skipping.")
            else:
                print(f"Warning: Serialized data for Component (ID: {conn_comp_instance_to_serialize.id}, "
                      f"Type: {type(conn_comp_instance_to_serialize).__name__}) is malformed. Skipping.")
                      
        return preset_data

def register_all_components():
    """
    Dynamically registers all Component subclasses found in the physi_sim.core.component module.
    """
    SceneSerializer.unregister_all_components() 
    if not inspect.ismodule(components_module):
        print(f"Error: components_module ({components_module}) not valid for registration."); return

    found_component_names = []
    for name, obj in inspect.getmembers(components_module):
        if inspect.isclass(obj) and issubclass(obj, Component) and \
           obj is not Component and obj.__module__ == components_module.__name__:
            SceneSerializer.register_component(obj)
            found_component_names.append(obj.__name__)
    
    if not found_component_names: print("Warning: No components dynamically registered from 'physi_sim.core.component'.")
    # else: print(f"Dynamically registered components: {found_component_names}")


if __name__ == '__main__':
    print("--- SceneSerializer Test Script ---")
    print("\n--- Registering Components from physi_sim.core.component ---")
    register_all_components()
    # print(f"Registered components: {list(SceneSerializer.COMPONENT_REGISTRY.keys())}")

    class MockEntityManager(EntityManager):
        def __init__(self):
            self._entities: Dict[str, Dict[Type[Component], Component]] = {}
            self._next_id_counter = 1

        def create_entity(self, entity_id: Optional[str] = None) -> str:
            if entity_id is None: entity_id = f"test-entity-{self._next_id_counter}"; self._next_id_counter += 1
            entity_id_str = str(entity_id)
            if entity_id_str not in self._entities: self._entities[entity_id_str] = {}
            return entity_id_str
        
        def entity_exists(self, entity_id: str) -> bool: return str(entity_id) in self._entities

        def add_component(self, entity_id: str, component_instance: Component):
            entity_id_str = str(entity_id)
            if not self.entity_exists(entity_id_str): self.create_entity(entity_id_str)
            self._entities[entity_id_str][type(component_instance)] = component_instance

        def get_all_components_for_entity(self, entity_id: str) -> List[Component]:
            return list(self._entities.get(str(entity_id), {}).values())

        def get_all_entity_ids(self) -> List[str]: return list(self._entities.keys())
        def clear_all_entities_and_components(self): self._entities.clear(); self._next_id_counter = 1; print("MockEntityManager cleared.")
        def get_component(self, entity_id: str, component_type: Type[Component]) -> Optional[Component]:
            return self._entities.get(str(entity_id), {}).get(component_type)

    em = MockEntityManager()
    serializer = SceneSerializer()

    print("\n--- Populating EntityManager for Serialization ---")
    IdC = SceneSerializer.COMPONENT_REGISTRY.get('IdentifierComponent')
    TfC = SceneSerializer.COMPONENT_REGISTRY.get('TransformComponent')
    RdC = SceneSerializer.COMPONENT_REGISTRY.get('RenderComponent')
    GmC = SceneSerializer.COMPONENT_REGISTRY.get('GeometryComponent')
    PbC = SceneSerializer.COMPONENT_REGISTRY.get('PhysicsBodyComponent')
    CnC = SceneSerializer.COMPONENT_REGISTRY.get('ConnectionComponent') # ConnectionComponent

    e1_id = em.create_entity("player-1")
    if IdC: em.add_component(e1_id, IdC(id=e1_id, name="Hero", type_tags=["character", "interactive"]))
    if TfC: em.add_component(e1_id, TfC(position=Vector2D(10,20), rotation=0.1, scale=Vector2D(1.1,0.9)))
    if RdC: em.add_component(e1_id, RdC(fill_color=(0,128,255,220), z_order=5))
    if GmC: em.add_component(e1_id, GmC(shape_type="CIRCLE", parameters={"radius": 15.0}))

    e2_id = em.create_entity("static-platform-alpha")
    if IdC: em.add_component(e2_id, IdC(id=e2_id, name="Ground"))
    if TfC: em.add_component(e2_id, TfC(position=Vector2D(0,-100), scale=Vector2D(500,20)))
    if PbC: em.add_component(e2_id, PbC(is_fixed=True, restitution=0.1))
    
    if CnC and e1_id and e2_id : # Test ConnectionComponent
        # Ensure target_entity_id for ConnectionComponent is a UUID object
        # If your entity IDs are strings, they need to be valid UUID hex strings.
        try:
            target_uuid_for_connection = UUID(e1_id) # Assuming e1_id is a valid UUID hex string
            em.add_component(e2_id, CnC(target_entity_id=target_uuid_for_connection, connection_type="ROD", parameters={"length":50.0}))
            print(f"Added ConnectionComponent from {e2_id} to {target_uuid_for_connection}")
        except ValueError:
            print(f"Warning: Could not create UUID from e1_id ('{e1_id}') for ConnectionComponent test.")
        except Exception as e_cnc_test:
             print(f"Warning: Could not add ConnectionComponent in test: {e_cnc_test}")


    print("\n--- Serializing Scene to JSON ---")
    json_data_string = serializer.serialize_scene_to_json_string(em)
    print("Serialized JSON:")
    print(json_data_string)

    print("\n--- Deserializing JSON to New EntityManager ---")
    em_deserialized = MockEntityManager()
    try:
        serializer.deserialize_json_string_to_scene(json_data_string, em_deserialized)
    except Exception as e: print(f"ERROR during deserialization: {e}")

    print("\n--- Verifying Deserialized Data ---")
    original_ids = sorted(em.get_all_entity_ids())
    deserialized_ids = sorted(em_deserialized.get_all_entity_ids())
    assert original_ids == deserialized_ids, f"Entity ID list mismatch: {original_ids} vs {deserialized_ids}"
    print(f"Entity IDs match: {deserialized_ids}")

    for entity_id_str in deserialized_ids:
        print(f"  Verifying Entity: {entity_id_str}")
        original_comps = {type(c):c for c in em.get_all_components_for_entity(entity_id_str)}
        deserialized_comps = {type(c):c for c in em_deserialized.get_all_components_for_entity(entity_id_str)}
        
        assert sorted(original_comps.keys(), key=lambda t:t.__name__) == sorted(deserialized_comps.keys(), key=lambda t:t.__name__), \
            f"Component types mismatch for {entity_id_str}"

        for comp_type, orig_comp_inst in original_comps.items():
            deser_comp_inst = deserialized_comps.get(comp_type)
            assert deser_comp_inst is not None, f"Component {comp_type.__name__} missing in deserialized for {entity_id_str}"
            
            if dataclasses.is_dataclass(orig_comp_inst):
                for field in dataclasses.fields(orig_comp_inst):
                    orig_val = getattr(orig_comp_inst, field.name)
                    deser_val = getattr(deser_comp_inst, field.name)
                    # Basic assertion; for float, consider math.isclose
                    # For complex objects like Vector2D, their __eq__ should handle it if defined.
                    # If Vector2D has no __eq__, compare fields.
                    if isinstance(orig_val, Vector2D) and isinstance(deser_val, Vector2D):
                         assert orig_val.x == deser_val.x and orig_val.y == deser_val.y, \
                            f"Field {field.name} Vector2D mismatch in {comp_type.__name__} for {entity_id_str}"
                    elif isinstance(orig_val, float) and isinstance(deser_val, float):
                        assert abs(orig_val - deser_val) < 1e-9, \
                             f"Field {field.name} float mismatch in {comp_type.__name__} for {entity_id_str}"
                    else:
                        assert orig_val == deser_val, \
                            f"Field {field.name} mismatch in {comp_type.__name__} for {entity_id_str}: {orig_val} vs {deser_val}"
            print(f"    {comp_type.__name__}: OK")
    print("Verification complete for deserialized data.")

    print("\n--- Testing Unknown Component Robustness ---")
    if RdC: # If RenderComponent was found and registered
        SceneSerializer.COMPONENT_REGISTRY.pop(RdC.__name__, None)
        em_unknown_test = MockEntityManager()
        print(f"Unregistered {RdC.__name__} for robustness test.")
        serializer.deserialize_json_string_to_scene(json_data_string, em_unknown_test) # Should log warnings
        # Check if other components still loaded for e1_id
        if TfC and e1_id in em_unknown_test.get_all_entity_ids():
            assert em_unknown_test.get_component(e1_id, TfC) is not None, "TransformComponent should load despite RenderComponent missing"
            assert em_unknown_test.get_component(e1_id, RdC) is None, "RenderComponent should NOT load"
            print(f"  Robustness test for missing {RdC.__name__} passed for entity {e1_id}.")
        SceneSerializer.register_component(RdC) # Restore
    else:
        print("  Skipping unknown component test as RenderComponent was not initially registered.")
        
    print("\n--- SceneSerializer Test Script Complete ---")