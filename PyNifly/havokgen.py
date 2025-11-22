"""Havok collision generator for PyNifly.

Generates and applies Havok collision shapes to Blender objects.
Integrates with PyNifly's existing collision system and enums.
"""

try:
    import bpy
except ImportError:
    # Running outside Blender context
    bpy = None

from nifdefs import SkyrimHavokMaterial, SkyrimCollisionLayer


class HavokCollisionGenerator:
    """Generate Havok collision properties and shapes."""

    def __init__(self, target_material=SkyrimHavokMaterial.STONE, target_layer=SkyrimCollisionLayer.STATIC):
        """Initialize generator with default Havok settings.

        Args:
          target_material: HavokMaterial enum value (default: STONE)
          target_layer: CollisionLayer enum value (default: STATIC)
        """
        self.TARGET_MATERIAL_ENUM = SkyrimHavokMaterial
        self.default_havok_collision_layer = SkyrimHavokMaterial.STATIC
        self.default_havok_collision_flags = 0  # Bitmask, byte
        self.default_havok_collision_group = 0  # Group ID, ushort

        self.packed_havok_collision_filter = (
            int(self.default_havok_collision_layer)
            | (self.default_havok_collision_flags << 8)
            | (self.default_havok_collision_group << 16)
        )

        self.havok_defaults = {
            "HavokLayer": int(self.default_havok_collision_layer),
            "HavokColFilter": self.packed_havok_collision_filter,
            "HavokMaterial": int(self.TARGET_MATERIAL_ENUM.STONE),
            "HavokMass": 0.0,  # 0.0 = Infinite/Static
            "HavokFriction": 0.5,
            "HavokRestitution": 0.4,
            "HavokMotionSystem": 7,  # MO_SYS_FIXED
            "HavokQualityType": 1,  # MO_QUAL_FIXED
            "HavokSolverDeactivation": 1,  # SOLVER_DEACTIVATION_OFF
        }

    def _add_havok_properties(self, obj):
        """Add Havok custom properties to an object.

        Args:
          obj: Blender object to add properties to
        """
        for prop, value in self.havok_defaults.items():
            # Convert Enum to int for storage
            if hasattr(value, "value"):
                value = int(value)

            obj[prop] = value

            # Enable property editing UI
            if isinstance(value, (int, float)):
                obj.id_properties_ui(prop).update(min=0)

    def create_collision_root(self, target_obj):
        """Create bhkCollisionObject Empty for a target.

        Args:
          target_obj: Target object to create collision root for

        Returns:
          Collision root empty object
        """
        col_name = f"Collision_{target_obj.name}"

        # Avoid duplicates
        existing = [c for c in target_obj.children if c.name.startswith("Collision_")]
        if existing:
            print(f"Skipping {target_obj.name}, already has collision: " f"{existing[0].name}")
            return existing[0]

        col_empty = bpy.data.objects.new(col_name, None)
        col_empty.empty_display_type = "ARROWS"
        col_empty.empty_display_size = 0.5

        # Link to collection and parent
        bpy.context.collection.objects.link(col_empty)
        col_empty.parent = target_obj
        col_empty.matrix_parent_inverse = target_obj.matrix_world.inverted()

        self._add_havok_properties(col_empty)

        return col_empty

    def apply_multiple_collisions_to_target(self, target_obj, collision_meshes):
        """Apply multiple collision shapes to a single target (Many-to-One).

        Args:
          target_obj: Target object for collision
          collision_meshes: List of collision mesh objects
        """
        valid_collision_meshes = [
            obj for obj in collision_meshes if "collision" in obj.name.lower() and obj.type == "MESH"
        ]

        if not valid_collision_meshes:
            print(
                f"Error: Target '{target_obj.name}' selected, but no MESH "
                f"objects with 'Collision' in name were found."
            )
            return

        col_root = self.create_collision_root(target_obj)

        for mesh_obj in valid_collision_meshes:
            mesh_obj.parent = col_root
            mesh_obj.matrix_parent_inverse = col_root.matrix_world.inverted()
            mesh_obj.display_type = "WIRE"

            if not mesh_obj.name.startswith("Shape_"):
                mesh_obj.name = f"Shape_{mesh_obj.name}"

        print(f"Applied {len(valid_collision_meshes)} shapes to target " f"'{target_obj.name}'.")

    def apply_single_collision_to_targets(self, source_collision_mesh, target_objects):
        """Apply single collision shape to multiple targets (One-to-Many).

        Args:
          source_collision_mesh: Source collision mesh object
          target_objects: List of target objects
        """
        count = 0
        for target in target_objects:
            if target.type != "MESH":
                continue

            col_root = self.create_collision_root(target)

            # Create linked duplicate to keep Blender filesize down.
            linked_shape_name = f"Shape_Linked_{target.name}"
            linked_shape = bpy.data.objects.new(linked_shape_name, source_collision_mesh.data)

            bpy.context.collection.objects.link(linked_shape)
            linked_shape.parent = col_root

            # TODO: Ensure this doesn't cause issues.
            # Reset transform (snap to target origin)
            linked_shape.location = (0, 0, 0)
            linked_shape.rotation_euler = (0, 0, 0)
            linked_shape.scale = (1, 1, 1)
            linked_shape.display_type = "WIRE"

            count += 1

        print(f"Linked collision mesh '{source_collision_mesh.name}' to " f"{count} targets.")

    def run_smart_detect(self):
        """Auto-detect collision scenario and apply appropriately.

        Detection logic:
        - If active object has "Collision" in name -> source (One-to-Many)
        - Otherwise -> target (Many-to-One)
        """
        active = bpy.context.active_object
        selected = bpy.context.selected_objects

        if not active or not selected:
            print("Error: Selection required.")
            return

        # Active object must be a MESH
        if active.type != "MESH":
            print(f"Error: Active object '{active.name}' must be a MESH. " f"Got '{active.type}'.")
            return

        # Filter selected objects (keep only MESSHes)
        others = [o for o in selected if o != active and o.type == "MESH"]

        if not others:
            print("Error: Select at least one other MESH object.")
            return

        # Detect scenario
        if "collision" in active.name.lower():
            print(f"Mode: One-to-Many Collision Active. Source: '{active.name}'.")
            self.apply_single_collision_to_targets(active, others)
        else:
            print(f"Mode: Many-to-One Collision Active. Target: '{active.name}'.")
            self.apply_multiple_collisions_to_target(active, others)


# Execution
if __name__ == "__main__":
    generator = HavokCollisionGenerator()
    generator.run_smart_detect()
