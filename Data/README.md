# Data Folder - Collaborative Dataset Repository

This folder is for **collaborators to share audio datasets**.

## How to Contribute

### For Collaborators

1. **Clone the repository**
   ```bash
   git clone https://github.com/stableminded/DSP-mini-project.git
   cd DSP-mini-project
   ```

2. **Create a subfolder** with your dataset name (e.g., `mymusic`, `gtzan_subset`, `test_songs`)
   ```
   Data/
   ├── mymusic/
   │   ├── song1.mp3
   │   ├── song2.mp3
   │   └── ...
   ├── gtzan_subset/
   │   ├── blues_00000.au
   │   └── ...
   └── README.md (this file)
   ```

3. **Add audio files** (supported formats: MP3, WAV, FLAC, OGG, M4A, AU)

4. **Commit and push**
   ```bash
   git add Data/mymusic/
   git commit -m "Add mymusic dataset to Data folder"
   git push origin main
   ```

## Using Data Folder in the App

The app automatically detects all subfolders in `Data/`:

1. Open the app (local or deployed)
2. Go to **"Index Builder"** tab
3. **Dataset selection**: Choose "Data Folder"
4. **Folder path**: Select from dropdown list of available collaborator datasets
5. Click **"Build Index"**

## Recommended Folder Structure

```
Data/
├── gtzan_10_songs/          # GTZAN sample (10 songs)
│   ├── blues_00000.au
│   ├── classical_00000.au
│   └── ...
├── fma_sample/              # FMA sample (20 songs)
│   ├── track_0.mp3
│   ├── track_1.mp3
│   └── ...
├── custom_dataset/          # Your custom dataset
│   ├── song1.mp3
│   ├── song2.mp3
│   └── ...
└── README.md (this file)
```

## Guidelines

- **Folder naming**: Use descriptive names (e.g., `mymusic`, not `dataset1`)
- **File formats**: MP3, WAV, FLAC, OGG, M4A, AU (all supported)
- **File size**: Keep individual files < 20 MB for faster git operations
- **Total size**: Keep total Data/ folder < 500 MB (GitHub large file limits)
- **Licensing**: Only add files you have the right to use (public domain, Creative Commons, etc.)

## Large Files

If you have files larger than 20 MB:
- Consider using GitHub LFS (Large File Storage)
- Or compress the dataset
- Or document external download links

## Contributing New Datasets

Example: Adding a dataset from GTZAN

```bash
# Download subset
wget http://marsyasweb.appspot.com/download/blues_00000.au
wget http://marsyasweb.appspot.com/download/blues_00001.au
# ... more files

# Create folder
mkdir Data/gtzan_blues_sample

# Move files
mv blues_*.au Data/gtzan_blues_sample/

# Commit
git add Data/gtzan_blues_sample/
git commit -m "Add GTZAN blues sample (10 tracks)"
git push origin main
```

## App Integration

When collaborators push new datasets:
1. Other team members pull latest code: `git pull origin main`
2. Datasets appear automatically in the app's Data folder dropdown
3. No code changes needed!

---

**Note**: The `Data/` folder is shared across all branches. Always work on the `main` branch for datasets.
