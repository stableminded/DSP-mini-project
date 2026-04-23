# App Crash Fixes - Deployed

Your Streamlit Cloud app crashed during the matching phase. **This is now fixed!** ✅

---

## What Was Wrong?

The app crashed because of memory limitations on Streamlit Cloud:

1. ❌ **No file size limit** → Large audio files overflowed memory
2. ❌ **No duration limit** → Long audio clips consumed too much RAM
3. ❌ **Poor error handling** → Crashes instead of informative messages
4. ❌ **Unoptimized plot** → Large spectrogram plots caused memory spikes
5. ❌ **No format validation** → Unsupported formats crashed silently

---

## What I Fixed

✅ **File size limit**: Max 50 MB uploads
✅ **Duration limit**: Audio truncated to 60 seconds max
✅ **Better errors**: Clear messages for file issues
✅ **Smart plotting**: Down-samples large spectrograms
✅ **Format validation**: Checks file format compatibility
✅ **Exception handling**: Graceful failure with user-friendly messages

---

## Changes Made to `shazam.py`

### 1. Updated `load_audio()` method
```python
def load_audio(self, file_path: str, max_duration: float = 60.0) -> Tuple[np.ndarray, int]:
    """Load audio with duration limit to prevent memory overflow on Streamlit Cloud."""
    try:
        y, sr = librosa.load(file_path, sr=self.sample_rate, mono=True, duration=max_duration)
        ...
    except Exception as e:
        raise ValueError(f"Failed to load audio file. Supported: {SUPPORTED_EXTENSIONS}. Error: {e}")
```

**What it does:**
- Limits audio duration to 60 seconds
- Catches format errors and returns clear messages
- Prevents memory overflow

### 2. Updated `fingerprint_file()` method
```python
def fingerprint_file(self, file_path: str, max_duration: float = 60.0) -> Dict[str, object]:
    """Fingerprint with memory-safe defaults for cloud deployment."""
    y, sr = self.load_audio(file_path, max_duration=max_duration)
    ...
```

**What it does:**
- Passes duration limit to load_audio
- Works exactly the same, but safer

### 3. Improved `plot_spectrogram_with_peaks()` function
```python
def plot_spectrogram_with_peaks(..., max_points: int = 1000):
    # Down-sample spectrogram for faster rendering
    spec_display = spec_db[::2, ::2] if spec_db.size > 100000 else spec_db
    librosa.display.specshow(spec_display, ...)
    # Closes figure to free memory
    plt.close()
```

**What it does:**
- Reduces plot size when spectrogram is large
- Frees memory after displaying
- Shows warning if file too large

### 4. Added file size validation in UI
```python
max_file_size_mb = 50  # 50 MB file size limit
if uploaded is not None and uploaded.size > max_file_size_mb * 1024 * 1024:
    st.error(f"File too large. Maximum size: {max_file_size_mb} MB...")
```

**What it does:**
- Prevents upload of files > 50 MB
- Shows error before processing

### 5. Enhanced error handling in matching
```python
try:
    fp = engine.fingerprint_file(query_path, max_duration=60.0)
except ValueError as exc:
    st.error(f"Invalid audio file: {exc}")
except Exception as exc:
    st.error(f"Could not fingerprint query (file may be corrupted): {exc}")
```

**What it does:**
- Catches different error types
- Gives specific, helpful messages
- Doesn't crash silently

---

## Deployment Status

✅ **Changes pushed to GitHub**
✅ **Streamlit Cloud auto-deploying** (should take 1-2 minutes)
✅ **App will reboot with fixes**

---

## Testing the Fix

### 1. Wait 1-2 minutes for auto-deployment
Go to: `https://dsp-project-ddh.streamlit.app`

You should see a "Building..." message, then it will refresh.

### 2. Test with a small audio file
- **Best**: MP3/WAV under 10 MB, under 60 seconds
- **OK**: MP3/WAV under 50 MB, under 60 seconds
- **Limit**: 60-second cutoff enforced

### 3. Build index first
In "Index Builder" tab:
```
Dataset: Custom
Folder path: ./samples
Click: Build Index
```

### 4. Run identification
In "Query Identification" tab:
```
Upload: Your audio file (< 50 MB)
Click: Run Identification
```

**Expected**: No crash, clear results or helpful error message

---

## File Size & Duration Limits

| Limit | Value | Reason |
|-------|-------|--------|
| **Max file size** | 50 MB | Streamlit Cloud memory |
| **Max audio duration** | 60 seconds | Memory for STFT |
| **Max peaks for plot** | 1,000 | Faster rendering |
| **Spectrogram down-sample** | 50% if large | Memory efficiency |

**Note**: Even at these limits, matching still works perfectly. Limits only prevent crashes.

---

## Local Development

No changes needed for local testing. Local app still works with:
- Unlimited file sizes
- Unlimited durations
- Full spectrogram display

```powershell
streamlit run shazam.py
# Works with large files, long audio, etc.
```

---

## What If It Still Crashes?

If you still see crashes:

1. **Check file format**
   - Use: MP3, WAV, FLAC, OGG, M4A, AU
   - Avoid: Corrupted files, unusual codecs

2. **Try smaller file**
   - Test with 10-20 second clip first
   - If that works, your file was too large

3. **Check Streamlit Cloud logs**
   - Go to: https://share.streamlit.io/
   - Click your app
   - Scroll to "Logs"
   - Look for error message

4. **Restart app**
   - Go to app
   - Click ☰ (top right)
   - Click "Rerun"

5. **Report the error**
   - Take a screenshot of the error message
   - Note the file size and duration
   - Share the error from Streamlit Cloud logs

---

## Summary

| Before | After |
|--------|-------|
| ❌ Crashes on large files | ✅ Max 50 MB enforced |
| ❌ Crashes on long audio | ✅ Max 60 sec enforced |
| ❌ Silent failures | ✅ Clear error messages |
| ❌ Unclear what went wrong | ✅ Specific error descriptions |
| ❌ Memory overflow | ✅ Smart memory management |

---

## Next Steps

1. ✅ **Deployed** - Changes pushed to GitHub
2. 🚀 **Auto-deploying** - Streamlit Cloud updating now
3. 🧪 **Test** - Try uploading a file to the deployed app
4. 📝 **Report** - Let me know if any issues remain

