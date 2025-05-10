from typing import Type, TypeVar, Optional, Dict, Set, List, Any
import uuid

from .component import Component # Import the actual Component class

# Define a type variable for Component subtypes
C = TypeVar('C', bound=Component) # Use the imported Component class
# Define EntityID type
EntityID = uuid.UUID

class EntityManager:
    """
    Manages entities and their components in an ECS architecture.
    """

    def __init__(self):
        self.entities: Set[EntityID] = set()
        self.components_by_type: Dict[Type[Component], Dict[EntityID, Component]] = {}
        # For potentially faster access to all components of a specific entity
        self.components_by_entity: Dict[EntityID, Dict[Type[Component], Component]] = {}
        # --- Added for creation order tracking ---
        self._creation_counter: int = 0
        self.entity_creation_order: Dict[EntityID, int] = {}
        # --- End added ---
        self._next_entity_id_int: int = 0 # If using simple integer IDs
        # Data structure for independent components
        self.independent_components: Dict[Type[Component], Dict[uuid.UUID, Component]] = {}
 
    def _generate_entity_id(self) -> EntityID:
        """Generates a unique entity ID."""
        # Using UUIDs for globally unique IDs
        return uuid.uuid4()
        # Alternatively, for simple integer IDs:
        # new_id = self._next_entity_id_int
        # self._next_entity_id_int += 1
        # return new_id


    def create_entity(self, entity_id: Optional[EntityID] = None) -> EntityID:
        """
        Creates a new entity. If entity_id is provided, it attempts to use it.
        Otherwise, a new unique ID is generated.
        """
        if entity_id is None:
            entity_id = self._generate_entity_id()
        elif not isinstance(entity_id, uuid.UUID): # Ensure it's a UUID if provided
            try:
                # Attempt to convert if string, though type hint is EntityID (UUID)
                # This path might not be hit if type checking is strict upstream
                entity_id = uuid.UUID(str(entity_id))
            except ValueError:
                # Or raise an error if conversion fails / ID is invalid format
                # logger.warning(f"Provided entity_id '{entity_id}' is not a valid UUID. Generating a new one.")
                print(f"Warning: Provided entity_id '{entity_id}' is not a valid UUID. Generating a new one.")
                entity_id = self._generate_entity_id()
            
        if entity_id in self.entities:
            # Handle case where ID already exists, e.g. raise error or log warning
            # For loading, we might expect to overwrite or just ensure it's there.
            # For now, let's assume if it exists, we are good.
            # logger.warning(f"Entity with ID {entity_id} already exists. Re-using.")
            print(f"Warning: Entity with ID {entity_id} already exists. Re-using.")
        else:
            self.entities.add(entity_id)
            # Ensure this entry is created for new entities
            self.components_by_entity[entity_id] = {}
            # --- Record creation order ---
            self.entity_creation_order[entity_id] = self._creation_counter
            self._creation_counter += 1
            # --- End record ---
        return entity_id
 
    def destroy_entity(self, entity_id: EntityID) -> None:
        """
        Destroys an entity and all its associated components.
        """
        if entity_id not in self.entities:
            # Or raise an error, e.g., ValueError(f"Entity {entity_id} not found.")
            return

        # Remove components associated with this entity
        if entity_id in self.components_by_entity:
            for component_type in list(self.components_by_entity[entity_id].keys()): # list() for safe iteration
                self.remove_component(entity_id, component_type)
            del self.components_by_entity[entity_id]
 
        # --- Remove creation order record ---
        if entity_id in self.entity_creation_order:
            del self.entity_creation_order[entity_id]
        # --- End remove ---

        self.entities.remove(entity_id)
 
 
    def add_component(self, entity_id: EntityID, component_instance: C) -> C:
        """
        Adds a component instance to an entity.
        Returns the added component instance.
        Raises ValueError if the entity does not exist.
        """
        if entity_id not in self.entities:
            raise ValueError(f"Cannot add component to non-existent entity {entity_id}")

        component_type = type(component_instance)

        if component_type not in self.components_by_type:
            self.components_by_type[component_type] = {}
        self.components_by_type[component_type][entity_id] = component_instance

        if entity_id not in self.components_by_entity: # Should be created with entity
            self.components_by_entity[entity_id] = {}
        self.components_by_entity[entity_id][component_type] = component_instance
        
        return component_instance

    def remove_component(self, entity_id: EntityID, component_type: Type[C]) -> None:
        """
        Removes a component of a specific type from an entity.
        """
        if entity_id not in self.entities:
            # Or raise an error
            return

        if component_type in self.components_by_type and entity_id in self.components_by_type[component_type]:
            del self.components_by_type[component_type][entity_id]
            # If this was the last component of this type, clean up the dictionary entry
            if not self.components_by_type[component_type]:
                del self.components_by_type[component_type]

        if entity_id in self.components_by_entity and component_type in self.components_by_entity[entity_id]:
            del self.components_by_entity[entity_id][component_type]


    def get_component(self, entity_id: EntityID, component_type: Type[C]) -> Optional[C]:
        """
        Retrieves a component of a specific type from an entity.
        Returns the component instance or None if not found.
        """
        if entity_id not in self.entities:
            return None # Or raise error
        
        # Faster lookup via components_by_entity if available and populated this way
        # return self.components_by_entity.get(entity_id, {}).get(component_type)
        
        # Lookup via components_by_type
        return self.components_by_type.get(component_type, {}).get(entity_id)


    def has_component(self, entity_id: EntityID, component_type: Type[Component]) -> bool:
        """
        Checks if an entity has a component of a specific type.
        """
        if entity_id not in self.entities:
            return False
        return component_type in self.components_by_type and entity_id in self.components_by_type[component_type]
        # Or:
        # return entity_id in self.components_by_entity and component_type in self.components_by_entity[entity_id]

    def get_entities_with_components(self, *component_types: Type[Component]) -> List[EntityID]:
        """
        Retrieves a list of entity IDs that have all the specified component types.
        """
        if not component_types:
            return list(self.entities) # Return all entities if no types specified

        # Start with entities that have the first component type
        first_type = component_types[0]
        if first_type not in self.components_by_type:
            return []
        
        candidate_entities: Set[EntityID] = set(self.components_by_type[first_type].keys())

        # Iteratively filter down the set
        for comp_type in component_types[1:]:
            if not candidate_entities: # No need to continue if set is empty
                break
            if comp_type not in self.components_by_type:
                return [] # If any component type is not present at all
            
            # Keep only entities that also have this component_type
            candidate_entities.intersection_update(self.components_by_type[comp_type].keys())
            
        return list(candidate_entities)

    def get_all_components_of_type(self, component_type: Type[C]) -> List[C]:
        """
        Retrieves all component instances of a specific type across all entities.
        """
        if component_type not in self.components_by_type:
            return []
        return list(self.components_by_type[component_type].values()) # type: ignore

    def get_all_components_for_entity(self, entity_id: EntityID) -> Dict[Type[Component], Component]:
        """
        Retrieves all components associated with a specific entity.
        Returns a dictionary mapping component types to component instances.
        Returns an empty dict if the entity does not exist or has no components.
        """
        if entity_id not in self.entities:
            return {} # Or raise error
        
        return dict(self.components_by_entity.get(entity_id, {})) # Return a copy

    # --- Methods for Independent Components ---

    def create_independent_component(self, component_type: Type[C], component_id: Optional[uuid.UUID] = None, **kwargs) -> C:
        """
        Creates an instance of an independent component, assigns it an ID, and stores it.

        Args:
            component_type: The class of the component to create (e.g., SpringComponent).
            component_id: Optional UUID for the component. If None, a new UUID is generated.
            **kwargs: Arguments to pass to the component's constructor.
                      The 'id' will be added/overridden by this method.

        Returns:
            The created component instance.

        Raises:
            ValueError: If a component_id is provided and already exists for this component_type.
        """
        if component_id is None:
            component_id = uuid.uuid4()
        elif not isinstance(component_id, uuid.UUID):
            # Attempt to convert if string, though type hint is UUID
            try:
                component_id = uuid.UUID(str(component_id))
            except ValueError:
                # Or raise an error if conversion fails / ID is invalid format
                print(f"Warning: Provided component_id '{component_id}' for {component_type.__name__} "
                      f"is not a valid UUID. Generating a new one.")
                component_id = uuid.uuid4()

        if component_type not in self.independent_components:
            self.independent_components[component_type] = {}
        
        if component_id in self.independent_components[component_type]:
            raise ValueError(
                f"Independent component of type {component_type.__name__} with ID {component_id} already exists."
            )

        # Ensure 'id' is part of kwargs for the component constructor
        # This assumes the component's __init__ can accept 'id' or has an 'id' attribute to be set.
        kwargs['id'] = component_id
        
        try:
            component_instance = component_type(**kwargs)
        except TypeError as e:
            # A common issue might be if the component_type.__init__ doesn't accept 'id'.
            # We'll try to set it post-init if that's the case, assuming 'id' is a public attribute.
            if 'id' in str(e): # Heuristic: check if 'id' was an unexpected argument
                temp_kwargs = {k: v for k, v in kwargs.items() if k != 'id'}
                component_instance = component_type(**temp_kwargs)
                # Try setting the id attribute directly after instantiation
                # This requires the component to have an 'id' attribute.
                if hasattr(component_instance, 'id'):
                    setattr(component_instance, 'id', component_id)
                else:
                    # If it doesn't have an 'id' attribute, this is a problem with component design.
                    # For now, re-raise, or log a more specific warning.
                    raise TypeError(
                        f"Component {component_type.__name__} constructor failed with 'id' and "
                        f"instance does not have an 'id' attribute to set. Original error: {e}"
                    ) from e
            else:
                raise # Re-raise other TypeErrors

        # Ensure the instance has the ID, either from constructor or setattr
        # This is a safeguard; ideally, the component itself handles its ID.
        if not hasattr(component_instance, 'id') or getattr(component_instance, 'id') != component_id:
             # If the component is expected to manage its ID internally via constructor,
             # but it wasn't set, or set incorrectly, this is a sign of mismatch.
             # For now, we'll forcefully set it if possible.
            try:
                setattr(component_instance, 'id', component_id)
            except AttributeError:
                 # This means the component doesn't even have an 'id' attribute.
                 # This is a more fundamental issue with the component design for independent use.
                print(f"Warning: Component {component_type.__name__} instance does not have an 'id' attribute. "
                      f"The provided/generated component_id {component_id} could not be set.")


        self.independent_components[component_type][component_id] = component_instance
        return component_instance

    def add_independent_component(self, component_instance: C) -> None:
        """
        Adds a pre-existing independent component instance.
        The component instance must have its 'id' attribute already set and be a UUID.

        Args:
            component_instance: The component instance to add.

        Raises:
            ValueError: If the component instance does not have an 'id' attribute,
                        or if the id is not a UUID,
                        or if a component of the same type and id already exists.
            AttributeError: If component_instance.id does not exist.
        """
        component_type = type(component_instance)
        
        if not hasattr(component_instance, 'id'):
            raise ValueError(f"Component instance of type {component_type.__name__} must have an 'id' attribute.")
        
        component_id = getattr(component_instance, 'id')
        if not isinstance(component_id, uuid.UUID):
            raise ValueError(
                f"Component instance 'id' must be a UUID. Got {type(component_id)} for {component_type.__name__}."
            )

        if component_type not in self.independent_components:
            self.independent_components[component_type] = {}

        if component_id in self.independent_components[component_type]:
            raise ValueError(
                f"Independent component of type {component_type.__name__} with ID {component_id} already exists."
            )
        
        self.independent_components[component_type][component_id] = component_instance


    def get_independent_component_by_id(self, component_id: uuid.UUID, component_type: Type[C]) -> Optional[C]:
        """
        Retrieves an independent component instance by its ID and type.

        Args:
            component_id: The UUID of the component.
            component_type: The class of the component.

        Returns:
            The component instance if found, otherwise None.
        """
        return self.independent_components.get(component_type, {}).get(component_id)

    def get_all_independent_components_of_type(self, component_type: Type[C]) -> List[C]:
        """
        Retrieves all independent component instances of a specific type.

        Args:
            component_type: The class of the components to retrieve.

        Returns:
            A list of component instances of the specified type.
        """
        return list(self.independent_components.get(component_type, {}).values()) # type: ignore

    def remove_independent_component_by_id(self, component_id: uuid.UUID, component_type: Type[Component]) -> bool:
        """
        Removes an independent component by its ID and type.

        Args:
            component_id: The UUID of the component to remove.
            component_type: The class of the component to remove.

        Returns:
            True if the component was found and removed, False otherwise.
        """
        if component_type in self.independent_components and \
           component_id in self.independent_components[component_type]:
            del self.independent_components[component_type][component_id]
            if not self.independent_components[component_type]: # Clean up type dict if empty
                del self.independent_components[component_type]
            return True
        return False

    def clear_all_independent_components(self) -> None:
        """
        Removes all independent components of all types.
        """
        self.independent_components.clear()

    # --- General Management ---
    def clear_all(self) -> None:
        """
        Clears all entities, their components, and all independent components.
        Resets the entity manager to its initial state.
        """
        # Clear entity-related data
        self.entities.clear()
        self.components_by_type.clear()
        self.components_by_entity.clear()
        self.entity_creation_order.clear()
        self._creation_counter = 0
        # self._next_entity_id_int = 0 # Reset if using integer IDs

        # Clear independent components
        self.clear_all_independent_components()
        
        print("EntityManager cleared: All entities, components, and independent components removed.")


# Example Usage (can be removed or moved to tests)
if __name__ == '__main__':
    # Define some example components
    class PositionComponent(Component):
        def __init__(self, x: float, y: float):
            self.x = x
            self.y = y
        def __repr__(self):
            return f"Position({self.x}, {self.y})"

    class VelocityComponent(Component):
        def __init__(self, dx: float, dy: float):
            self.dx = dx
            self.dy = dy
        def __repr__(self):
            return f"Velocity({self.dx}, {self.dy})"

    class RenderComponent(Component):
        def __init__(self, color: str):
            self.color = color
        def __repr__(self):
            return f"Render({self.color})"

    em = EntityManager()

    # Create entities
    entity1 = em.create_entity()
    entity2 = em.create_entity()
    entity3 = em.create_entity()

    print(f"Created entities: {entity1}, {entity2}, {entity3}")

    # Add components
    pos1 = em.add_component(entity1, PositionComponent(0, 0))
    vel1 = em.add_component(entity1, VelocityComponent(1, 0))
    ren1 = em.add_component(entity1, RenderComponent("red"))

    pos2 = em.add_component(entity2, PositionComponent(10, 5))
    vel2 = em.add_component(entity2, VelocityComponent(0, -1))
    # Entity 2 does not have RenderComponent

    pos3 = em.add_component(entity3, PositionComponent(-5, -5))
    ren3 = em.add_component(entity3, RenderComponent("blue"))
    # Entity 3 does not have VelocityComponent


    print(f"\nComponents for entity1: {em.get_all_components_for_entity(entity1)}")
    print(f"Components for entity2: {em.get_all_components_for_entity(entity2)}")

    # Get specific component
    print(f"\nPosition of entity1: {em.get_component(entity1, PositionComponent)}")
    print(f"Velocity of entity2: {em.get_component(entity2, VelocityComponent)}")
    print(f"Render of entity2: {em.get_component(entity2, RenderComponent)}") # Should be None

    # Has component
    print(f"\nEntity1 has VelocityComponent: {em.has_component(entity1, VelocityComponent)}")
    print(f"Entity2 has RenderComponent: {em.has_component(entity2, RenderComponent)}")

    # Get entities with components
    print(f"\nEntities with PositionComponent: {em.get_entities_with_components(PositionComponent)}")
    entities_with_pos_and_render = em.get_entities_with_components(PositionComponent, RenderComponent)
    print(f"Entities with Position AND Render: {entities_with_pos_and_render}")
    for e_id in entities_with_pos_and_render:
        print(f"  Entity {e_id}: Pos={em.get_component(e_id, PositionComponent)}, Render={em.get_component(e_id, RenderComponent)}")

    entities_with_pos_vel_render = em.get_entities_with_components(PositionComponent, VelocityComponent, RenderComponent)
    print(f"Entities with Position, Velocity AND Render: {entities_with_pos_vel_render}")
    if entities_with_pos_vel_render:
         print(f"  Entity {entities_with_pos_vel_render[0]} has all three.")


    # Get all components of a type
    all_positions = em.get_all_components_of_type(PositionComponent)
    print(f"\nAll PositionComponents: {all_positions}")
    all_renders = em.get_all_components_of_type(RenderComponent)
    print(f"All RenderComponents: {all_renders}")


    # Destroy entity
    print(f"\nDestroying entity2: {entity2}")
    em.destroy_entity(entity2)
    print(f"Entity2 exists: {entity2 in em.entities}")
    print(f"Position of entity2 after destruction: {em.get_component(entity2, PositionComponent)}")
    print(f"All PositionComponents after destroying entity2: {em.get_all_components_of_type(PositionComponent)}")

    print(f"\nRemaining entities: {em.entities}")
    print(f"Components by type: {em.components_by_type}")
    print(f"Components by entity: {em.components_by_entity}")

    # Test destroying an entity that doesn't exist
    non_existent_id = uuid.uuid4()
    em.destroy_entity(non_existent_id) # Should not error

    # Test adding component to non-existent entity
    try:
        em.add_component(non_existent_id, PositionComponent(1,1))
    except ValueError as e:
        print(f"\nError as expected: {e}")

    # --- Test Independent Components ---
    print("\n--- Testing Independent Components ---")

    # Define a dummy independent component for testing
    class SpringConnection(Component):
        def __init__(self, entity_a_id: EntityID, entity_b_id: EntityID, stiffness: float, id: Optional[uuid.UUID]=None):
            self.id = id # Set by EntityManager or passed in
            self.entity_a_id = entity_a_id
            self.entity_b_id = entity_b_id
            self.stiffness = stiffness
            if self.id is None: # Should ideally be handled by create_independent_component
                self.id = uuid.uuid4()


        def __repr__(self):
            return f"SpringConnection(id={self.id}, a={self.entity_a_id}, b={self.entity_b_id}, k={self.stiffness})"

    # Create independent components
    spring1_id = uuid.uuid4()
    spring1 = em.create_independent_component(
        SpringConnection,
        component_id=spring1_id,
        entity_a_id=entity1,
        entity_b_id=entity3, # entity2 was destroyed
        stiffness=100.0
    )
    print(f"Created spring1: {spring1}")

    spring2 = em.create_independent_component(
        SpringConnection,
        entity_a_id=entity1, # Re-using entity1
        entity_b_id=uuid.uuid4(), # A dummy ID for an entity that might not exist in EM's entities list
        stiffness=50.0
    )
    print(f"Created spring2: {spring2}")
    
    # Test creating with an existing ID (should fail)
    try:
        em.create_independent_component(
            SpringConnection,
            component_id=spring1_id, # Duplicate ID
            entity_a_id=entity1,
            entity_b_id=entity3,
            stiffness=10.0
        )
    except ValueError as e:
        print(f"Error as expected when creating duplicate ID: {e}")


    # Get independent component by ID
    retrieved_spring1 = em.get_independent_component_by_id(spring1.id, SpringConnection)
    print(f"Retrieved spring1 by ID: {retrieved_spring1}")
    
    non_existent_spring_id = uuid.uuid4()
    retrieved_non_existent = em.get_independent_component_by_id(non_existent_spring_id, SpringConnection)
    print(f"Retrieved non-existent spring by ID: {retrieved_non_existent}") # Should be None

    # Get all independent components of type
    all_springs = em.get_all_independent_components_of_type(SpringConnection)
    print(f"All SpringConnections: {all_springs}")

    # Remove independent component by ID
    print(f"Removing spring2 (ID: {spring2.id})")
    remove_success = em.remove_independent_component_by_id(spring2.id, SpringConnection)
    print(f"Removal successful: {remove_success}")
    all_springs_after_remove = em.get_all_independent_components_of_type(SpringConnection)
    print(f"All SpringConnections after removal: {all_springs_after_remove}")

    remove_fail = em.remove_independent_component_by_id(spring2.id, SpringConnection) # Try removing again
    print(f"Second removal attempt successful: {remove_fail}")


    # Test add_independent_component
    print("\n--- Testing add_independent_component ---")
    
    # Valid case
    pre_made_spring_id = uuid.uuid4()
    pre_made_spring = SpringConnection(entity1, entity3, 200.0, id=pre_made_spring_id)
    try:
        em.add_independent_component(pre_made_spring)
        print(f"Added pre_made_spring: {em.get_independent_component_by_id(pre_made_spring_id, SpringConnection)}")
    except Exception as e:
        print(f"Error adding pre_made_spring: {e}")

    all_springs_after_add = em.get_all_independent_components_of_type(SpringConnection)
    print(f"All SpringConnections after add: {all_springs_after_add}")

    # Case: ID already exists
    try:
        em.add_independent_component(pre_made_spring) # Adding same instance again
    except ValueError as e:
        print(f"Error as expected when adding component with existing ID: {e}")

    # Case: No 'id' attribute (modify class temporarily for test, or use a different class)
    class NoIdComponent(Component):
        def __init__(self, val): self.val = val
    
    no_id_comp = NoIdComponent(123)
    try:
        em.add_independent_component(no_id_comp)
    except ValueError as e:
        print(f"Error as expected when adding component with no 'id' attribute: {e}")

    # Case: 'id' attribute is not UUID
    class WrongIdTypeComponent(Component):
        def __init__(self, val): self.id = "not-a-uuid"; self.val = val
    
    wrong_id_comp = WrongIdTypeComponent(456)
    try:
        em.add_independent_component(wrong_id_comp)
    except ValueError as e:
        print(f"Error as expected when adding component with non-UUID 'id': {e}")


    # Test clear_all_independent_components
    print("\nClearing all independent components...")
    em.clear_all_independent_components()
    all_springs_after_clear = em.get_all_independent_components_of_type(SpringConnection)
    print(f"All SpringConnections after clear_all_independent_components: {all_springs_after_clear}")
    print(f"Independent components dict: {em.independent_components}")


    # Re-populate some data for full clear_all test
    em.create_entity()
    em.create_independent_component(SpringConnection, entity_a_id=entity1, entity_b_id=entity3, stiffness=5.0)
    print(f"\nEntities before clear_all: {em.entities}")
    print(f"Independent SpringConnections before clear_all: {em.get_all_independent_components_of_type(SpringConnection)}")
    
    print("\nCalling EntityManager.clear_all()...")
    em.clear_all()
    print(f"Entities after clear_all: {em.entities}")
    print(f"Components_by_type after clear_all: {em.components_by_type}")
    print(f"Components_by_entity after clear_all: {em.components_by_entity}")
    print(f"Independent_components after clear_all: {em.independent_components}")
    print(f"Entity creation order after clear_all: {em.entity_creation_order}")
    print(f"Creation counter after clear_all: {em.creation_counter}")