from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import maximum_filter

try:
	import streamlit as st
except ModuleNotFoundError:
	st = None


SUPPORTED_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".au")


@dataclass
class MatchCandidate:
	track_id: str
	votes: int
	best_offset: int
	confidence: float


class AudioFingerprintEngine:
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
		self.sample_rate = sample_rate
		self.n_fft = n_fft
		self.hop_length = hop_length
		self.peak_neighborhood_size = peak_neighborhood_size
		self.amp_min_db = amp_min_db
		self.fan_value = fan_value
		self.min_time_delta = min_time_delta
		self.max_time_delta = max_time_delta

		self.hash_db: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
		self.track_meta: Dict[str, Dict[str, float]] = {}

	def load_audio(self, file_path: str, max_duration: float = 60.0) -> Tuple[np.ndarray, int]:
		"""Load audio with duration limit to prevent memory overflow on Streamlit Cloud."""
		try:
			y, sr = librosa.load(file_path, sr=self.sample_rate, mono=True, duration=max_duration)
			duration_actual = len(y) / sr
			if duration_actual > max_duration:
				y = y[: int(max_duration * sr)]
			return y, sr
		except Exception as e:
			raise ValueError(f"Failed to load audio file. Supported: {SUPPORTED_EXTENSIONS}. Error: {e}") from e

	def spectrogram_db(self, y: np.ndarray) -> np.ndarray:
		stft = librosa.stft(y, n_fft=self.n_fft, hop_length=self.hop_length)
		magnitude = np.abs(stft)
		return librosa.amplitude_to_db(magnitude, ref=np.max)

	def find_peaks(self, spec_db: np.ndarray) -> List[Tuple[int, int, float]]:
		neighborhood = (self.peak_neighborhood_size, self.peak_neighborhood_size)
		local_max = maximum_filter(spec_db, size=neighborhood) == spec_db
		amp_mask = spec_db >= self.amp_min_db
		mask = local_max & amp_mask

		freq_idx, time_idx = np.where(mask)
		peaks = [
			(int(t), int(f), float(spec_db[f, t]))
			for f, t in zip(freq_idx, time_idx)
		]
		peaks.sort(key=lambda x: x[0])
		return peaks

	def generate_hashes(self, peaks: List[Tuple[int, int, float]]) -> List[Tuple[str, int]]:
		hashes: List[Tuple[str, int]] = []
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

	def fingerprint_file(self, file_path: str, max_duration: float = 60.0) -> Dict[str, object]:
		"""Fingerprint with memory-safe defaults for cloud deployment."""
		y, sr = self.load_audio(file_path, max_duration=max_duration)
		spec_db = self.spectrogram_db(y)
		peaks = self.find_peaks(spec_db)
		hashes = self.generate_hashes(peaks)
		duration = len(y) / float(sr)
		return {
			"hashes": hashes,
			"duration": duration,
			"num_peaks": len(peaks),
			"spec_db": spec_db,
			"peaks": peaks,
		}

	def add_track(self, track_id: str, fingerprint: Dict[str, object]) -> None:
		hashes = fingerprint["hashes"]
		for h, anchor_time in hashes:
			self.hash_db[h].append((track_id, int(anchor_time)))

		self.track_meta[track_id] = {
			"duration": float(fingerprint["duration"]),
			"num_peaks": float(fingerprint["num_peaks"]),
			"num_hashes": float(len(hashes)),
		}

	def build_index(
		self,
		dataset_root: str,
		max_files: Optional[int] = None,
		progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
	) -> Dict[str, object]:
		root = Path(dataset_root)
		if not root.exists():
			raise FileNotFoundError(f"Dataset folder does not exist: {dataset_root}")

		files = [
			p
			for p in root.rglob("*")
			if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
		]
		files.sort()

		if max_files is not None and max_files > 0:
			files = files[:max_files]

		total = len(files)
		if total == 0:
			return {
				"indexed": 0,
				"failed": [],
				"total_files": 0,
				"total_hashes": 0,
				"total_tracks": len(self.track_meta),
			}

		failed: List[Tuple[str, str]] = []
		for i, path in enumerate(files, start=1):
			rel_id = str(path.relative_to(root)).replace("\\", "/")
			try:
				fp = self.fingerprint_file(str(path))
				self.add_track(rel_id, fp)
				status = "indexed"
			except Exception as exc:  # noqa: BLE001
				failed.append((rel_id, str(exc)))
				status = "failed"

			if progress_callback is not None:
				progress_callback(i, total, rel_id, status)

		total_hashes = sum(len(v) for v in self.hash_db.values())
		return {
			"indexed": total - len(failed),
			"failed": failed,
			"total_files": total,
			"total_hashes": total_hashes,
			"total_tracks": len(self.track_meta),
		}

	def match_fingerprint(
		self,
		query_hashes: List[Tuple[str, int]],
		top_k: int = 5,
	) -> List[MatchCandidate]:
		if not query_hashes:
			return []

		offset_votes: Dict[str, Counter] = defaultdict(Counter)
		for h, q_time in query_hashes:
			if h not in self.hash_db:
				continue
			for track_id, db_time in self.hash_db[h]:
				offset = db_time - q_time
				offset_votes[track_id][offset] += 1

		candidates: List[MatchCandidate] = []
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

	def export_index(self, output_file: str) -> None:
		serializable = {
			"params": {
				"sample_rate": self.sample_rate,
				"n_fft": self.n_fft,
				"hop_length": self.hop_length,
				"peak_neighborhood_size": self.peak_neighborhood_size,
				"amp_min_db": self.amp_min_db,
				"fan_value": self.fan_value,
				"min_time_delta": self.min_time_delta,
				"max_time_delta": self.max_time_delta,
			},
			"track_meta": self.track_meta,
			"hash_db": {k: v for k, v in self.hash_db.items()},
		}
		with open(output_file, "w", encoding="utf-8") as f:
			json.dump(serializable, f)

	def import_index(self, index_file: str) -> None:
		with open(index_file, "r", encoding="utf-8") as f:
			data = json.load(f)

		self.track_meta = data.get("track_meta", {})
		self.hash_db = defaultdict(list, {k: [tuple(x) for x in v] for k, v in data["hash_db"].items()})


def plot_spectrogram_with_peaks(spec_db: np.ndarray, peaks: List[Tuple[int, int, float]], max_points: int = 1000):
	"""Plot spectrogram with memory optimization for cloud deployment."""
	try:
		fig, ax = plt.subplots(figsize=(12, 5))
		# Down-sample spectrogram for faster rendering on cloud
		spec_display = spec_db[::2, ::2] if spec_db.size > 100000 else spec_db
		librosa.display.specshow(spec_display, x_axis="time", y_axis="log", cmap="magma", ax=ax)
		ax.set_title("Log-Magnitude Spectrogram with Constellation Peaks")
		ax.set_xlabel("Time (frames)")
		ax.set_ylabel("Frequency (Hz)")

		if peaks:
			sampled = peaks[:min(max_points, len(peaks))]
			xs = [p[0] for p in sampled]
			ys = [p[1] for p in sampled]
			ax.scatter(xs, ys, s=5, c="cyan", alpha=0.6, label=f"Peaks ({len(sampled)})")
			ax.legend(loc="upper right")

		if len(peaks) > max_points:
			ax.text(0.02, 0.98, f"Showing {max_points}/{len(peaks)} peaks", 
					transform=ax.transAxes, verticalalignment="top",
					bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

		plt.tight_layout()
		plt.close()  # Close figure to free memory
		return fig
	except Exception as e:
		st.warning(f"Could not plot spectrogram: {e}. File may be too large.")
		return None


def get_engine_from_ui() -> AudioFingerprintEngine:
	st.sidebar.header("Fingerprint Parameters")
	sample_rate = st.sidebar.selectbox("Sample rate", [16000, 22050, 44100], index=1)
	n_fft = st.sidebar.selectbox("N FFT", [1024, 2048, 4096], index=2)
	hop_length = st.sidebar.selectbox("Hop length", [256, 512, 1024], index=1)
	peak_neighborhood_size = st.sidebar.slider("Peak neighborhood", 5, 40, 20)
	amp_min_db = st.sidebar.slider("Min peak amplitude (dB)", -80.0, -5.0, -40.0, 1.0)
	fan_value = st.sidebar.slider("Fan value", 3, 30, 15)
	min_time_delta = st.sidebar.slider("Min delta t", 1, 10, 1)
	max_time_delta = st.sidebar.slider("Max delta t", 20, 400, 200)

	params = {
		"sample_rate": sample_rate,
		"n_fft": n_fft,
		"hop_length": hop_length,
		"peak_neighborhood_size": peak_neighborhood_size,
		"amp_min_db": amp_min_db,
		"fan_value": fan_value,
		"min_time_delta": min_time_delta,
		"max_time_delta": max_time_delta,
	}

	if "engine_params" not in st.session_state or st.session_state.engine_params != params:
		st.session_state.engine = AudioFingerprintEngine(**params)
		st.session_state.engine_params = params

	return st.session_state.engine


def formulas_section() -> None:
	st.subheader("Core Formulas Used")
	st.info(
		"DSP implementation note: this project does not import any Shazam fingerprinting library. "
		"Core logic is implemented in code using STFT, constellation peak detection, peak-pair hashing, and offset voting."
	)
	st.markdown(
		r"""
1. Short-Time Fourier Transform (STFT):
$$
X(m, k) = \sum_{n=0}^{N-1} x[n + mH] w[n] e^{-j2\pi kn/N}
$$

2. Magnitude Spectrogram (dB scale):
$$
S_{dB}(m,k) = 20\log_{10}(|X(m,k)| + \epsilon)
$$

3. Fingerprint Hash from peak pairs:
$$
h = H(f_1, f_2, \Delta t), \quad \Delta t = t_2 - t_1
$$

4. Voting for alignment offset during matching:
$$
\Delta = t_{db} - t_q
$$
The best match maximizes votes for one consistent offset.
"""
	)


def algorithm_section() -> None:
	st.subheader("Processing Pipeline")
	st.markdown(
		"**Implementation scope:** STFT, local-max peak detection, landmark pairing, hash generation, "
		"inverted index construction, and offset-voting matching are all implemented in `AudioFingerprintEngine`."
	)
	st.markdown(
		"""
1. Load and resample audio to a fixed sampling rate.
2. Compute STFT and convert to log-magnitude spectrogram.
3. Detect local maxima to build a constellation map.
4. Pair peaks in a local time window and hash each pair.
5. Store hashes in an inverted index: hash -> (track_id, anchor_time).
6. For a query, generate query hashes and vote over time offsets.
7. Return the track with the strongest, most consistent vote cluster.
"""
	)


def build_index_ui(engine: AudioFingerprintEngine) -> None:
	st.subheader("Build Fingerprint Index")
	dataset_choice = st.selectbox("Dataset", ["Custom Path", "GTZAN", "FMA"])

	default_path = ""
	if dataset_choice == "GTZAN":
		default_path = "./Data/genres_original"
	elif dataset_choice == "FMA":
		default_path = "./Data/fma_small"

	dataset_path = st.text_input("Dataset folder path", value=default_path)
	max_files = st.number_input("Max files to index (0 = all)", min_value=0, value=100)

	col1, col2 = st.columns(2)
	build_btn = col1.button("Build / Rebuild Index", type="primary")
	clear_btn = col2.button("Clear Index")

	if clear_btn:
		st.session_state.engine = AudioFingerprintEngine(**st.session_state.engine_params)
		st.success("Index cleared.")
		return

	if build_btn:
		if not dataset_path.strip():
			st.error("Please provide a valid dataset path.")
			return

		progress_bar = st.progress(0)
		status_text = st.empty()

		def cb(current: int, total: int, rel_id: str, status: str) -> None:
			frac = current / total if total > 0 else 0.0
			progress_bar.progress(min(max(frac, 0.0), 1.0))
			status_text.write(f"[{current}/{total}] {status.upper()}: {rel_id}")

		try:
			result = engine.build_index(
				dataset_root=dataset_path,
				max_files=None if max_files == 0 else int(max_files),
				progress_callback=cb,
			)
		except Exception as exc:  # noqa: BLE001
			st.error(f"Indexing failed: {exc}")
			return

		st.success("Indexing completed.")
		st.json(result)

		if result["failed"]:
			st.warning("Some files could not be indexed.")
			st.dataframe(
				[{"file": f[0], "reason": f[1]} for f in result["failed"]],
				use_container_width=True,
			)

	st.markdown("### Index Persistence")
	index_file = st.text_input("Index JSON file", value="fingerprint_index.json")
	save_col, load_col = st.columns(2)

	if save_col.button("Save Index"):
		try:
			engine.export_index(index_file)
			st.success(f"Index saved to {index_file}")
		except Exception as exc:  # noqa: BLE001
			st.error(f"Could not save index: {exc}")

	if load_col.button("Load Index"):
		try:
			engine.import_index(index_file)
			st.success(f"Index loaded from {index_file}")
		except Exception as exc:  # noqa: BLE001
			st.error(f"Could not load index: {exc}")

	st.info(f"Tracks in memory: {len(engine.track_meta)} | Unique hash keys: {len(engine.hash_db)}")


def identify_query_ui(engine: AudioFingerprintEngine) -> None:
	st.subheader("Identify Query Audio")
	uploaded = st.file_uploader("Upload an audio clip", type=[e[1:] for e in SUPPORTED_EXTENSIONS])
	top_k = st.slider("Top K matches", 1, 10, 5)

	# File size check (Streamlit Cloud limit)
	max_file_size_mb = 50  # 50 MB file size limit
	if uploaded is not None and uploaded.size > max_file_size_mb * 1024 * 1024:
		st.error(f"File too large. Maximum size: {max_file_size_mb} MB. Please upload a smaller file.")
		uploaded = None

	if st.button("Run Identification", type="primary"):
		if uploaded is None:
			st.error("Please upload an audio file (max 50 MB).")
			return
		if len(engine.track_meta) == 0:
			st.error("Index is empty. Build or load an index first.")
			return

		suffix = Path(uploaded.name).suffix or ".wav"
		with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
			temp_file.write(uploaded.getvalue())
			query_path = temp_file.name

		st.markdown("### Processing Trace")
		st.write("Step 1: Loading and resampling query audio (max 60 seconds)")
		try:
			# Limit to 60 seconds to prevent memory overflow
			fp = engine.fingerprint_file(query_path, max_duration=60.0)
		except ValueError as exc:
			st.error(f"Invalid audio file: {exc}")
			return
		except Exception as exc:  # noqa: BLE001
			st.error(f"Could not fingerprint query (file may be corrupted): {exc}")
			return
		finally:
			try:
				os.remove(query_path)
			except OSError:
				pass

		st.write("Step 2: Spectrogram computed and converted to dB scale")
		st.write("Step 3: Constellation map peaks extracted")
		st.write("Step 4: Peak pairs converted to hashes")

		st.metric("Query duration (s)", f"{fp['duration']:.2f}")
		st.metric("Detected peaks", int(fp["num_peaks"]))
		st.metric("Generated hashes", len(fp["hashes"]))

		with st.expander("Show constellation samples and hash samples", expanded=False):
			peak_preview = [
				{"time_bin": p[0], "freq_bin": p[1], "amplitude_db": round(p[2], 2)}
				for p in fp["peaks"][:12]
			]
			hash_preview = [
				{"hash": h, "anchor_time_bin": t}
				for h, t in fp["hashes"][:12]
			]
			st.write("Peak preview from constellation map")
			st.dataframe(peak_preview, use_container_width=True)
			st.write("Hash preview generated from peak pairs (f1, f2, delta_t)")
			st.dataframe(hash_preview, use_container_width=True)

		with st.expander("Show query spectrogram and peaks", expanded=True):
			fig = plot_spectrogram_with_peaks(fp["spec_db"], fp["peaks"])
			if fig is not None:
				st.pyplot(fig)
			else:
				st.info("Spectrogram too large to display. Matching still works.")

		st.write("Step 5: Matching by hash collisions and offset voting")
		try:
			candidates = engine.match_fingerprint(fp["hashes"], top_k=top_k)
		except Exception as exc:  # noqa: BLE001
			st.error(f"Matching failed: {exc}")
			return

		if not candidates:
			st.warning("No match found. Try tuning parameters or indexing more files.")
			return

		best = candidates[0]
		st.success(f"Best match: {best.track_id}")
		st.write(
			f"Votes: {best.votes} | Best offset: {best.best_offset} frames | Confidence: {best.confidence:.4f}"
		)

		st.markdown("### Top Matches")
		st.dataframe(
			[
				{
					"track_id": c.track_id,
					"votes": c.votes,
					"best_offset": c.best_offset,
					"confidence": c.confidence,
				}
				for c in candidates
			],
			use_container_width=True,
		)


def main() -> None:
	if st is None:
		raise ModuleNotFoundError(
			"Streamlit is required to run the UI. Install dependencies from requirements.txt."
		)

	st.set_page_config(page_title="Shazam-Style Audio Fingerprinting", layout="wide")
	st.title("Shazam Algorithm Demo (Audio Fingerprinting)")
	st.caption("Academic mini-project with GTZAN/FMA dataset support, formula display, and process tracing.")
	st.markdown(
		"This app demonstrates a DSP-first implementation with spectrogram constellation hashing; "
		"no external Shazam fingerprinting SDK is used."
	)

	engine = get_engine_from_ui()

	tab1, tab2, tab3 = st.tabs(["Index Builder", "Query Identification", "Algorithm + Formulas"])

	with tab1:
		build_index_ui(engine)

	with tab2:
		identify_query_ui(engine)

	with tab3:
		algorithm_section()
		formulas_section()


if __name__ == "__main__":
	main()
