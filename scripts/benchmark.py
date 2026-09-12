import os
import sys
import time
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import psutil
import torch
from ultralytics import YOLO

from scripts.common import get_device

def benchmark_model(
    model_path: str = "models/trained/best.pt",
    source: str = None,
    rounds: int = 100,
    warmup: int = 15,
    imgsz: int = 640,
    device: str = None
):
    model_file = Path(model_path)
    if not model_file.exists():
        # Fallback to base model for benchmarking if trained model not yet generated
        fallback = Path("yolo11n.pt")
        if fallback.exists():
            print(f"[Notice] '{model_path}' not found, benchmarking base model '{fallback}' instead.")
            model_file = fallback
        else:
            raise FileNotFoundError(f"Neither '{model_path}' nor 'yolo11n.pt' found.")

    comp_device = device or get_device()
    model_size_mb = model_file.stat().st_size / (1024 * 1024)

    print("=" * 65)
    print(" SmartRetail AI - Edge Hardware Performance Benchmark")
    print(f" Model:       {model_file.name} ({model_size_mb:.2f} MB)")
    print(f" Device:      {comp_device.upper()}")
    print(f" Resolution:  {imgsz}x{imgsz} | Iterations: {rounds} (Warmup: {warmup})")
    print("=" * 65)

    # Prepare input frame
    if source and Path(source).is_file():
        import cv2
        frame = cv2.imread(source)
    else:
        frame = np.random.randint(0, 255, (imgsz, imgsz, 3), dtype=np.uint8)

    model = YOLO(str(model_file))

    # Warmup runs
    print("[Benchmark] Running warmup rounds...")
    for _ in range(warmup):
        _ = model(frame, imgsz=imgsz, device=comp_device, verbose=False)

    # Benchmark loop
    print(f"[Benchmark] Measuring {rounds} inference cycles...")
    process = psutil.Process(os.getpid())
    cpu_measurements = []
    latencies = []

    # Reset GPU stats if CUDA
    if comp_device.startswith("cuda") and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    start_bench = time.perf_counter()
    for _ in range(rounds):
        t0 = time.perf_counter()
        _ = model(frame, imgsz=imgsz, device=comp_device, verbose=False)
        if comp_device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.synchronize()
        t1 = time.perf_counter()

        latencies.append((t1 - t0) * 1000.0) # milliseconds
        cpu_measurements.append(process.cpu_percent(interval=None))

    total_time = time.perf_counter() - start_bench
    effective_fps = rounds / total_time

    # Latency stats
    latencies = np.array(latencies)
    mean_lat = float(np.mean(latencies))
    median_lat = float(np.median(latencies))
    p95_lat = float(np.percentile(latencies, 95))
    min_lat = float(np.min(latencies))
    max_lat = float(np.max(latencies))

    # RAM and VRAM
    ram_mb = process.memory_info().rss / (1024 * 1024)
    vram_str = "N/A"
    if comp_device.startswith("cuda") and torch.cuda.is_available():
        vram_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
        vram_str = f"{vram_mb:.1f} MB"

    avg_cpu = float(np.mean([c for c in cpu_measurements if c > 0] or [0]))

    print("\n" + "=" * 65)
    print(" Benchmark Results & Edge Hardware Profile")
    print("=" * 65)
    print(f"  Throughput (FPS):       {effective_fps:.1f} FPS")
    print(f"  Mean Latency:           {mean_lat:.2f} ms")
    print(f"  Median Latency:         {median_lat:.2f} ms")
    print(f"  95th Percentile (p95):  {p95_lat:.2f} ms")
    print(f"  Latency Min / Max:      {min_lat:.2f} ms / {max_lat:.2f} ms")
    print(f"  Process RAM Usage:      {ram_mb:.1f} MB")
    print(f"  GPU Peak VRAM:          {vram_str}")
    print(f"  Model Size on Disk:     {model_size_mb:.2f} MB")
    print("-" * 65)

    # Edge Suitability Summary
    if effective_fps >= 25:
        tier = "Tier-1 Real-time Capable (Smooth 25+ FPS for live CCTV)"
    elif effective_fps >= 10:
        tier = "Tier-2 Edge Capable (10-24 FPS, sufficient for shelf & queue tracking)"
    else:
        tier = "Edge Low-power (1-9 FPS, recommended for sampled shelf audits)"
    print(f"  Deployment Profile:     {tier}")
    print("=" * 65)

    return {
        "model": model_file.name,
        "device": comp_device,
        "fps": round(effective_fps, 1),
        "mean_latency_ms": round(mean_lat, 2),
        "median_latency_ms": round(median_lat, 2),
        "p95_latency_ms": round(p95_lat, 2),
        "ram_mb": round(ram_mb, 1),
        "vram": vram_str,
        "model_size_mb": round(model_size_mb, 2)
    }

def main():
    parser = argparse.ArgumentParser(description="Benchmark edge inference FPS, latency, and resource footprint")
    parser.add_argument("--model", default="models/trained/best.pt", help="Path to model checkpoint")
    parser.add_argument("--source", default=None, help="Optional image file path")
    parser.add_argument("--rounds", type=int, default=50, help="Number of test iterations")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference resolution")
    parser.add_argument("--device", default=None, help="Device ('cpu', 'cuda', etc.)")
    args = parser.parse_args()

    benchmark_model(
        model_path=args.model,
        source=args.source,
        rounds=args.rounds,
        imgsz=args.imgsz,
        device=args.device
    )

if __name__ == "__main__":
    main()
