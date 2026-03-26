"""Image pipeline: quadrant mixing + 1/4-3/4 cut-and-swap transform + seam inpainting."""
import random
import numpy as np
from PIL import Image


POSITIONS = ["TL", "TR", "BL", "BR"]


def cut_quadrants(img: Image.Image) -> dict:
    """Cut image into 4 quadrants. Returns dict keyed by TL/TR/BL/BR."""
    w, h = img.size
    mx, my = w // 2, h // 2
    return {
        "TL": img.crop((0,  0,  mx, my)),
        "TR": img.crop((mx, 0,  w,  my)),
        "BL": img.crop((0,  my, mx, h)),
        "BR": img.crop((mx, my, w,  h)),
    }


def make_composites(source_images: list) -> list:
    """
    Build 4 new images from 4 source images.
    Each new image gets exactly one quadrant from each source, placed randomly.
    """
    # Normalize all sources to the same size (first image's dimensions)
    w, h = source_images[0].size
    resized = [img.resize((w, h), Image.LANCZOS) for img in source_images]

    # Cut each source into quadrants
    all_quads = [cut_quadrants(img) for img in resized]

    # For each source, shuffle which quadrant goes to which new image
    # assignments[src_idx][new_img_idx] = quadrant key
    assignments = []
    for quads in all_quads:
        order = POSITIONS.copy()
        random.shuffle(order)
        assignments.append(order)

    pos_coords = {
        "TL": (0,  0),
        "TR": (w // 2, 0),
        "BL": (0,  h // 2),
        "BR": (w // 2, h // 2),
    }

    composites = []
    for j in range(4):
        # Collect one quadrant from each source for this new image
        pieces = [all_quads[i][assignments[i][j]] for i in range(4)]

        # Randomly assign pieces to positions in the new image
        dest_positions = POSITIONS.copy()
        random.shuffle(dest_positions)

        composite = Image.new(resized[0].mode, (w, h))
        for piece, dest in zip(pieces, dest_positions):
            composite.paste(piece, pos_coords[dest])

        composites.append(composite)

    return composites


def apply_transform(img: Image.Image) -> Image.Image:
    """
    3x3 cut at 1/4 and 3/4 on both axes.
    Swap left/right outer columns, swap top/bottom outer rows.
    """
    w, h = img.size
    x1, x2 = w // 4, 3 * w // 4
    y1, y2 = h // 4, 3 * h // 4

    def crop(left, upper, right, lower):
        return img.crop((left, upper, right, lower))

    blocks = {
        (0, 0): crop(0,  0,  x1, y1),
        (0, 1): crop(x1, 0,  x2, y1),
        (0, 2): crop(x2, 0,  w,  y1),
        (1, 0): crop(0,  y1, x1, y2),
        (1, 1): crop(x1, y1, x2, y2),
        (1, 2): crop(x2, y1, w,  y2),
        (2, 0): crop(0,  y2, x1, h),
        (2, 1): crop(x1, y2, x2, h),
        (2, 2): crop(x2, y2, w,  h),
    }

    # Swap left<->right (col 0<->2), swap top<->bottom (row 0<->2)
    remap = {
        (0, 0): (2, 2),  (0, 1): (2, 1),  (0, 2): (2, 0),
        (1, 0): (1, 2),  (1, 1): (1, 1),  (1, 2): (1, 0),
        (2, 0): (0, 2),  (2, 1): (0, 1),  (2, 2): (0, 0),
    }

    col_x = [0, x1, x2]
    row_y = [0, y1, y2]

    out = Image.new(img.mode, (w, h))
    for (dst_row, dst_col), (src_row, src_col) in remap.items():
        out.paste(blocks[(src_row, src_col)], (col_x[dst_col], row_y[dst_row]))

    return out


def blend_seams(img: Image.Image, strip_width: int = 30) -> Image.Image:
    """
    Remove a 30px strip along every seam and inpaint with LaMa.

    Seams in the final image:
      Vertical:   x = w/4, w/2, 3w/4
      Horizontal: y = h/4, h/2, 3h/4
    """
    from simple_lama_inpainting import SimpleLama

    w, h = img.size
    half = strip_width // 2

    mask = Image.new("L", (w, h), 0)
    mask_arr = np.zeros((h, w), dtype=np.uint8)

    for x in [w // 4, w // 2, 3 * w // 4]:
        x0, x1 = max(0, x - half), min(w, x + half)
        mask_arr[:, x0:x1] = 255

    for y in [h // 4, h // 2, 3 * h // 4]:
        y0, y1 = max(0, y - half), min(h, y + half)
        mask_arr[y0:y1, :] = 255

    mask = Image.fromarray(mask_arr)

    import torch
    _orig_load = torch.jit.load
    def _cpu_load(f, **kwargs):
        kwargs.setdefault("map_location", "cpu")
        return _orig_load(f, **kwargs)
    torch.jit.load = _cpu_load
    try:
        lama = SimpleLama(device=torch.device("cpu"))
    finally:
        torch.jit.load = _orig_load

    return lama(img, mask)
