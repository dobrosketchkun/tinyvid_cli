#!/usr/bin/env python3
"""
TinyAudio CLI - Audio compression using FFmpeg
Compress audio files with quality presets for voice or music
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".aif", ".aifc", ".caf"}

# Presets configuration
PRESETS = {
    'voice': {
        'samplerate': 24000,
        'channels': 1,
        'bitrate_bps': 32000,
        'codec': 'opus',
        'lufs': -16.0,
        'highpass': 80,
        'lowpass': 12000,
        'description': 'Voice optimized - mono, 32kbps Opus (~70-90% smaller)'
    },
    'music': {
        'samplerate': 48000,
        'channels': 2,
        'bitrate_bps': 80000,
        'codec': 'opus',
        'lufs': -14.0,
        'highpass': None,
        'lowpass': None,
        'description': 'Music quality - stereo, 80kbps Opus (~40-60% smaller)'
    },
    'podcast': {
        'samplerate': 44100,
        'channels': 1,
        'bitrate_bps': 64000,
        'codec': 'opus',
        'lufs': -16.0,
        'highpass': 60,
        'lowpass': 15000,
        'description': 'Podcast - mono, 64kbps Opus (~50-75% smaller)'
    }
}

DEFAULT_PRESET = 'voice'


# ----------------------------- Helpers -----------------------------

def require_ffmpeg() -> None:
    """Check if FFmpeg is installed"""
    for binname in ("ffmpeg", "ffprobe"):
        if shutil.which(binname) is None:
            print(f"ERROR: '{binname}' not found in PATH!")
            print("\nTo install FFmpeg:")
            print("  Windows: winget install ffmpeg")
            print("  macOS:   brew install ffmpeg")
            print("  Linux:   sudo apt install ffmpeg")
            sys.exit(1)


def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr"""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    return proc.returncode, out, err


def human_to_bytes(s: str) -> int:
    """Convert strings like '2.5MB', '900KB' to bytes"""
    m = re.match(r"^\s*([\d.]+)\s*([KMG]?B)?\s*$", s, re.IGNORECASE)
    if not m:
        raise ValueError(f"Could not parse size: {s}")
    val = float(m.group(1))
    unit = (m.group(2) or "B").upper()
    scale = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    if unit not in scale:
        raise ValueError(f"Unsupported unit: {unit}")
    return int(val * scale[unit])


def bytes_to_human(n: int) -> str:
    """Format bytes to human readable size"""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}GB"


def ffprobe_duration(path: Path) -> float:
    """Get audio file duration using ffprobe"""
    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path)
    ]
    code, out, err = run_cmd(cmd)
    if code != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {err.strip()}")
    
    info = json.loads(out or "{}")
    
    # Prefer format.duration; fallback to first audio stream duration
    dur = None
    if "format" in info and "duration" in info["format"]:
        dur = float(info["format"]["duration"])
    else:
        for s in info.get("streams", []):
            if s.get("codec_type") == "audio" and "duration" in s:
                dur = float(s["duration"])
                break
    
    if dur is None or not math.isfinite(dur):
        raise RuntimeError(f"Could not determine duration for {path}")
    
    return dur


def compute_bitrate_for_target_size(target_bytes: int, duration_sec: float) -> int:
    """
    Compute target audio bitrate (bps) to approximately hit target_bytes.
    Apply 3% overhead cushion for container/headers.
    """
    if duration_sec <= 0:
        raise ValueError("Duration must be positive")
    bits_available = target_bytes * 8 * 0.97
    br = int(bits_available / duration_sec)
    # Keep within reasonable bounds
    return max(6000, min(br, 512000))  # 6 kbps .. 512 kbps


def normalize_ext_for_codec(codec: str) -> str:
    """Get file extension for codec"""
    if codec == "opus":
        return ".opus"
    elif codec == "aac":
        return ".m4a"
    elif codec == "mp3":
        return ".mp3"
    else:
        return ".m4a"


# ----------------------------- Processing -----------------------------

def build_filterchain(args, preset_config) -> str:
    """Build FFmpeg audio filter chain"""
    filters = []

    # Silence trim (start & end)
    if args.st:
        # More aggressive defaults for voice
        thr = args.sth if args.sth is not None else (-50 if args.preset == "voice" else -45)
        dur = args.sd if args.sd is not None else (0.5 if args.preset == "voice" else 0.8)
        filters.append(
            f"silenceremove=start_periods=1:start_duration={dur}:start_threshold={thr}dB:"
            f"stop_periods=1:stop_duration={dur}:stop_threshold={thr}dB"
        )

    # High-pass for rumble removal
    hp = args.hp if args.hp is not None else preset_config.get("highpass")
    if hp:
        filters.append(f"highpass=f={hp}")

    # Low-pass to save bits
    lp = args.lp if args.lp is not None else preset_config.get("lowpass")
    if lp:
        filters.append(f"lowpass=f={lp}")

    # Loudness normalization
    lufs = args.lufs if args.lufs is not None else preset_config.get("lufs")
    if lufs is not None:
        filters.append(f"loudnorm=I={float(lufs)}:LRA=11:TP=-1.5")

    return ",".join(filters) if filters else ""


def build_ffmpeg_cmd(
    inp: Path,
    out: Path,
    codec: str,
    bitrate_bps: int,
    samplerate: int,
    channels: int,
    filterchain: str
) -> List[str]:
    """Build FFmpeg command"""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(inp)]

    if filterchain:
        cmd.extend(["-af", filterchain])

    # Channels & sample rate
    cmd.extend(["-ac", str(channels), "-ar", str(samplerate)])

    # Codec specifics
    if codec == "opus":
        cmd.extend(["-c:a", "libopus", "-b:a", f"{bitrate_bps}", "-vbr", "on", "-compression_level", "10"])
    elif codec == "aac":
        cmd.extend(["-c:a", "aac", "-b:a", f"{bitrate_bps}"])
    elif codec == "mp3":
        cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{bitrate_bps}"])
    else:
        raise ValueError(f"Unsupported codec: {codec}")

    cmd.append(str(out))
    return cmd


def compress_audio(input_path, output_path, preset_config, args):
    """Compress a single audio file"""
    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}")
        return False
    
    try:
        # Get duration
        duration = ffprobe_duration(input_path)
        original_size = os.path.getsize(input_path)
        
        # Determine bitrate
        if args.ts:
            bitrate_bps = compute_bitrate_for_target_size(args.ts, duration)
        elif args.b:
            # Parse bitrate like "32k" or "32"
            m = re.match(r"^\s*(\d+)\s*[kK]?\s*$", args.b)
            if not m:
                raise ValueError(f"Invalid bitrate: {args.b}")
            bitrate_bps = int(m.group(1)) * 1000
        else:
            bitrate_bps = preset_config["bitrate_bps"]
        
        # Adjust lowpass for ultra-low bitrates
        if args.preset == "voice" and bitrate_bps <= 24000 and args.lp is None:
            args.lp = 8000
        
        # Get encoding parameters
        samplerate = args.sr or preset_config["samplerate"]
        channels = args.ch or preset_config["channels"]
        codec = args.codec or preset_config["codec"]
        
        # Build filter chain
        filterchain = build_filterchain(args, preset_config)
        
        # Estimate output size
        est_size = int(bitrate_bps * duration / 8)
        reduction = ((original_size - est_size) / original_size) * 100 if est_size < original_size else 0
        
        print(f"✓ {input_path}")
        print(f"  {bytes_to_human(original_size)} → ~{bytes_to_human(est_size)} "
              f"({reduction:.1f}% smaller, {int(bitrate_bps/1000)}kbps {codec})")
        
        # Build and run FFmpeg command
        cmd = build_ffmpeg_cmd(
            input_path,
            output_path,
            codec,
            bitrate_bps,
            samplerate,
            channels,
            filterchain
        )
        
        code, out, err = run_cmd(cmd)
        
        if code != 0:
            print(f"✗ FFmpeg error: {err.strip()}")
            # Clean up failed output
            if os.path.exists(output_path):
                os.remove(output_path)
            return False
        
        # Show actual result
        if os.path.exists(output_path):
            actual_size = os.path.getsize(output_path)
            actual_reduction = ((original_size - actual_size) / original_size) * 100
            print(f"  Actual: {bytes_to_human(actual_size)} ({actual_reduction:.1f}% smaller)")
            return True
        
        return False
        
    except Exception as e:
        print(f"✗ {input_path}")
        print(f"  Error: {str(e)}")
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        return False


def collect_inputs(paths: List[Path]) -> List[Path]:
    """Find all audio files from given paths"""
    files: List[Path] = []
    for p in paths:
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
            files.append(p)
        elif p.is_dir():
            for root, dirs, fs in os.walk(p):
                for f in fs:
                    ext = Path(f).suffix.lower()
                    if ext in AUDIO_EXTS:
                        files.append(Path(root) / f)
    return sorted(set(files))


# ----------------------------- CLI -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description='TinyAudio CLI - Compress audio files using FFmpeg',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Presets:
{chr(10).join(f"  {name:10} - {info['description']}" for name, info in PRESETS.items())}

Examples:
  python tinyaudio_cli.py audio.wav
  python tinyaudio_cli.py audio.wav -p music
  python tinyaudio_cli.py audio.wav -b 64k
  python tinyaudio_cli.py audio.wav -ts 2.5MB
  python tinyaudio_cli.py recordings/ -p voice --st
  python tinyaudio_cli.py audio.wav -o output.opus
        """
    )
    
    parser.add_argument('paths', nargs='+', help='Audio files or directories to compress')
    parser.add_argument('-p', '--preset',
                        choices=list(PRESETS.keys()),
                        default=DEFAULT_PRESET,
                        help=f'Compression preset (default: {DEFAULT_PRESET})')
    parser.add_argument('-o', '--output',
                        help='Output file (single file only) or directory')
    parser.add_argument('-s', '--suffix',
                        default='',
                        help='Suffix for output files (default: none, just changes extension)')
    parser.add_argument('--codec',
                        choices=['opus', 'aac', 'mp3'],
                        help='Audio codec (default: from preset)')
    
    # Bitrate options
    parser.add_argument('-b', '--bitrate',
                        help='Target bitrate (e.g., 32k, 64k, 96k)')
    parser.add_argument('-ts', '--target-size',
                        help='Target output size (e.g., 2.5MB) - overrides bitrate')
    
    # Audio parameters
    parser.add_argument('-sr', '--samplerate',
                        type=int,
                        help='Sample rate in Hz (e.g., 24000, 48000)')
    parser.add_argument('-ch', '--channels',
                        type=int,
                        help='Number of channels (1=mono, 2=stereo)')
    
    # Filters
    parser.add_argument('--lufs',
                        type=float,
                        help='Loudness target in LUFS (e.g., -16 for voice, -14 for music)')
    parser.add_argument('--st', '--silence-trim',
                        action='store_true',
                        help='Trim silence at start/end')
    parser.add_argument('--sth', '--silence-threshold',
                        type=float,
                        help='Silence threshold in dB (e.g., -50)')
    parser.add_argument('--sd', '--silence-duration',
                        type=float,
                        help='Silence duration in seconds (e.g., 0.5)')
    parser.add_argument('--hp', '--highpass',
                        type=int,
                        help='High-pass filter cutoff in Hz (e.g., 80)')
    parser.add_argument('--lp', '--lowpass',
                        type=int,
                        help='Low-pass filter cutoff in Hz (e.g., 12000)')
    
    parser.add_argument('--list-presets',
                        action='store_true',
                        help='List all available presets and exit')
    
    args = parser.parse_args()
    
    # List presets if requested
    if args.list_presets:
        print("Available presets:")
        for name, info in PRESETS.items():
            default_marker = " (default)" if name == DEFAULT_PRESET else ""
            print(f"\n  {name}{default_marker}")
            print(f"    {info['description']}")
            print(f"    Codec: {info['codec']}, Bitrate: {int(info['bitrate_bps']/1000)}kbps")
            print(f"    Sample rate: {info['samplerate']}Hz, Channels: {info['channels']}")
        return
    
    require_ffmpeg()
    
    # Get preset configuration
    preset_config = PRESETS[args.preset]
    
    # Find all audio files
    input_paths = [Path(p) for p in args.paths]
    audio_files = collect_inputs(input_paths)
    
    if not audio_files:
        print("ERROR: No audio files found!")
        print(f"Supported extensions: {', '.join(sorted(AUDIO_EXTS))}")
        sys.exit(1)
    
    # Parse target size if provided
    if args.target_size:
        try:
            args.ts = human_to_bytes(args.target_size)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
    else:
        args.ts = None
    
    # Store parsed values for easier access
    args.b = args.bitrate
    args.sr = args.samplerate
    args.ch = args.channels
    
    # Determine output mode
    single_file = len(audio_files) == 1
    output_is_dir = args.output and (Path(args.output).is_dir() or not single_file)
    
    # Print summary
    print(f"\nCompressing {len(audio_files)} audio file(s)")
    print(f"Preset: {args.preset} - {preset_config['description']}")
    print("-" * 70)
    print()
    
    # Process files
    success_count = 0
    failed_count = 0
    
    for audio_file in audio_files:
        # Determine output path
        if single_file and args.output and not output_is_dir:
            # Single file with specific output name
            output_path = Path(args.output)
        elif args.output and output_is_dir:
            # Output directory specified
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            codec = args.codec or preset_config['codec']
            ext = normalize_ext_for_codec(codec)
            output_path = output_dir / (audio_file.stem + ext)
        else:
            # Same directory as input with new extension
            codec = args.codec or preset_config['codec']
            ext = normalize_ext_for_codec(codec)
            suffix = args.suffix if args.suffix else ''
            output_path = audio_file.parent / (audio_file.stem + suffix + ext)
        
        # Safety check: don't overwrite input file
        if output_path == audio_file:
            output_path = audio_file.parent / (audio_file.stem + '-compressed' + audio_file.suffix)
        
        if compress_audio(audio_file, output_path, preset_config, args):
            success_count += 1
        else:
            failed_count += 1
        
        print()
    
    # Print final summary
    print("-" * 70)
    print(f"Completed: {success_count} successful, {failed_count} failed")


if __name__ == '__main__':
    main()
