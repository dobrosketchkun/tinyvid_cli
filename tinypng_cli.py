#!/usr/bin/env python3
"""
TinyPNG-ish CLI - PNG compression using pngquant
A simple script to compress PNG images with quality presets
"""

import argparse
import os
import sys
import shutil
from pathlib import Path

try:
    import pngquant
except ImportError:
    print("ERROR: pngquant Python package is not installed!")
    print("\nTo install:")
    print("  pip install pngquant")
    print("\nNote: You also need the pngquant binary installed:")
    print("  Windows: Download from https://pngquant.org/")
    print("  macOS:   brew install pngquant")
    print("  Linux:   sudo apt install pngquant")
    sys.exit(1)


# Presets configuration
PRESETS = {
    'high': {
        'min_quality': 80,
        'max_quality': 95,
        'speed': 3,
        'description': 'High quality - minimal compression (~50-70% smaller)'
    },
    'balanced': {
        'min_quality': 65,
        'max_quality': 85,
        'speed': 3,
        'description': 'Balanced - good compression/quality ratio (~60-80% smaller)'
    },
    'maximum': {
        'min_quality': 50,
        'max_quality': 70,
        'speed': 3,
        'description': 'Maximum compression - aggressive (~70-85% smaller)'
    },
    'web': {
        'min_quality': 70,
        'max_quality': 85,
        'speed': 8,
        'description': 'Web optimized - fast processing for web images'
    }
}

DEFAULT_PRESET = 'balanced'


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


def compress_png(input_path, output_path, preset_config, overwrite=False):
    """Compress a single PNG file using pngquant Python wrapper"""
    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}")
        return False
    
    # Get original size
    original_size = get_file_size(input_path)
    
    try:
        # Configure pngquant with preset settings
        pngquant.config(
            min_quality=preset_config['min_quality'],
            max_quality=preset_config['max_quality'],
            speed=preset_config['speed']
        )
        
        # Compress the image
        # If overwrite=True, we use the same path temporarily then replace
        # quant_image returns True on success, False on failure
        result = pngquant.quant_image(
            image=input_path,
            dst=output_path,
            override=True,
            delete=False  # Don't delete the original yet
        )
        
        # Check if compression was successful and output exists
        if result and os.path.exists(output_path):
            compressed_size = get_file_size(output_path)
            
            # Check if the compressed file is actually smaller
            if compressed_size < original_size:
                reduction = ((original_size - compressed_size) / original_size) * 100
                
                print(f"✓ {input_path}")
                print(f"  {format_size(original_size)} → {format_size(compressed_size)} "
                      f"({reduction:.1f}% smaller)")
                return True
            else:
                # Compressed file is larger, remove it
                if os.path.exists(output_path):
                    os.remove(output_path)
                print(f"⊘ {input_path}")
                print(f"  Already optimized or would be larger")
                return False
        else:
            print(f"✗ {input_path}")
            print(f"  Could not compress to desired quality")
            return False
            
    except Exception as e:
        print(f"✗ {input_path}")
        print(f"  Exception: {str(e)}")
        # Clean up output file if it exists
        if os.path.exists(output_path) and output_path != input_path:
            try:
                os.remove(output_path)
            except:
                pass
        return False


def find_png_files(paths):
    """Find all PNG files from given paths (files or directories)"""
    png_files = []
    
    for path_str in paths:
        path = Path(path_str)
        
        if not path.exists():
            print(f"WARNING: Path does not exist: {path_str}")
            continue
            
        if path.is_file():
            if path.suffix.lower() in ['.png']:
                png_files.append(path)
            else:
                print(f"WARNING: Not a PNG file: {path_str}")
        elif path.is_dir():
            # Recursively find all PNG files
            png_files.extend(path.rglob('*.png'))
            png_files.extend(path.rglob('*.PNG'))
    
    return sorted(set(png_files))


def main():
    parser = argparse.ArgumentParser(
        description='TinyPNG-ish CLI - Compress PNG images using pngquant',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Presets:
{chr(10).join(f"  {name:10} - {info['description']}" for name, info in PRESETS.items())}

Examples:
  python tinypng_cli.py image.png
  python tinypng_cli.py image.png --preset maximum
  python tinypng_cli.py *.png --overwrite
  python tinypng_cli.py images/ --preset web
  python tinypng_cli.py img1.png img2.png folder/ --suffix -compressed
        """
    )
    
    parser.add_argument('paths', nargs='+', help='PNG files or directories to compress')
    parser.add_argument('--preset', '-p', 
                        choices=list(PRESETS.keys()),
                        default=DEFAULT_PRESET,
                        help=f'Compression preset (default: {DEFAULT_PRESET})')
    parser.add_argument('--overwrite', '-o', 
                        action='store_true',
                        help='Overwrite original files')
    parser.add_argument('--suffix', '-s',
                        default='-min',
                        help='Suffix for output files when not overwriting (default: -min)')
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
            print(f"    Quality: {info['min_quality']}-{info['max_quality']}, Speed: {info['speed']}")
        return
    
    # Get preset configuration
    preset_config = PRESETS[args.preset]
    
    # Find all PNG files
    png_files = find_png_files(args.paths)
    
    if not png_files:
        print("ERROR: No PNG files found!")
        sys.exit(1)
    
    # Print summary
    print(f"\nCompressing {len(png_files)} PNG file(s)")
    print(f"Preset: {args.preset} - {preset_config['description']}")
    print(f"Mode: {'OVERWRITE' if args.overwrite else f'CREATE NEW (suffix: {args.suffix})'}")
    print("-" * 70)
    print()
    
    # Process files
    success_count = 0
    failed_count = 0
    
    for png_file in png_files:
        if args.overwrite:
            # Use temporary file then replace original
            temp_output = png_file.with_suffix('.tmp.png')
            if compress_png(str(png_file), str(temp_output), preset_config, overwrite=True):
                # Replace original with compressed version
                shutil.move(str(temp_output), str(png_file))
                success_count += 1
            else:
                # Clean up temp file if it exists
                if temp_output.exists():
                    temp_output.unlink()
                failed_count += 1
        else:
            # Create new file with suffix
            output_path = png_file.with_stem(png_file.stem + args.suffix)
            if compress_png(str(png_file), str(output_path), preset_config, overwrite=False):
                success_count += 1
            else:
                failed_count += 1
        
        print()
    
    # Print final summary
    print("-" * 70)
    print(f"Completed: {success_count} successful, {failed_count} failed/skipped")


if __name__ == '__main__':
    main()

