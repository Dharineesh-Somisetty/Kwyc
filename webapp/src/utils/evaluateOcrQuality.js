/**
 * Evaluate OCR output quality and decide if a retake should be suggested.
 *
 * @param {string} text       – extracted text from OCR
 * @param {{ confidence?: number }} [meta] – optional metadata (e.g. confidence score)
 * @returns {{ ok: boolean, reasons: string[] }}
 */
export default function evaluateOcrQuality(text, meta = {}) {
  const reasons = [];

  if (!text || typeof text !== 'string') {
    return { ok: false, reasons: ['No text could be extracted from the image.'] };
  }

  const trimmed = text.trim();

  // 1. Too short
  if (trimmed.length < 80) {
    reasons.push('Extracted text is very short — the label may not be fully visible.');
  }

  // 2. Low alphabetic ratio (garbage characters)
  const alphaCount = (trimmed.match(/[a-zA-Z]/g) || []).length;
  if (trimmed.length > 0 && alphaCount / trimmed.length < 0.5) {
    reasons.push('Text contains too many non-alphabetic characters — image may be blurry.');
  }

  // 3. Too few words
  const words = trimmed.split(/\s+/).filter(Boolean);
  if (words.length < 15) {
    reasons.push('Very few words detected — try filling the frame with the label.');
  }

  // 4. No ingredient separators (commas / semicolons)
  if (!/[,;]/.test(trimmed)) {
    reasons.push('No ingredient separators found — this may not be an ingredient list.');
  }

  // 5. Confidence threshold (if provided by OCR engine)
  if (typeof meta.confidence === 'number' && meta.confidence < 0.6) {
    reasons.push('OCR confidence is low — try better lighting or holding steady.');
  }

  return { ok: reasons.length === 0, reasons };
}
