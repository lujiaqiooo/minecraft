from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

import cadquery as cq
from cadquery import exporters


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
MODEL_PREFIX = "hhkb-topre-hhkb-style"
CORE_3MF_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


TOPRE_KEY_ROW_DIMENSIONS = {
    "row-e": {"height": 10.20, "front_angle": 64.0, "top_angle": 2.0},
    "row-d": {"height": 8.20, "front_angle": 60.0, "top_angle": -2.0},
    "row-c": {"height": 6.70, "front_angle": 58.0, "top_angle": -8.0},
    "row-b": {"height": 6.70, "front_angle": 60.0, "top_angle": -13.0},
    "row-a": {"height": 6.70, "front_angle": 60.0, "top_angle": -13.0},
}


@dataclass(frozen=True)
class KeycapSpec:
    name_prefix: str = MODEL_PREFIX
    shape_name: str = "row-c-1u"
    row_name: str = "row-c"
    key_length: float = 1.00
    unit_pitch: float = 19.05
    bottom_unit_width: float = 18.00
    bottom_depth: float = 18.00
    top_width_difference: float = 6.50
    top_depth_reference: float = 11.50
    bottom_base_angle_back: float = 86.00
    height: float = 6.70
    front_angle: float = 58.00
    top_angle: float = -8.00
    outer_corner_radius: float = 1.50
    wall_thickness: float = 1.40
    roof_thickness: float = 1.40
    top_edge_fillet: float = 0.00
    bottom_edge_fillet: float = 0.00
    dish_depth: float = 0.60
    connector_radius: float = 2.85
    connector_wall_thickness: float = 1.00
    connector_height_offset: float = -1.35
    connector_support_height: float = 4.00
    connector_middle_space: float = 1.50
    connector_entry_chamfer_height: float = 0.35
    connector_entry_chamfer_delta: float = 0.20

    @property
    def bottom_width(self) -> float:
        return self.bottom_unit_width + ((self.key_length - 1) * self.unit_pitch)

    @property
    def outer_top_width(self) -> float:
        return self.bottom_width - self.top_width_difference

    @property
    def outer_top_depth(self) -> float:
        return self.top_base_length

    @property
    def top_base_translate(self) -> float:
        return self.height / tand(self.bottom_base_angle_back)

    @property
    def top_base_length(self) -> float:
        front_tangent = tand(self.front_angle)
        top_tangent = tand(self.top_angle)
        return ((self.bottom_depth * front_tangent) - self.height) / (front_tangent - top_tangent)

    @property
    def top_base_height_front(self) -> float:
        return self.height - (self.top_base_length * tand(self.top_angle))

    @property
    def top_base_rotated_length(self) -> float:
        return self.top_base_length / cosd(self.top_angle)

    @property
    def connector_top_height(self) -> float:
        return max(self.top_base_height_front, self.height)

    @property
    def inner_bottom_width(self) -> float:
        return self.bottom_width - (2 * self.wall_thickness)

    @property
    def inner_bottom_depth(self) -> float:
        return self.bottom_depth - (2 * self.wall_thickness)

    @property
    def inner_height(self) -> float:
        return self.connector_top_height - self.roof_thickness

    @property
    def inner_corner_radius(self) -> float:
        return max(0.80, self.outer_corner_radius - self.wall_thickness)

    @property
    def connector_inner_diameter(self) -> float:
        return (self.connector_radius - self.connector_wall_thickness) * 2

    @property
    def connector_height(self) -> float:
        return self.connector_top_height - self.connector_height_offset

    @property
    def connector_slot_height(self) -> float:
        return self.connector_top_height - self.connector_height_offset - self.connector_support_height

    @property
    def dish_radius(self) -> float:
        chord = self.outer_top_width
        sagitta = self.dish_depth
        central_chord = ((chord / 2) ** 2) / sagitta
        return (central_chord + sagitta) / 2

    @property
    def rotated_cylinder_translate(self) -> float:
        return self.dish_depth / tand(self.front_angle - self.top_angle)

    @property
    def back_cylinder_translate(self) -> float:
        return self.dish_depth / tand(self.bottom_base_angle_back + self.top_angle)


HHKB_SHAPES = {
    "row-e-1u": {"row_name": "row-e", "key_length": 1.00, "description": "HHKB US number-row 1u key"},
    "row-d-1u": {"row_name": "row-d", "key_length": 1.00, "description": "HHKB US Q-row 1u key"},
    "tab-1_5u-row-d": {"row_name": "row-d", "key_length": 1.50, "description": "HHKB US Tab/Delete sized key"},
    "row-c-1u": {"row_name": "row-c", "key_length": 1.00, "description": "HHKB US A-row 1u key"},
    "control-1_75u-row-c": {"row_name": "row-c", "key_length": 1.75, "description": "HHKB US Control sized key"},
    "return-2_25u-row-c": {"row_name": "row-c", "key_length": 2.25, "description": "HHKB US Return sized key"},
    "row-b-1u": {"row_name": "row-b", "key_length": 1.00, "description": "HHKB US Z-row 1u key"},
    "rshift-1_75u-row-b": {"row_name": "row-b", "key_length": 1.75, "description": "HHKB US right Shift sized key"},
    "lshift-2_25u-row-b": {"row_name": "row-b", "key_length": 2.25, "description": "HHKB US left Shift sized key"},
    "mod-1_5u-row-a": {"row_name": "row-a", "key_length": 1.50, "description": "HHKB US bottom-row modifier sized key"},
    "space-6u-row-a": {"row_name": "row-a", "key_length": 6.00, "description": "HHKB US 6u Space prototype"},
}


FIT_VARIANTS = {
    "fit-tight": -0.05,
    "fit-nominal": 0.00,
    "fit-loose": 0.05,
}


def tag(name: str) -> str:
    return f"{{{CORE_3MF_NS}}}{name}"


def tand(angle: float) -> float:
    return math.tan(math.radians(angle))


def cosd(angle: float) -> float:
    return math.cos(math.radians(angle))


def sind(angle: float) -> float:
    return math.sin(math.radians(angle))


def rounded_rect_points(width: float, depth: float, radius: float, segments: int = 12) -> list[tuple[float, float]]:
    radius = min(radius, width / 2, depth / 2)
    corners = [
        ((width / 2) - radius, (depth / 2) - radius, 0, 90),
        (-(width / 2) + radius, (depth / 2) - radius, 90, 180),
        (-(width / 2) + radius, -(depth / 2) + radius, 180, 270),
        ((width / 2) - radius, -(depth / 2) + radius, 270, 360),
    ]
    points: list[tuple[float, float]] = []
    for center_x, center_y, start_angle, end_angle in corners:
        for step in range(segments + 1):
            angle = math.radians(start_angle + ((end_angle - start_angle) * step / segments))
            points.append((center_x + (radius * math.cos(angle)), center_y + (radius * math.sin(angle))))
    return points


def topre_key_loft(
    *,
    bottom_width: float,
    bottom_depth: float,
    top_width: float,
    top_depth: float,
    top_base_translate: float,
    top_base_height_back: float,
    top_base_angle: float,
    corner_radius: float,
    y_offset: float = 0.0,
    z_offset: float = 0.0,
) -> cq.Workplane:
    top_center_y = y_offset + top_base_translate + (top_depth * cosd(top_base_angle) / 2) - (bottom_depth / 2)
    top_center_z = z_offset + top_base_height_back - (top_depth * sind(top_base_angle) / 2)
    bottom_points = rounded_rect_points(bottom_width, bottom_depth, corner_radius)
    top_points = rounded_rect_points(top_width, top_depth, corner_radius)
    return (
        cq.Workplane("XY")
        .workplane(offset=z_offset)
        .center(0, y_offset)
        .polyline(bottom_points)
        .close()
        .transformed(rotate=(-top_base_angle, 0, 0), offset=(0, top_center_y, top_center_z))
        .polyline(top_points)
        .close()
        .loft(ruled=True)
    )


def make_outer_shell(spec: KeycapSpec) -> cq.Workplane:
    return topre_key_loft(
        bottom_width=spec.bottom_width,
        bottom_depth=spec.bottom_depth,
        top_width=spec.outer_top_width,
        top_depth=spec.top_base_rotated_length,
        top_base_translate=spec.top_base_translate,
        top_base_height_back=spec.height,
        top_base_angle=spec.top_angle,
        corner_radius=spec.outer_corner_radius,
    )


def make_inner_cavity(spec: KeycapSpec) -> cq.Workplane:
    key_scale = (spec.bottom_width - (2 * spec.wall_thickness)) / spec.bottom_width
    y_offset = spec.wall_thickness + (key_scale * spec.bottom_depth / 2) - (spec.bottom_depth / 2)
    return topre_key_loft(
        bottom_width=spec.bottom_width * key_scale,
        bottom_depth=spec.bottom_depth * key_scale,
        top_width=spec.outer_top_width * key_scale,
        top_depth=spec.top_base_rotated_length * key_scale,
        top_base_translate=spec.top_base_translate * key_scale,
        top_base_height_back=spec.height * key_scale,
        top_base_angle=spec.top_angle,
        corner_radius=max(0.35, spec.outer_corner_radius * key_scale),
        y_offset=y_offset,
        z_offset=0.00,
    )


def make_top_dish(spec: KeycapSpec) -> cq.Solid:
    axis = cq.Vector(0, cosd(spec.top_angle), -sind(spec.top_angle))
    normal = cq.Vector(0, sind(spec.top_angle), cosd(spec.top_angle))
    top_center = cq.Vector(
        0,
        spec.top_base_translate + (spec.top_base_rotated_length * cosd(spec.top_angle) / 2) - (spec.bottom_depth / 2),
        spec.height - (spec.top_base_rotated_length * sind(spec.top_angle) / 2),
    )
    center = top_center + (normal * (spec.dish_radius - spec.dish_depth))
    length = spec.top_base_rotated_length + spec.rotated_cylinder_translate + spec.back_cylinder_translate + spec.bottom_depth
    return cq.Solid.makeCylinder(
        spec.dish_radius,
        length,
        pnt=center - (axis * (length / 2)),
        dir=axis,
    )


def make_stem(spec: KeycapSpec, fit_delta: float) -> cq.Workplane:
    inner_diameter = spec.connector_inner_diameter + fit_delta
    slot_width = max(1.00, spec.connector_middle_space + fit_delta)
    connector_height = spec.connector_height

    outer_tube = (
        cq.Workplane("XY")
        .circle(spec.connector_radius)
        .extrude(connector_height)
        .translate((0, 0, spec.connector_height_offset))
    )
    inner_bore = (
        cq.Workplane("XY")
        .circle(inner_diameter / 2)
        .extrude(connector_height + 0.05)
        .translate((0, 0, spec.connector_height_offset - 0.025))
    )

    entry_cone = cq.Workplane("XY").add(
        cq.Solid.makeCone(
            (inner_diameter / 2) + spec.connector_entry_chamfer_delta,
            inner_diameter / 2,
            spec.connector_entry_chamfer_height,
            pnt=cq.Vector(0, 0, spec.connector_height_offset),
            dir=cq.Vector(0, 0, 1),
        )
    )

    slot_cut = (
        cq.Workplane("XY")
        .box(
            slot_width,
            (spec.connector_radius * 2) + 1.00,
            spec.connector_slot_height + 0.10,
            centered=(True, True, False),
        )
        .translate((0, 0, spec.connector_height_offset - 0.05))
    )

    stem = outer_tube.cut(inner_bore).cut(entry_cone).cut(slot_cut)
    return stem


def build_keycap(spec: KeycapSpec, fit_delta: float) -> cq.Workplane:
    dish = make_top_dish(spec)
    shell = make_outer_shell(spec).cut(make_inner_cavity(spec)).cut(dish)
    stem = make_stem(spec, fit_delta).cut(dish)
    return shell.union(stem)


def spec_for_shape(shape_name: str) -> KeycapSpec:
    shape = HHKB_SHAPES[shape_name]
    row_name = shape["row_name"]
    row = TOPRE_KEY_ROW_DIMENSIONS[row_name]
    return KeycapSpec(
        shape_name=shape_name,
        row_name=row_name,
        key_length=shape["key_length"],
        height=row["height"],
        front_angle=row["front_angle"],
        top_angle=row["top_angle"],
    )


def weld_3mf_vertices(path: Path, precision: int = 6) -> dict[str, int]:
    with zipfile.ZipFile(path, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}

    root = ET.fromstring(entries["3D/3dmodel.model"])
    mesh = root.find(f".//{tag('mesh')}")
    if mesh is None:
        raise ValueError(f"No mesh found in {path}")

    vertices_node = mesh.find(tag("vertices"))
    triangles_node = mesh.find(tag("triangles"))
    if vertices_node is None or triangles_node is None:
        raise ValueError(f"No vertices/triangles found in {path}")

    original_vertices = []
    for vertex in vertices_node.findall(tag("vertex")):
        original_vertices.append(tuple(float(vertex.attrib[axis]) for axis in ("x", "y", "z")))

    coordinate_to_new_id: dict[tuple[float, float, float], int] = {}
    old_to_new_id: list[int] = []
    welded_vertices: list[tuple[float, float, float]] = []

    for coords in original_vertices:
        key = tuple(round(value, precision) for value in coords)
        if key not in coordinate_to_new_id:
            coordinate_to_new_id[key] = len(welded_vertices)
            welded_vertices.append(coords)
        old_to_new_id.append(coordinate_to_new_id[key])

    welded_triangles: list[tuple[int, int, int]] = []
    for triangle in triangles_node.findall(tag("triangle")):
        mapped = tuple(old_to_new_id[int(triangle.attrib[index])] for index in ("v1", "v2", "v3"))
        if len(set(mapped)) == 3:
            welded_triangles.append(mapped)

    vertices_node.clear()
    for coords in welded_vertices:
        ET.SubElement(
            vertices_node,
            tag("vertex"),
            {axis: f"{value:.6f}".rstrip("0").rstrip(".") for axis, value in zip(("x", "y", "z"), coords)},
        )

    triangles_node.clear()
    for v1, v2, v3 in welded_triangles:
        ET.SubElement(
            triangles_node,
            tag("triangle"),
            {"v1": str(v1), "v2": str(v2), "v3": str(v3)},
        )

    ET.register_namespace("", CORE_3MF_NS)
    entries["3D/3dmodel.model"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    tmp_path = path.with_suffix(".tmp.3mf")
    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for filename, payload in entries.items():
            target.writestr(filename, payload)
    tmp_path.replace(path)

    return {
        "original_vertices": len(original_vertices),
        "welded_vertices": len(welded_vertices),
        "triangles": len(welded_triangles),
    }


def export_variants(specs: list[KeycapSpec]) -> list[dict[str, float | str]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_previous_exports()

    manifest: list[dict[str, float | str]] = []
    for spec in specs:
        for variant, fit_delta in FIT_VARIANTS.items():
            model_name = f"{spec.name_prefix}-{spec.shape_name}-{variant}"
            solid = build_keycap(spec, fit_delta)
            threemf_path = OUTPUT_DIR / f"{model_name}.3mf"

            exporters.export(solid, str(threemf_path))
            weld_stats = weld_3mf_vertices(threemf_path)

            manifest.append(
                {
                    "shape": spec.shape_name,
                    "row_name": spec.row_name,
                    "key_length": spec.key_length,
                    "bottom_width_mm": round(spec.bottom_width, 4),
                    "bottom_depth_mm": round(spec.bottom_depth, 4),
                    "top_base_length_mm": round(spec.top_base_length, 4),
                    "top_base_rotated_length_mm": round(spec.top_base_rotated_length, 4),
                    "top_base_height_front_mm": round(spec.top_base_height_front, 4),
                    "variant": variant,
                    "fit_delta_mm": fit_delta,
                    "3mf": threemf_path.name,
                    "welded_vertices": weld_stats["welded_vertices"],
                    "triangles": weld_stats["triangles"],
                }
            )

    return manifest


def cleanup_previous_exports() -> None:
    for path in OUTPUT_DIR.glob(f"{MODEL_PREFIX}-*.3mf"):
        path.unlink()
    manifest_path = OUTPUT_DIR / f"{MODEL_PREFIX}-manifest.json"
    if manifest_path.exists():
        manifest_path.unlink()


def write_manifest(specs: list[KeycapSpec], manifest: list[dict[str, float | str]]) -> None:
    base_spec = KeycapSpec()
    payload = {
        "model": base_spec.name_prefix,
        "base_spec": asdict(base_spec),
        "shapes": [
            asdict(spec)
            | {
                "description": HHKB_SHAPES[spec.shape_name]["description"],
                "bottom_width_mm": round(spec.bottom_width, 4),
                "bottom_depth_mm": round(spec.bottom_depth, 4),
                "outer_top_width_mm": round(spec.outer_top_width, 4),
                "outer_top_depth_mm": round(spec.outer_top_depth, 4),
                "top_base_length_mm": round(spec.top_base_length, 4),
                "top_base_rotated_length_mm": round(spec.top_base_rotated_length, 4),
                "top_base_translate_mm": round(spec.top_base_translate, 4),
                "top_base_height_front_mm": round(spec.top_base_height_front, 4),
            }
            for spec in specs
        ],
        "source": {
            "name": "fernandodeperto/topre_key",
            "license": "CC0-1.0",
            "url": "https://github.com/fernandodeperto/topre_key",
            "adapted_defaults": {
                "KEY_THICKNESS": 1.4,
                "CONNECTOR_RADIUS": 2.85,
                "CONNECTOR_THICKNESS": 1.0,
                "CONNECTOR_MIDDLE_SPACE": 1.5,
                "KEY_DIMENSIONS": [0.6, 11.5, 18.0, 18.0, 86.0],
                "ROW_DIMENSIONS": TOPRE_KEY_ROW_DIMENSIONS,
            },
        },
        "variants": manifest,
        "notes": [
            "Exports include HHKB common key shapes adapted from fernandodeperto/topre_key dimensions.",
            "The three variants only change the Topre connector clearance.",
            "fernandodeperto/topre_key only implements one centered Topre connector; wide keys follow that scope and do not add OEM HHKB stabilizers.",
            "KeyV2 stabilized wide-key helpers target Cherry/Costar stabilizers and are intentionally not mixed into this Topre connector model.",
            "3MF vertices are welded after export to avoid non-manifold imports in Bambu Studio.",
            "Print top-up on a 0.4 mm nozzle without supports for the first fit test.",
        ],
    }
    (OUTPUT_DIR / "hhkb-topre-hhkb-style-manifest.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    specs = [spec_for_shape(shape_name) for shape_name in HHKB_SHAPES]
    manifest = export_variants(specs)
    write_manifest(specs, manifest)
    print(f"Exported {len(manifest)} keycap variants to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
