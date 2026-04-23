from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import librosa

from shazam import AudioFingerprintEngine, SUPPORTED_EXTENSIONS


@dataclass
class EvalResult:
    track_id: str
    query_start_sec: float
    top1_correct: bool
    topk_correct: bool
    top1_prediction: Optional[str]
    top1_confidence: float


def collect_audio_files(dataset_root: Path) -> List[Path]:
    files = [
        p
        for p in dataset_root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    files.sort()
    return files


def fingerprint_audio_array(engine: AudioFingerprintEngine, y) -> Dict[str, object]:
    spec_db = engine.spectrogram_db(y)
    peaks = engine.find_peaks(spec_db)
    hashes = engine.generate_hashes(peaks)
    return {
        "hashes": hashes,
        "duration": len(y) / float(engine.sample_rate),
        "num_peaks": len(peaks),
    }


def build_engine_index(
    dataset_root: Path,
    max_index_files: int,
    sample_rate: int,
) -> AudioFingerprintEngine:
    engine = AudioFingerprintEngine(sample_rate=sample_rate)

    def progress(current: int, total: int, rel_id: str, status: str) -> None:
        if current == 1 or current == total or current % 25 == 0:
            print(f"[{current}/{total}] {status.upper()} {rel_id}")

    index_stats = engine.build_index(
        dataset_root=str(dataset_root),
        max_files=max_index_files if max_index_files > 0 else None,
        progress_callback=progress,
    )

    print("\nIndex build summary:")
    print(json.dumps(index_stats, indent=2))
    return engine


def evaluate(
    dataset_root: Path,
    engine: AudioFingerprintEngine,
    n_queries: int,
    clip_duration: float,
    top_k: int,
    seed: int,
) -> Dict[str, object]:
    random.seed(seed)
    indexed_track_ids = list(engine.track_meta.keys())
    if not indexed_track_ids:
        raise RuntimeError("No indexed tracks available. Build index first.")

    query_results: List[EvalResult] = []
    skipped_short = 0
    skipped_no_hash = 0

    clip_samples = int(clip_duration * engine.sample_rate)

    for i in range(1, n_queries + 1):
        true_track_id = random.choice(indexed_track_ids)
        true_path = dataset_root / true_track_id

        if not true_path.exists():
            print(f"[{i}/{n_queries}] SKIP missing file: {true_track_id}")
            continue

        y, _ = librosa.load(str(true_path), sr=engine.sample_rate, mono=True)
        if len(y) <= clip_samples + 1:
            skipped_short += 1
            print(f"[{i}/{n_queries}] SKIP too short: {true_track_id}")
            continue

        start_idx = random.randint(0, len(y) - clip_samples - 1)
        start_sec = start_idx / float(engine.sample_rate)
        query_y = y[start_idx : start_idx + clip_samples]

        query_fp = fingerprint_audio_array(engine, query_y)
        query_hashes = query_fp["hashes"]

        if not query_hashes:
            skipped_no_hash += 1
            print(f"[{i}/{n_queries}] SKIP no hashes: {true_track_id}")
            continue

        candidates = engine.match_fingerprint(query_hashes, top_k=top_k)
        if not candidates:
            result = EvalResult(
                track_id=true_track_id,
                query_start_sec=start_sec,
                top1_correct=False,
                topk_correct=False,
                top1_prediction=None,
                top1_confidence=0.0,
            )
        else:
            top1_pred = candidates[0].track_id
            top1_correct = top1_pred == true_track_id
            topk_correct = any(c.track_id == true_track_id for c in candidates)
            result = EvalResult(
                track_id=true_track_id,
                query_start_sec=start_sec,
                top1_correct=top1_correct,
                topk_correct=topk_correct,
                top1_prediction=top1_pred,
                top1_confidence=float(candidates[0].confidence),
            )

        query_results.append(result)
        print(
            f"[{i}/{n_queries}] true={true_track_id} | pred={result.top1_prediction} | "
            f"Top1={result.top1_correct} | Top{top_k}={result.topk_correct}"
        )

    total_valid = len(query_results)
    top1_hits = sum(r.top1_correct for r in query_results)
    topk_hits = sum(r.topk_correct for r in query_results)

    top1_acc = (top1_hits / total_valid) if total_valid else 0.0
    topk_acc = (topk_hits / total_valid) if total_valid else 0.0

    return {
        "config": {
            "n_queries": n_queries,
            "clip_duration": clip_duration,
            "top_k": top_k,
            "seed": seed,
            "sample_rate": engine.sample_rate,
        },
        "summary": {
            "total_valid_queries": total_valid,
            "top1_hits": top1_hits,
            "topk_hits": topk_hits,
            "top1_accuracy": top1_acc,
            "topk_accuracy": topk_acc,
            "skipped_short": skipped_short,
            "skipped_no_hash": skipped_no_hash,
        },
        "details": [
            {
                "track_id": r.track_id,
                "query_start_sec": r.query_start_sec,
                "top1_correct": r.top1_correct,
                "topk_correct": r.topk_correct,
                "top1_prediction": r.top1_prediction,
                "top1_confidence": r.top1_confidence,
            }
            for r in query_results
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Shazam-style fingerprint matching")
    parser.add_argument("--dataset_root", type=str, required=True, help="Path to dataset root")
    parser.add_argument("--max_index_files", type=int, default=100, help="Max files to index (0 for all)")
    parser.add_argument("--n_queries", type=int, default=50, help="Number of query excerpts")
    parser.add_argument("--clip_duration", type=float, default=5.0, help="Duration of each query clip in seconds")
    parser.add_argument("--top_k", type=int, default=5, help="Top-K for retrieval metric")
    parser.add_argument("--sample_rate", type=int, default=22050, help="Target sample rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--report_file",
        type=str,
        default="evaluation_report.json",
        help="Output JSON report path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_root = Path(args.dataset_root)

    if not dataset_root.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {dataset_root}")

    files = collect_audio_files(dataset_root)
    if not files:
        raise RuntimeError("No supported audio files found in dataset path.")

    print(f"Found {len(files)} audio files under: {dataset_root}")
    engine = build_engine_index(dataset_root, args.max_index_files, args.sample_rate)

    print("\nRunning evaluation...")
    report = evaluate(
        dataset_root=dataset_root,
        engine=engine,
        n_queries=args.n_queries,
        clip_duration=args.clip_duration,
        top_k=args.top_k,
        seed=args.seed,
    )

    print("\nEvaluation summary:")
    print(json.dumps(report["summary"], indent=2))

    with open(args.report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nSaved report to: {args.report_file}")


if __name__ == "__main__":
    main()
