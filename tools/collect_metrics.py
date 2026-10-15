#!/usr/bin/env python3
import os
import json
import csv
from pathlib import Path

def format_metric(val, format_str):
    try:
        return format_str.format(float(val))
    except (ValueError, TypeError):
        return "N/A"

def collect_metrics(eval_dir="eval_out", output_csv="metrics_summary.csv"):
    eval_path = Path(eval_dir)
    if not eval_path.exists():
        print(f"Error: The directory '{eval_dir}' does not exist.")
        print("Please place the script in the directory containing 'eval_out' or specify the correct path.")
        return

    records = []
    
    # Recursively find all results.json files in the eval_out directory
    results_files = list(eval_path.glob("**/results.json"))
    
    if not results_files:
        print(f"No 'results.json' files found under '{eval_dir}/'.")
        return

    print(f"Found {len(results_files)} 'results.json' files. Parsing...")

    for file_path in results_files:
        # Resolve the relative components to capture algo, dataset, scene
        # Path structure: eval_out / {algo_name} / {dataset_name} / {scene_name} / results.json
        try:
            relative_parts = file_path.relative_to(eval_path).parts
            if len(relative_parts) < 3:
                print(f"Skipping file with unexpected directory structure: {file_path}")
                continue
            
            algo_name = relative_parts[0]
            dataset_name = relative_parts[1]
            scene_name = relative_parts[2]
        except Exception as e:
            print(f"Error parsing path components for {file_path}: {e}")
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Find the inner dictionary containing PSNR, SSIM, LPIPS.
            # Usually it's key "ours_30000", but we search dynamically to make it robust.
            metrics_dict = None
            iteration_key = "unknown"
            
            for key, val in data.items():
                if isinstance(val, dict) and any(m in val for m in ["PSNR", "SSIM", "LPIPS", "psnr", "ssim", "lpips"]):
                    metrics_dict = val
                    iteration_key = key
                    break
            
            # Fallback if no matching structure found: use first dictionary key
            if not metrics_dict and data:
                first_key = list(data.keys())[0]
                if isinstance(data[first_key], dict):
                    metrics_dict = data[first_key]
                    iteration_key = first_key

            if not metrics_dict:
                print(f"Warning: Could not parse metric dictionary from {file_path}")
                continue

            # Extract metrics (case-insensitive keys for robustness)
            psnr = metrics_dict.get("PSNR", metrics_dict.get("psnr"))
            ssim = metrics_dict.get("SSIM", metrics_dict.get("ssim"))
            lpips = metrics_dict.get("LPIPS", metrics_dict.get("lpips"))

            # Format values
            formatted_psnr = format_metric(psnr, "{:.2f}")
            formatted_ssim = format_metric(ssim, "{:.3f}")
            formatted_lpips = format_metric(lpips, "{:.3f}")

            records.append({
                "Algorithm": algo_name,
                "Dataset": dataset_name,
                "Scene": scene_name,
                "Iteration_Key": iteration_key,
                "PSNR": formatted_psnr,
                "SSIM": formatted_ssim,
                "LPIPS": formatted_lpips
            })

        except Exception as e:
            print(f"Failed to read/parse {file_path}: {e}")

    if not records:
        print("No valid metric records compiled.")
        return

    # Sort records by Algorithm, then Dataset, then Scene to ensure a clean structured table
    records.sort(key=lambda x: (x["Algorithm"], x["Dataset"], x["Scene"]))

    # Write to CSV
    csv_columns = ["Algorithm", "Dataset", "Scene", "Iteration_Key", "PSNR", "SSIM", "LPIPS"]
    try:
        with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=csv_columns)
            writer.writeheader()
            writer.writerows(records)
        print(f"\nSuccess! Metrics compiled and saved to: {Path(output_csv).resolve()}")
        print(f"Total rows exported: {len(records)}")
    except Exception as e:
        print(f"Failed to write CSV file: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Collect 3DGS metrics (PSNR, SSIM, LPIPS) across algorithms, datasets, and scenes.")
    parser.add_argument("--dir", default="eval_out", help="Path to the eval_out directory (default: eval_out)")
    parser.add_argument("--out", default="metrics_summary.csv", help="Output CSV file name (default: metrics_summary.csv)")
    
    args = parser.parse_args()
    collect_metrics(args.dir, args.out)
