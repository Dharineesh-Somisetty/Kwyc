import { useState, useRef, useCallback, useEffect } from 'react';

/**
 * Custom hook to manage camera stream lifecycle: start, capture, stop.
 * Handles permission errors gracefully and ensures tracks are released on cleanup.
 */
export default function useCameraCapture() {
  const [state, setState] = useState('idle');
  // idle | requesting-permission | camera-live | captured-preview | error
  const [errorMsg, setErrorMsg] = useState('');
  const [capturedBlob, setCapturedBlob] = useState(null);
  const [capturedUrl, setCapturedUrl] = useState(null);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const canvasRef = useRef(null);

  /** Stop all tracks on the current stream */
  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  /** Start camera */
  const startCamera = useCallback(async () => {
    setState('requesting-permission');
    setErrorMsg('');
    setCapturedBlob(null);
    if (capturedUrl) {
      URL.revokeObjectURL(capturedUrl);
      setCapturedUrl(null);
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setState('camera-live');
    } catch (err) {
      let msg = 'Camera access was denied.';
      if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        msg = 'No camera found on this device.';
      } else if (err.name === 'NotReadableError') {
        msg = 'Camera is in use by another app.';
      }
      setErrorMsg(msg);
      setState('error');
    }
  }, [capturedUrl]);

  /** Capture current frame from video */
  const capture = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        setCapturedBlob(blob);
        setCapturedUrl(URL.createObjectURL(blob));
        stopStream();
        setState('captured-preview');
      },
      'image/jpeg',
      0.92,
    );
  }, [stopStream]);

  /** Retake – restart camera */
  const retake = useCallback(() => {
    if (capturedUrl) URL.revokeObjectURL(capturedUrl);
    setCapturedBlob(null);
    setCapturedUrl(null);
    startCamera();
  }, [capturedUrl, startCamera]);

  /** Full reset back to idle */
  const reset = useCallback(() => {
    stopStream();
    if (capturedUrl) URL.revokeObjectURL(capturedUrl);
    setCapturedBlob(null);
    setCapturedUrl(null);
    setErrorMsg('');
    setState('idle');
  }, [stopStream, capturedUrl]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStream();
    };
  }, [stopStream]);

  return {
    state,
    errorMsg,
    capturedBlob,
    capturedUrl,
    videoRef,
    canvasRef,
    startCamera,
    capture,
    retake,
    reset,
    stopStream,
  };
}
