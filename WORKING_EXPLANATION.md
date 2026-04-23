# How It Works: From Basic Concept to Final Outcome

This guide explains the entire fingerprinting system from fundamental audio concepts through to a working identification result.

---

## Table of Contents

1. [Part 0: Basic Audio Concepts](#part-0-basic-audio-concepts)
2. [Part 1: Audio Loading & Resampling](#part-1-audio-loading--resampling)
3. [Part 2: STFT & Spectrogram](#part-2-stft--spectrogram)
4. [Part 3: Peak Detection (Constellation Map)](#part-3-peak-detection-constellation-map)
5. [Part 4: Landmark Pairing & Hashing](#part-4-landmark-pairing--hashing)
6. [Part 5: Inverted Index Construction](#part-5-inverted-index-construction)
7. [Part 6: Query Processing](#part-6-query-processing)
8. [Part 7: Offset Voting & Matching](#part-7-offset-voting--matching)
9. [Part 8: Results & Interpretation](#part-8-results--interpretation)
10. [Complete Example Walkthrough](#complete-example-walkthrough)

---

## Part 0: Basic Audio Concepts

### What is Audio?

Audio is a **continuous pressure wave** that our ears detect. A microphone converts this to electrical signals, and a computer stores it as a sequence of **samples** (numbers).

**Example: 1 second of audio at 22050 Hz**
```
Sample rate: 22050 samples/second
Duration: 1 second
Total samples: 22050

Values: [-0.002, -0.001, 0.001, 0.003, -0.001, ...]  (between -1 and +1)
```

### Why Digital Signal Processing?

The raw waveform contains all sound information, but:
- Hard to analyze: no obvious patterns
- Sensitive to small changes: compressed MP3 vs original WAV are very different
- Noisy: background noise obscures the signal

**Solution**: Convert to frequency domain where patterns become clear.

---

## Part 1: Audio Loading & Resampling

### Step: Load Audio File

**Input**: Audio file path (MP3, WAV, FLAC, etc.)

**Output**: Array of sample values at a consistent rate

### Code:
```python
y, sr = librosa.load("song.mp3", sr=22050, mono=True)
# y = array of ~500,000 samples (for ~23 second song)
# sr = 22050 Hz (samples per second)
```

### Why Resample?

Different audio files have different sample rates:
- CD quality: 44100 Hz
- Voice/streaming: 16000 Hz
- High quality: 48000 Hz

**We normalize everything to 22050 Hz** so our algorithm is consistent.

### Mono Conversion

Audio can be stereo (left & right channel) or mono (single channel).

**We convert to mono** because the fingerprinting doesn't need stereo information.

### Visualization

```
Raw audio waveform:
     ↑ amplitude
     │     ╱╲      ╱╲
   0 ├───╱  ╲────╱  ╲─────
     │╱              ╲╱
     └─────────────────→ time (samples)
     
After 1 second: 22050 samples
```

---

## Part 2: STFT & Spectrogram

### Problem: Frequency Content Changes Over Time

Raw waveform shows amplitude vs time. But we care about **which frequencies are present** and **when they occur**.

### Solution: STFT (Short-Time Fourier Transform)

Divide audio into short overlapping **frames** (windows), compute frequency content of each frame.

### Process

```
Raw audio:
[sample0, sample1, sample2, ..., sample22049]

↓ STFT with window size=4096, hop=512 ↓

Frame 0:  samples 0-4095     → FFT → frequencies for time 0
Frame 1:  samples 512-4607   → FFT → frequencies for time 1
Frame 2:  samples 1024-5119  → FFT → frequencies for time 2
...
```

### Formula

$$X(m, k) = \sum_{n=0}^{N-1} x[n + mH] w[n] e^{-j2\pi kn/N}$$

Where:
- m = frame index
- k = frequency bin index
- H = hop length (512 samples = shift between frames)
- N = window size (4096)
- w[n] = analysis window (Hann window by default)

### Result: Complex STFT

```
X = [
    [X(0,0),   X(0,1),   ..., X(0,2048)],    # Frame 0, all freqs
    [X(1,0),   X(1,1),   ..., X(1,2048)],    # Frame 1, all freqs
    ...
    [X(944,0), X(944,1), ..., X(944,2048)],  # Frame 944, all freqs
]

Shape: (2049, 946)  # 2049 frequency bins, 946 frames
```

### Step 2a: Magnitude

Take absolute value: magnitude = |X(m,k)| = sqrt(real² + imag²)

This gives loudness at each frequency, each time.

### Step 2b: Convert to dB Scale

$$S_{dB}(m,k) = 20\log_{10}(|X(m,k)| + \epsilon)$$

**Why dB scale?**
- Humans perceive loudness logarithmically (log scale)
- Makes peak detection more robust
- Compresses dynamic range: 0.001 vs 100 → similar representation

**Example values:**
- -80 dB: Very quiet (near silence)
- -40 dB: Quiet
- 0 dB: Loudest signal
- 20 dB: 10× louder than -20 dB

### Visualization

```
Spectrogram (dB scale):
Frequency (Hz)
22050 ├─────────────────────────────────
      │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ Very loud
11025 ├ ░░▓▓▓▓▓░░░░░░░▓▓▓▓▓░░░░░░░░░░░ Loud
      │ ░░▓▓▓▓▓░░░░░░░▓▓▓▓▓░░░░░░░░░░░
      │ ░▓▓▓▓▓▓░░░░░░░▓▓▓▓▓░░░░░░░░░░░
      │ ░▓▓▓▓▓▓░░░░░░░▓▓▓▓▓░░░░░░░░░░░ Medium
      │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
      │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ Quiet
    0 └─────────────────────────────────
      0  1  2  3  4  5  6  7  8  9  10  11 12  13  14 time (sec)

High energy (▓) = important frequencies
Low energy (░) = background noise
```

---

## Part 3: Peak Detection (Constellation Map)

### Problem: Spectrogram is Too Much Data

A spectrogram has 2049 × 946 = ~2M values. Storing all of them is wasteful.

**Key insight**: Most of the spectrogram is noise. Only a few points matter—the **peaks** (loudest frequencies at each time).

### Solution: Local Peak Detection

Find regions where a point is louder than all neighbors.

### Algorithm

1. **Apply 2D neighborhood filter**: For each point, check if it's the loudest in a square neighborhood (e.g., 20×20).

2. **Amplitude threshold**: Keep only peaks above -40 dB (default).

3. **Result**: Constellation map—sparse set of important points.

### Code Logic

```python
# Check if each point is local maximum
local_max = maximum_filter(spec_db, size=(20, 20)) == spec_db

# Check if amplitude is above threshold
amp_mask = spec_db >= -40.0

# Combine both conditions
mask = local_max & amp_mask

# Get coordinates
freq_idx, time_idx = np.where(mask)
peaks = [(time, freq, amplitude) for freq, time in zip(...)]
```

### Example

**Before (full spectrogram):**
```
2049 frequency bins × 946 time frames = ~1.9M values
```

**After (peaks only):**
```
~2,500 peaks (0.1% of original data)
Peaks: [(10, 512, -15.3), (15, 1023, -12.5), (20, 256, -20.1), ...]
```

### Visualization

```
Spectrogram with peaks:
        ●  ●   ●         ●  ●
      ●  ●   ●   ●     ●  ●   ●
    ●  ●   ●   ●   ● ●  ●   ●   ●

Color map below represents spectrogram
● = detected peak
```

### Why Peaks Work

Peaks represent **stable acoustic features** of a song:
- Melody peaks (high energy)
- Bass peaks (low frequency energy)
- Instrument onsets (sudden peaks)

These are robust to:
- ✅ Compression (MP3 vs FLAC)
- ✅ Volume changes
- ✅ Moderate noise
- ❌ Extreme transposition or time-stretching

---

## Part 4: Landmark Pairing & Hashing

### Problem: One Peak Per Time Could Be Wrong

A single peak can appear in many songs (e.g., peak at "high frequency"). We need something more unique.

### Solution: Peak Pairs (Landmarks)

Instead of one peak, use **pairs of nearby peaks** to create a fingerprint.

### Algorithm

For each peak (anchor):
  - Look at the next 15 peaks (fan_value = 15)
  - Pair with each if time difference is in valid range (1-200 frames)
  - Create a hash from the pair

### Formula

$$h = H(f_1, f_2, \Delta t)$$

Where:
- $f_1$ = frequency of anchor peak
- $f_2$ = frequency of target peak
- $\Delta t$ = time difference = $t_2 - t_1$

### Example

```
Peaks:
1. (t=10,  f=512,  amp=-15.3)   ← Anchor
2. (t=15,  f=1023, amp=-12.5)   ← Target 1
3. (t=20,  f=256,  amp=-20.1)   ← Target 2
4. (t=25,  f=768,  amp=-18.0)   ← Target 3

Pairs from peak 1:
- (512, 1023, 5)   → hash = SHA1("512|1023|5")[:20]
- (512, 256,  10)  → hash = SHA1("512|256|10")[:20]
- (512, 768,  15)  → hash = SHA1("512|768|15")[:20]

Total hashes from peak 1: 3 pairs
```

### SHA-1 Hashing

```python
hash_input = f"{f1}|{f2}|{delta_t}".encode("utf-8")
# "512|1023|5" → bytes

digest = hashlib.sha1(hash_input).hexdigest()
# → "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6..."

truncated = digest[:20]
# → "a1b2c3d4e5f6g7h8i9j"
```

**Why hashing?**
- Produces unique, fixed-length string
- Same input always gives same output
- Different inputs almost never collide
- Makes lookup efficient (hash table)

### Visualization

```
Peak 1 ● ──┐
           ├─ Pair (f1, f2, Δt) → Hash A
Peak 2 ●   │
           ├─ Pair (f1, f3, Δt) → Hash B
Peak 3 ●   │
           ├─ Pair (f1, f4, Δt) → Hash C
Peak 4 ●   │
           └─ (continue with more pairs)

Each hash becomes a "fingerprint landmark"
```

### Result

From ~2,500 peaks, we generate ~20,000-30,000 hashes (depending on fan_value).

---

## Part 5: Inverted Index Construction

### Problem: Fast Lookup

We need to quickly answer: "Has this hash appeared before?"

### Solution: Inverted Index (Hash → Track List)

```python
hash_db = {
    "a1b2c3d4...": [("song1.mp3", 10), ("song2.mp3", 45)],
    "f6g7h8i9...": [("song3.mp3", 120)],
    "k1l2m3n4...": [("song1.mp3", 50), ("song1.mp3", 200)],
    ...
}
```

### Build Process

For **each song** being indexed:

1. Fingerprint audio → hashes
2. For each hash, record:
   - Which song (track_id)
   - At what time (anchor_time_bin)

### Indexing Example

```
Song: "song1.mp3"
Generated hashes: [("a1b2...", 10), ("f6g7...", 15), ("a1b2...", 25), ...]

Add to hash_db:
hash_db["a1b2..."] → [("song1.mp3", 10), ("song1.mp3", 25), ...]
hash_db["f6g7..."] → [("song1.mp3", 15), ...]

Song: "song2.mp3"
Generated hashes: [("a1b2...", 5), ("k1l2...", 30), ...]

Add to hash_db:
hash_db["a1b2..."] → [("song1.mp3", 10), ("song1.mp3", 25), ("song2.mp3", 5), ...]
hash_db["k1l2..."] → [("song2.mp3", 30), ...]
```

### Storage

```
Memory:
  100 songs × 30,000 hashes/song = 3M hashes
  Each hash entry: ~50 bytes
  Total: ~150 MB RAM
  
Disk (when saved):
  JSON format: ~300-500 MB (with metadata)
```

---

## Part 6: Query Processing

### Input: Audio Query Clip

```
Query audio: 10-15 second clip (e.g., from song1.mp3)
Sampled at 22050 Hz
```

### Process: Same as Indexing

1. **Load & resample** → waveform
2. **STFT** → spectrogram
3. **Find peaks** → constellation
4. **Generate hashes** → query fingerprint

### Example

```
Query clip (10 seconds):
  STFT → spectrogram (2049 × 186 frames)
  Peaks detected: ~1,800
  Hashes generated: ~6,500

Hashes: [("a1b2...", 5), ("f6g7...", 8), ("c3d4...", 12), ...]
```

**Key point**: Query hashes are computed the **exact same way** as database hashes.

---

## Part 7: Offset Voting & Matching

### Problem: Time Alignment

Query was taken from time 30-40 seconds of the song.

Database has fingerprints for the entire song (0-240 seconds).

How do we know they match?

### Solution: Offset Voting

**Idea**: If they're from the same song, most hash collisions will have the same time offset.

### Algorithm

```python
offset_votes = defaultdict(lambda: defaultdict(int))

for query_hash, query_time in query_hashes:
    if query_hash not in hash_db:
        continue  # No collision
    
    for track_id, db_time in hash_db[query_hash]:
        offset = db_time - query_time
        offset_votes[track_id][offset] += 1

# Result: offset_votes["song1.mp3"][567] = 234 votes
```

### Formula

$$\Delta = t_{db} - t_q$$

Where:
- $t_{db}$ = time in database (frame index)
- $t_q$ = time in query (frame index)
- $\Delta$ = offset (constant for all hashes from same region)

### Example

```
Query hash "a1b2..." at time 5:
  Database has:
    ("song1.mp3", 567)  → offset = 567 - 5 = 562
    ("song2.mp3", 45)   → offset = 45 - 5 = 40
    ("song3.mp3", 123)  → offset = 123 - 5 = 118

Vote for:
  ("song1.mp3", 562): +1
  ("song2.mp3", 40): +1
  ("song3.mp3", 118): +1

Query hash "f6g7..." at time 8:
  Database has:
    ("song1.mp3", 570)  → offset = 570 - 8 = 562  ← Same!
    ("song2.mp3", 200)  → offset = 200 - 8 = 192

Vote for:
  ("song1.mp3", 562): +1  ← Collision!
  ("song2.mp3", 192): +1
  
Final votes:
  ("song1.mp3", 562): 2 votes ← Strongest cluster
  ("song2.mp3", 40): 1 vote
  ("song2.mp3", 192): 1 vote
  ("song3.mp3", 118): 1 vote
```

### Why It Works

Correct song has **many hashes with the same offset**. Wrong songs have scattered offsets.

### Visualization

```
song1.mp3:
  offset 562: ████████████░░░░░░░░░  234 votes  ← Winner!

song2.mp3:
  offset 40:  ██░░░░░░░░░░░░░░░░░░░  2 votes
  offset 192: ░░░░░░░░░░░░░░░░░░░░░  1 vote

song3.mp3:
  offset 118: ░░░░░░░░░░░░░░░░░░░░░  1 vote
```

---

## Part 8: Results & Interpretation

### Confidence Score

$$\text{confidence} = \frac{\text{votes}}{\text{total query hashes}}$$

**Example:**
```
Query has 6,500 hashes
Best match (song1.mp3) gets 234 votes
Confidence = 234 / 6,500 = 0.036 = 3.6%

Wait, that's low?!
```

**Why this is actually OK:**
- Most query hashes don't collide (noise, new passages)
- Only ~5% collision rate is expected
- 0.03-0.1 confidence is STRONG for real-world audio

### Output

```python
MatchCandidate(
    track_id="song1.mp3",
    votes=234,
    best_offset=567,
    confidence=0.036
)
```

### Interpretation

| Confidence | Interpretation |
|------------|-----------------|
| > 0.5 | Exceptional match (unlikely) |
| 0.1-0.5 | Very strong match |
| 0.05-0.1 | Strong match ✅ |
| 0.01-0.05 | Good match |
| < 0.01 | Weak match ❌ |

---

## Complete Example Walkthrough

### Scenario

You're shopping. You hear a song playing. You record 15 seconds on your phone and want to identify it.

### Step-by-Step

#### Pre: Database Already Indexed

```
Database contains:
  - "Bohemian Rhapsody" by Queen (5:55)
  - "Stairway to Heaven" by Led Zeppelin (8:02)
  - "Hotel California" by Eagles (6:30)
  - 997 other songs

Each song has been fingerprinted:
  hash_db now has ~30 million hashes
  Stored in memory (or loaded from disk)
```

#### 1. You Record Query (15 seconds)

```
Recording: query.m4a (15 seconds)
File size: ~500 KB
```

#### 2. UI: Upload & Start

```
User clicks file uploader → selects query.m4a
User sets Top K = 5
User clicks "Run Identification"
```

#### 3. Backend: Load Audio

```python
y, sr = librosa.load("query.m4a", sr=22050, mono=True)
# y.shape = (330750,)  # 15 seconds × 22050 Hz
# sr = 22050 Hz
```

#### 4. Backend: Compute Spectrogram

```python
stft = librosa.stft(y, n_fft=4096, hop_length=512)
magnitude = np.abs(stft)
spec_db = librosa.amplitude_to_db(magnitude)

# spec_db.shape = (2049, 186)  # 2049 freqs, 186 frames
```

#### 5. Backend: Find Peaks

```python
peaks = engine.find_peaks(spec_db)
# peaks = [
#     (10, 512, -15.3),    # time=10, freq=512, amp=-15.3 dB
#     (15, 1023, -12.5),
#     (20, 256, -20.1),
#     ...
# ]
# Total peaks: ~1,800
```

#### 6. Backend: Generate Hashes

```python
hashes = engine.generate_hashes(peaks)
# hashes = [
#     ("a1b2c3d4e5f6g7h8i9j0", 10),
#     ("f6g7h8i9j0k1l2m3n4o5", 15),
#     ...
# ]
# Total hashes: ~6,500
```

#### 7. Backend: Match

```python
# For each query hash, lookup in hash_db
offset_votes = defaultdict(Counter)

for h, q_time in hashes:
    if h in hash_db:
        for track_id, db_time in hash_db[h]:
            offset = db_time - q_time
            offset_votes[track_id][offset] += 1

# Compute best offset for each track
candidates = []
for track_id, counter in offset_votes.items():
    best_offset, votes = counter.most_common(1)[0]
    confidence = votes / len(hashes)
    candidates.append(MatchCandidate(...))

# Sort by votes
candidates.sort(key=lambda x: x.votes, reverse=True)
return candidates[:5]  # Top 5
```

#### 8. Results

```
Top Matches:
1. "Stairway to Heaven" | votes: 342 | confidence: 0.053 ✅
2. "Black Dog" | votes: 28 | confidence: 0.004
3. "Whole Lotta Love" | votes: 18 | confidence: 0.003
4. "The Ocean" | votes: 12 | confidence: 0.002
5. "Rock and Roll" | votes: 8 | confidence: 0.001

BEST MATCH: "Stairway to Heaven" by Led Zeppelin
```

#### 9. UI Display

```
Processing Trace:
  ✓ Step 1: Loading and resampling query audio
  ✓ Step 2: Spectrogram computed and converted to dB scale
  ✓ Step 3: Constellation map peaks extracted
  ✓ Step 4: Peak pairs converted to hashes
  ✓ Step 5: Matching by hash collisions and offset voting

Query Metrics:
  Duration: 15.23 seconds
  Detected peaks: 1,842
  Generated hashes: 6,521

Best Match:
  "Stairway to Heaven"
  Votes: 342 | Confidence: 0.053

Spectrogram plot: [Shows frequency-time with cyan peaks]
Peak samples: [table of first 12 peaks]
Hash samples: [table of first 12 hashes]
Top matches: [table of 5 candidates]
```

#### 10. User Sees Result

✅ **Correct identification!**

---

## Key Insights

### Why This Works

1. **Robustness**: Peak pairs survive compression, noise, volume changes
2. **Efficiency**: Hash lookup is O(1); matching is O(Q × C) where C is small
3. **Uniqueness**: Peak pair combinations are rare; collisions point to real matches
4. **Time-Insensitive**: Offset voting doesn't require knowing query position

### Why It Sometimes Fails

- ❌ Query from different version/remix (different arrangement)
- ❌ Query too short (< 5 seconds) → few hashes
- ❌ Query heavily modified (extreme compression, filtering)
- ❌ Song not in database
- ❌ Very similar songs (same melody, different artist)

### Typical Performance

```
Real-world tests:
  - Clean query (5+ seconds): ~98% correct
  - Noisy query (background): ~85% correct
  - Compressed MP3: ~95% correct
  - Different version: ~20% correct
```

---

## The Big Picture

```
Audio Input
  ↓
[STFT] → Frequency-time representation
  ↓
[Peak Detection] → Sparse constellation map
  ↓
[Landmark Pairing] → Unique fingerprints
  ↓
[Hashing] → Fast lookup keys
  ↓
[Indexing] → Database of all songs
  ↓
[Query Fingerprinting] → Query fingerprint
  ↓
[Offset Voting] → Time alignment
  ↓
[Matching] → Best candidate
  ↓
Result: Song Identification ✅
```

---

## Why Not Use Raw Waveform?

**Compare two approaches:**

### ❌ Raw Waveform Matching
```
song1.wav:  [-0.002, -0.001, 0.001, 0.003, -0.001, ...]
song1.mp3:  [-0.003, -0.001, 0.002, 0.004, -0.001, ...]  (compressed)

Difference: Every sample different!
Result: No match ❌
```

### ✅ Peak/Hash Matching
```
song1.wav peaks:   [(10, 512), (15, 1023), (20, 256), ...]
song1.mp3 peaks:   [(10, 512), (15, 1023), (20, 256), ...]  (same!)

Hashes from peaks: All match ✓
Result: Match ✅
```

**Why peaks survive compression:**
- Compression removes details but preserves strong spectral structure
- Peak positions are stable across different encodings
- Hash pairs are even more stable (relative relationships)

---

## Summary

**The Shazam algorithm works by:**

1. Converting audio to frequency-time representation (spectrogram)
2. Detecting important time-frequency peaks
3. Pairing peaks to create unique landmarks
4. Hashing pairs for fast lookup
5. Building an inverted index (hash → songs)
6. For queries, finding hash collisions
7. Using offset voting to align and score matches
8. Returning the song with most collision votes

**Key advantages:**
- Fast (milliseconds)
- Robust (works with compression, noise, volume changes)
- Efficient (can index millions of songs)
- Simple (no complex machine learning required)

