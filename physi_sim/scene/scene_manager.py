import json
import logging
import os
from typing import Optional, List, Tuple # Added List, Tuple
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

    def save_entity_as_preset(self, entity_id: UUID, preset_name: str) -> bool: # Changed entity_id type hint to UUID
        """
        Saves a specific entity from the current scene as a preset.

        Args:
            entity_id: The ID of the entity to save as a preset.
            preset_name: The name for the preset (filename without extension).

        Returns:
            True if saving was successful, False otherwise.
        """
        # entity_id is now expected to be a UUID object
        logger.info(f"Attempting to save entity UUID '{entity_id}' as preset '{preset_name}'")
        if entity_id not in self.entity_manager.entities: # Check using UUID object
            logger.error(f"Entity UUID '{entity_id}' not found. Cannot save as preset.")
            return False

        # Sanitize preset_name to be a valid filename (basic sanitization)
        safe_preset_name = "".join(c for c in preset_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        if not safe_preset_name:
            logger.error(f"Invalid preset name '{preset_name}' after sanitization. Cannot save.")
            return False
        
        filename = f"{safe_preset_name}.json"
        filepath = os.path.join(self.PRESETS_DIR, filename)

        try:
            # Pass the UUID object directly to the serializer
            preset_data = self.serializer.serialize_entity_to_preset_dict(self.entity_manager, entity_id)
            if not preset_data: # serialize_entity_to_preset_dict might return empty if entity not found
                logger.error(f"Failed to serialize entity UUID '{entity_id}' for preset '{preset_name}'.")
                return False

            # Custom default function for json.dump to handle UUID
            def json_default_serializer(obj):
                if isinstance(obj, uuid.UUID):
                    return str(obj)
                # Let the base class default method raise the TypeError
                # Or handle other types here if needed
                raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
            
            # --- DEBUG: Print the data just before json.dump ---
            print(f"DEBUG: Data before json.dump in save_entity_as_preset: {preset_data}")
            # --- END DEBUG ---

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2, default=json_default_serializer)
            
            logger.info(f"Entity '{entity_id}' saved successfully as preset to {filepath}")
            return True
        except IOError as e:
            logger.error(f"IOError saving preset '{preset_name}' to {filepath}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving preset '{preset_name}' to {filepath}: {e}")
        return False

    def load_preset_to_scene(
        self,
        preset_name: str,
        target_position: Vector2D,
        name_override: Optional[str] = None
    ) -> Optional[str]:
        """
        Loads a preset and adds it as a new entity to the current scene.

        Args:
            preset_name: The name of the preset to load (filename without extension).
            target_position: The position where the new entity should be placed.
            name_override: Optional new name for the entity (for its IdentifierComponent).

        Returns:
            The ID of the newly created entity if successful, None otherwise.
        """
        logger.info(f"Attempting to load preset '{preset_name}' to scene.")
        filename = f"{preset_name}.json" # Assume preset_name is already sanitized or valid
        filepath = os.path.join(self.PRESETS_DIR, filename)

        if not os.path.exists(filepath):
            logger.error(f"Preset file not found: {filepath}")
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
            
            # Generate a new unique ID for the entity being loaded from preset
            # Let EntityManager handle the creation and return the actual UUID object
            actual_entity_uuid = self.entity_manager.create_entity()
            # Ensure entity_manager can create an entity with this ID or uses it.
            # The SceneSerializer's deserialize_preset_dict_to_entity will add components to this ID.
            # If entity_manager.create_entity actually returns an ID, use that instead.
            # For now, assuming new_entity_id is passed directly.
            
            # It's good practice to "create" the entity in EntityManager first if it has such a method
            # that doesn't require components immediately, or if add_component implicitly creates it.
            # Let's assume add_component will handle creation if new_entity_id doesn't exist.
            # self.entity_manager.create_entity(new_entity_id) # This line is now handled by the call above that assigns to actual_entity_uuid
 
            created_entity_id = self.serializer.deserialize_preset_dict_to_entity(
                preset_data,
                self.entity_manager,
                actual_entity_uuid, # Pass the UUID object
                target_position,
                name_override
            )
            
            logger.info(f"Preset '{preset_name}' loaded successfully as new entity '{created_entity_id}' at {target_position}.")
            return created_entity_id
        except FileNotFoundError: # Should be caught by os.path.exists, but good to have
            logger.error(f"Preset file not found during load: {filepath}")
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError loading preset from {filepath}: {e}")
        except ValueError as e: # Raised by deserializer for bad preset data
            logger.error(f"ValueError (e.g., invalid preset data format) loading preset from {filepath}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading preset '{preset_name}' from {filepath}: {e}")
        
        return None

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