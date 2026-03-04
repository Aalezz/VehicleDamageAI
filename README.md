# 🚗 VehicleDamageAI

> **AI-powered vehicle damage detection, severity classification & repair cost estimation**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.3-red?logo=pytorch)](https://pytorch.org)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-brightgreen)](https://ultralytics.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![HuggingFace](https://img.shields.io/badge/🤗-Live%20Demo-orange)](https://huggingface.co/spaces/Aalezz/VehicleDamageAI)

---

## 📌 Overview

VehicleDamageAI is a **2-stage deep learning pipeline** that takes a photo of a damaged vehicle and automatically:

1. **Detects** where the damage is and what part is affected
2. **Classifies** how severe the damage is
3. **Explains** the AI decision with visual heatmaps
4. **Estimates** the repair cost

---

## 🎯 Demo

| Input | Detection | Grad-CAM |
|-------|-----------|----------|
| Car photo | Bounding boxes with labels | AI attention heatmap |

> 🔗 **Try it live:** [huggingface.co/spaces/Aalezz/VehicleDamageAI](https://huggingface.co/spaces/Aalezz/VehicleDamageAI)

---

## 🧠 Architecture

```
Input Image
     │
     ▼
┌─────────────────────┐
│   YOLOv8m Detector  │  ← Stage 1: WHERE is damage + WHAT type
│   (Object Detection)│
└─────────────────────┘
     │
     ▼ (cropped damage regions)
┌─────────────────────┐
│ EfficientNetV2-S    │  ← Stage 2: HOW BAD is the damage
│ (Classification)    │
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│   Grad-CAM          │  ← WHY did the model decide this
│ (Explainability)    │
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│  Cost Estimator     │  ← HOW MUCH will it cost to repair
│  (Rule Engine)      │
└─────────────────────┘
```

---

## 📊 Model Performance

| Model | Metric | Score |
|-------|--------|-------|
| YOLOv8m | mAP@0.5 | ~0.82 |
| YOLOv8m | mAP@0.5:0.95 | ~0.58 |
| EfficientNetV2-S | Val Accuracy | ~89% |
| Full Pipeline | Inference Time | < 0.3s |

---

## 🏷️ Damage Classes

| Class | Description |
|-------|-------------|
| 🚗 Bonnet | Hood / front cover damage |
| 🛡️ Bumper | Front or rear bumper |
| 🚪 Dickey | Trunk / boot lid |
| 🚪 Door | Side door panels |
| 🔧 Fender | Side panels above wheels |
| 💡 Light | Headlights / taillights |
| 🪟 Windshield | Front or rear glass |

## 🎨 Severity Levels

| Level | Meaning | Example Cost Range |
|-------|---------|-------------------|
| 🟢 Minor | Surface scratches, small dents | $150 – $600 |
| 🟡 Moderate | Panel damage, partial replacement | $400 – $1,500 |
| 🔴 Severe | Full replacement required | $900 – $4,000 |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Object Detection | YOLOv8m (Ultralytics) |
| Classification | EfficientNetV2-S (timm) |
| Explainability | Grad-CAM (pytorch-grad-cam) |
| Data Augmentation | Albumentations |
| Training Framework | PyTorch 2.3 |
| Dataset | Car Damage Detection — Roboflow |
| Web Interface | Gradio |
| Deployment | HuggingFace Spaces |

---

## 📁 Project Structure

```
VehicleDamageAI/
├── VehicleDamageAI_Colab.ipynb   # Full training notebook (Google Colab)
├── app.py                         # Gradio web application
├── requirements.txt               # Dependencies
├── models/
│   ├── yolov8_detector.pt         # Trained YOLOv8m weights
│   └── efficientnetv2.pth         # Trained EfficientNetV2-S weights
├── examples/                      # Sample car images
└── outputs/
    ├── dataset_samples.png        # Dataset visualization
    ├── yolo_training_curves.png   # Training metrics
    ├── confusion_matrix.png       # Classifier evaluation
    └── gradcam.png                # Grad-CAM examples
```

---

## 🚀 Quick Start

### Run locally

```bash
# Clone repo
git clone https://github.com/Aalezz/VehicleDamageAI.git
cd VehicleDamageAI

# Install dependencies
pip install -r requirements.txt

# Launch app
python app.py
```

### Train from scratch (Google Colab)

1. Open `VehicleDamageAI_Colab.ipynb` in Google Colab
2. Enable **T4 GPU**: Runtime → Change runtime type → T4 GPU
3. Run all cells top to bottom
4. Training takes ~45 mins on T4

---

## 📈 Training Details

**Stage 1 — YOLOv8m Detector**
- Dataset: 3,291 images, 7 damage classes
- Epochs: 50 with early stopping (patience=10)
- Optimizer: AdamW, lr=0.001
- Augmentation: mosaic, mixup, flipping, rotation

**Stage 2 — EfficientNetV2-S Classifier**
- Input: Cropped damage regions from Stage 1
- Epochs: 30 with backbone freeze for first 5
- Optimizer: AdamW with cosine annealing
- Classes: minor / moderate / severe

---

## 📝 Results

Sample output on a test image:

```
🚗 VEHICLE DAMAGE ASSESSMENT REPORT
================================================
1. 🚪 DOOR
   Severity  : 🟡 MODERATE (87% confidence)
   Repair    : Body filler + repaint
   Est. Cost : $500 – $1,200

2. 💡 LIGHT
   Severity  : 🔴 SEVERE (91% confidence)
   Repair    : Full assembly replacement
   Est. Cost : $700 – $2,000
================================================
💵 TOTAL ESTIMATE  : $1,200 – $3,200
📊 DAMAGES FOUND   : 2
```

---

## 👨‍💻 Author

**Aalezz** — AI/ML Engineer

[![GitHub](https://img.shields.io/badge/GitHub-Aalezz-black?logo=github)](https://github.com/Aalezz)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin)](https://linkedin.com/in/YOUR_LINKEDIN)

---

## 📄 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

## ⚠️ Disclaimer

Cost estimates are indicative only and based on US average repair pricing.
Actual costs vary by location, vehicle make/model, and repair shop.
