#!/usr/bin/env python3
"""
TinyJPG CLI - JPEG compression using mozjpeg and jpegtran
Compress JPEG images with quality presets
"""

import argparse
import os
import sys
import shutil
import subprocess
from pathlib import Path

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


# Presets configuration
PRESETS = {
    'high': {
        'quality': 90,
        'description': 'High quality - minimal compression (~50-60% smaller)'
    },
    'balanced': {
        'quality': 85,
        'description': 'Balanced - good compression/quality ratio (~60-70% smaller)'
    },
    'maximum': {
        'quality': 75,
        'description': 'Maximum compression - aggressive (~70-80% smaller)'
    },
    'lossless': {
        'quality': None,
        'description': 'Lossless optimization - no quality loss (~5-10% smaller)'
    }
}

DEFAULT_PRESET = 'balanced'


def find_cjpeg():
    """Find mozjpeg's cjpeg binary"""
    # Check system PATH
    if shutil.which('cjpeg'):
        return 'cjpeg'
    
    # Check local mozjpeg folder
    local = Path(__file__).parent / 'mozjpeg' / 'cjpeg.exe'
    if local.exists():
        return str(local)
    
    # Unix-like systems might have it without .exe
    local_unix = Path(__file__).parent / 'mozjpeg' / 'cjpeg'
    if local_unix.exists():
        return str(local_unix)
    
    return None


def find_jpegtran():
    """Find jpegtran binary"""
    # Check system PATH
    if shutil.which('jpegtran'):
        return 'jpegtran'
    
    # Check local mozjpeg folder (mozjpeg includes jpegtran)
    local = Path(__file__).parent / 'mozjpeg' / 'jpegtran.exe'
    if local.exists():
        return str(local)
    
    # Unix-like systems
    local_unix = Path(__file__).parent / 'mozjpeg' / 'jpegtran'
    if local_unix.exists():
        return str(local_unix)
    
    return None


def get_file_size(filepath):
    """Get file size in bytes"""
    return os.path.getsize(filepath)


def format_size(bytes_size):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def compress_jpeg_mozjpeg(input_path, output_path, quality):
    """Compress JPEG using mozjpeg (via Pillow decode + cjpeg encode)"""
    if not PILLOW_AVAILABLE:
        return False, "Pillow required for mozjpeg compression"
    
    cjpeg = find_cjpeg()
    if not cjpeg:
        return False, "mozjpeg not found"
    
    temp_ppm = None
    try:
        # Decode JPEG to PPM using Pillow
        img = Image.open(input_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Save as temporary PPM (cjpeg can read this)
        temp_ppm = Path(output_path).with_suffix('.tmp.ppm')
        img.save(temp_ppm, 'PPM')
        
        # Encode with mozjpeg
        cmd = [
            cjpeg,
            '-quality', str(quality),
            '-optimize',
            '-outfile', str(output_path),
            str(temp_ppm)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Clean up temp file
        if temp_ppm and temp_ppm.exists():
            temp_ppm.unlink()
        
        if result.returncode == 0 and os.path.exists(output_path):
            return True, None
        else:
            return False, result.stderr.strip() if result.stderr else "Unknown error"
    
    except Exception as e:
        # Clean up temp file on error
        if temp_ppm and temp_ppm.exists():
            try:
                temp_ppm.unlink()
            except:
                pass
        return False, str(e)


def compress_jpeg_jpegtran(input_path, output_path):
    """Lossless JPEG optimization using jpegtran"""
    jpegtran = find_jpegtran()
    if not jpegtran:
        return False, "jpegtran not found"
    
    try:
        cmd = [
            jpegtran,
            '-optimize',
            '-progressive',
            '-copy', 'none',  # Strip metadata
            '-outfile', str(output_path),
            str(input_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return True, None
        else:
            return False, result.stderr.strip() if result.stderr else "Unknown error"
    
    except Exception as e:
        return False, str(e)


def compress_jpeg_pillow(input_path, output_path, quality):
    """Compress JPEG using Pillow (fallback)"""
    if not PILLOW_AVAILABLE:
        return False, "Pillow not installed"
    
    try:
        img = Image.open(input_path)
        
        # Convert to RGB if needed (some JPEGs have different modes)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        return True, None
    
    except Exception as e:
        return False, str(e)


def compress_jpeg(input_path, output_path, preset_config, force_pillow=False):
    """Compress a single JPEG file"""
    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}")
        return False
    
    original_size = get_file_size(input_path)
    
    # Determine compression method
    if preset_config['quality'] is None:
        # Lossless preset - use jpegtran
        method = "jpegtran"
        success, error = compress_jpeg_jpegtran(input_path, output_path)
    elif force_pillow:
        # Forced Pillow usage
        method = "Pillow"
        success, error = compress_jpeg_pillow(input_path, output_path, preset_config['quality'])
    else:
        # Try mozjpeg first, fallback to Pillow
        cjpeg = find_cjpeg()
        if cjpeg:
            method = "mozjpeg"
            success, error = compress_jpeg_mozjpeg(input_path, output_path, preset_config['quality'])
        elif PILLOW_AVAILABLE:
            method = "Pillow"
            success, error = compress_jpeg_pillow(input_path, output_path, preset_config['quality'])
        else:
            print(f"✗ {input_path}")
            print(f"  No compression tool available (install mozjpeg, jpegtran, or pillow)")
            return False
    
    if not success:
        print(f"✗ {input_path}")
        print(f"  Compression failed ({method}): {error}")
        # Clean up failed output
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        return False
    
    # Check if compression was actually beneficial
    if os.path.exists(output_path):
        compressed_size = get_file_size(output_path)
        
        if compressed_size < original_size:
            reduction = ((original_size - compressed_size) / original_size) * 100
            print(f"✓ {input_path}")
            print(f"  {format_size(original_size)} → {format_size(compressed_size)} "
                  f"({reduction:.1f}% smaller) [{method}]")
            return True
        else:
            # Compressed file is larger or same, remove it
            os.remove(output_path)
            print(f"⊘ {input_path}")
            print(f"  Already optimized or would be larger")
            return False
    
    return False


def find_jpeg_files(paths):
    """Find all JPEG files from given paths (files or directories)"""
    jpeg_exts = {'.jpg', '.jpeg', '.jpe', '.jfif'}
    jpeg_files = []
    
    for path_str in paths:
        path = Path(path_str)
        
        if not path.exists():
            print(f"WARNING: Path does not exist: {path_str}")
            continue
        
        if path.is_file():
            if path.suffix.lower() in jpeg_exts:
                jpeg_files.append(path)
            else:
                print(f"WARNING: Not a JPEG file: {path_str}")
        elif path.is_dir():
            # Recursively find all JPEG files
            for ext in jpeg_exts:
                jpeg_files.extend(path.rglob(f'*{ext}'))
                jpeg_files.extend(path.rglob(f'*{ext.upper()}'))
    
    return sorted(set(jpeg_files))


def main():
    parser = argparse.ArgumentParser(
        description='TinyJPG CLI - Compress JPEG images using mozjpeg/jpegtran',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Presets:
{chr(10).join(f"  {name:10} - {info['description']}" for name, info in PRESETS.items())}

Tools priority:
  Lossy:    mozjpeg (best) > Pillow (fallback)
  Lossless: jpegtran

Examples:
  python tinyjpg_cli.py image.jpg
  python tinyjpg_cli.py image.jpg -p maximum
  python tinyjpg_cli.py *.jpg -o
  python tinyjpg_cli.py photos/ -p high
  python tinyjpg_cli.py image.jpg -s -compressed
        """
    )
    
    parser.add_argument('paths', nargs='+', help='JPEG files or directories to compress')
    parser.add_argument('-p', '--preset',
                        choices=list(PRESETS.keys()),
                        default=DEFAULT_PRESET,
                        help=f'Compression preset (default: {DEFAULT_PRESET})')
    parser.add_argument('-o', '--overwrite',
                        action='store_true',
                        help='Overwrite original files')
    parser.add_argument('-s', '--suffix',
                        default='-min',
                        help='Suffix for output files when not overwriting (default: -min)')
    parser.add_argument('-q', '--quality',
                        type=int,
                        help='Override quality (1-100, ignored for lossless preset)')
    parser.add_argument('--pillow',
                        action='store_true',
                        help='Force use of Pillow instead of mozjpeg')
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
            if info['quality'] is not None:
                print(f"    Quality: {info['quality']}")
            else:
                print(f"    Method: Lossless (jpegtran)")
        
        # Show available tools
        print("\nAvailable compression tools:")
        cjpeg = find_cjpeg()
        jpegtran = find_jpegtran()
        print(f"  mozjpeg (cjpeg):  {'✓ Found' if cjpeg else '✗ Not found'}")
        print(f"  jpegtran:         {'✓ Found' if jpegtran else '✗ Not found'}")
        print(f"  Pillow:           {'✓ Available' if PILLOW_AVAILABLE else '✗ Not installed'}")
        
        if not cjpeg and not jpegtran and not PILLOW_AVAILABLE:
            print("\n⚠ No compression tools available!")
            print("Install at least one:")
            print("  - mozjpeg: Place cjpeg.exe in ./mozjpeg/ folder or system PATH")
            print("  - jpegtran: Install libjpeg-turbo or place in ./mozjpeg/ folder")
            print("  - Pillow: pip install pillow")
        
        return
    
    # Check if any compression tool is available
    if not PILLOW_AVAILABLE and not find_jpegtran():
        print("ERROR: No compression tools available!")
        print("\nInstall at least one:")
        print("  - Pillow: pip install pillow (required for mozjpeg and general compression)")
        print("  - jpegtran: For lossless optimization only")
        sys.exit(1)
    
    # Warn if mozjpeg requested but Pillow not available
    if find_cjpeg() and not PILLOW_AVAILABLE:
        print("WARNING: mozjpeg found but Pillow not installed. mozjpeg won't be used.")
        print("Install Pillow: pip install pillow")
    
    # Get preset configuration
    preset_config = PRESETS[args.preset].copy()
    
    # Override quality if specified
    if args.quality is not None:
        if args.preset == 'lossless':
            print("WARNING: --quality ignored for lossless preset")
        else:
            preset_config['quality'] = args.quality
    
    # Find all JPEG files
    jpeg_files = find_jpeg_files(args.paths)
    
    if not jpeg_files:
        print("ERROR: No JPEG files found!")
        sys.exit(1)
    
    # Print summary
    print(f"\nCompressing {len(jpeg_files)} JPEG file(s)")
    print(f"Preset: {args.preset} - {preset_config['description']}")
    print(f"Mode: {'OVERWRITE' if args.overwrite else f'CREATE NEW (suffix: {args.suffix})'}")
    print("-" * 70)
    print()
    
    # Process files
    success_count = 0
    failed_count = 0
    
    for jpeg_file in jpeg_files:
        if args.overwrite:
            # Use temporary file then replace original
            temp_output = jpeg_file.with_suffix('.tmp.jpg')
            if compress_jpeg(str(jpeg_file), str(temp_output), preset_config, args.pillow):
                # Replace original with compressed version
                shutil.move(str(temp_output), str(jpeg_file))
                success_count += 1
            else:
                # Clean up temp file if it exists
                if temp_output.exists():
                    temp_output.unlink()
                failed_count += 1
        else:
            # Create new file with suffix
            output_path = jpeg_file.with_stem(jpeg_file.stem + args.suffix)
            if compress_jpeg(str(jpeg_file), str(output_path), preset_config, args.pillow):
                success_count += 1
            else:
                failed_count += 1
        
        print()
    
    # Print final summary
    print("-" * 70)
    print(f"Completed: {success_count} successful, {failed_count} failed/skipped")


if __name__ == '__main__':
    main()

