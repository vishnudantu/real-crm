/** Client-side image resize/compress for uploads.
 *
 * The founder requirement is that uploads are compressed before they leave the
 * device. Browser-only pieces (decode/encode) are isolated behind
 * `compressImageFile`; the pure dimension math in `scaledDimensions` is unit
 * tested. JPEG re-encode strips EXIF and typically cuts phone photos ~10x.
 */

/** Max edge (px) a compressed image keeps. 2560 covers A4 at ~300 DPI. */
export const MAX_IMAGE_EDGE_PX = 2560;

/** JPEG quality used for the re-encode. */
export const JPEG_QUALITY = 0.82;

export interface ScaledDimensions {
  width: number;
  height: number;
}

/**
 * Compute the dimensions that keep the aspect ratio while fitting both edges
 * inside `maxEdge`. Never upscales: images already within the limit pass
 * through unchanged. Pure and unit tested.
 */
export function scaledDimensions(
  width: number,
  height: number,
  maxEdge: number = MAX_IMAGE_EDGE_PX,
): ScaledDimensions {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return { width: 0, height: 0 };
  }
  const longestEdge = Math.max(width, height);
  if (longestEdge <= maxEdge) {
    return { width: Math.round(width), height: Math.round(height) };
  }
  const scale = maxEdge / longestEdge;
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

export interface CompressedImage {
  blob: Blob;
  width: number;
  height: number;
  originalBytes: number;
  compressedBytes: number;
  wasResized: boolean;
}

interface ImageDecodeResult {
  bitmap: ImageBitmap;
  width: number;
  height: number;
}

async function decodeImage(file: Blob): Promise<ImageDecodeResult> {
  if (typeof createImageBitmap === "function") {
    const bitmap = await createImageBitmap(file);
    return { bitmap, width: bitmap.width, height: bitmap.height };
  }
  throw new Error("This browser cannot prepare images for upload. Please send the photo as-is.");
}

/**
 * Resize and re-encode an image file to JPEG within the backend's 10 MB limit.
 * Falls back to the original file when compression would not help (already
 * small, or the result came out larger). The caller receives the blob to send.
 */
export async function compressImageFile(
  file: File,
  options: { maxEdge?: number; quality?: number } = {},
): Promise<CompressedImage> {
  const maxEdge = options.maxEdge ?? MAX_IMAGE_EDGE_PX;
  const quality = options.quality ?? JPEG_QUALITY;

  const { bitmap, width, height } = await decodeImage(file);
  try {
    const target = scaledDimensions(width, height, maxEdge);
    const canvas = document.createElement("canvas");
    canvas.width = target.width;
    canvas.height = target.height;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Canvas is unavailable in this browser.");
    }
    context.drawImage(bitmap, 0, 0, target.width, target.height);

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((result) => resolve(result), "image/jpeg", quality);
    });
    if (!blob) {
      throw new Error("This image could not be processed. Please try a different photo.");
    }

    // If compression made it bigger (rare: tiny PNGs, already-JPEG artifacts),
    // the original is the better upload.
    if (blob.size >= file.size) {
      return {
        blob: file,
        width,
        height,
        originalBytes: file.size,
        compressedBytes: file.size,
        wasResized: false,
      };
    }

    return {
      blob,
      width: target.width,
      height: target.height,
      originalBytes: file.size,
      compressedBytes: blob.size,
      wasResized: target.width !== width || target.height !== height,
    };
  } finally {
    bitmap.close();
  }
}

/**
 * Prepare a picked file for upload: images are compressed, PDFs (and anything
 * else the backend accepts) pass through untouched. Returns the blob plus the
 * content type the backend should record.
 */
export async function prepareUpload(
  file: File,
): Promise<{ blob: Blob; contentType: string }> {
  if (shouldPassThrough(file.type)) {
    return { blob: file, contentType: normalizedType(file.type) };
  }
  const compressed = await compressImageFile(file);
  return { blob: compressed.blob, contentType: "image/jpeg" };
}

function normalizedType(type: string): string {
  return type.split(";")[0]?.trim().toLowerCase() ?? "application/octet-stream";
}

/** PDFs and unknown types bypass compression; images go through it. */
function shouldPassThrough(type: string): boolean {
  const normalized = normalizedType(type);
  return normalized === "application/pdf" || !normalized.startsWith("image/");
}
