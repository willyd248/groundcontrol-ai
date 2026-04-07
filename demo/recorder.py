"""
recorder.py — Optional pygame-window-to-mp4 recorder using imageio-ffmpeg.

Usage (from side_by_side.py):
    recorder = Recorder("demo_output.mp4", fps=30)
    recorder.capture(screen_surface)  # call each frame
    recorder.close()

Requires: imageio, imageio-ffmpeg (pip install imageio imageio-ffmpeg)
"""

from __future__ import annotations
import numpy as np


class Recorder:
    """Captures pygame Surface frames and writes them to an mp4 file."""

    def __init__(self, output_path: str, fps: int = 30) -> None:
        try:
            import imageio
        except ImportError:
            raise ImportError(
                "imageio not installed. Run: pip install imageio imageio-ffmpeg"
            )

        import imageio.v2 as iio

        self.output_path = output_path
        self.fps = fps
        self._writer = iio.get_writer(
            output_path,
            fps=fps,
            codec="libx264",
            quality=8,
            macro_block_size=None,
        )
        self._frame_count = 0
        print(f"[Recorder] Writing to {output_path!r} at {fps} fps")

    def capture(self, surface) -> None:
        """Capture one pygame Surface as a video frame."""
        import pygame

        # pygame surface → numpy (H, W, 3) RGB array
        raw = pygame.surfarray.array3d(surface)
        # pygame uses (W, H, 3); imageio needs (H, W, 3)
        frame = np.transpose(raw, (1, 0, 2))
        self._writer.append_data(frame)
        self._frame_count += 1

    def close(self) -> None:
        """Finalise and close the video file."""
        self._writer.close()
        print(
            f"[Recorder] Saved {self._frame_count} frames → {self.output_path!r}"
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
