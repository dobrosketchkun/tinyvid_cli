# tiny_suite

Four CLI tools for compressing stuff.

## Why?

I wanted local tools that do what [tinyvid.io](https://tinyvid.io) and [tinypng.com](https://tinypng.com) do without uploading files. And maybe add something to it myself, like for audio. That's it.

## Tools


### tinyvid_cli.py
Compress videos using FFmpeg with settings reverse-engineered from tinyvid.io.

**Requirements:**
- FFmpeg (installed on your system)
- `rich` (Python package)

**Usage:**
```bash
# Basic compression
python tinyvid_cli.py video.mp4

# Quality presets: high, medium (default), low, extreme
python tinyvid_cli.py video.mp4 -q high

# Scale to specific height (maintains aspect ratio)
python tinyvid_cli.py video.mp4 -s 720

# Custom output name
python tinyvid_cli.py video.mp4 -o compressed.mp4

# Batch process
python tinyvid_cli.py video1.mp4 video2.mp4 video3.mp4
```

### tinyjpg_cli.py
Compress JPEG images using mozjpeg and jpegtran.

**Requirements:**
- mozjpeg (optional, best compression) or jpegtran (lossless) or Pillow (fallback)

**Usage:**
```bash
# Basic compression (default: balanced preset, creates filename-min.jpg)
python tinyjpg_cli.py image.jpg

# Presets: high, balanced (default), maximum, lossless
python tinyjpg_cli.py image.jpg -p maximum

# Lossless optimization (no quality loss)
python tinyjpg_cli.py image.jpg -p lossless

# Overwrite original files
python tinyjpg_cli.py *.jpg -o

# Custom suffix
python tinyjpg_cli.py image.jpg -s -compressed

# Process entire directory
python tinyjpg_cli.py photos/

# Custom quality (1-100)
python tinyjpg_cli.py image.jpg -q 80

# List available presets and tools
python tinyjpg_cli.py --list-presets
```

### tinypng_cli.py
Compress PNG images using pngquant.

**Requirements:**
- pngquant binary (installed on your system)
- `pngquant` (Python package)

**Usage:**
```bash
# Basic compression (creates filename-min.png)
python tinypng_cli.py image.png

# Presets: high, balanced (default), maximum, web
python tinypng_cli.py image.png --preset maximum

# Overwrite original files
python tinypng_cli.py *.png --overwrite

# Custom suffix
python tinypng_cli.py image.png --suffix -compressed

# Process entire directory
python tinypng_cli.py images/

# List available presets
python tinypng_cli.py --list-presets
```


### tinyaudio_cli.py
Compress audio files using FFmpeg with presets for voice and music.

**Requirements:**
- FFmpeg (installed on your system)

**Usage:**
```bash
# Basic compression (default: voice preset, creates .opus file)
python tinyaudio_cli.py audio.wav

# Presets: voice (default), music, podcast
python tinyaudio_cli.py audio.wav -p music

# Target specific bitrate
python tinyaudio_cli.py audio.wav -b 64k

# Target specific file size
python tinyaudio_cli.py audio.wav -ts 2.5MB

# Trim silence (useful for voice)
python tinyaudio_cli.py recording.wav --st

# Custom output name
python tinyaudio_cli.py audio.wav -o compressed.opus

# Process entire directory
python tinyaudio_cli.py recordings/ -p voice

# List available presets
python tinyaudio_cli.py --list-presets
```


## Installation

```bash
pip install -r requirements.txt
```

**System dependencies:**

- **FFmpeg** (for tinyaudio and tinyvid)
  - Windows: `winget install ffmpeg` or download from https://www.ffmpeg.org/download.html/
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

- **mozjpeg** (for tinyjpg, optional but recommended)
  - Windows: Download from https://mozjpeg.codelove.de/binaries.html and place in `./mozjpeg/` folder
  - macOS: `brew install mozjpeg`
  - Linux: Build from https://github.com/mozilla/mozjpeg or use package manager

- **jpegtran** (for tinyjpg lossless, optional)
  - Included with libjpeg-turbo: https://libjpeg-turbo.org/
  - macOS: `brew install libjpeg-turbo`
  - Linux: `sudo apt install libjpeg-turbo-progs`

- **pngquant** (for tinypng)
  - Windows: Download from https://pngquant.org/
  - macOS: `brew install pngquant`
  - Linux: `sudo apt install pngquant`

**Note:** tinyjpg_cli.py will work with just `pillow` (Python package) if you don't want to install system binaries, but compression won't be as good.
