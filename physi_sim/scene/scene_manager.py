import json
import logging
import os
from typing import Optional, List, Tuple, Dict # Added List, Tuple, Dict
from uuid import UUID # Import UUID for type hinting
import uuid # Keep this for generating UUIDs if needed elsewhere
from physi_sim.core.vector import Vector2D # Added for type hinting
from physi_sim.core.component import SpringComponent # Import SpringComponent

from physi_sim.core.entity_manager import EntityManager
from physi_sim.scene.scene_serializer import SceneSerializer, register_all_components
# 确保所有组件都被注册，这通常在 SceneSerializer 模块加载时或特定初始化点完成。
# 如果 register_all_components 不是在导入时自动运行，则需要在使用 SceneSerializer 前显式调用。

logger = logging.getLogger(__name__)

class SceneManager:
    """
    Manages the lifecycle of scenes, including creating, loading, and saving.
    It also handles management of entity presets.
    """
    # Determine the base directory of the physi_sim package to correctly locate assets
    # Assuming this file (scene_manager.py) is in physi_sim/scene/
    # So, __file__ -> .../physi_sim/scene/scene_manager.py
    # os.path.dirname(__file__) -> .../physi_sim/scene
    # os.path.dirname(os.path.dirname(__file__)) -> .../physi_sim
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PRESETS_DIR = os.path.join(BASE_DIR, "assets", "presets")


    def __init__(self, entity_manager: EntityManager):
        """
        Initializes the SceneManager.

        Args:
            entity_manager: An instance of EntityManager to manage scene entities.
        """
        self.entity_manager = entity_manager
        self.serializer = SceneSerializer()
        # 调用 register_all_components 来确保所有组件都已注册到序列化器中
        # 这对于 SceneSerializer 正确地反序列化组件至关重要。
        register_all_components()
        self.current_scene_filepath: Optional[str] = None
        logger.info("SceneManager initialized.")
        # Ensure presets directory exists
        if not os.path.exists(self.PRESETS_DIR):
            try:
                os.makedirs(self.PRESETS_DIR)
                logger.info(f"Created presets directory: {self.PRESETS_DIR}")
            except OSError as e:
                logger.error(f"Failed to create presets directory {self.PRESETS_DIR}: {e}")

    def new_scene(self) -> None:
        """
        Clears the current scene, effectively creating a new, empty scene.
        """
        logger.info("Creating new scene...")
        self.entity_manager.clear_all() # This will clear entities, their components, and independent components
        
        self.current_scene_filepath = None
        # Logger message in clear_all() already states "EntityManager cleared..."
        # So, we can refine this message or rely on the one from clear_all().
        logger.info("New scene created and EntityManager fully cleared via clear_all().")

    def save_scene(self, filepath: str) -> bool:
        """
        Saves the current scene to the specified filepath.

        Args:
            filepath: The path to save the scene file to.

        Returns:
            True if saving was successful, False otherwise.
        """
        logger.info(f"Attempting to save scene to: {filepath}")
        try:
            json_data_string = self.serializer.serialize_scene_to_json_string(self.entity_manager)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_data_string)
            self.current_scene_filepath = filepath
            logger.info(f"Scene saved successfully to {filepath}")
            return True
        except IOError as e:
            logger.error(f"IOError saving scene to {filepath}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving scene to {filepath}: {e}")
        return False

    def load_scene(self, filepath: str) -> bool:
        """
        Loads a scene from the specified filepath.

        Args:
            filepath: The path to load the scene file from.

        Returns:
            True if loading was successful, False otherwise.
        """
        logger.info(f"Attempting to load scene from: {filepath}")
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return False

        try:
            # 清空当前场景
            self.new_scene() # new_scene 内部会记录日志

            with open(filepath, 'r', encoding='utf-8') as f:
                json_data_string = f.read()
            
            self.serializer.deserialize_json_string_to_scene(json_data_string, self.entity_manager)
            self.current_scene_filepath = filepath
            logger.info(f"Scene loaded successfully from {filepath}")
            return True
        except FileNotFoundError: # 理论上已被 os.path.exists 覆盖，但为了稳健
            logger.error(f"File not found during load attempt: {filepath}")
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError loading scene from {filepath}: {e}")
        except ValueError as e: # SceneSerializer 可能抛出 ValueError
            logger.error(f"ValueError (e.g., invalid scene data format) loading scene from {filepath}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading scene from {filepath}: {e}")
        
        # 如果加载失败，最好将 current_scene_filepath 重置，因为加载不完整或失败
        self.current_scene_filepath = None 
        return False

    def save_current_scene(self) -> bool:
        """
        Saves the current scene to its existing filepath.
        If no filepath is associated (i.e., it's a new, unsaved scene),
        this method will log an error and return False.

        Returns:
            True if saving was successful, False otherwise (e.g., no path or IO error).
        """
        if self.current_scene_filepath:
            logger.info(f"Saving current scene to: {self.current_scene_filepath}")
            return self.save_scene(self.current_scene_filepath)
        else:
            logger.warning("Cannot save current scene: No filepath associated. Use 'save_scene(filepath)' instead.")
            return False

    def get_current_scene_filepath(self) -> Optional[str]:
        """
        Returns the filepath of the currently loaded scene.
        """
        return self.current_scene_filepath

    def save_selection_as_preset(
        self,
        preset_name: str,
        selected_entity_ids: List[UUID],
        selected_connection_ids: List[UUID]
    ) -> bool:
        """
        Saves the selected entities and their connections as a composite preset.

        Args:
            preset_name: The name for the preset (filename without extension).
            selected_entity_ids: A list of UUIDs for the selected entities.
            selected_connection_ids: A list of UUIDs for the selected connections (ConnectionComponent instances).

        Returns:
            True if saving was successful, False otherwise.
        """
        logger.info(f"Attempting to save selection as preset '{preset_name}'")
        if not selected_entity_ids:
            logger.warning("No entities selected. Cannot save as preset.")
            return False

        # Determine group anchor (e.g., position of the first selected entity)
        group_anchor_world_pos = Vector2D(0, 0) # Default anchor
        first_entity_id = selected_entity_ids[0]
        if first_entity_id in self.entity_manager.entities:
            from physi_sim.core.component import TransformComponent # Local import
            transform_comp = self.entity_manager.get_component(first_entity_id, TransformComponent)
            if transform_comp:
                group_anchor_world_pos = transform_comp.position
            else:
                logger.warning(f"First selected entity {first_entity_id} has no TransformComponent. Using default anchor (0,0).")
        else:
            logger.warning(f"First selected entity {first_entity_id} not found. Using default anchor (0,0).")


        # Sanitize preset_name
        safe_preset_name = "".join(c for c in preset_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        if not safe_preset_name:
            logger.error(f"Invalid preset name '{preset_name}' after sanitization. Cannot save.")
            return False
        
        filename = f"{safe_preset_name}.json"
        filepath = os.path.join(self.PRESETS_DIR, filename)

        try:
            preset_data = self.serializer.serialize_object_group_to_preset_data(
                selected_entity_ids,
                selected_connection_ids,
                self.entity_manager,
                group_anchor_world_pos
            )

            if not preset_data or not preset_data.get("entities"):
                logger.error(f"Failed to serialize selection for preset '{preset_name}'. No data generated.")
                return False

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2) # UUIDs are handled as strings by _component_to_dict
            
            logger.info(f"Selection saved successfully as preset to {filepath}")
            return True
        except IOError as e:
            logger.error(f"IOError saving preset '{preset_name}' to {filepath}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving preset '{preset_name}' to {filepath}: {e}", exc_info=True)
        return False

    def load_preset(
        self,
        preset_name: str,
        load_position_world: Vector2D,
        name_override: Optional[str] = None, # Note: Name override for group presets might need more complex logic
        initial_velocity: Optional[Vector2D] = None # TODO: Implement initial_velocity for group presets
    ) -> List[UUID]:
        """
        Loads a preset (either single entity or group) and adds it to the current scene.

        Args:
            preset_name: The name of the preset to load.
            load_position_world: The world position where the preset (or its anchor) should be placed.
            name_override: Optional new name. For single entity presets, it renames the entity.
                           For group presets, its application might be more complex (e.g., prefixing).
            initial_velocity: Optional initial velocity for the loaded objects.

        Returns:
            A list of UUIDs of the newly created entities if successful, an empty list otherwise.
        """
        logger.info(f"Attempting to load preset '{preset_name}' to scene at {load_position_world}.")
        filename = f"{preset_name}.json"
        filepath = os.path.join(self.PRESETS_DIR, filename)

        if not os.path.exists(filepath):
            logger.error(f"Preset file not found: {filepath}")
            return []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)

            created_entity_ids: List[UUID] = []

            # Check if it's a new group preset or an old single-entity preset
            if preset_data.get("preset_type") == "group":
                logger.info(f"Loading group preset: {preset_name}")
                from physi_sim.core.component import TransformComponent, ConnectionComponent # Local import
                
                local_to_global_id_map: Dict[int, UUID] = {}

                # 1. Load Entities
                for entity_data_in_preset in preset_data.get("entities", []):
                    local_id = entity_data_in_preset.get("local_id")
                    components_json_list = entity_data_in_preset.get("components", [])
                    
                    if local_id is None:
                        logger.warning(f"Entity in group preset '{preset_name}' missing local_id. Skipping.")
                        continue

                    new_scene_entity_id = self.entity_manager.create_entity()
                    local_to_global_id_map[local_id] = new_scene_entity_id
                    created_entity_ids.append(new_scene_entity_id)

                    for component_json_item_dict in components_json_list:
                        component_instance = self.serializer._dict_to_component(component_json_item_dict, self.entity_manager)
                        if component_instance:
                            if isinstance(component_instance, TransformComponent):
                                # Position in preset is relative to group anchor
                                relative_pos_dict = component_json_item_dict.get("data", {}).get("position", {})
                                if 'x' in relative_pos_dict and 'y' in relative_pos_dict:
                                    relative_pos = Vector2D(relative_pos_dict['x'], relative_pos_dict['y'])
                                    component_instance.position = load_position_world + relative_pos
                                else: # Should not happen if serialization was correct
                                     component_instance.position = load_position_world
                            
                            # TODO: Handle name_override for group entities (e.g., prefixing)
                            # TODO: Handle initial_velocity for PhysicsBodyComponent

                            self.entity_manager.add_component(new_scene_entity_id, component_instance)
                
                # 2. Load Connections
                for conn_data_in_preset in preset_data.get("connections", []):
                    # conn_data_in_preset is already the "data" part of a ConnectionComponent serialization
                    # It needs to be wrapped to look like a full component dict for _dict_to_component
                    
                    original_comp_type_name = conn_data_in_preset.get('original_component_type')
                    if not original_comp_type_name: # Check if original_comp_type_name is None or empty
                        logger.warning(f"Connection data in preset '{preset_name}' missing 'original_component_type'. Skipping.")
                        continue
                        
                    is_spring_type = (original_comp_type_name == SpringComponent.__name__)

                    local_entity_one_id_key = "entity_a_id" if is_spring_type else "source_entity_id"
                    local_entity_two_id_key = "entity_b_id" if is_spring_type else "target_entity_id"

                    local_entity_one_id = conn_data_in_preset.get(local_entity_one_id_key)
                    local_entity_two_id = conn_data_in_preset.get(local_entity_two_id_key)

                    if local_entity_one_id is None or local_entity_two_id is None:
                        logger.warning(f"{original_comp_type_name} in group preset '{preset_name}' missing local entity IDs ('{local_entity_one_id_key}' or '{local_entity_two_id_key}'). Skipping.")
                        continue
                    
                    global_entity_one_id = local_to_global_id_map.get(local_entity_one_id)
                    global_entity_two_id = local_to_global_id_map.get(local_entity_two_id)

                    if not global_entity_one_id or not global_entity_two_id:
                        logger.warning(f"Could not map local entity IDs for a {original_comp_type_name} in '{preset_name}'. Skipping.")
                        continue
                    
                    # Create a temporary full component dict for deserialization
                    original_comp_type_name = conn_data_in_preset.get('original_component_type')
                    if not original_comp_type_name:
                        logger.warning(f"Connection data in preset '{preset_name}' missing 'original_component_type'. Skipping.")
                        continue

                    # Create a copy to modify, ensuring we don't carry over the original_component_type field
                    # into the actual component's data if it's not part of its definition.
                    modified_conn_data = {k: v for k, v in conn_data_in_preset.items() if k != 'original_component_type'}
                    
                    # is_spring = (original_comp_type_name == SpringComponent.__name__) # Already defined as is_spring_type

                    if is_spring_type:
                        modified_conn_data["entity_a_id"] = str(global_entity_one_id)
                        modified_conn_data["entity_b_id"] = str(global_entity_two_id)
                        modified_conn_data.pop('source_entity_id', None) # Clean up if present
                        modified_conn_data.pop('target_entity_id', None) # Clean up if present
                    else: # ConnectionComponent
                        modified_conn_data["source_entity_id"] = str(global_entity_one_id)
                        modified_conn_data["target_entity_id"] = str(global_entity_two_id)
                        modified_conn_data.pop('entity_a_id', None) # Clean up if present
                        modified_conn_data.pop('entity_b_id', None) # Clean up if present

                    # Ensure a new, unique ID is assigned for the component being loaded.
                    # This ID will be used by _dict_to_component for instantiation if the component's
                    # constructor requires 'id' (like SpringComponent), or it will be the ID
                    # of the instance if the component generates its own (like ConnectionComponent's default_factory).
                    # EntityManager.add_independent_component will then use this ID.
                    new_component_id = uuid.uuid4()
                    modified_conn_data['id'] = str(new_component_id) # Pass as string, _reconstruct_value handles UUID conversion

                    temp_conn_component_json = {
                        "type": original_comp_type_name, # Use the actual type name
                        "data": modified_conn_data
                    }
                    
                    conn_instance = self.serializer._dict_to_component(temp_conn_component_json, self.entity_manager)

                    if conn_instance:
                        # The ID should now be correctly set by _dict_to_component
                        # either from the provided 'id' in modified_conn_data or by the component's default_factory.
                        # We then ensure the entity references are correct.
                        if not hasattr(conn_instance, 'id') or not isinstance(conn_instance.id, UUID):
                             logger.error(f"Loaded component {original_comp_type_name} instance is missing a valid UUID 'id'. Skipping.")
                             continue
                        
                        # Ensure the instance has the correct global UUIDs for connected entities
                        if is_spring_type and isinstance(conn_instance, SpringComponent):
                            conn_instance.entity_a_id = global_entity_one_id
                            conn_instance.entity_b_id = global_entity_two_id
                        elif not is_spring_type and isinstance(conn_instance, ConnectionComponent):
                            conn_instance.source_entity_id = global_entity_one_id
                            conn_instance.target_entity_id = global_entity_two_id
                        else:
                            logger.warning(f"Created connection instance type mismatch or invalid. Expected {original_comp_type_name}, got {type(conn_instance).__name__}")
                            continue # Skip adding if type is wrong
                        
                        # Ensure the instance's ID is the new_component_id we generated if it was a type
                        # that took 'id' in its constructor.
                        # If it used a default_factory, its ID might be different, but add_independent_component
                        # will use the ID from the instance.
                        if hasattr(conn_instance, 'id'): # Should always be true now
                             conn_instance.id = new_component_id # Explicitly set to the one we generated for consistency for SpringComponent

                        self.entity_manager.add_independent_component(conn_instance)
                    else:
                        logger.warning(f"Failed to create {original_comp_type_name} instance from preset '{preset_name}'. Data: {modified_conn_data}")

            else: # Old single-entity preset
                logger.info(f"Loading single-entity preset: {preset_name}")
                actual_entity_uuid = self.entity_manager.create_entity()
                # Pass the UUID object
                created_id_obj = self.serializer.deserialize_preset_dict_to_entity(
                    preset_data,
                    self.entity_manager,
                    actual_entity_uuid,
                    load_position_world,
                    name_override
                )
                if created_id_obj:
                    created_entity_ids.append(created_id_obj)
                # TODO: Handle initial_velocity for single entity preset

            if created_entity_ids:
                logger.info(f"Preset '{preset_name}' loaded successfully. Created entities: {created_entity_ids}")
            else:
                logger.warning(f"Preset '{preset_name}' loaded, but no entities were created.")
            return created_entity_ids

        except FileNotFoundError:
            logger.error(f"Preset file not found during load: {filepath}")
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError loading preset from {filepath}: {e}")
        except ValueError as e:
            logger.error(f"ValueError loading preset from {filepath}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading preset '{preset_name}' from {filepath}: {e}", exc_info=True)
        
        return []

    def get_available_presets(self) -> List[str]:
        """
        Scans the presets directory and returns a list of available preset names.

        Returns:
            A list of preset names (filenames without .json extension).
        """
        if not os.path.exists(self.PRESETS_DIR):
            logger.warning(f"Presets directory not found: {self.PRESETS_DIR}")
            return []
        
        presets = []
        try:
            for filename in os.listdir(self.PRESETS_DIR):
                if filename.endswith(".json"):
                    presets.append(os.path.splitext(filename)[0])
            logger.debug(f"Found available presets: {presets}")
        except OSError as e:
            logger.error(f"Error listing presets in {self.PRESETS_DIR}: {e}")
            return [] # Return empty list on error
        return presets