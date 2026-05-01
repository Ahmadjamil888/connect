from __future__ import annotations

from pathlib import Path

import numpy as np

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["enroll_owner", "authenticate"]},
        "num_samples": {"type": "integer"},
    },
    "required": ["action"],
}


def _opencv():
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise RuntimeError("face auth unavailable: missing dependency 'opencv-contrib-python'") from exc
    if not hasattr(cv2, "face"):
        raise RuntimeError("face auth unavailable: install 'opencv-contrib-python' instead of plain opencv.")
    return cv2


def _owner_dir(workspace: str) -> Path:
    path = Path(workspace) / "assets" / "owner_face"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _recognizer_and_detector():
    cv2 = _opencv()
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return cv2, recognizer, detector


def _train(workspace: str):
    cv2, recognizer, detector = _recognizer_and_detector()
    faces = []
    labels = []
    for img_path in _owner_dir(workspace).glob("*.jpg"):
        image = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            continue
        detected = detector.detectMultiScale(image, 1.3, 5)
        for x, y, w, h in detected:
            faces.append(image[y : y + h, x : x + w])
            labels.append(0)
    if not faces:
        return None, detector
    recognizer.train(faces, np.array(labels))
    return recognizer, detector


def run(inputs, *, workspace: str, **_kwargs):
    action = str(inputs.get("action", "")).strip().lower()
    cv2 = _opencv()
    if action == "enroll_owner":
        owner_dir = _owner_dir(workspace)
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        camera = cv2.VideoCapture(0)
        samples = 0
        limit = int(inputs.get("num_samples", 20) or 20)
        while samples < limit:
            ok, frame = camera.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, 1.3, 5)
            for x, y, w, h in faces:
                cv2.imwrite(str(owner_dir / f"face_{samples}.jpg"), gray[y : y + h, x : x + w])
                samples += 1
                if samples >= limit:
                    break
        camera.release()
        cv2.destroyAllWindows()
        return {"ok": samples > 0, "samples": samples, "path": str(owner_dir)}
    if action == "authenticate":
        recognizer, detector = _train(workspace)
        if recognizer is None:
            return {"ok": False, "error": "No enrolled owner face data found."}
        camera = cv2.VideoCapture(0)
        authenticated = False
        attempts = 0
        while attempts < 30:
            ok, frame = camera.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, 1.3, 5)
            for x, y, w, h in faces:
                label, confidence = recognizer.predict(gray[y : y + h, x : x + w])
                if label == 0 and confidence < 70:
                    authenticated = True
                    break
            if authenticated:
                break
            attempts += 1
        camera.release()
        cv2.destroyAllWindows()
        return {"ok": authenticated, "authenticated": authenticated, "attempts": attempts + 1}
    return {"ok": False, "error": f"Unknown action: {action}"}
