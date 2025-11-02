"""
Copilot: Implement image comparison utilities:
- function compare_images(images_a, images_b)
- compute imagehash.phash for each image and hamming distance
- implement an optional function using CLIP if model available:
  - compute CLIP embeddings and cosine similarity
  - allow flag use_clip=True to use CLIP
- returns list of matches with similarity scores and unmatched images
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Tuple
import io

from PIL import Image
import imagehash


@dataclass
class ImageEntry:
    page: int
    name: str
    bytes: bytes
    thumbnail_b64: str | None = None


def _phash(img_bytes: bytes):
    with Image.open(io.BytesIO(img_bytes)) as im:
        im = im.convert("RGB")
        return imagehash.phash(im)


def compare_images(
    images_a: List[ImageEntry],
    images_b: List[ImageEntry],
    use_clip: bool = False,  # placeholder, non-CLIP baseline
    distance_threshold: int = 10,
) -> Dict:
    """Compare images using perceptual hash; return matches and unmatched lists.

    Returns dict with keys: 'matches': List[{'A','B','distance'}],
    'unmatched_A': [...], 'unmatched_B': [...]
    """
    # Simple greedy matching by minimal distance
    remaining_b = list(images_b)
    matches = []
    unmatched_a = []

    for a in images_a:
        best = None
        best_dist = None
        best_idx = None
        try:
            ah = _phash(a.bytes)
        except Exception:
            unmatched_a.append(a)
            continue
        for idx, b in enumerate(remaining_b):
            try:
                bh = _phash(b.bytes)
            except Exception:
                continue
            dist = ah - bh  # hamming distance
            if best is None or dist < best_dist:
                best = b
                best_dist = dist
                best_idx = idx
        if best is not None:
            matches.append({"A": a, "B": best, "distance": int(best_dist)})
            remaining_b.pop(best_idx)
        else:
            unmatched_a.append(a)

    unmatched_b = remaining_b

    return {"matches": matches, "unmatched_A": unmatched_a, "unmatched_B": unmatched_b}
