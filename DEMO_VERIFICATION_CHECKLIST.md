# Demo Verification Checklist

This checklist walks you through the key features to demo for your academic project presentation.

---

## Tab 1: Index Builder

### Verify Index Building from Local Samples
1. **Dataset Selection**
   - [ ] Sidebar shows "Fingerprint Parameters" with tunable controls
   - [ ] Dataset choice dropdown visible with options: "Custom Path", "GTZAN", "FMA"
   - [ ] Default sample path: `./samples`

2. **Build Index**
   - [ ] Click "Build / Rebuild Index"
   - [ ] Progress bar appears and fills as files are indexed
   - [ ] Status shows: `[1/3] INDEXED song1.mp3`, `[2/3] INDEXED song2.mp3`, etc.
   - [ ] Expected result summary:
     - Total files: 3
     - Indexed: 3
     - Failed: 0
     - Total hashes generated: ~1,100,000+
     - Unique hash keys: thousands

3. **Index Persistence**
   - [ ] "Index Persistence" section shows save/load buttons
   - [ ] Click "Save Index" → file `fingerprint_index.json` created
   - [ ] Click "Load Index" → loads previously saved index

4. **Index Statistics**
   - [ ] Bottom of tab shows "Tracks in memory: 3 | Unique hash keys: XXXXX"

---

## Tab 2: Query Identification

### Verify Matching on Real Audio

1. **Upload and Process**
   - [ ] Upload a small audio clip (can be a 10-15 sec excerpt from one of the songs)
   - [ ] Adjust "Top K matches" slider (e.g., set to 3)
   - [ ] Click "Run Identification"

2. **Processing Trace (Step-by-Step)**
   - [ ] Title: "Processing Trace"
   - [ ] Shows step-by-step breakdown:
     - "Step 1: Loading and resampling query audio"
     - "Step 2: Spectrogram computed and converted to dB scale"
     - "Step 3: Constellation map peaks extracted"
     - "Step 4: Peak pairs converted to hashes"
     - "Step 5: Matching by hash collisions and offset voting"

3. **Query Metrics**
   - [ ] "Query duration (s)": e.g., 14.23
   - [ ] "Detected peaks": e.g., 1,250+
   - [ ] "Generated hashes": e.g., 5,000+

4. **Constellation Samples & Hash Samples**
   - [ ] Expander: "Show constellation samples and hash samples"
   - [ ] Peak preview table shows: time_bin, freq_bin, amplitude_db (up to 12 rows)
   - [ ] Hash preview table shows: hash (SHA1 truncated), anchor_time_bin (up to 12 rows)

5. **Spectrogram Visualization**
   - [ ] Expander: "Show query spectrogram and peaks"
   - [ ] Plot displays log-magnitude spectrogram (magma colormap)
   - [ ] Cyan dots overlay showing detected peaks on constellation

6. **Top Matches Result**
   - [ ] Success message: "Best match: song1.mp3" (or whichever file matched)
   - [ ] Metrics: "Votes: XXX | Best offset: YYY frames | Confidence: Z.ZZZZ"
   - [ ] Table "Top Matches" shows:
     - track_id
     - votes (highest for correct match)
     - best_offset
     - confidence (0.0 to 1.0)

---

## Tab 3: Algorithm + Formulas

### Verify Educational Content

1. **Implementation Clarity Statement**
   - [ ] Message visible: "DSP implementation note: this project does not import any Shazam fingerprinting library..."
   - [ ] Message visible: "Implementation scope: STFT, local-max peak detection, landmark pairing, hash generation, inverted index construction, and offset-voting matching are all implemented in AudioFingerprintEngine."
   - [ ] Message at top: "This app demonstrates a DSP-first implementation with spectrogram constellation hashing; no external Shazam fingerprinting SDK is used."

2. **Processing Pipeline**
   - [ ] Section "Processing Pipeline" explains 7-step process
   - [ ] Steps include STFT, spectrogram, peaks, landmark pairing, index, query hashing, offset voting

3. **Core Formulas**
   - [ ] Section "Core Formulas Used"
   - [ ] Displays 4 key LaTeX formulas:
     1. STFT: $X(m, k) = \sum_{n=0}^{N-1} ...$
     2. dB Spectrogram: $S_{dB}(m,k) = 20\log_{10}(|X(m,k)| + \epsilon)$
     3. Fingerprint Hash: $h = H(f_1, f_2, \Delta t)$ with $\Delta t = t_2 - t_1$
     4. Offset Vote: $\Delta = t_{db} - t_q$

---

## Sidebar: Parameter Tuning

### Fingerprint Parameters
- [ ] **Sample rate**: default 22050 Hz (dropdown: 16000, 22050, 44100)
- [ ] **N FFT**: default 4096 (dropdown: 1024, 2048, 4096)
- [ ] **Hop length**: default 512 (dropdown: 256, 512, 1024)
- [ ] **Peak neighborhood**: default 20 (slider: 5-40)
- [ ] **Min peak amplitude (dB)**: default -40.0 (slider: -80 to -5)
- [ ] **Fan value**: default 15 (slider: 3-30)
- [ ] **Min delta t**: default 1 (slider: 1-10)
- [ ] **Max delta t**: default 200 (slider: 20-400)

**Demo tip**: Adjust one parameter (e.g., lower amp threshold to -50) and rebuild index to show impact on peak detection.

---

## Command-Line Evaluation (For Report Results)

### Run Full Evaluation Suite
```bash
cd "c:\Users\Dhairya Mehta\Downloads\DSP Mini Project"
& ".\.venv\Scripts\python.exe" evaluate_fingerprinting.py `
  --dataset_root "samples" `
  --max_index_files 3 `
  --n_queries 20 `
  --clip_duration 5 `
  --top_k 3 `
  --report_file final_eval_report.json
```

Expected output:
- Top-1 accuracy: 1.0 (100%)
- Top-3 accuracy: 1.0 (100%)
- 0 failed or skipped queries

Result saved to: `final_eval_report.json`

---

## Viva/Presentation Flow (2-3 minutes)

1. **Introduction** (30 seconds)
   - "This is a spectrogram constellation hashing implementation, similar to Shazam."
   - "Core DSP logic is implemented in code; no Shazam SDK."

2. **Show Tab 3 (Formulas)** (1 minute)
   - Discuss STFT and dB conversion
   - Explain peak constellation and landmark pairing
   - Show offset-voting concept

3. **Build Index** (30 seconds)
   - Switch to Tab 1
   - Click "Build Index" on samples folder
   - Show progress and final stats

4. **Run Query** (1 minute)
   - Switch to Tab 2
   - Upload a 10-15 second clip from one of the songs
   - Show spectrogram with peaks
   - Show perfect match result

5. **Discuss Parameters & Results** (1 minute)
   - Refer to sidebar parameters
   - Mention evaluation results: 100% Top-1 accuracy on test set
   - Briefly discuss robustness

---

## Files to Mention in Viva

- **[shazam.py](shazam.py)**: Main fingerprinting engine and UI
- **[evaluate_fingerprinting.py](evaluate_fingerprinting.py)**: CLI evaluation tool
- **[DEVELOPMENT_README.md](DEVELOPMENT_README.md)**: Full technical documentation
- **[VIVA_SHEET.md](VIVA_SHEET.md)**: Quick reference for Q&A
- **[sample_eval_report.json](sample_eval_report.json)**: Results from 9-query test (100% accuracy)

---

## Troubleshooting During Demo

| Issue | Solution |
|-------|----------|
| App doesn't load | Ensure Streamlit is installed: `pip install streamlit` |
| No files appear in index builder | Check dataset path is correct, e.g., `./samples` |
| Audio upload fails | Ensure file is MP3, WAV, or other supported format |
| Spectrogram doesn't show | Click "Show query spectrogram and peaks" expander |
| Formulas not rendering | If LaTeX not visible, they're stored as markdown; content is there |

---

## Key Talking Points

1. **Why spectrogram peaks?** → Robust to compression, noise, time shifts
2. **Why offset voting?** → Finds time alignment between query and DB
3. **Why constellation hashing?** → Efficient matching; scales to millions of songs
4. **Current limitations?** → No explicit pitch/tempo invariance; single-threshold peaks
5. **Future work?** → Adaptive thresholding, GPU acceleration, binary index compression

---

## Success Criteria

✅ Index builds without errors  
✅ Query returns correct match with high confidence  
✅ Top-1 accuracy ≥ 95% (expect 100% on clean samples)  
✅ Formulas clearly explained  
✅ Code shows pure DSP implementation, not SDK wrapper  
✅ Evaluation report produced with metrics  

