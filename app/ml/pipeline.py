"""Two-stage inference pipeline: YOLOv8 detection -> EfficientNetV2-S severity -> cost.

Loads your trained weights from `models/` when present:
    models/yolov8_detector.pt   (Stage 1 - trained YOLOv8m)
    models/efficientnetv2.pth   (Stage 2 - trained severity classifier)

Falls back to a pretrained YOLOv8n detector + heuristic severity when trained
weights are missing (results flagged `model_source: fallback`).
DEMO_MODE=true skips torch entirely (mock results) - for CI/frontend work.
"""
from __future__ import annotations

import base64
import logging
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from ..config import get_settings
from .cost_engine import estimate_cost

logger = logging.getLogger(__name__)
settings = get_settings()

DAMAGE_CLASSES = ["Bonnet", "Bumper", "Dickey", "Door", "Fender", "Light", "Windshield"]
SEVERITY_CLASSES = ["minor", "moderate", "severe"]

CLASS_COLORS = {
    0: (255, 99, 71), 1: (30, 144, 255), 2: (255, 165, 0), 3: (50, 205, 50),
    4: (186, 85, 211), 5: (255, 215, 0), 6: (0, 206, 209),
}


@dataclass
class PipelineResult:
    damages: list[dict] = field(default_factory=list)
    total_min: int = 0
    total_max: int = 0
    inference_ms: float = 0.0
    annotated_image: str | None = None
    gradcam_image: str | None = None
    model_source: str = "trained"
    warning: str | None = None


class DamagePipeline:
    """Thread-safe singleton pipeline. Models are lazy-loaded on first request."""

    _instance: "DamagePipeline | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._detector = None
        self._classifier = None
        self._gradcam = None
        self._device = None
        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self.model_source = "demo" if settings.demo_mode else "unloaded"

    @classmethod
    def get(cls) -> "DamagePipeline":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _ensure_loaded(self) -> None:
        if settings.demo_mode or self._detector is not None:
            return
        with self._load_lock:
            if self._detector is not None:
                return
            import torch
            from ultralytics import YOLO

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            det_path = settings.models_dir / settings.detector_weights
            if det_path.exists():
                self._detector = YOLO(str(det_path))
                self.model_source = "trained"
            else:
                logger.warning("Trained detector not found at %s - using pretrained fallback", det_path)
                self._detector = YOLO(settings.detector_fallback)
                self.model_source = "fallback"

            clf_path = settings.models_dir / settings.classifier_weights
            if clf_path.exists():
                self._classifier = self._build_classifier(str(clf_path))
            else:
                logger.warning("Severity classifier not found at %s - using heuristic severity", clf_path)
                self.model_source = "fallback"

    def _build_classifier(self, ckpt_path: str):
        import timm
        import torch
        import torch.nn as nn

        class SeverityClassifier(nn.Module):
            def __init__(self, nc: int = 3):
                super().__init__()
                self.backbone = timm.create_model(
                    "efficientnetv2_s", pretrained=False, num_classes=0, global_pool="avg"
                )
                fdim = self.backbone.num_features
                self.head = nn.Sequential(
                    nn.Dropout(0.3), nn.Linear(fdim, 512), nn.ReLU(),
                    nn.BatchNorm1d(512), nn.Dropout(0.2), nn.Linear(512, nc),
                )

            def forward(self, x):
                return self.head(self.backbone(x))

            def cam_layer(self):
                return self.backbone.conv_head

        model = SeverityClassifier(nc=len(SEVERITY_CLASSES))
        ckpt = torch.load(ckpt_path, map_location=self._device)
        state = ckpt.get("model", ckpt) if isinstance(ckpt, dict) else ckpt
        model.load_state_dict(state)
        model.to(self._device).eval()

        if settings.enable_gradcam:
            try:
                from pytorch_grad_cam import GradCAM
                self._gradcam = GradCAM(model=model, target_layers=[model.cam_layer()])
            except Exception as exc:
                logger.warning("Grad-CAM unavailable: %s", exc)
        return model

    def _classify_severity(self, crop_bgr: np.ndarray) -> tuple[str, float, np.ndarray | None]:
        if self._classifier is None:
            return "moderate", 0.5, None

        import cv2
        import torch

        img = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (224, 224)).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        tensor = torch.from_numpy(((img - mean) / std).transpose(2, 0, 1)).unsqueeze(0).to(self._device)

        with torch.no_grad():
            probs = torch.softmax(self._classifier(tensor), dim=1)[0]
        idx = int(probs.argmax())
        severity, conf = SEVERITY_CLASSES[idx], float(probs[idx])

        overlay = None
        if self._gradcam is not None:
            try:
                from pytorch_grad_cam.utils.image import show_cam_on_image
                grayscale = self._gradcam(input_tensor=tensor)[0]
                overlay = show_cam_on_image(img, grayscale, use_rgb=True)
            except Exception as exc:
                logger.debug("Grad-CAM failed: %s", exc)
        return severity, conf, overlay

    def assess(self, image_bytes: bytes, conf: float | None = None,
               include_images: bool = True, quality: str = "standard",
               cost_multiplier: float = 1.0) -> PipelineResult:
        """quality: 'standard' (free) or 'high' (paid) - high runs a larger input
        resolution plus test-time augmentation for better recall on small damage."""
        start = time.perf_counter()
        conf = conf or settings.default_confidence

        if settings.demo_mode:
            return self._demo_result(start, cost_multiplier)

        import cv2

        self._ensure_loaded()
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError("Could not decode image. Please upload a valid JPEG/PNG.")

        h, w = img_bgr.shape[:2]
        annotated = img_bgr.copy()
        result = PipelineResult(model_source=self.model_source)
        overlays: list[tuple[np.ndarray, str]] = []

        if self.model_source == "fallback":
            # A generic pretrained detector CANNOT detect damage. Never show
            # fake results - tell the operator to install the trained weights.
            result.warning = (
                "Trained damage model is not installed on this server. "
                "Place yolov8_detector.pt and efficientnetv2.pth in the models/ folder "
                "and restart. No analysis was performed to avoid inaccurate results."
            )
            if include_images:
                result.annotated_image = _b64_jpeg(annotated)
            result.inference_ms = round((time.perf_counter() - start) * 1000, 1)
            return result

        imgsz = 1280 if quality == "high" else 640
        augment = quality == "high"

        with self._infer_lock:
            yolo_out = self._detector(img_bgr, conf=conf, imgsz=imgsz,
                                      augment=augment, verbose=False)[0]

            for box in yolo_out.boxes:
                cls_id = int(box.cls[0])
                det_conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                pad = 10
                crop = img_bgr[max(0, y1 - pad):min(h, y2 + pad), max(0, x1 - pad):min(w, x2 + pad)]
                if crop.size == 0:
                    continue

                if self.model_source == "trained":
                    dmg = DAMAGE_CLASSES[cls_id] if cls_id < len(DAMAGE_CLASSES) else "Unknown"
                else:
                    dmg = self._detector.names.get(cls_id, "Unknown")

                severity, sev_conf, overlay = self._classify_severity(crop)
                cost = estimate_cost(dmg, severity, cost_multiplier)
                result.damages.append({
                    "damage_type": dmg,
                    "severity": severity,
                    "detection_confidence": round(det_conf, 3),
                    "severity_confidence": round(sev_conf, 3),
                    "box": [x1, y1, x2, y2],
                    **cost,
                })
                result.total_min += cost["cost_min"]
                result.total_max += cost["cost_max"]
                if overlay is not None:
                    overlays.append((overlay, f"{dmg} [{severity}]"))

                color = CLASS_COLORS.get(cls_id, (255, 255, 255))[::-1]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.putText(annotated, f"{dmg}[{severity}]{det_conf:.2f}",
                            (x1, max(y1 - 8, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        if include_images:
            result.annotated_image = _b64_jpeg(annotated)
            if overlays:
                result.gradcam_image = _b64_jpeg(_stack_overlays(overlays))

        result.inference_ms = round((time.perf_counter() - start) * 1000, 1)
        return result

    def _demo_result(self, start: float, mult: float = 1.0) -> PipelineResult:
        damages = [
            {"damage_type": "Door", "severity": "moderate", "detection_confidence": 0.91,
             "severity_confidence": 0.87, "box": [120, 200, 420, 480], **estimate_cost("Door", "moderate", mult)},
            {"damage_type": "Light", "severity": "severe", "detection_confidence": 0.88,
             "severity_confidence": 0.91, "box": [500, 300, 640, 400], **estimate_cost("Light", "severe", mult)},
        ]
        return PipelineResult(
            damages=damages,
            total_min=sum(d["cost_min"] for d in damages),
            total_max=sum(d["cost_max"] for d in damages),
            inference_ms=round((time.perf_counter() - start) * 1000, 1),
            model_source="demo",
        )


def _b64_jpeg(img_bgr: np.ndarray) -> str:
    import cv2
    ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return base64.b64encode(buf.tobytes()).decode() if ok else ""


def _stack_overlays(overlays: list[tuple[np.ndarray, str]]) -> np.ndarray:
    import cv2
    tiles = []
    for overlay_rgb, label in overlays:
        tile = cv2.cvtColor(cv2.resize(overlay_rgb, (320, 320)), cv2.COLOR_RGB2BGR)
        cv2.putText(tile, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        tiles.append(tile)
    return np.vstack(tiles)
