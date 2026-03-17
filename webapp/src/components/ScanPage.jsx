import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import Scanner from './Scanner';
import ProfileSelector from './ProfileSelector';
import useCameraCapture from '../hooks/useCameraCapture';
import BrandLogo from './BrandLogo';

const ScanPage = ({ onScanResult, isLoading, lastFailedBarcode = '', ocrQualityInfo, onAcceptPendingResult, onClearOcrQuality }) => {
    const [barcode, setBarcode] = useState('');
    const [isCameraMode, setIsCameraMode] = useState(false);
    const [selectedImage, setSelectedImage] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);

    // ── Label input mode: 'upload' | 'camera' ───
    const [labelMode, setLabelMode] = useState('upload');

    // ── Camera hook ──────────────────────────────
    const cam = useCameraCapture();

    // ── Manual edit state ────────────────────────
    const [editedText, setEditedText] = useState('');
    const [showManualEdit, setShowManualEdit] = useState(false);

    // ── Selected household profile ───────────────
    const [selectedProfileId, setSelectedProfileId] = useState(null);
    const [selectedProfileName, setSelectedProfileName] = useState('');

    const handleProfileSelect = (id, name) => {
        setSelectedProfileId(id);
        if (name) setSelectedProfileName(name);
    };

    // Stop camera when switching back to upload mode
    useEffect(() => {
        if (labelMode === 'upload') {
            cam.reset();
        }
    }, [labelMode]); // eslint-disable-line react-hooks/exhaustive-deps

    // Start camera when switching to camera mode
    useEffect(() => {
        if (labelMode === 'camera' && cam.state === 'idle') {
            cam.startCamera();
        }
    }, [labelMode]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Barcode submit ───────────────────────────
    const handleBarcodeSubmit = (e) => {
        e?.preventDefault();
        if (!barcode.trim()) return;
        onScanResult({
            type: 'barcode',
            barcode: barcode.trim(),
            userProfile: {},
            profileId: selectedProfileId,
            profileName: selectedProfileName,
        });
    };

    const handleScanSuccess = (decodedText) => {
        setBarcode(decodedText);
        setIsCameraMode(false);
        onScanResult({
            type: 'barcode',
            barcode: decodedText,
            userProfile: {},
            profileId: selectedProfileId,
            profileName: selectedProfileName,
        });
    };

    // ── Image upload (dropzone) ──────────────────
    const onDrop = useCallback((files) => {
        const file = files[0];
        if (!file) return;
        setSelectedImage(file);
        setPreviewUrl(URL.createObjectURL(file));
        clearOcrState();
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { 'image/*': ['.jpeg', '.jpg', '.png', '.webp'] },
        maxFiles: 1,
    });

    const clearImage = () => {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setSelectedImage(null);
        setPreviewUrl(null);
        clearOcrState();
    };

    const clearOcrState = () => {
        if (onClearOcrQuality) onClearOcrQuality();
        setEditedText('');
        setShowManualEdit(false);
    };

    // ── Submit image for analysis ────────────────
    const submitImage = (imageFile) => {
        onScanResult({
            type: 'label',
            imageFile,
            barcode: lastFailedBarcode,
            userProfile: {},
            profileId: selectedProfileId,
            profileName: selectedProfileName,
        });
    };

    const handleImageSubmit = () => {
        if (!selectedImage) return;
        submitImage(selectedImage);
    };

    // ── Camera "Use Photo" handler ───────────────
    const handleUsePhoto = () => {
        if (!cam.capturedBlob) return;
        const file = new File([cam.capturedBlob], 'camera-capture.jpg', { type: 'image/jpeg' });
        submitImage(file);
    };

    // ── Retake from OCR error ────────────────────
    const handleRetakeFromError = () => {
        clearOcrState();
        clearImage();
        setLabelMode('camera');
        // camera will auto-start via useEffect
    };

    const handleSwitchToUpload = () => {
        clearOcrState();
        clearImage();
        cam.reset();
        setLabelMode('upload');
    };

    // ── "Continue anyway" – accept the pending result despite low quality
    const handleContinueAnyway = () => {
        setShowManualEdit(true);
        if (ocrQualityInfo?.rawText) {
            setEditedText(ocrQualityInfo.rawText);
        }
    };

    // ── Manual edit: accept pending result (backend already analyzed it)
    const handleManualAnalyze = () => {
        if (onAcceptPendingResult) onAcceptPendingResult();
    };

    return (
        <div className="min-h-screen bg-bg1 text-gray-800">
            <div className="mx-auto max-w-2xl px-4 py-14">

                {/* Hero */}
                <div className="text-center mb-12 animate-fade-in">
                    <BrandLogo showTagline />
                    <p className="mt-4 text-lg text-gray-600">Scan. Understand. Decide.</p>
                    <p className="text-gray-400 text-sm mt-1">
                        Scan a barcode or upload a label photo to get personalized ingredient insights.
                    </p>
                </div>

                {/* Profile Selector */}
                <div className="mb-8 animate-slide-up">
                    <div className="glass-strong px-5 py-4">
                        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                            Scoring for
                        </label>
                        <ProfileSelector
                            selectedId={selectedProfileId}
                            onSelect={handleProfileSelect}
                        />
                    </div>
                </div>

                {/* ── Primary action: Label photo ──────── */}
                <div className="animate-slide-up mb-6">
                    {/* Barcode fallback banner */}
                    {lastFailedBarcode && (
                        <div className="mb-3 flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-200 px-4 py-2.5 text-sm text-amber-700 animate-fade-in">
                            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                            </svg>
                            <span>
                                Barcode <strong>{lastFailedBarcode}</strong> didn&apos;t have full data &mdash; upload a label photo to complete it.
                            </span>
                        </div>
                    )}

                    {/* ── Upload / Camera segmented toggle ── */}
                    <div className="flex justify-center mb-5" role="tablist" aria-label="Label input mode">
                        <div className="inline-flex bg-gray-100 rounded-full p-1">
                            <button
                                role="tab"
                                aria-selected={labelMode === 'upload'}
                                aria-label="Upload label photo"
                                onClick={() => setLabelMode('upload')}
                                className={`px-5 py-2 rounded-full text-sm font-semibold transition-all flex items-center gap-1.5 min-h-[40px] ${
                                    labelMode === 'upload' ? 'bg-brand text-white shadow' : 'text-gray-500 hover:text-brandDeep'
                                }`}
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                                </svg>
                                Upload
                            </button>
                            <button
                                role="tab"
                                aria-selected={labelMode === 'camera'}
                                aria-label="Use camera to capture label"
                                onClick={() => setLabelMode('camera')}
                                className={`px-5 py-2 rounded-full text-sm font-semibold transition-all flex items-center gap-1.5 min-h-[40px] ${
                                    labelMode === 'camera' ? 'bg-brand text-white shadow' : 'text-gray-500 hover:text-brandDeep'
                                }`}
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
                                </svg>
                                Camera
                            </button>
                        </div>
                    </div>

                    {/* ── OCR Quality Error Card ───────── */}
                    {ocrQualityInfo && !ocrQualityInfo.ok && !showManualEdit && (
                        <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-5 animate-fade-in">
                            <h4 className="font-bold text-amber-800 mb-2 flex items-center gap-2">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
                                </svg>
                                We couldn&apos;t read that clearly.
                            </h4>
                            <p className="text-sm text-amber-700 mb-3">Try these tips for a better scan:</p>
                            <ul className="text-sm text-amber-700 space-y-1 mb-4 ml-4">
                                <li className="flex items-start gap-2">
                                    <span className="mt-1 w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                                    Ensure the label fills most of the frame
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="mt-1 w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                                    Avoid glare and shadows
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="mt-1 w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                                    Hold steady and let the camera focus
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="mt-1 w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                                    Good, even lighting works best
                                </li>
                            </ul>
                            <div className="flex flex-wrap gap-3">
                                <button onClick={handleRetakeFromError} className="btn-primary text-sm px-4 py-2">
                                    Retake photo
                                </button>
                                <button onClick={handleSwitchToUpload} className="btn-secondary text-sm px-4 py-2">
                                    Try another upload
                                </button>
                            </div>
                            <button
                                onClick={handleContinueAnyway}
                                className="mt-3 text-xs text-amber-600 hover:text-amber-800 underline"
                            >
                                Continue anyway &rarr;
                            </button>
                        </div>
                    )}

                    {/* ── Manual edit fallback ────────── */}
                    {showManualEdit && (
                        <div className="mb-4 rounded-2xl border border-gray-200 bg-white p-5 animate-fade-in">
                            <label className="block text-sm font-semibold text-gray-700 mb-2">
                                Edit ingredients (optional)
                            </label>
                            <textarea
                                value={editedText}
                                onChange={(e) => setEditedText(e.target.value)}
                                placeholder="Paste or edit the ingredient list here..."
                                rows={5}
                                className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-800 placeholder-gray-400 focus:outline-none focus:border-brand transition-colors text-sm resize-y"
                            />
                            <div className="mt-3 flex justify-end">
                                <button onClick={handleManualAnalyze} disabled={isLoading} className="btn-primary text-sm px-5 py-2">
                                    {isLoading ? 'Analyzing...' : 'Analyze ingredients'}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ── UPLOAD MODE ─────────────────── */}
                    {labelMode === 'upload' && (
                        <>
                            <div
                                {...getRootProps()}
                                className={`upload-zone p-10 text-center ${isDragActive ? 'active' : ''} ${previewUrl ? 'border-solid border-brandLine' : ''}`}
                            >
                                <input {...getInputProps()} />
                                {!previewUrl ? (
                                    <div>
                                        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-brandTint flex items-center justify-center">
                                            <svg className="w-8 h-8 text-brandDeep" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                                            </svg>
                                        </div>
                                        <h3 className="text-xl font-bold mb-1 text-gray-800">
                                            {isDragActive ? 'Drop here' : 'Upload Ingredient Label'}
                                        </h3>
                                        <p className="text-gray-400 text-sm">
                                            Drag & drop or click -- JPEG, PNG, WebP (max 10 MB)
                                        </p>
                                    </div>
                                ) : (
                                    <div className="animate-fade-in">
                                        <img src={previewUrl} alt="Preview" className="max-h-64 mx-auto rounded-2xl shadow-lg mb-3 border border-gray-100" />
                                        <p className="text-emerald-600 font-semibold text-sm">Image ready</p>
                                    </div>
                                )}
                            </div>

                            {previewUrl && (
                                <div className="flex gap-4 justify-center mt-5">
                                    <button onClick={clearImage} className="btn-secondary text-sm">Clear</button>
                                    <button onClick={handleImageSubmit} disabled={isLoading} className="btn-primary text-sm flex items-center gap-1">
                                        {isLoading ? 'Analyzing...' : 'Analyze Label'}
                                    </button>
                                </div>
                            )}
                        </>
                    )}

                    {/* ── CAMERA MODE ─────────────────── */}
                    {labelMode === 'camera' && (
                        <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden">
                            {/* Hidden canvas for capture */}
                            <canvas ref={cam.canvasRef} className="hidden" />

                            {/* Requesting permission */}
                            {cam.state === 'requesting-permission' && (
                                <div className="p-10 text-center">
                                    <div className="w-12 h-12 mx-auto mb-4 rounded-full border-4 border-gray-200 border-t-brand animate-spin" />
                                    <p className="text-gray-500 text-sm">Requesting camera access...</p>
                                </div>
                            )}

                            {/* Camera error */}
                            {cam.state === 'error' && (
                                <div className="p-10 text-center">
                                    <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-red-50 flex items-center justify-center">
                                        <svg className="w-7 h-7 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                        </svg>
                                    </div>
                                    <p className="text-gray-700 font-semibold mb-1">{cam.errorMsg}</p>
                                    <p className="text-gray-400 text-sm mb-4">You can still upload a photo instead.</p>
                                    <div className="flex justify-center gap-3">
                                        <button onClick={() => cam.startCamera()} className="btn-secondary text-sm">
                                            Try again
                                        </button>
                                        <button onClick={() => setLabelMode('upload')} className="btn-primary text-sm">
                                            Switch to Upload
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Live camera feed */}
                            {cam.state === 'camera-live' && (
                                <div>
                                    <div className="relative bg-black">
                                        <video
                                            ref={cam.videoRef}
                                            autoPlay
                                            playsInline
                                            muted
                                            className="w-full max-h-80 object-cover"
                                        />
                                        {/* Viewfinder overlay */}
                                        <div className="absolute inset-0 pointer-events-none">
                                            <div className="absolute inset-4 border-2 border-white/30 rounded-xl" />
                                        </div>
                                    </div>
                                    <div className="p-4 flex justify-center gap-3">
                                        <button onClick={cam.capture} className="btn-primary text-sm px-6 py-2.5 flex items-center gap-2">
                                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                <circle cx="12" cy="12" r="10" />
                                                <circle cx="12" cy="12" r="4" fill="currentColor" />
                                            </svg>
                                            Capture
                                        </button>
                                    </div>
                                    <p className="text-center text-xs text-gray-400 pb-3">
                                        Position the ingredient label in the frame
                                    </p>
                                </div>
                            )}

                            {/* Captured preview */}
                            {cam.state === 'captured-preview' && cam.capturedUrl && (
                                <div>
                                    <div className="p-4">
                                        <img
                                            src={cam.capturedUrl}
                                            alt="Captured label"
                                            className="w-full max-h-72 object-contain rounded-xl border border-gray-100"
                                        />
                                    </div>
                                    <div className="px-4 pb-4 flex justify-center gap-3">
                                        <button onClick={cam.retake} className="btn-secondary text-sm px-5 py-2">
                                            Retake
                                        </button>
                                        <button onClick={handleUsePhoto} disabled={isLoading} className="btn-primary text-sm px-5 py-2">
                                            {isLoading ? 'Analyzing...' : 'Use Photo'}
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Idle state (shouldn't normally show, camera auto-starts) */}
                            {cam.state === 'idle' && labelMode === 'camera' && (
                                <div className="p-10 text-center">
                                    <button onClick={cam.startCamera} className="btn-primary text-sm px-6 py-2.5">
                                        Start Camera
                                    </button>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Divider */}
                <div className="flex items-center gap-4 mb-6">
                    <div className="flex-1 h-px bg-gray-200" />
                    <span className="text-gray-400 text-xs uppercase tracking-wider">or scan a barcode</span>
                    <div className="flex-1 h-px bg-gray-200" />
                </div>

                {/* ── Secondary action: Barcode scan ────── */}
                <div className="glass-strong p-6 mb-10 animate-slide-up">
                    <h3 className="text-lg font-semibold mb-4 text-gray-700 text-center">Scan or Enter Barcode</h3>

                    {/* Segmented control */}
                    <div className="flex justify-center mb-5" role="tablist" aria-label="Barcode input mode">
                        <div className="inline-flex bg-gray-100 rounded-full p-1">
                            <button
                                role="tab"
                                aria-selected={!isCameraMode}
                                aria-label="Enter barcode manually"
                                onClick={() => setIsCameraMode(false)}
                                className={`px-4 py-2 rounded-full text-sm font-semibold transition-all min-h-[40px] ${
                                    !isCameraMode ? 'bg-brand text-white shadow' : 'text-gray-500 hover:text-brandDeep'
                                }`}
                            >
                                Manual
                            </button>
                            <button
                                role="tab"
                                aria-selected={isCameraMode}
                                aria-label="Scan barcode with camera"
                                onClick={() => setIsCameraMode(true)}
                                className={`px-4 py-2 rounded-full text-sm font-semibold transition-all min-h-[40px] ${
                                    isCameraMode ? 'bg-brand text-white shadow' : 'text-gray-500 hover:text-brandDeep'
                                }`}
                            >
                                Camera
                            </button>
                        </div>
                    </div>

                    {isCameraMode ? (
                        <Scanner onScanSuccess={handleScanSuccess} onScanFailure={() => {}} />
                    ) : (
                        <form onSubmit={handleBarcodeSubmit} className="flex gap-2">
                            <input
                                value={barcode}
                                onChange={e => setBarcode(e.target.value)}
                                placeholder="Enter barcode number..."
                                aria-label="Barcode number"
                                className="flex-1 px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-gray-800 placeholder-gray-400 focus:outline-none focus:border-brand transition-colors"
                            />
                            <button
                                type="submit"
                                disabled={isLoading || !barcode}
                                aria-label="Search barcode"
                                className="btn-primary min-w-[48px] min-h-[48px] px-5 py-3 disabled:opacity-40 flex items-center justify-center"
                            >
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                                </svg>
                            </button>
                        </form>
                    )}
                </div>

                {/* Feature cards */}
                <div className="grid sm:grid-cols-3 gap-4 mt-8">
                    {[
                        {
                            title: 'AI Analysis',
                            desc: 'Groq-powered ingredient parsing & evidence lookup',
                            color: 'bg-brandTint text-brandDeep',
                            icon: (
                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                                </svg>
                            ),
                        },
                        {
                            title: 'Conflict Detection',
                            desc: 'Allergy, diet & caffeine flags tailored to you',
                            color: 'bg-emerald-50 text-emerald-600',
                            icon: (
                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                                </svg>
                            ),
                        },
                        {
                            title: 'Product Chat',
                            desc: 'Ask follow-up questions about any ingredient',
                            color: 'bg-amber-50 text-amber-600',
                            icon: (
                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                                </svg>
                            ),
                        },
                    ].map((f, i) => (
                        <div key={i} className="glass-strong p-5 text-center hover:shadow-card-hover transition-all">
                            <div className={`w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center ${f.color}`}>
                                {f.icon}
                            </div>
                            <h4 className="font-bold text-sm mb-1 text-gray-800">{f.title}</h4>
                            <p className="text-gray-400 text-xs">{f.desc}</p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default ScanPage;
