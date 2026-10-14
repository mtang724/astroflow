"""Raw frames of any kind: FITS from astronomy cameras and the RAW files of DSLR and mirrorless cameras.

Capture programs write FITS with a header (IMAGETYP, EXPTIME, GAIN, CCD-TEMP ...). A camera's own RAW files (CR2, CR3,
NEF, ARW, DNG, RAF, ORF, RW2, PEF ...) carry EXIF instead: exposure, ISO, the camera and the capture time on the
camera's clock (local time), but never the frame type, which comes from the file or folder name. header() gives both as
FITS keywords so the rest of astroflow reads them the same way. WBPP reads RAW files itself (PixInsight's RAW module
loads the CFA data, Bayer or X-Trans, with the same metadata).

    frameio.is_frame(path)                  FITS or camera RAW
    frameio.frame_files(folder)             the frames in a folder (and below it: multi-night targets have subfolders)
    frameio.header(path)                    FITS header, or a RAW file's metadata as FITS keywords
    frameio.read_luminance(path)            binned linear luminance for measuring stars and background
"""
import struct
from pathlib import Path

import numpy as np
from astropy.io import fits

FITS_SUFFIXES = (".fit", ".fits", ".fts")
RAW_SUFFIXES = (".3fr", ".arw", ".cr2", ".cr3", ".crw", ".dng", ".erf", ".iiq", ".kdc", ".mef", ".mos", ".mrw",
                ".nef", ".nrw", ".orf", ".pef", ".raf", ".rw2", ".rwl", ".sr2", ".srf", ".srw", ".x3f")


def is_fits(path):
    return Path(path).suffix.lower() in FITS_SUFFIXES


def is_raw(path):
    return Path(path).suffix.lower() in RAW_SUFFIXES


def is_frame(path):
    return is_fits(path) or is_raw(path)


def frame_files(folder, recursive=True):
    """Frames in `folder`, sorted (with recursive=True also those in subfolders, e.g. a multi-night target's
    Light/NIGHT_2026May17/)."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    found = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(p for p in found if p.is_file() and is_frame(p))


# ----------------------------------------------------------------------------------------------- metadata

def header(path):
    """FITS keywords of a frame: the FITS header itself, or for a camera RAW file INSTRUME, EXPTIME, ISO, DATE-LOC (the
    camera's clock), NAXIS1/2, FOCALLEN and CFATYPE (BAYER / X-TRANS). Raises OSError / ValueError for unreadable
    files."""
    if not is_raw(path):
        return fits.getheader(path)
    import rawpy
    raw = rawpy.RawPy()
    try:
        raw.open_file(str(path))                      # metadata only: the pixels are not decoded
        other, sizes = raw.other, raw.sizes
        pattern = raw.raw_pattern
    except (rawpy.LibRawError, OSError) as e:
        raise ValueError(f"not a readable RAW file: {e}") from e
    finally:
        raw.close()
    when = other.timestamp if other.timestamp and other.timestamp.year > 1990 else None
    return {"INSTRUME": camera_name(path),
            "EXPTIME": float(other.shutter_speed or 0),
            "ISO": round(other.iso_speed) if other.iso_speed else None,
            "DATE-LOC": when.isoformat(timespec="seconds") if when else None,
            "NAXIS1": sizes.width, "NAXIS2": sizes.height,
            "FOCALLEN": round(float(other.focal_length), 1) if other.focal_length else None,
            "CFATYPE": "X-TRANS" if pattern is not None and pattern.shape == (6, 6) else "BAYER"}


def camera_name(path):
    """'FUJIFILM X-T30', 'Canon EOS 6D', 'NIKON D5100' ... from the RAW file's own header, '' when it has none.
    TIFF-based files (CR2, NEF, ARW, DNG, PEF, ORF, RW2 ...) keep Make and Model in their first IFD, Canon CR3 in a
    TIFF block (box CMT1), Fujifilm RAF writes the model into its file header."""
    try:
        with open(path, "rb") as f:
            head = f.read(1 << 18)
    except OSError:
        return ""
    if head.startswith(b"FUJIFILM"):
        model = head[28:60].split(b"\0")[0].decode("ascii", "replace").strip()
        return f"FUJIFILM {model}" if model else "FUJIFILM"
    if head[4:8] == b"ftyp":                          # ISO base media (CR3)
        at = head.find(b"CMT1")
        tags = _tiff_strings(head[at + 4:]) if at > 4 else {}
    else:
        tags = _tiff_strings(head)
    make, model = tags.get(0x010F, ""), tags.get(0x0110, "")
    brand = make.split()[0] if make else ""
    if not brand or model.lower().startswith(brand.lower()):
        return model or make
    return f"{brand} {model}".strip()


def _tiff_strings(buf):
    """ASCII tags of a TIFF block's first IFD: {tag: text}. {} for anything that is not a TIFF."""
    order = {b"II": "<", b"MM": ">"}.get(bytes(buf[:2]))
    if order is None:
        return {}
    out = {}
    try:
        ifd = struct.unpack_from(order + "I", buf, 4)[0]
        for i in range(struct.unpack_from(order + "H", buf, ifd)[0]):
            entry = ifd + 2 + 12 * i
            tag, kind, count, value = struct.unpack_from(order + "HHII", buf, entry)
            if kind == 2:                             # ASCII; up to 4 bytes are stored in the entry itself
                start = entry + 8 if count <= 4 else value
                out[tag] = bytes(buf[start:start + count]).split(b"\0")[0].decode("ascii", "replace").strip()
    except struct.error:
        pass
    return out


# ----------------------------------------------------------------------------------------------- pixels

def read_luminance(path):
    """A frame's linear signal as a float32 image scaled to 0..1 (1 = the sensor's saturation level), with colour
    filter arrays binned to luminance (Bayer 2x2, X-Trans 3x3) so the colour pattern does not look like structure;
    mono frames are binned 2x2 as well (stars and background are measured, not detail). Returns (image, bin)."""
    if is_raw(path):
        import rawpy
        with rawpy.imread(str(path)) as raw:
            data = raw.raw_image_visible.astype(np.float32)
            black = float(np.mean(raw.black_level_per_channel))
            white = float(raw.white_level)
            xtrans = raw.raw_pattern is not None and raw.raw_pattern.shape == (6, 6)
        img = (data - black) / max(white - black, 1.0)
        b = 3 if xtrans else 2
    else:
        data = fits.getdata(path)                     # 16-bit camera data arrives as uint16 (BZERO applied)
        if data is None or data.ndim != 2:
            raise ValueError("not a single-plane image")
        img = data.astype(np.float32)
        if data.dtype.kind in "iu":
            img /= float(np.iinfo(data.dtype).max)
        b = 2
    return _bin(img, b), b


def _bin(img, b):
    hh, ww = img.shape[0] // b * b, img.shape[1] // b * b
    return img[:hh, :ww].reshape(hh // b, b, ww // b, b).mean(axis=(1, 3), dtype=np.float32)
