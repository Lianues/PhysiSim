import json
import logging
import os
from typing import Optional, List, Tuple, Dict # Added List, Tuple, Dict
from uuid import UUID # Import UUID for type hinting
import uuid # Keep this for generating UUIDs if needed elsewhere
from physi_sim.core.vector import Vector2D # Added for type hinting

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
                    
                    local_source_entity_id = conn_data_in_preset.get("source_entity_id") # Changed key
                    local_target_entity_id = conn_data_in_preset.get("target_entity_id") # Changed key

                    if local_source_entity_id is None or local_target_entity_id is None: # Changed variable names
                        logger.warning(f"Connection in group preset '{preset_name}' missing local entity IDs. Skipping.")
                        continue
                    
                    global_source_entity_id = local_to_global_id_map.get(local_source_entity_id) # Changed variable name
                    global_target_entity_id = local_to_global_id_map.get(local_target_entity_id) # Changed variable name

                    if not global_source_entity_id or not global_target_entity_id: # Changed variable names
                        logger.warning(f"Could not map local entity IDs for a connection in '{preset_name}'. Skipping.")
                        continue
                    
                    # Create a temporary full component dict for deserialization
                    # The 'type' is ConnectionComponent.__name__
                    # The 'data' is conn_data_in_preset, but with entity IDs replaced
                    
                    # Create a copy to modify
                    modified_conn_data = dict(conn_data_in_preset)
                    modified_conn_data["source_entity_id"] = str(global_source_entity_id) # Changed key and variable name
                    modified_conn_data["target_entity_id"] = str(global_target_entity_id) # Changed key and variable name
                    
                    # The ConnectionComponent itself needs a unique ID if it's stored independently
                    # Let's assume ConnectionComponent from preset might not have its own 'id' field in 'data'
                    # or if it does, it's irrelevant as a new one will be generated by EntityManager.
                    # If ConnectionComponent instances are expected to have their own persistent UUIDs stored
                    # in the preset and reused, this logic needs adjustment.
                    # For now, let's assume new ConnectionComponents are created.
                    if 'id' in modified_conn_data: # Remove preset's own connection ID if present
                        del modified_conn_data['id']


                    temp_conn_component_json = {
                        "type": ConnectionComponent.__name__,
                        "data": modified_conn_data
                    }
                    
                    conn_instance = self.serializer._dict_to_component(temp_conn_component_json, self.entity_manager)
                    if conn_instance and isinstance(conn_instance, ConnectionComponent):
                        # Ensure the instance has the correct global UUIDs if _dict_to_component didn't fully set them
                        # (though it should if the data was prepared correctly)
                        conn_instance.source_entity_id = global_source_entity_id # Changed attribute name
                        conn_instance.target_entity_id = global_target_entity_id # Changed attribute name
                        
                        # ConnectionComponents are independent, add them as such
                        self.entity_manager.add_independent_component(conn_instance)
                    else:
                        logger.warning(f"Failed to create ConnectionComponent instance from preset '{preset_name}'. Data: {modified_conn_data}")

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