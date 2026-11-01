from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

Vec3 = List[float]

class CanvasSpec(BaseModel):
    source_width: int = 1920
    source_height: int = 1080
    pixel_aspect: float = 1.0

class ScaleCalibration(BaseModel):
    meters_per_unit: float = 1.0
    reference_label: Optional[str] = None
    reference_length_m: Optional[float] = None

class Transform3D(BaseModel):
    position: Vec3 = Field(default_factory=lambda:[0.0,0.0,0.0])
    rotation_deg: Vec3 = Field(default_factory=lambda:[0.0,0.0,0.0])
    scale: Vec3 = Field(default_factory=lambda:[1.0,1.0,1.0])

class CameraShot(BaseModel):
    label: str
    mode: Literal["plate_preserving","crop","true_3d"] = "plate_preserving"
    position: Vec3 = Field(default_factory=lambda:[0.0,1.65,4.0])
    rotation_deg: Vec3 = Field(default_factory=lambda:[0.0,0.0,0.0])
    fov: float = 45.0
    background_override: Optional[str] = None
    calibration_override: Optional[Dict[str, Any]] = None

class CameraSetup(BaseModel):
    default_shot: str = "cam_wide"
    focal_length_mm: float = 35.0
    sensor_height_mm: float = 24.0
    calculated_fov_vertical: float = 45.0
    horizon_y_ratio: float = 0.5
    camera_pitch_deg: float = 0.0
    camera_roll_deg: float = 0.0
    camera_elevation_m: float = 1.65
    shots: Dict[str, CameraShot] = Field(default_factory=dict)

class GroundSurface(BaseModel):
    surface_id: str
    type: Literal["plane","ramp","drop_ledge"] = "plane"
    elevation_y: float = 0.0
    pitch_deg: float = 0.0
    elevation_start_y: Optional[float] = None
    elevation_end_y: Optional[float] = None
    ramp_pitch_deg: Optional[float] = None
    ledge_trigger_line: Optional[List[List[float]]] = None
    walkable_polygon: List[List[float]] = Field(default_factory=list)

class Occluder(BaseModel):
    occluder_id: str
    type: Literal["3d_depth_box","2d_sprite_plane"]
    transform: Optional[Transform3D] = None
    image: Optional[str] = None
    depth_z: Optional[float] = None
    position: Optional[Vec3] = None

class ScreenAudio(BaseModel):
    spatialized: bool = True
    ref_distance: float = 1.5
    max_distance: float = 10.0

class InteractiveScreen(BaseModel):
    screen_id: str
    label: str
    type: Literal["local_file","playlist","webrtc_stream","browser"]
    stream_channel: Optional[str] = None
    fallback_video: Optional[str] = None
    transform: Transform3D
    audio: ScreenAudio = Field(default_factory=ScreenAudio)
    allow_focus_overlay: bool = True

class PropItem(BaseModel):
    prop_id: str
    model: str
    is_interactive: bool = True
    default_transform: Transform3D

class AmbientAnimation(BaseModel):
    id: str
    type: Literal["flipbook","rotation","translation"]
    frames: List[str] = Field(default_factory=list)
    fps: int = 8
    rect: List[float] = Field(default_factory=lambda:[0.0,0.0,1.0,1.0])
    depth_order: int = 0

class LightingSpec(BaseModel):
    ambient: float = 1.0
    key_direction: Vec3 = Field(default_factory=lambda:[0.0,-1.0,-1.0])
    notes: Optional[str] = None

class BlockingMark(BaseModel):
    mark_id: str
    position: Vec3
    label: Optional[str] = None
    radius_m: float = 0.25

class SceneManifest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    schema_version: str = Field(default="1.1.0", alias="$schema")
    scene_id: str
    title: str
    version: str = "1.0.0"
    background_image: str
    canvas: CanvasSpec = Field(default_factory=CanvasSpec)
    scale_calibration: ScaleCalibration = Field(default_factory=ScaleCalibration)
    camera_setup: CameraSetup = Field(default_factory=CameraSetup)
    lighting: LightingSpec = Field(default_factory=LightingSpec)
    ground_surfaces: List[GroundSurface] = Field(default_factory=list)
    occluders: List[Occluder] = Field(default_factory=list)
    interactive_screens: List[InteractiveScreen] = Field(default_factory=list)
    props: List[PropItem] = Field(default_factory=list)
    ambient_animations: List[AmbientAnimation] = Field(default_factory=list)
    surface_connections: List[Dict[str, Any]] = Field(default_factory=list)
    interaction_anchors: List[Dict[str, Any]] = Field(default_factory=list)
    blocking_marks: List[BlockingMark] = Field(default_factory=list)
    performance_profile: Dict[str, Any] = Field(default_factory=dict)
    asset_manifest: List[str] = Field(default_factory=list)

    @field_validator("scene_id")
    @classmethod
    def safe_scene_id(cls, v: str) -> str:
        if not v or any(x in v for x in ("..","/","\\")):
            raise ValueError("scene_id must be a simple portable identifier")
        return v

class ManifestStore:
    def __init__(self, storage_root: Path):
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def get_manifest_path(self, scene_id: str) -> Path:
        SceneManifest.safe_scene_id(scene_id)
        return self.storage_root / scene_id / "scene_manifest.json"

    def list_scenes(self) -> list[str]:
        return sorted(p.name for p in self.storage_root.iterdir() if p.is_dir() and (p/"scene_manifest.json").exists())

    def load(self, scene_id: str) -> Optional[SceneManifest]:
        target = self.get_manifest_path(scene_id)
        if not target.exists(): return None
        return SceneManifest.model_validate_json(target.read_text(encoding="utf-8"))

    def save(self, manifest: SceneManifest) -> Path:
        target = self.get_manifest_path(manifest.scene_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest.model_dump(by_alias=True), indent=2), encoding="utf-8")
        tmp.replace(target)
        return target

    def export_bundle(self, scene_id: str) -> Optional[bytes]:
        scene_dir = self.storage_root / scene_id
        if not scene_dir.is_dir(): return None
        buf = BytesIO()
        with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
            for p in scene_dir.rglob("*"):
                if p.is_file(): z.write(p, p.relative_to(scene_dir).as_posix())
        return buf.getvalue()

    @staticmethod
    def _safe_extract(z: zipfile.ZipFile, dest: Path) -> None:
        root = dest.resolve()
        for info in z.infolist():
            if info.is_dir(): continue
            out = (dest / info.filename).resolve()
            if root not in out.parents and out != root:
                raise ValueError(f"unsafe bundle path: {info.filename}")
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)

    def import_bundle(self, scene_id: str, bundle_bytes: bytes) -> bool:
        SceneManifest.safe_scene_id(scene_id)
        with tempfile.TemporaryDirectory(dir=self.storage_root) as td:
            staged = Path(td)
            with zipfile.ZipFile(BytesIO(bundle_bytes),"r") as z:
                self._safe_extract(z, staged)
            manifest_path = staged / "scene_manifest.json"
            if not manifest_path.exists(): return False
            manifest = SceneManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
            if manifest.scene_id != scene_id:
                raise ValueError("bundle scene_id does not match import target")
            target = self.storage_root / scene_id
            backup = target.with_name(target.name+".bak")
            if backup.exists(): shutil.rmtree(backup)
            if target.exists(): target.replace(backup)
            shutil.copytree(staged, target)
            if backup.exists(): shutil.rmtree(backup)
        return True
