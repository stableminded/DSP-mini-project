# Code Explanation

This document provides a detailed breakdown of the codebase structure, classes, and functions.

---

## Table of Contents

1. [File Overview](#file-overview)
2. [Core Class: AudioFingerprintEngine](#core-class-audiofingerprintengine)
3. [Key Methods](#key-methods)
4. [Helper Functions](#helper-functions)
5. [Streamlit UI Functions](#streamlit-ui-functions)
6. [Data Structures](#data-structures)
7. [Code Flow Diagram](#code-flow-diagram)

---

## File Overview

### shazam.py (Main Implementation)
- **Size**: ~720 lines
- **Purpose**: Complete audio fingerprinting engine + Streamlit web UI
- **Dependencies**: librosa, scipy, numpy, matplotlib, streamlit
- **Main exports**: `AudioFingerprintEngine`, `main()`

### evaluate_fingerprinting.py (Evaluation Script)
- **Size**: ~250 lines
- **Purpose**: CLI evaluation tool for measuring Top-1/Top-K accuracy
- **Main function**: `evaluate()` - runs random queries and computes metrics

---

## Core Class: AudioFingerprintEngine

### Purpose
Handles all audio fingerprinting operations: loading, analyzing, indexing, and matching.

### Constructor
```python
def __init__(
    self,
    sample_rate: int = 22050,
    n_fft: int = 4096,
    hop_length: int = 512,
    peak_neighborhood_size: int = 20,
    amp_min_db: float = -40.0,
    fan_value: int = 15,
    min_time_delta: int = 1,
    max_time_delta: int = 200,
) -> None:
```

**Parameters:**
- `sample_rate`: Target audio resampling rate (Hz)
- `n_fft`: FFT window size for STFT
- `hop_length`: Hop size between STFT frames
- `peak_neighborhood_size`: Size of local region for peak detection
- `amp_min_db`: Minimum amplitude threshold for peaks
- `fan_value`: Number of peak pairs per anchor
- `min_time_delta`: Minimum time gap in peak pairs
- `max_time_delta`: Maximum time gap in peak pairs

**Instance Variables:**
```python
self.hash_db: Dict[str, List[Tuple[str, int]]]  # hash → [(track_id, anchor_time), ...]
self.track_meta: Dict[str, Dict[str, float]]    # track_id → {duration, num_peaks, num_hashes}
```

---

## Key Methods

### 1. load_audio(file_path: str) → Tuple[np.ndarray, int]

**Purpose:** Load audio file and resample to target sample rate.

**Input:**
- `file_path`: Path to audio file (.mp3, .wav, etc.)

**Output:**
- `y`: Audio samples as numpy array (mono, shape: (num_samples,))
- `sr`: Sample rate (always = self.sample_rate)

**Under the hood:**
```python
y, sr = librosa.load(file_path, sr=self.sample_rate, mono=True)
```

**Example:**
```python
engine = AudioFingerprintEngine()
y, sr = engine.load_audio("song.mp3")
# y.shape = (485100,)  # ~22 seconds at 22050 Hz
# sr = 22050
```

---

### 2. spectrogram_db(y: np.ndarray) → np.ndarray

**Purpose:** Compute log-magnitude spectrogram from audio waveform.

**Input:**
- `y`: Audio samples (1D array)

**Output:**
- `spec_db`: Log-magnitude spectrogram, shape (n_freqs, n_frames)

**Formula:**
$$S_{dB}(m,k) = 20\log_{10}(|X(m,k)| + \epsilon)$$

Where:
- $X(m,k)$ = STFT at frame m, frequency bin k
- Takes absolute value (magnitude)
- Converts to dB scale for robust peak picking

**Under the hood:**
```python
stft = librosa.stft(y, n_fft=self.n_fft, hop_length=self.hop_length)
magnitude = np.abs(stft)
return librosa.amplitude_to_db(magnitude, ref=np.max)
```

**Example:**
```python
spec_db = engine.spectrogram_db(y)
# spec_db.shape = (2049, 946)  # 2049 frequency bins, 946 time frames
```

---

### 3. find_peaks(spec_db: np.ndarray) → List[Tuple[int, int, float]]

**Purpose:** Detect local maxima in spectrogram (constellation map).

**Input:**
- `spec_db`: Log-magnitude spectrogram (2D array)

**Output:**
- List of peaks: `[(time_bin, freq_bin, amplitude_db), ...]`

**Algorithm:**
1. Apply 2D maximum filter (neighborhood size = `peak_neighborhood_size`)
2. Find cells where value equals max in neighborhood (local maxima)
3. Mask out low-energy regions (< `amp_min_db`)
4. Return coordinates of remaining peaks

**Code:**
```python
neighborhood = (self.peak_neighborhood_size, self.peak_neighborhood_size)
local_max = maximum_filter(spec_db, size=neighborhood) == spec_db
amp_mask = spec_db >= self.amp_min_db
mask = local_max & amp_mask

freq_idx, time_idx = np.where(mask)
peaks = [(int(t), int(f), float(spec_db[f, t])) for f, t in zip(freq_idx, time_idx)]
peaks.sort(key=lambda x: x[0])  # Sort by time
return peaks
```

**Example:**
```python
peaks = engine.find_peaks(spec_db)
# peaks = [(10, 512, -15.3), (15, 1023, -12.5), (20, 256, -20.1), ...]
# First peak: time_bin=10, freq_bin=512, amplitude=-15.3 dB
```

**Visual:** Peaks are plotted as cyan dots on spectrogram.

---

### 4. generate_hashes(peaks: List[Tuple[int, int, float]]) → List[Tuple[str, int]]

**Purpose:** Create fingerprint hashes from peak pairs.

**Input:**
- `peaks`: List of constellation peaks from `find_peaks()`

**Output:**
- List of hashes: `[(hash_string, anchor_time_bin), ...]`

**Algorithm:**
For each peak i (anchor peak):
  For j = 1 to fan_value:
    Get peak i+j (target peak)
    If min_time_delta < time_diff < max_time_delta:
      Create hash from (f_i, f_j, time_diff)

**Formula:**
$$h = H(f_1, f_2, \Delta t)$$

where hash function uses SHA-1:
```python
hash_input = f"{f1}|{f2}|{delta_t}".encode("utf-8")
digest = hashlib.sha1(hash_input).hexdigest()[:20]  # Truncate to 20 chars
```

**Code:**
```python
hashes = []
for i, (t1, f1, _) in enumerate(peaks):
    for j in range(1, self.fan_value + 1):
        if i + j >= len(peaks):
            break
        t2, f2, _ = peaks[i + j]
        delta_t = t2 - t1
        if delta_t < self.min_time_delta:
            continue
        if delta_t > self.max_time_delta:
            break
        
        hash_input = f"{f1}|{f2}|{delta_t}".encode("utf-8")
        digest = hashlib.sha1(hash_input).hexdigest()[:20]
        hashes.append((digest, t1))
return hashes
```

**Example:**
```python
peaks = [(10, 512, -15.3), (15, 1023, -12.5), (20, 256, -20.1), ...]
hashes = engine.generate_hashes(peaks)
# hashes = [
#   ("a1b2c3d4e5f6g7h8i9j0", 10),  # hash from (512, 1023, 5)
#   ("k1l2m3n4o5p6q7r8s9t0", 10),  # hash from (512, 256, 10)
#   ...
# ]
```

---

### 5. fingerprint_file(file_path: str) → Dict[str, object]

**Purpose:** Complete fingerprinting pipeline for a single file.

**Input:**
- `file_path`: Path to audio file

**Output:**
```python
{
    "hashes": [(hash, time), ...],
    "duration": float (seconds),
    "num_peaks": int,
    "spec_db": np.ndarray,
    "peaks": [(t, f, amp), ...]
}
```

**Code:**
```python
def fingerprint_file(self, file_path: str) -> Dict[str, object]:
    y, sr = self.load_audio(file_path)                    # Step 1
    spec_db = self.spectrogram_db(y)                      # Step 2
    peaks = self.find_peaks(spec_db)                      # Step 3
    hashes = self.generate_hashes(peaks)                  # Step 4
    duration = len(y) / float(sr)
    return {
        "hashes": hashes,
        "duration": duration,
        "num_peaks": len(peaks),
        "spec_db": spec_db,
        "peaks": peaks,
    }
```

**Full pipeline:**
1. Load audio → raw waveform
2. Compute STFT → spectrogram
3. Detect peaks → constellation map
4. Generate hashes → fingerprint

---

### 6. add_track(track_id: str, fingerprint: Dict[str, object]) → None

**Purpose:** Add fingerprint to the inverted index database.

**Input:**
- `track_id`: Unique identifier (filename, song ID, etc.)
- `fingerprint`: Dict from `fingerprint_file()`

**Action:**
1. For each hash in fingerprint, add mapping: hash → (track_id, anchor_time)
2. Store metadata (duration, peak count, hash count)

**Code:**
```python
def add_track(self, track_id: str, fingerprint: Dict[str, object]) -> None:
    hashes = fingerprint["hashes"]
    for h, anchor_time in hashes:
        self.hash_db[h].append((track_id, int(anchor_time)))
    
    self.track_meta[track_id] = {
        "duration": float(fingerprint["duration"]),
        "num_peaks": float(fingerprint["num_peaks"]),
        "num_hashes": float(len(hashes)),
    }
```

**Example:**
```python
engine.add_track("song1.mp3", fingerprint_data)
# Now hash_db maps thousands of hashes to song1.mp3 at various times
```

**Index structure:**
```
hash_db = {
    "a1b2c3d4e5...": [("song1.mp3", 10), ("song2.mp3", 45)],
    "f6g7h8i9j0...": [("song3.mp3", 120)],
    ...
}
```

---

### 7. build_index(dataset_root: str, max_files: int, progress_callback) → Dict

**Purpose:** Fingerprint all audio files in a folder and build complete index.

**Input:**
- `dataset_root`: Path to folder with audio files
- `max_files`: Limit (0 = all)
- `progress_callback`: Function called for each file `(current, total, rel_id, status)`

**Output:**
```python
{
    "indexed": int,          # Successfully indexed
    "failed": [(filename, error_msg), ...],
    "total_files": int,
    "total_hashes": int,
    "total_tracks": len(self.track_meta),
}
```

**Algorithm:**
```python
def build_index(self, dataset_root, max_files=None, progress_callback=None):
    root = Path(dataset_root)
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    
    if max_files and max_files > 0:
        files = files[:max_files]
    
    failed = []
    for i, path in enumerate(files, start=1):
        rel_id = str(path.relative_to(root))
        try:
            fp = self.fingerprint_file(str(path))
            self.add_track(rel_id, fp)
            status = "indexed"
        except Exception as exc:
            failed.append((rel_id, str(exc)))
            status = "failed"
        
        if progress_callback:
            progress_callback(i, len(files), rel_id, status)
    
    total_hashes = sum(len(v) for v in self.hash_db.values())
    return {
        "indexed": len(files) - len(failed),
        "failed": failed,
        "total_files": len(files),
        "total_hashes": total_hashes,
        "total_tracks": len(self.track_meta),
    }
```

---

### 8. match_fingerprint(query_hashes, top_k=5) → List[MatchCandidate]

**Purpose:** Find best matching tracks for a query fingerprint.

**Input:**
- `query_hashes`: List of (hash, time_bin) from query audio
- `top_k`: Return top K matches

**Output:**
- List of `MatchCandidate` objects (sorted by vote count)

**Algorithm (Offset Voting):**
1. For each query hash, look up all database occurrences
2. For each DB occurrence, compute offset: `offset = db_time - query_time`
3. Accumulate votes: `votes[track_id][offset] += 1`
4. For each track, find the offset with most votes
5. Score = votes at that offset
6. Return top-K by score

**Formula:**
$$\Delta = t_{db} - t_q$$

A correct match has many hashes with the same offset.

**Code:**
```python
def match_fingerprint(self, query_hashes, top_k=5):
    offset_votes = defaultdict(Counter)
    
    for h, q_time in query_hashes:
        if h not in self.hash_db:
            continue
        for track_id, db_time in self.hash_db[h]:
            offset = db_time - q_time
            offset_votes[track_id][offset] += 1
    
    candidates = []
    total_query_hashes = max(len(query_hashes), 1)
    
    for track_id, counter in offset_votes.items():
        best_offset, votes = counter.most_common(1)[0]
        confidence = votes / total_query_hashes
        candidates.append(
            MatchCandidate(
                track_id=track_id,
                votes=votes,
                best_offset=best_offset,
                confidence=confidence,
            )
        )
    
    candidates.sort(key=lambda x: x.votes, reverse=True)
    return candidates[:top_k]
```

**Example:**
```python
query_hashes = [("a1b2...", 10), ("f6g7...", 15), ...]
matches = engine.match_fingerprint(query_hashes, top_k=3)
# matches[0].track_id = "song1.mp3", votes=250, confidence=0.85
# matches[1].track_id = "song2.mp3", votes=12,  confidence=0.04
```

---

### 9. export_index(output_file: str) → None

**Purpose:** Save index to JSON file.

**Code:**
```python
def export_index(self, output_file: str) -> None:
    serializable = {
        "params": {...},  # All init parameters
        "track_meta": self.track_meta,
        "hash_db": {k: v for k, v in self.hash_db.items()},
    }
    with open(output_file, "w") as f:
        json.dump(serializable, f)
```

---

### 10. import_index(index_file: str) → None

**Purpose:** Load index from JSON file.

---

## Helper Functions

### get_data_folder_options() → Dict[str, str]

**Purpose:** Auto-detect collaborative datasets in `Data/` folder contributed by team members.

**Returns:** Dictionary mapping dataset names to folder paths.

**Code:**
```python
def get_data_folder_options() -> Dict[str, str]:
    """Detect available datasets in Data/ folder contributed by collaborators."""
    data_path = Path("./Data")
    options = {}
    
    if data_path.exists():
        for item in data_path.iterdir():
            if item.is_dir() and item.name != "__pycache__":
                audio_files = [
                    p for p in item.rglob("*")
                    if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
                ]
                if audio_files:
                    options[f"{item.name} ({len(audio_files)} files)"] = str(item)
    
    return options
```

**What it does:**
- Scans `Data/` folder for subfolders
- Counts audio files in each subfolder
- Returns only folders with audio files
- Displays file count in UI

**Example:**
```python
options = get_data_folder_options()
# {"gtzan_blues (10 files)": "./Data/gtzan_blues", "mymusic (15 files)": "./Data/mymusic"}
```

---

### plot_spectrogram_with_peaks(spec_db, peaks, max_points=1000)

Displays spectrogram with detected peaks overlaid. Optimized for cloud deployment.

**Key improvements:**
- Down-samples large spectrograms (50% reduction) for faster rendering
- Closes figure after display to free memory
- Returns `None` if spectrogram too large

**Usage in UI:**
```python
fig = plot_spectrogram_with_peaks(fp["spec_db"], fp["peaks"])
if fig is not None:
    st.pyplot(fig)
else:
    st.info("Spectrogram too large to display. Matching still works.")
```

---

### get_engine_from_ui() → AudioFingerprintEngine

Reads all sidebar parameters and creates/updates engine instance.

Checks if parameters changed; if so, reinitializes engine.

---

## Streamlit UI Functions

### formulas_section()
Displays core mathematical formulas (STFT, dB conversion, hashing, voting).

### algorithm_section()
Explains 7-step pipeline with implementation scope.

### build_index_ui(engine)
Tab 1 - Index building interface with collaborative dataset support.

**Controls:**
- Dataset selection (Custom Path / GTZAN / FMA / Collaborative datasets from `Data/` folder)
- Folder path input (auto-populated based on selection)
- Max files slider
- Build/Clear buttons
- Save/Load index
- Expandable section showing available collaborative datasets

**Features:**
- **Auto-detection**: Scans `Data/` folder for subfolders with audio files
- **Dropdown integration**: Collaborator-contributed datasets appear as options
- **File counting**: Shows number of audio files in each collaborative dataset
- **Dynamic paths**: Folder path auto-updates when dataset selected

**Displays:**
- Progress bar with real-time file indexing status
- Build summary JSON (indexed count, failed count, total hashes)
- Failed files table with error reasons
- Track count and metadata

**Collaborative workflow:**
1. Team member adds dataset to `Data/subfolder/` and pushes to GitHub
2. Other members pull latest code (`git pull origin main`)
3. Dataset automatically appears in dropdown
4. Select dataset and build index - no code changes needed

### identify_query_ui(engine)
Tab 2 - Query matching interface.

**Controls:**
- File uploader
- Top-K slider
- Identification button

**Displays:**
- Processing trace
- Query metrics (duration, peaks, hashes)
- Peak/hash sample tables
- Spectrogram plot
- Top matches table

### main()
Entry point, sets up page layout and three tabs.

---

## Data Structures

### MatchCandidate (Dataclass)
```python
@dataclass
class MatchCandidate:
    track_id: str           # Song ID/filename
    votes: int              # Number of matching hashes
    best_offset: int        # Time alignment in frames
    confidence: float       # votes / total_query_hashes
```

### hash_db (Dictionary)
```python
hash_db: Dict[str, List[Tuple[str, int]]]

Example:
{
    "abc123...": [("song1.mp3", 45), ("song2.mp3", 120)],
    "def456...": [("song1.mp3", 50), ("song3.mp3", 200)],
    ...
}
```

### track_meta (Dictionary)
```python
track_meta: Dict[str, Dict[str, float]]

Example:
{
    "song1.mp3": {
        "duration": 240.5,      # seconds
        "num_peaks": 5234,      # detected peaks
        "num_hashes": 18945,    # fingerprint hashes
    },
    ...
}
```

---

## Code Flow Diagram

### Indexing Flow
```
Audio File
    ↓
load_audio() → raw waveform
    ↓
spectrogram_db() → frequency-time matrix
    ↓
find_peaks() → (time, freq, amplitude) constellation
    ↓
generate_hashes() → (hash_string, anchor_time) list
    ↓
add_track() → update hash_db and track_meta
    ↓
[Repeat for all files] → Complete Index
    ↓
export_index() → JSON file
```

### Matching Flow
```
Query Audio File
    ↓
fingerprint_file() → query_hashes, query_duration, peaks
    ↓
match_fingerprint(query_hashes) → offset voting
    ↓
For each hash:
    - Lookup in hash_db
    - Get all (track_id, db_time) pairs
    - Compute offset = db_time - query_time
    - Vote for (track_id, offset)
    ↓
For each track:
    - Find offset with most votes
    - Compute confidence = votes / len(query_hashes)
    ↓
Sort by votes, return top-K
    ↓
MatchCandidate(track_id, votes, offset, confidence)
```

---

## Complexity Analysis

| Operation | Time | Space |
|-----------|------|-------|
| load_audio(file) | O(n) | O(n) |
| spectrogram_db(y) | O(n log n) | O(n) |
| find_peaks(spec_db) | O(h × w) | O(h × w) |
| generate_hashes(peaks) | O(P × F) | O(P × F) |
| add_track() | O(H) | O(H) |
| build_index(N files) | O(N × M) | O(H) |
| match_fingerprint(Q) | O(Q × C) | O(T) |

Where:
- n = audio samples
- h, w = spectrogram height, width
- P = number of peaks
- F = fan value
- H = number of hashes
- N = number of files
- M = avg samples per file
- Q = number of query hashes
- C = avg collisions per hash
- T = number of tracks

---

## Dependencies

```python
import hashlib              # SHA-1 hashing
import json                 # Index serialization
import os                   # File operations
import tempfile             # Temporary files
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path    # Path manipulation
from typing import ...      # Type hints

import librosa              # Audio loading & STFT
import librosa.display      # Spectrogram display
import matplotlib.pyplot    # Plotting
import numpy as np          # Arrays & math
import streamlit as st      # Web UI
from scipy.ndimage import maximum_filter  # 2D local max
```

---

## Key Insights

1. **No External Fingerprinting Library**: All core DSP is hand-implemented.

2. **Robustness Through Constellation**: Peak pairs are resistant to noise/compression.

3. **Efficiency**: Hash-based indexing allows fast O(Q × C) lookup.

4. **Offset Voting**: Clever technique that naturally aligns query to database without explicit alignment algorithms.

5. **Modular Design**: Each method does one thing (STFT, peaks, hashing, matching).

