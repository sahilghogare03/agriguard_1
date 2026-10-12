# predict.py

from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "plant_disease_resnet18.pth"
LABELS_PATH = BASE_DIR / "plant_disease_resnet18_labels.txt"

with LABELS_PATH.open("r", encoding="utf-8") as labels_file:
    class_names = [line.strip() for line in labels_file if line.strip()]

model = models.resnet18(weights=None)
model.fc = torch.nn.Linear(model.fc.in_features, len(class_names))
state_dict = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
model.load_state_dict(state_dict, strict=True)
model.eval()

preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=(0.485, 0.456, 0.406),
        std=(0.229, 0.224, 0.225)
    )
])


def is_leaf_image(image_path, min_leaf_ratio=0.12):
    """
    Verifies if the uploaded image contains plant leaf features using color analysis.
    Returns (is_leaf, error_message).
    """
    try:
        img = Image.open(image_path).convert('RGB')
    except Exception:
        return False, "Invalid image format or corrupted file."

    img_resized = img.resize((224, 224))
    arr = np.array(img_resized)

    r = arr[:, :, 0].astype(float)
    g = arr[:, :, 1].astype(float)
    b = arr[:, :, 2].astype(float)

    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    delta = max_c - min_c + 1e-5

    hue = np.zeros_like(r)
    mask_r = (max_c == r)
    hue[mask_r] = ((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6
    mask_g = (max_c == g)
    hue[mask_g] = ((b[mask_g] - r[mask_g]) / delta[mask_g]) + 2
    mask_b = (max_c == b)
    hue[mask_b] = ((r[mask_b] - g[mask_b]) / delta[mask_b]) + 4
    hue = hue * 60.0

    sat = delta / (max_c + 1e-5)
    val = max_c / 255.0

    leaf_hue_mask = (
        ((hue >= 35) & (hue <= 170)) |
        ((hue >= 10) & (hue < 35) & (sat > 0.15) & (val > 0.15) & (val < 0.9))
    ) & (sat > 0.08) & (val > 0.12)

    leaf_ratio = float(np.mean(leaf_hue_mask))

    if leaf_ratio < min_leaf_ratio:
        return False, "Invalid image: The uploaded image does not appear to be a plant leaf. Please upload a clear leaf image."

    return True, None


def predict_disease(image_path):
    is_leaf, error_msg = is_leaf_image(image_path)
    if not is_leaf:
        return {
            "error": error_msg
        }

    with Image.open(image_path) as image:
        input_tensor = preprocess(image.convert("RGB")).unsqueeze(0)

    with torch.inference_mode():
        prediction = torch.softmax(model(input_tensor), dim=1)[0]

    confidence, predicted_index = torch.max(prediction, dim=0)
    confidence = float(confidence.item()) * 100

    if confidence < 40.0:
        return {
            "error": "Invalid image: The uploaded image could not be verified as a valid plant leaf. Please upload a clearer plant leaf photo."
        }

    disease = class_names[predicted_index.item()]

    return {
        "disease": disease,
        "confidence": round(confidence, 2)
    }