import os
import sys
import argparse
from pathlib import Path
from ultralytics import YOLO

def export_model(
    model_path: str = "models/trained/best.pt",
    export_format: str = "onnx",
    imgsz: int = 640,
    dynamic: bool = False,
    half: bool = False,
    simplify: bool = True
):
    print("=" * 65)
    print(" SmartRetail AI - Edge Inference Model Exporter")
    print(f" Source Model: {model_path}")
    print(f" Target Format: {export_format.upper()} | Imgsz: {imgsz} | Half (FP16): {half}")
    print("=" * 65)

    model_file = Path(model_path)
    if not model_file.exists():
        fallback = Path("yolo11n.pt")
        if fallback.exists():
            print(f"[Notice] '{model_path}' not found. Exporting base checkpoint '{fallback}' as demonstration.")
            model_file = fallback
        else:
            raise FileNotFoundError(f"Model checkpoint not found: {model_path}")

    model = YOLO(str(model_file))

    print(f"[Export] Converting PyTorch checkpoint to {export_format.upper()}...")
    exported_path = model.export(
        format=export_format,
        imgsz=imgsz,
        dynamic=dynamic,
        half=half,
        simplify=simplify
    )

    print("\n" + "=" * 65)
    print(" Export Succeeded!")
    print(f" Exported Artifact: {exported_path}")
    print("-" * 65)

    if export_format == "onnx":
        onnx_file = Path(exported_path).resolve()
        engine_file = onnx_file.with_suffix(".engine")
        print("To deploy with maximum acceleration on Nvidia Jetson (Orin / Xavier / Nano),")
        print("compile this ONNX graph into a TensorRT execution engine directly on your Jetson:")
        print()
        print(f"  /usr/src/tensorrt/bin/trtexec \\")
        print(f"    --onnx=\"{onnx_file}\" \\")
        print(f"    --saveEngine=\"{engine_file}\" \\")
        print(f"    --fp16 \\")
        print(f"    --workspace=2048")
        print()
        print("Or run inference directly using the ONNX runtime or Ultralytics:")
        print(f"  python scripts/predict.py --model \"{onnx_file}\" --source 0")

    print("=" * 65)
    return str(exported_path)

def main():
    parser = argparse.ArgumentParser(description="Export trained SKU model to ONNX / TensorRT / OpenVINO")
    parser.add_argument("--model", default="models/trained/best.pt", help="Path to PyTorch checkpoint")
    parser.add_argument("--format", default="onnx", choices=["onnx", "engine", "openvino", "torchscript"], help="Export format")
    parser.add_argument("--imgsz", type=int, default=640, help="Image resolution")
    parser.add_argument("--dynamic", action="store_true", help="Enable dynamic batching / axes")
    parser.add_argument("--half", action="store_true", help="Export with FP16 half precision")
    parser.add_argument("--no-simplify", action="store_true", help="Skip onnxsim graph simplification")
    args = parser.parse_args()

    export_model(
        model_path=args.model,
        export_format=args.format,
        imgsz=args.imgsz,
        dynamic=args.dynamic,
        half=args.half,
        simplify=not args.no_simplify
    )

if __name__ == "__main__":
    main()
