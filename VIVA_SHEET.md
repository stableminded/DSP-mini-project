# Viva / Presentation Sheet

## 1. Project Title
Shazam-Style Audio Fingerprinting with Explainable UI (GTZAN/FMA)

## 2. One-Line Objective
Identify a query audio clip by matching robust spectral fingerprints against an indexed music database.

## 3. Core Idea
Instead of matching raw waveforms, we match compact hashes generated from stable spectrogram peak pairs:
- Build fingerprints for each dataset track.
- Build an inverted index from hash to track/time positions.
- For a query, compute the same hashes and vote for the best time-aligned track.

Implementation clarification for viva:
- We did not use any direct Shazam fingerprinting package.
- The DSP core is implemented in our code: STFT, local peak detection, constellation mapping, pair-hash generation, and offset-voting matcher.

## 4. Key Formulas to Explain

### STFT
$$
X(m, k) = \sum_{n=0}^{N-1} x[n + mH] w[n] e^{-j2\pi kn/N}
$$

### dB Spectrogram
$$
S_{dB}(m,k) = 20\log_{10}(|X(m,k)| + \epsilon)
$$

### Fingerprint Hash
$$
h = H(f_1, f_2, \Delta t), \; \Delta t = t_2 - t_1
$$

### Offset Vote
$$
\Delta = t_{db} - t_q
$$
Most likely song has the strongest vote cluster at one offset.

## 5. End-to-End Process (What to Say)
1. Load and resample audio.
2. Compute STFT and convert to log spectrogram.
3. Detect local spectral peaks (constellation map).
4. Pair anchor-target peaks and hash tuples.
5. Store hashes in inverted index.
6. Query hashes collide with database hashes.
7. Use offset voting to find best aligned track.

## 6. Why It Is Robust
- Resistant to moderate noise and compression.
- Works on short clips (few seconds).
- Efficient lookup due to hash indexing.

## 7. Parameters You Can Defend in Viva
- `n_fft`: frequency resolution vs speed.
- `hop_length`: time resolution vs speed.
- `amp_min_db`: strictness of peak selection.
- `fan_value`: number of pairings per anchor peak.
- `max_time_delta`: temporal pairing window.

## 8. Evaluation Script (What It Measures)
The evaluation script:
- Builds an index from dataset tracks.
- Samples random clips from indexed songs.
- Measures Top-1 and Top-K retrieval accuracy.
- Saves detailed per-query results in JSON.

## 9. Typical Viva Questions and Short Answers

Q1. Why not compare raw waveform directly?
A1. Raw waveform is too sensitive to time shifts, noise, and compression. Fingerprint landmarks are more stable and efficient.

Q2. Why use peak pairs instead of single peaks?
A2. Pair relationships encode both frequency and relative time, making matches more discriminative and robust.

Q3. What does offset voting solve?
A3. It aligns query and database timelines. Correct song produces many collisions at one consistent offset.

Q4. What are current limitations?
A4. No explicit tempo or pitch shift invariance; index size grows with data; basic peak thresholding.

Q5. How can this be improved?
A5. Adaptive peak thresholds, compressed index storage, and robustness testing under augmentations.

## 10. Demo Flow for Presentation (2-3 minutes)
1. Open Streamlit app and show formulas tab.
2. Build index on a small subset (fast demo).
3. Upload query clip and run identification.
4. Show spectrogram peaks and Top-K results.
5. Show evaluation report with Top-1/Top-K metrics.
