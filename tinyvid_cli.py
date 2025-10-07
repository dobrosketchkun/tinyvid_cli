#!/usr/bin/env python3
import subprocess
import sys
import os
import re
import argparse
from pathlib import Path

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
)
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()


class TinyVidCLI:
    """CLI tool to compress videos like tinyvid.io"""
    
    # Based on discovered command from tinyvid.io
    DEFAULT_MP4_SETTINGS = {
        "video_codec": "libx264",
        "crf": 28,
        "pixel_format": "yuv420p",
        "audio_codec": "aac",
        "audio_bitrate": "128k",
        "movflags": "+faststart"
    }
    
    # Quality presets (CRF values)
    QUALITY_PRESETS = {
        "high": 23,      # Higher quality, larger file
        "medium": 28,    # Default (tinyvid.io default)
        "low": 32,       # Lower quality, smaller file
        "extreme": 35    # Very compressed
    }
    
    def __init__(self):
        self.check_ffmpeg()
    
    def check_ffmpeg(self):
        """Check if FFmpeg is installed"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Extract version
                version_match = re.search(r'ffmpeg version (\S+)', result.stdout)
                version = version_match.group(1) if version_match else "unknown"
                console.print(f"[green]✓[/green] FFmpeg {version} found")
                return True
        except FileNotFoundError:
            console.print("[red]✗ FFmpeg not found![/red]")
            console.print("\n[yellow]Please install FFmpeg:[/yellow]")
            console.print("  • Windows: https://www.gyan.dev/ffmpeg/builds/")
            console.print("  • Or use: [cyan]winget install ffmpeg[/cyan]")
            sys.exit(1)
    
    def get_video_duration(self, input_file):
        """Get video duration in seconds using ffprobe"""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    input_file
                ],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except (FileNotFoundError, ValueError):
            pass
        return None
    
    def parse_ffmpeg_progress(self, line, duration):
        """Parse FFmpeg progress output"""
        # Look for time=XX:XX:XX.XX pattern
        time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
        if time_match and duration:
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2))
            seconds = float(time_match.group(3))
            current_time = hours * 3600 + minutes * 60 + seconds
            progress = min(current_time / duration, 1.0)
            return progress
        return None
    
    def compress_video(self, input_file, output_file=None, quality="medium", 
                      scale_height=None):
        """
        Compress video using TinyVid's method with  progress bar
        
        Args:
            input_file: Path to input video
            output_file: Path to output video (optional)
            quality: Quality preset (high/medium/low/extreme)
            scale_height: Scale to specific height (e.g., 480, 720, 1080)
        """
        
        # Validate input
        if not os.path.exists(input_file):
            console.print(f"[red]✗ Input file not found:[/red] {input_file}")
            return False
        
        # Generate output filename
        if not output_file:
            input_path = Path(input_file)
            output_file = str(input_path.parent / f"{input_path.stem}_compressed{input_path.suffix}")
        
        # Get input file info
        input_size = os.path.getsize(input_file)
        duration = self.get_video_duration(input_file)
        
        # Get CRF value for quality
        crf = self.QUALITY_PRESETS.get(quality, 28)
        
        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-i", input_file,
            "-c:v", self.DEFAULT_MP4_SETTINGS["video_codec"],
            "-crf", str(crf),
            "-pix_fmt", self.DEFAULT_MP4_SETTINGS["pixel_format"],
            "-c:a", self.DEFAULT_MP4_SETTINGS["audio_codec"],
            "-b:a", self.DEFAULT_MP4_SETTINGS["audio_bitrate"],
            "-movflags", self.DEFAULT_MP4_SETTINGS["movflags"],
            "-progress", "pipe:1",  # Send progress to stdout
            "-loglevel", "error",    # Only show errors
            "-stats_period", "0.5",  # Update every 0.5 seconds
        ]
        
        # Add resolution scaling if needed
        if scale_height:
            cmd.extend(["-vf", f"scale=-2:{scale_height}"])
        
        # Add output file
        cmd.append(output_file)
        
        # Show command info
        console.print()
        panel_content = f"[cyan]Input:[/cyan] {Path(input_file).name}\n"
        panel_content += f"[cyan]Output:[/cyan] {Path(output_file).name}\n"
        panel_content += f"[cyan]Quality:[/cyan] {quality.upper()} (CRF {crf})\n"
        panel_content += f"[cyan]Size:[/cyan] {self.format_size(input_size)}"
        if scale_height:
            panel_content += f"\n[cyan]Scale:[/cyan] {scale_height}p (maintains aspect ratio)"
        
        console.print(Panel(panel_content, title="[bold]Video Compression[/bold]", border_style="blue"))
        
        # Run FFmpeg with progress bar
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(complete_style="green", finished_style="bold green"),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                
                task = progress.add_task("[cyan]Compressing...", total=100.0)
                
                # Start FFmpeg process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                
                # Read progress output
                last_progress = 0.0
                for line in process.stdout:
                    # Parse progress
                    if duration:
                        prog = self.parse_ffmpeg_progress(line, duration)
                        if prog is not None and prog > last_progress:
                            progress.update(task, completed=prog * 100)
                            last_progress = prog
                    
                    # Check for errors
                    if "error" in line.lower() or "failed" in line.lower():
                        console.print(f"[red]Error:[/red] {line.strip()}")
                
                process.wait()
                
                # Ensure progress reaches 100%
                progress.update(task, completed=100.0)
                
                if process.returncode == 0:
                    # Success!
                    if os.path.exists(output_file):
                        output_size = os.path.getsize(output_file)
                        reduction = ((input_size - output_size) / input_size) * 100
                        
                        # Show results
                        console.print()
                        result_table = Table(box=box.ROUNDED, show_header=False, border_style="green")
                        result_table.add_column(style="cyan")
                        result_table.add_column(style="white")
                        
                        result_table.add_row("✓ Status", "[bold green]Success![/bold green]")
                        result_table.add_row("📦 Original", self.format_size(input_size))
                        result_table.add_row("📦 Compressed", self.format_size(output_size))
                        result_table.add_row("📊 Reduction", f"[bold]{reduction:.1f}%[/bold]")
                        result_table.add_row("💾 Saved", self.format_size(input_size - output_size))
                        result_table.add_row("📁 Output", str(output_file))
                        
                        console.print(result_table)
                        console.print()
                        
                        return True
                else:
                    console.print(f"[red]✗ Compression failed with code {process.returncode}[/red]")
                    return False
                    
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Compression cancelled by user[/yellow]")
            # Clean up partial output file
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                    console.print(f"[dim]Cleaned up partial file: {output_file}[/dim]")
                except OSError as e:
                    console.print(f"[dim]Could not remove partial file: {e}[/dim]")
            return False
        except Exception as e:
            console.print(f"[red]✗ Error:[/red] {e}")
            return False
    
    @staticmethod
    def format_size(bytes):
        """Format bytes to human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024
        return f"{bytes:.2f} TB"
    
    def batch_compress(self, input_files, quality="medium", scale_height=None):
        """Compress multiple videos"""
        console.print()
        console.print(Panel(
            f"[cyan]Processing {len(input_files)} file(s)[/cyan]",
            title="[bold]Batch Compression[/bold]",
            border_style="blue"
        ))
        console.print()
        
        results = []
        for i, input_file in enumerate(input_files, 1):
            console.rule(f"[bold cyan]File {i}/{len(input_files)}[/bold cyan]")
            success = self.compress_video(input_file, quality=quality, scale_height=scale_height)
            results.append((input_file, success))
        
        # Summary
        console.print()
        console.rule("[bold]Summary[/bold]")
        
        summary_table = Table(box=box.ROUNDED, show_header=True, border_style="blue")
        summary_table.add_column("#", style="dim")
        summary_table.add_column("File", style="cyan")
        summary_table.add_column("Status", style="bold")
        
        for i, (file, success) in enumerate(results, 1):
            status = "[green]✓ Success[/green]" if success else "[red]✗ Failed[/red]"
            summary_table.add_row(str(i), Path(file).name, status)
        
        console.print(summary_table)
        
        successful = sum(1 for _, success in results if success)
        console.print()
        console.print(f"[bold]Results:[/bold] {successful}/{len(results)} successful")
        console.print()


def main():
    parser = argparse.ArgumentParser(
        description="TinyVid CLI - Compress videos like tinyvid.io (beautiful edition!)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
[bold cyan]Examples:[/bold cyan]
  # Compress with default (medium) quality
  python tinyvid_cli_rich.py video.mp4
  
  # Compress with high quality
  python tinyvid_cli_rich.py video.mp4 -q high
  
  # Specify output file
  python tinyvid_cli_rich.py video.mp4 -o compressed.mp4
  
  # Scale to 480p
  python tinyvid_cli_rich.py video.mp4 -s 480
  
  # Batch compress multiple videos
  python tinyvid_cli_rich.py video1.mp4 video2.mp4 video3.mp4
        """
    )
    
    parser.add_argument(
        "input",
        nargs="+",
        help="Input video file(s)"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output file (only for single file)"
    )
    
    parser.add_argument(
        "-q", "--quality",
        choices=["high", "medium", "low", "extreme"],
        default="medium",
        help="Compression quality (default: medium, same as tinyvid.io)"
    )
    
    parser.add_argument(
        "-s", "--scale",
        type=int,
        metavar="HEIGHT",
        help="Scale to specific height in pixels (e.g., 480, 720, 1080), maintains aspect ratio"
    )
    
    args = parser.parse_args()
    
    # Create CLI instance
    cli = TinyVidCLI()
    
    # Single or batch processing
    if len(args.input) == 1:
        # Single file
        cli.compress_video(
            args.input[0],
            output_file=args.output,
            quality=args.quality,
            scale_height=args.scale
        )
    else:
        # Batch processing
        if args.output:
            console.print("[yellow]⚠ Warning: -o/--output ignored for batch processing[/yellow]")
        cli.batch_compress(args.input, quality=args.quality, scale_height=args.scale)


if __name__ == "__main__":
    main()