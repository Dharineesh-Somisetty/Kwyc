import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import Scanner from './Scanner';

const ScanPage = ({ onScanResult, isLoading }) => {
    const [barcode, setBarcode] = useState('');
    const [isCameraMode, setIsCameraMode] = useState(false);
    const [selectedImage, setSelectedImage] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);

    // ── User profile state ─────────────────────
    const [showProfile, setShowProfile] = useState(false);
    const [profile, setProfile] = useState({
        vegan: false,
        vegetarian: false,
        halal: false,
        allergies: '',
        caffeine_limit_mg: '',
        avoid_terms: '',
    });

    const buildProfilePayload = () => ({
        vegan: profile.vegan,
        vegetarian: profile.vegetarian,
        halal: profile.halal,
        allergies: profile.allergies
            ? profile.allergies.split(',').map(s => s.trim()).filter(Boolean)
            : [],
        caffeine_limit_mg: profile.caffeine_limit_mg ? Number(profile.caffeine_limit_mg) : null,
        avoid_terms: profile.avoid_terms
            ? profile.avoid_terms.split(',').map(s => s.trim()).filter(Boolean)
            : [],
    });

    // ── Barcode submit ─────────────────────────
    const handleBarcodeSubmit = (e) => {
        e?.preventDefault();
        if (!barcode.trim()) return;
        onScanResult({ type: 'barcode', barcode: barcode.trim(), userProfile: buildProfilePayload() });
    };

    const handleScanSuccess = (decodedText) => {
        setBarcode(decodedText);
        setIsCameraMode(false);
        onScanResult({ type: 'barcode', barcode: decodedText, userProfile: buildProfilePayload() });
    };

    // ── Image upload ───────────────────────────
    const onDrop = useCallback((files) => {
        const file = files[0];
        if (!file) return;
        setSelectedImage(file);
        setPreviewUrl(URL.createObjectURL(file));
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { 'image/*': ['.jpeg', '.jpg', '.png', '.webp'] },
        maxFiles: 1,
    });

    const handleImageSubmit = () => {
        if (!selectedImage) return;
        onScanResult({ type: 'label', imageFile: selectedImage, userProfile: buildProfilePayload() });
    };

    const clearImage = () => {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setSelectedImage(null);
        setPreviewUrl(null);
    };

    // ── Toggle helper ──────────────────────────
    const Toggle = ({ label, checked, onChange }) => (
        <label className="flex items-center gap-2 cursor-pointer">
            <div
                className={`w-9 h-5 flex items-center rounded-full p-0.5 transition-colors ${checked ? 'bg-primary-500' : 'bg-white/15'}`}
                onClick={onChange}
            >
                <div className={`bg-white w-4 h-4 rounded-full shadow transition-transform ${checked ? 'translate-x-4' : ''}`} />
            </div>
            <span className="text-sm text-gray-300">{label}</span>
        </label>
    );

    return (
        <div className="container mx-auto px-4 py-12 max-w-2xl">
            {/* Hero */}
            <div className="text-center mb-10 animate-fade-in">
                <h1 className="text-5xl sm:text-6xl font-display font-bold mb-3 gradient-text">LabelLens</h1>
                <p className="text-lg text-gray-300">Scan. Understand. Decide.</p>
                <p className="text-gray-500 text-sm mt-1">Scan a barcode or upload a label photo to get personalized ingredient insights.</p>
            </div>

            {/* Preferences toggle */}
            <div className="mb-6 animate-slide-up">
                <button
                    onClick={() => setShowProfile(p => !p)}
                    className="w-full text-left glass-strong px-5 py-3 flex items-center justify-between rounded-xl"
                >
                    <span className="text-gray-200 font-semibold text-sm">⚙️ My Preferences</span>
                    <span className="text-gray-400 text-xs">{showProfile ? '▲' : '▼'}</span>
                </button>
                {showProfile && (
                    <div className="glass p-5 mt-2 space-y-4 animate-fade-in rounded-xl">
                        <div className="flex flex-wrap gap-6">
                            <Toggle label="Vegan" checked={profile.vegan} onChange={() => setProfile(p => ({ ...p, vegan: !p.vegan }))} />
                            <Toggle label="Vegetarian" checked={profile.vegetarian} onChange={() => setProfile(p => ({ ...p, vegetarian: !p.vegetarian }))} />
                            <Toggle label="Halal" checked={profile.halal} onChange={() => setProfile(p => ({ ...p, halal: !p.halal }))} />
                        </div>
                        <input
                            value={profile.allergies}
                            onChange={e => setProfile(p => ({ ...p, allergies: e.target.value }))}
                            placeholder="Allergies (comma-separated, e.g. peanuts, milk)"
                            className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
                        />
                        <input
                            value={profile.caffeine_limit_mg}
                            onChange={e => setProfile(p => ({ ...p, caffeine_limit_mg: e.target.value }))}
                            placeholder="Caffeine limit (mg, optional)"
                            type="number"
                            className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
                        />
                        <input
                            value={profile.avoid_terms}
                            onChange={e => setProfile(p => ({ ...p, avoid_terms: e.target.value }))}
                            placeholder="Avoid terms (comma-separated, e.g. palm oil, MSG)"
                            className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
                        />
                    </div>
                )}
            </div>

            {/* Barcode section */}
            <div className="glass-strong p-6 mb-6 animate-slide-up">
                <h3 className="text-lg font-semibold mb-4 text-gray-200 text-center">Scan or Enter Barcode</h3>

                <div className="flex justify-center gap-4 mb-5">
                    <button
                        onClick={() => setIsCameraMode(false)}
                        className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${!isCameraMode ? 'bg-white text-primary-900' : 'bg-white/10 text-gray-400 hover:bg-white/20'}`}
                    >
                        ⌨️ Manual
                    </button>
                    <button
                        onClick={() => setIsCameraMode(true)}
                        className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${isCameraMode ? 'bg-white text-primary-900' : 'bg-white/10 text-gray-400 hover:bg-white/20'}`}
                    >
                        📸 Camera
                    </button>
                </div>

                {isCameraMode ? (
                    <Scanner onScanSuccess={handleScanSuccess} onScanFailure={() => {}} />
                ) : (
                    <form onSubmit={handleBarcodeSubmit} className="flex gap-2">
                        <input
                            value={barcode}
                            onChange={e => setBarcode(e.target.value)}
                            placeholder="Enter barcode number…"
                            className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 transition-colors"
                        />
                        <button
                            type="submit"
                            disabled={isLoading || !barcode}
                            className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-xl font-semibold transition-colors disabled:opacity-50"
                        >
                            {isLoading ? '…' : '🔍'}
                        </button>
                    </form>
                )}
            </div>

            {/* Divider */}
            <div className="flex items-center gap-4 mb-6">
                <div className="flex-1 h-px bg-white/10" />
                <span className="text-gray-500 text-xs uppercase tracking-wider">or upload a label photo</span>
                <div className="flex-1 h-px bg-white/10" />
            </div>

            {/* Image upload */}
            <div className="animate-slide-up">
                <div
                    {...getRootProps()}
                    className={`upload-zone p-10 text-center ${isDragActive ? 'active' : ''} ${previewUrl ? 'border-solid' : ''}`}
                >
                    <input {...getInputProps()} />
                    {!previewUrl ? (
                        <div>
                            <div className="text-5xl mb-3 animate-float">📷</div>
                            <h3 className="text-xl font-bold mb-1 text-white">
                                {isDragActive ? 'Drop here' : 'Upload Ingredient Label'}
                            </h3>
                            <p className="text-gray-400 text-sm">Drag & drop or click · JPEG, PNG, WebP (max 10 MB)</p>
                        </div>
                    ) : (
                        <div className="animate-fade-in">
                            <img src={previewUrl} alt="Preview" className="max-h-64 mx-auto rounded-lg shadow-2xl mb-3" />
                            <p className="text-green-400 font-semibold text-sm">✓ Image ready</p>
                        </div>
                    )}
                </div>

                {previewUrl && (
                    <div className="flex gap-4 justify-center mt-5">
                        <button onClick={clearImage} className="btn-secondary text-sm">Clear</button>
                        <button onClick={handleImageSubmit} disabled={isLoading} className="btn-primary text-sm flex items-center gap-1">
                            {isLoading ? 'Analyzing…' : 'Analyze Label →'}
                        </button>
                    </div>
                )}
            </div>

            {/* Feature cards */}
            <div className="grid sm:grid-cols-3 gap-4 mt-16">
                {[
                    { icon: '🔬', title: 'AI Analysis', desc: 'Groq-powered ingredient parsing & evidence lookup' },
                    { icon: '🛡️', title: 'Conflict Detection', desc: 'Allergy, diet & caffeine flags tailored to you' },
                    { icon: '💬', title: 'Product Chat', desc: 'Ask follow-up questions about any ingredient' },
                ].map((f, i) => (
                    <div key={i} className="glass-strong p-5 text-center hover:bg-white/20 transition-all">
                        <div className="text-3xl mb-2">{f.icon}</div>
                        <h4 className="font-bold text-sm mb-1 text-white">{f.title}</h4>
                        <p className="text-gray-400 text-xs">{f.desc}</p>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default ScanPage;
