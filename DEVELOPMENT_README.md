# Shazam-Style Audio Fingerprinting Mini Project

## 1. Project Overview
This project implements a simplified Shazam algorithm (audio fingerprinting) with a visual, educational UI.
It supports building a fingerprint database from either:
- GTZAN dataset (genre classification dataset)
- FMA (Free Music Archive) dataset

Important implementation note:
- No external Shazam fingerprinting SDK/library is used for core matching.
- Core DSP logic is explicitly coded in this project: STFT -> constellation peaks -> landmark pairing -> hash index -> offset-vote retrieval.

The app lets you:
1. Build an index of fingerprints from a dataset folder.
2. Upload a query audio clip.
3. Identify the most likely matching track.
4. Visualize intermediate processing stages and formulas.

---

## 2. File Structure
- `shazam.py`: Full implementation of the algorithm and Streamlit UI.
- `evaluate_fingerprinting.py`: Automatic Top-1/Top-K evaluation script using random query excerpts.
- `VIVA_SHEET.md`: Viva/presentation sheet with formulas, answers, and demo flow.
- `requirements.txt`: Python dependencies.
- `DEVELOPMENT_README.md`: This full academic development note.

---

## 3. Algorithmic Pipeline

Core implementation location:
- The end-to-end DSP fingerprinting and matching pipeline is implemented in `AudioFingerprintEngine` inside `shazam.py`.

### Step 1: Audio Loading and Normalization
- Audio is loaded in mono using `librosa.load`.
- Resampling is done to a fixed sampling rate (`sample_rate`, default 22050 Hz).

### Step 2: Time-Frequency Representation (STFT)
The Short-Time Fourier Transform is computed:

$$
X(m, k) = \sum_{n=0}^{N-1} x[n + mH] w[n] e^{-j2\pi kn/N}
$$

Where:
- $x[n]$ = input signal
- $w[n]$ = analysis window
- $N$ = FFT size
- $H$ = hop length
- $m$ = frame index
- $k$ = frequency bin index

### Step 3: Log-Magnitude Spectrogram
Magnitude values are converted to decibels for robust peak picking:

$$
S_{dB}(m,k) = 20\log_{10}(|X(m,k)| + \epsilon)
$$

### Step 4: Constellation Map (Peak Detection)
- Local maxima are detected using a 2D neighborhood max filter.
- Low-energy bins are removed using threshold (`amp_min_db`).
- Remaining points are spectral peaks: $(t, f)$.

### Step 5: Landmark Pairing and Hashing
For each anchor peak $(t_1, f_1)$, neighboring peaks $(t_2, f_2)$ are paired within a time window.

Time difference:

$$
\Delta t = t_2 - t_1
$$

Fingerprint hash key:

$$
h = H(f_1, f_2, \Delta t)
$$

`H` is implemented with SHA-1 (truncated) over the tuple `(f1, f2, delta_t)`.

### Step 6: Inverted Index Construction
Each hash points to one or many occurrences:

- Key: `hash`
- Value: list of `(track_id, anchor_time)`

This allows fast lookup from query hashes to candidate tracks.

### Step 7: Query Matching by Offset Voting
For each matching hash collision between query and database:

$$
\Delta = t_{db} - t_q
$$

Votes are accumulated for `(track_id, \Delta)`.
The best track has the strongest vote concentration at one offset.

Confidence (as implemented):

$$
\text{confidence} = \frac{\text{best votes}}{\text{number of query hashes}}
$$

---

## 4. Why This Works
Audio fingerprints are robust because:
- They rely on strong spectral peaks, not full waveforms.
- Peak pair relationships $(f_1, f_2, \Delta t)$ survive moderate noise/compression.
- Offset voting aligns clips regardless of where the query starts.

---

## 5. UI Features Implemented
In the Streamlit app:

1. **Index Builder tab**
- Choose dataset mode: Custom Path / GTZAN / FMA.
- Set max files to index.
- Build and monitor progress.
- Save/load index as JSON.

2. **Query Identification tab**
- Upload audio query file.
- View processing trace step-by-step.
- Inspect query duration, number of peaks, number of hashes.
- Display spectrogram with peak overlay.
- Show best match + Top-K candidates table.

3. **Algorithm + Formulas tab**
- Full pipeline explanation.
- Mathematical formulas used in implementation.

---

## 6. Dataset Notes

### GTZAN
Typical folder:
- `Data/genres_original/` with genre subfolders and `.wav` files.

### FMA
Typical folder:
- `Data/fma_small/` with nested folders and `.mp3` files.

The app recursively scans for supported audio extensions:
- `.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`, `.au`

---

## 7. How to Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start app:

```bash
streamlit run shazam.py
```

3. In browser:
- Build or load index.
- Upload query and run identification.

4. Run quantitative evaluation (CLI):

```bash
python evaluate_fingerprinting.py --dataset_root "Data/genres_original" --max_index_files 100 --n_queries 50 --clip_duration 5 --top_k 5 --report_file evaluation_report.json
```

Example for FMA:

```bash
python evaluate_fingerprinting.py --dataset_root "Data/fma_small" --max_index_files 200 --n_queries 100 --clip_duration 5 --top_k 5 --report_file evaluation_report_fma.json
```

---

## 8. Tunable Parameters and Impact
- `n_fft`: Higher values improve frequency resolution but increase computation.
- `hop_length`: Lower values improve time resolution but increase frames.
- `amp_min_db`: Higher threshold gives fewer, stronger peaks.
- `peak_neighborhood_size`: Controls local maxima strictness.
- `fan_value`: More pairings per anchor increases hashes and recall, but costs memory/time.
- `max_time_delta`: Controls temporal span used for landmark pairs.

---

## 9. Complexity Discussion
Let:
- $P$ = number of detected peaks
- $F$ = fan value
- $T$ = number of tracks

Fingerprint generation per track is approximately:
- Peak pairing: $O(P \cdot F)$

Matching a query with $Q$ hashes depends on hash collisions in index; practical performance is near-linear in number of observed collisions.

---

## 10. Limitations and Academic Extensions
Current limitations:
- Basic peak picking (single-threshold local maxima).
- No explicit tempo/pitch-shift invariance.
- JSON index can become large for huge datasets.

Good extensions for report/future work:
- Better peak salience filtering by adaptive thresholding.
- GPU/STFT acceleration.
- Binary compressed index format.
- Segment-level confidence calibration.
- Robustness tests under noise and codec distortion.

---

## 11. Validation Strategy (Suggested)
For academic evaluation:
1. Split dataset into index tracks and held-out query excerpts.
2. Create query clips of varying durations (3s, 5s, 10s).
3. Add controlled noise/compression.
4. Measure Top-1 and Top-K accuracy.
5. Plot accuracy vs clip length and SNR.

---

## 12. Summary
This project recreates the core idea of the Shazam algorithm:
- Spectrogram peak landmarks
- Hash-based fingerprint indexing
- Offset-voting match retrieval

It is implemented with an explainable UI suitable for demos, lab submissions, and academic reports.

---

## 13. Automatic Evaluation Script
The script `evaluate_fingerprinting.py` performs reproducible retrieval evaluation.

What it does:
1. Builds an index from the provided dataset path.
2. Samples random tracks from the indexed set.
3. Extracts random query clips of fixed duration.
4. Runs matching and computes:
	- Top-1 accuracy
	- Top-K accuracy
5. Saves full report as JSON.

Important arguments:
- `--dataset_root`: Root dataset folder (GTZAN or FMA path).
- `--max_index_files`: Number of files used for indexing (0 for all).
- `--n_queries`: Number of random query trials.
- `--clip_duration`: Duration of each query excerpt in seconds.
- `--top_k`: Value of K for Top-K metric.
- `--report_file`: Output JSON file path.

Output JSON contains:
- `config`: exact experiment setup.
- `summary`: aggregate metrics and skipped-case counts.
- `details`: per-query predictions and correctness flags.

---

## 14. Viva Sheet for Academic Defense
The file `VIVA_SHEET.md` is included for presentation and oral defense.

It contains:
1. Concise project objective.
2. Core formulas (STFT, dB conversion, hash, offset vote).
3. Step-by-step explanation you can narrate.
4. Typical viva questions and short model answers.
5. A 2-3 minute demo flow.

Recommended use:
- Use `VIVA_SHEET.md` during final project demo rehearsal.
- Use evaluation results from `evaluation_report.json` to support claims about retrieval quality.
