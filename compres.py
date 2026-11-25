import io
import os
from PIL import Image, ImageOps

MAX_UPLOAD_MB = 10
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

DEFAULT_TARGET_KB = 1000
DEFAULT_MAX_DIM = 1920
DEFAULT_MIN_QUALITY = 60


def compress_image_bytes(
    file_bytes: bytes,
    filename: str,
    target_kb: int = DEFAULT_TARGET_KB,
    max_dim: int = DEFAULT_MAX_DIM,
    min_quality: int = DEFAULT_MIN_QUALITY,
    max_upload_bytes: int = MAX_UPLOAD_BYTES,
) -> dict:
    """
    Mengompres bytes gambar di memori dengan batas upload maksimal 10 MB.
    Menjaga ketajaman visual dengan mengatur resolusi (dimensi) dan batas kualitas minimum
    bahkan ketika target ukuran ditekan hingga < 100 KB.
    """
    original_size = len(file_bytes)
    if original_size > max_upload_bytes:
        raise ValueError(
            f"Ukuran file '{filename}' ({original_size / (1024 * 1024):.2f} MB) "
            f"melebihi batas maksimal {MAX_UPLOAD_MB} MB."
        )

    with Image.open(io.BytesIO(file_bytes)) as raw_img:
        # Perbaiki orientasi kamera/HP berdasarkan metadata EXIF
        img = ImageOps.exif_transpose(raw_img)

        # Konversi ke RGB agar aman disimpan sebagai JPEG (beri latar putih jika ada transparansi)
        if img.mode in ("RGBA", "LA", "P"):
            alpha_img = img.convert("RGBA")
            background = Image.new("RGB", alpha_img.size, (255, 255, 255))
            background.paste(alpha_img, mask=alpha_img.split()[-1])
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        base_w, base_h = img.size

        # Jika target sangat ketat (< 150 KB), mulai dari resolusi yang lebih proporsional
        start_dim = min(max_dim, 1280) if target_kb <= 150 else max_dim

        # Kandidat dimensi bertingkat (dari resolusi tertinggi ke batas aman HD/ringkas)
        dim_candidates = []
        curr_dim = start_dim
        while curr_dim >= 800:
            dim_candidates.append(curr_dim)
            if curr_dim > 1600:
                curr_dim = 1600
            elif curr_dim > 1280:
                curr_dim = 1280
            elif curr_dim > 960:
                curr_dim = 960
            elif curr_dim > 800:
                curr_dim = 800
            else:
                break

        best_bytes = b""
        best_quality = min_quality
        best_dims = (base_w, base_h)
        found_target = False

        # Tahap 1: Coba capai target_kb sambil menjaga kualitas >= min_quality
        for dim in dim_candidates:
            if max(base_w, base_h) > dim:
                if base_w >= base_h:
                    new_w = dim
                    new_h = max(1, int(base_h * (dim / base_w)))
                else:
                    new_h = dim
                    new_w = max(1, int(base_w * (dim / base_h)))
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            else:
                resized = img
                new_w, new_h = base_w, base_h

            for q in range(90, min_quality - 1, -5):
                buf = io.BytesIO()
                resized.save(
                    buf,
                    format="JPEG",
                    quality=q,
                    optimize=True,
                    progressive=True,
                )
                data = buf.getvalue()
                size_kb = len(data) / 1024

                # Simpan kandidat terbaik sejauh ini
                if not best_bytes or (
                    (len(best_bytes) / 1024 > target_kb and size_kb < len(best_bytes) / 1024)
                    or (size_kb <= target_kb and q > best_quality)
                ):
                    best_bytes = data
                    best_quality = q
                    best_dims = (new_w, new_h)

                if size_kb <= target_kb:
                    found_target = True
                    break

            if found_target:
                break

        # Tahap 2: Jika target sangat kecil (mis. < 100 KB) belum tercapai di min_quality,
        # turunkan kualitas perlahan hingga maksimal 45 pada resolusi paling ringkas
        if not found_target and (len(best_bytes) / 1024) > target_kb:
            smallest_dim = dim_candidates[-1] if dim_candidates else 800
            if max(base_w, base_h) > smallest_dim:
                if base_w >= base_h:
                    new_w = smallest_dim
                    new_h = max(1, int(base_h * (smallest_dim / base_w)))
                else:
                    new_h = smallest_dim
                    new_w = max(1, int(base_w * (smallest_dim / base_h)))
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            else:
                resized = img
                new_w, new_h = base_w, base_h

            for q in range(min_quality - 5, 44, -5):
                buf = io.BytesIO()
                resized.save(
                    buf,
                    format="JPEG",
                    quality=q,
                    optimize=True,
                    progressive=True,
                )
                data = buf.getvalue()
                best_bytes = data
                best_quality = q
                best_dims = (new_w, new_h)
                if (len(data) / 1024) <= target_kb:
                    break

    base_name = os.path.splitext(filename)[0]
    compressed_size = len(best_bytes)
    saved_bytes = max(0, original_size - compressed_size)
    saved_percent = (saved_bytes / original_size * 100) if original_size > 0 else 0.0

    return {
        "name": filename,
        "output_name": f"compressed_{base_name}.jpg",
        "original_size": original_size,
        "compressed_size": compressed_size,
        "saved_bytes": saved_bytes,
        "saved_percent": round(saved_percent, 2),
        "quality_used": best_quality,
        "dimensions": f"{best_dims[0]}x{best_dims[1]}",
        "data": best_bytes,
        "mime": "image/jpeg",
    }