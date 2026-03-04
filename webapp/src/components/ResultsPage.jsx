import { useState } from 'react';
import ChatPanel from './ChatPanel';
import ScoreGauge from './ScoreGauge';
import NutritionStatusBadge from './NutritionStatusBadge';
import Sparkline from './Sparkline';

/* -- severity helpers (light theme) ------------ */
const severityColor = {
    high: 'border-red-400 bg-red-50 text-red-700',
    warn: 'border-amber-400 bg-amber-50 text-amber-700',
    info: 'border-indigo-400 bg-indigo-50 text-indigo-700',
};

/* -- grade pill color (light theme) ------------ */
const gradeColor = {
    A: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    B: 'bg-emerald-50 text-emerald-600 border-emerald-200',
    C: 'bg-amber-50 text-amber-700 border-amber-200',
    D: 'bg-orange-50 text-orange-700 border-orange-200',
    F: 'bg-red-50 text-red-700 border-red-200',
};

/* -- derive nutrition status from existing data -- */
const deriveNutritionStatus = (product, product_score, nutrition) => {
    const conf = product_score?.nutrition_confidence;
    if (conf === 'high' && product?.barcode) return 'verified_barcode';
    if (nutrition && (conf === 'medium' || conf === 'high')) return 'extracted_photo';
    return 'not_detected';
};

/* -- processing status helper (human-readable) -- */
const processingStatusFromScore = (score, upfSignalsPresent) => {
    if (upfSignalsPresent) {
        return {
            label: 'Ultra-processed signals detected',
            colorClass: 'bg-red-50 text-red-700 border-red-200',
            icon: '⚠️',
            description: 'Contains ingredients commonly associated with ultra-processed foods.',
        };
    }
    if (score >= 85) {
        return {
            label: 'Minimally processed',
            colorClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
            icon: '🌿',
            description: 'Close to its natural state with minimal processing.',
        };
    }
    if (score >= 60) {
        return {
            label: 'Moderately processed',
            colorClass: 'bg-amber-50 text-amber-700 border-amber-200',
            icon: '🔄',
            description: 'Has undergone moderate processing.',
        };
    }
    return {
        label: 'Highly processed',
        colorClass: 'bg-red-50 text-red-700 border-red-200',
        icon: '⚠️',
        description: 'Has undergone significant processing.',
    };
};

/* -- fallback badge maps for when no score available -- */
const fallbackBadge = {
    minimally_processed: { label: 'Minimally Processed', colorClass: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: '🌿', description: '' },
    processed:           { label: 'Processed',            colorClass: 'bg-amber-50 text-amber-700 border-amber-200',    icon: '🔄', description: '' },
    upf_signals:         { label: 'UPF Signals Detected', colorClass: 'bg-red-50 text-red-700 border-red-200',          icon: '⚠️', description: '' },
};

/* -- Segmented toggle pill component ------------ */
const ViewToggle = ({ view, onChange }) => {
    const tabs = [
        { key: 'serving', label: 'Per serving' },
        { key: '100g', label: 'Per 100g' },
    ];
    return (
        <div className="inline-flex items-center bg-gray-100 border border-gray-200 rounded-full p-0.5">
            {tabs.map((t) => (
                <button
                    key={t.key}
                    onClick={() => onChange(t.key)}
                    className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 ${
                        view === t.key
                            ? 'bg-indigo-100 text-indigo-700 border border-indigo-200 shadow-sm'
                            : 'text-gray-500 hover:text-gray-700'
                    }`}
                >
                    {t.label}
                </button>
            ))}
        </div>
    );
};

/* ═══════════════════════════════════════════════════
   ResultsPage
   ═══════════════════════════════════════════════════ */
const ResultsPage = ({ data, onReset, scoredForName }) => {
    const {
        session_id,
        product,
        product_score,
        nutrition,
        nutrition_per_serving,
        ingredients,
        umbrella_terms,
        allergen_statements,
        flags,
        evidence,
        personalized_summary,
        disclaimer,
        nutrition_status: apiNutritionStatus,
        nutrition_source,
    } = data;

    /* Determine default view from backend */
    const defaultView = product_score?.primary_nutrition_view || '100g';
    const [nutritionView, setNutritionView] = useState(defaultView);

    /* Portion info */
    const portionInfo = product_score?.portion_info;
    const isPortionSensitive = portionInfo?.portion_sensitive ?? false;

    /* Dual nutrition scores */
    const nutScore100g = product_score?.nutrition_score_100g;
    const nutScoreServing = product_score?.nutrition_score_serving;
    const hasBothViews = nutScore100g != null && nutScoreServing != null;

    /* Active view score */
    const activeNutScore = nutritionView === 'serving' ? nutScoreServing : nutScore100g;

    /* Display score: prefer active dual view, fallback to top-level */
    const displayScore = activeNutScore?.score ?? product_score?.score ?? 50;
    const displayGrade = activeNutScore?.grade ?? product_score?.grade ?? 'C';

    /* Use API-provided status if available, else derive */
    const nutritionStatus = apiNutritionStatus || deriveNutritionStatus(product, product_score, nutrition);

    /* Resolve split scoring objects */
    const nutScoreObj  = product_score?.nutrition_score;
    const procObj      = product_score?.processing;
    const procBadge    = procObj || product_score?.processing_badge;
    const procLevel    = procBadge?.level;
    const procScore    = procObj?.processing_score;
    const procSignals  = procBadge?.signals ?? [];
    const procDetails  = procObj?.details ?? [];

    /* Processing status (human-readable) */
    const upfSignalsPresent = procLevel === 'upf_signals' || procSignals.length > 0;
    const processingStatus = procScore != null
        ? processingStatusFromScore(procScore, upfSignalsPresent)
        : procLevel
            ? (fallbackBadge[procLevel] || fallbackBadge.processed)
            : null;

    /* Build stat cards based on current view */
    const buildStatCards = () => {
        if (nutritionView === 'serving' && nutrition_per_serving) {
            return [
                { label: 'Calories', value: nutrition_per_serving.calories,        unit: 'kcal', warn: v => v > 400, cardClass: 'stat-card-cyan',   color: '#14b8a6', sparkVariant: 'wave', suffix: '/serving' },
                { label: 'Sodium',   value: nutrition_per_serving.sodium_mg,       unit: 'mg',   warn: v => v > 600, cardClass: 'stat-card-purple', color: '#6366f1', sparkVariant: 'bar',  suffix: '/serving' },
                { label: 'Sugars',   value: nutrition_per_serving.total_sugars_g,  unit: 'g',    warn: v => v > 12,  cardClass: 'stat-card-amber',  color: '#f59e0b', sparkVariant: 'wave', suffix: '/serving' },
                { label: 'Sat Fat',  value: nutrition_per_serving.saturated_fat_g, unit: 'g',    warn: v => v > 5,   cardClass: 'stat-card-red',    color: '#ef4444', sparkVariant: 'bar',  suffix: '/serving' },
                { label: 'Fiber',    value: nutrition_per_serving.fiber_g,         unit: 'g',    warn: () => false,   cardClass: 'stat-card-green',  color: '#10b981', sparkVariant: 'wave', suffix: '/serving' },
                { label: 'Protein',  value: nutrition_per_serving.protein_g,       unit: 'g',    warn: () => false,   cardClass: 'stat-card-blue',   color: '#0ea5e9', sparkVariant: 'bar',  suffix: '/serving' },
            ];
        }
        return [
            { label: 'Calories', value: nutrition?.energy_kcal_100g, unit: 'kcal', warn: v => v > 400, cardClass: 'stat-card-cyan',   color: '#14b8a6', sparkVariant: 'wave', suffix: '/100g' },
            { label: 'Sodium',   value: nutrition?.sodium_mg_100g,   unit: 'mg',   warn: v => v > 600, cardClass: 'stat-card-purple', color: '#6366f1', sparkVariant: 'bar',  suffix: '/100g' },
            { label: 'Sugars',   value: nutrition?.sugars_g_100g,    unit: 'g',    warn: v => v > 12,  cardClass: 'stat-card-amber',  color: '#f59e0b', sparkVariant: 'wave', suffix: '/100g' },
            { label: 'Sat Fat',  value: nutrition?.sat_fat_g_100g,   unit: 'g',    warn: v => v > 5,   cardClass: 'stat-card-red',    color: '#ef4444', sparkVariant: 'bar',  suffix: '/100g' },
            { label: 'Fiber',    value: nutrition?.fiber_g_100g,     unit: 'g',    warn: () => false,   cardClass: 'stat-card-green',  color: '#10b981', sparkVariant: 'wave', suffix: '/100g' },
            { label: 'Protein',  value: nutrition?.protein_g_100g,   unit: 'g',    warn: () => false,   cardClass: 'stat-card-blue',   color: '#0ea5e9', sparkVariant: 'bar',  suffix: '/100g' },
        ];
    };
    const statCards = buildStatCards();

    /* Active reasons/penalties for the current view */
    const activeReasons = activeNutScore?.reasons ?? product_score?.reasons ?? [];
    const activePenalties = activeNutScore?.penalties ?? product_score?.penalties ?? [];

    return (
        <div className="min-h-screen bg-[#f5f7fb] text-gray-800">
            <div className="mx-auto max-w-4xl px-4 py-10 custom-scrollbar">

                {/* -- Back button ---------------------- */}
                <button
                    onClick={onReset}
                    className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-indigo-600 mb-6 transition-colors"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                    </svg>
                    Back to scan
                </button>

                {/* ╔══════════════════════════════════════╗
                   ║  1 - HEADER CARD                     ║
                   ╚══════════════════════════════════════╝ */}
                <div className="glass-strong p-6 mb-4 text-center animate-fade-in">
                    <h1 className="text-3xl sm:text-4xl font-display font-extrabold mb-1 text-gray-900 leading-tight">
                        {product?.name || 'Product Analysis'}
                    </h1>
                    {product?.brand && (
                        <p className="text-base text-gray-500 font-medium">{product.brand}</p>
                    )}
                    {product?.barcode && (
                        <p className="text-xs text-gray-400 mt-1 font-mono tracking-wide">
                            Barcode {product.barcode}
                        </p>
                    )}
                    <NutritionStatusBadge status={nutritionStatus} source={nutrition_source} />
                    {scoredForName && (
                        <p className="mt-2 text-xs text-indigo-500 font-medium">
                            Scored for: {scoredForName}
                        </p>
                    )}
                </div>

                {/* ╔══════════════════════════════════════╗
                   ║  ALLERGEN / DIET FLAGS (top priority) ║
                   ╚══════════════════════════════════════╝ */}
                {flags.length > 0 && (
                    <div className="glass-strong p-6 mb-4 animate-fade-in">
                        <h2 className="text-lg font-bold mb-3 text-gray-800">Flags</h2>
                        <div className="space-y-3">
                            {flags.map((f, i) => (
                                <div key={i} className={`border-l-4 rounded-2xl p-4 ${severityColor[f.severity] || severityColor.info}`}>
                                    <div className="flex items-start gap-2">
                                        <div>
                                            <span className="font-semibold text-sm uppercase tracking-wide">
                                                {f.type.replace('_', ' ')}
                                            </span>
                                            <p className="mt-1 text-sm">{f.message}</p>
                                            {f.related_ingredients.length > 0 && (
                                                <p className="mt-1 text-xs opacity-70">
                                                    Related: {f.related_ingredients.join(', ')}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* ╔══════════════════════════════════════╗
                   ║  2 - SCORE + STATS (tighter grid)    ║
                   ╚══════════════════════════════════════╝ */}
                {product_score && (
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-4 animate-slide-up">
                        {/* Score gauge card */}
                        <div className="lg:col-span-5 glass-strong p-6 flex flex-col items-center justify-center">
                            <h2 className="text-lg font-bold mb-2 text-gray-700">Wellness Score</h2>

                            {/* View toggle */}
                            {hasBothViews && (
                                <div className="mb-3">
                                    <ViewToggle view={nutritionView} onChange={setNutritionView} />
                                </div>
                            )}

                            <ScoreGauge score={Math.round(displayScore)} />

                            {/* Grade pill */}
                            <div className="mt-3">
                                <span className={`inline-block px-5 py-1.5 rounded-full text-sm font-bold tracking-wide border ${gradeColor[displayGrade] || gradeColor.C}`}>
                                    Grade {displayGrade}
                                </span>
                            </div>

                            {/* Portion note */}
                            {isPortionSensitive && portionInfo?.note && (
                                <p className="mt-2 text-xs text-gray-400 italic leading-relaxed max-w-xs mx-auto text-center">
                                    {portionInfo.note}
                                    {portionInfo.typical_serving_text && (
                                        <span className="block mt-0.5 text-gray-500 not-italic font-medium">
                                            Typical serving: {portionInfo.typical_serving_text}
                                        </span>
                                    )}
                                </p>
                            )}

                            {/* Processing Status Badge (human-readable) */}
                            {processingStatus && (
                                <div className="mt-3 text-center">
                                    <span className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold tracking-wide border ${processingStatus.colorClass}`}>
                                        <span>{processingStatus.icon}</span>
                                        {processingStatus.label}
                                    </span>
                                    {processingStatus.description && (
                                        <p className="mt-1 text-[11px] text-gray-400 max-w-[16rem] mx-auto leading-snug">
                                            {processingStatus.description}
                                        </p>
                                    )}
                                    {procScore != null && (
                                        <p className="mt-0.5 text-[10px] text-gray-400">
                                            Processing score: {procScore}/100
                                        </p>
                                    )}
                                </div>
                            )}

                            {/* Nutrition sub-score */}
                            {nutScoreObj && (
                                <div className="mt-3 flex justify-center gap-5 text-xs text-gray-400">
                                    <span>Nutrition: <span className="text-gray-700 font-semibold">{nutScoreObj.score}</span>/100</span>
                                </div>
                            )}
                        </div>

                        {/* Stats cards column */}
                        <div className="lg:col-span-7 flex flex-col">
                            <div className="flex items-center justify-between mb-3">
                                <h2 className="text-lg font-bold text-gray-700">Nutrient Stats</h2>
                                <span className="text-xs text-gray-400">
                                    {nutritionView === 'serving' ? 'per serving' : 'per 100 g'}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 flex-1">
                                {statCards.map((c, i) => {
                                    const isWarn = typeof c.warn === 'function' && c.value != null && c.warn(c.value);
                                    return (
                                        <div key={i} className={c.cardClass}>
                                            <div className="flex items-start justify-between">
                                                <div>
                                                    <p className="text-sm font-semibold text-gray-500 mb-1">{c.label}</p>
                                                    <p className={`text-3xl font-bold ${isWarn ? 'text-amber-700' : 'text-gray-800'}`}>
                                                        {c.value != null ? (Number.isFinite(c.value) ? parseFloat(c.value.toFixed(1)) : c.value) : '--'}
                                                        <span className="text-base font-normal text-gray-500 ml-1">{c.unit}</span>
                                                    </p>
                                                </div>
                                                <Sparkline color={c.color} width={56} height={24} variant={c.sparkVariant} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                )}

                {/* -- Key Factors / Penalties ----------- */}
                {product_score && (activeReasons.length > 0 || activePenalties.length > 0) && (
                    <div className="glass-strong p-6 mb-4 animate-slide-up">
                        <div className="space-y-4 max-w-2xl mx-auto">
                            {activeReasons.length > 0 && (
                                <div>
                                    <h3 className="text-sm font-semibold text-gray-700 mb-2">
                                        Key Factors
                                        <span className="ml-2 text-xs font-normal text-gray-400">
                                            ({nutritionView === 'serving' ? 'per serving' : 'per 100g'})
                                        </span>
                                    </h3>
                                    <ul className="space-y-1 text-xs text-gray-600">
                                        {activeReasons.slice(0, 5).map((r, i) => (
                                            <li key={i} className="flex items-start gap-1.5">
                                                <span className="text-indigo-500 mt-0.5">&#x2022;</span>{r}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {activePenalties.length > 0 && (
                                <details className="group">
                                    <summary className="text-sm font-semibold text-red-600 cursor-pointer select-none">
                                        Penalty Details ({activePenalties.length})
                                    </summary>
                                    <ul className="mt-2 space-y-1 text-xs text-gray-500">
                                        {activePenalties.map((p, i) => (
                                            <li key={i}>&#x2022; {p}</li>
                                        ))}
                                    </ul>
                                </details>
                            )}

                            {/* Processing signals */}
                            {procSignals.length > 0 && (
                                <details className="group">
                                    <summary className="text-sm font-semibold text-orange-600 cursor-pointer select-none">
                                        Processing Signals ({procSignals.length})
                                    </summary>
                                    <ul className="mt-2 space-y-1 text-xs text-gray-500">
                                        {procSignals.map((s, i) => (
                                            <li key={i}>&#x2022; {s}</li>
                                        ))}
                                    </ul>
                                </details>
                            )}

                            {/* Processing details */}
                            {procDetails.length > 0 && (
                                <details className="group">
                                    <summary className="text-sm font-semibold text-gray-500 cursor-pointer select-none">
                                        Processing Details ({procDetails.length})
                                    </summary>
                                    <ul className="mt-2 space-y-1 text-xs text-gray-400">
                                        {procDetails.map((d, i) => (
                                            <li key={i}>&#x2022; {d}</li>
                                        ))}
                                    </ul>
                                </details>
                            )}
                        </div>

                        {/* Personal conflicts */}
                        {product_score.personalized_conflicts?.length > 0 && (
                            <div className="mt-5 max-w-2xl mx-auto bg-amber-50 border border-amber-200 rounded-2xl p-4">
                                <h3 className="text-sm font-semibold text-amber-700 mb-2">Personal Conflicts</h3>
                                <ul className="space-y-1 text-xs text-amber-600">
                                    {product_score.personalized_conflicts.map((c, i) => (
                                        <li key={i}>&#x2022; {c}</li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* Uncertainties */}
                        {product_score.uncertainties?.length > 0 && (
                            <div className="mt-4 max-w-2xl mx-auto bg-gray-50 border border-gray-200 rounded-2xl p-4">
                                <h3 className="text-sm font-semibold text-gray-600 mb-2">Uncertainties</h3>
                                <ul className="space-y-1 text-xs text-gray-500">
                                    {product_score.uncertainties.map((u, i) => (
                                        <li key={i}>&#x2022; {u}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}

                {/* ╔══════════════════════════════════════╗
                   ║  3 - DETAILS SECTION                 ║
                   ╚══════════════════════════════════════╝ */}

                {/* Personalized Summary */}
                {personalized_summary && (
                    <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.05s' }}>
                        <h2 className="text-lg font-bold mb-3 text-gray-800">Personalized Summary</h2>
                        <p className="text-gray-600 leading-relaxed whitespace-pre-wrap text-sm">
                            {personalized_summary}
                        </p>
                    </div>
                )}

                {/* Nutrition per 100 g */}
                {nutrition && (
                    <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.08s' }}>
                        <h2 className="text-lg font-bold mb-3 text-gray-800">Nutrition per 100 g</h2>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                            {[
                                { v: nutrition.energy_kcal_100g, l: 'kcal',   u: '' },
                                { v: nutrition.sugars_g_100g,    l: 'Sugars', u: ' g' },
                                { v: nutrition.sat_fat_g_100g,   l: 'Sat Fat',u: ' g' },
                                { v: nutrition.sodium_mg_100g,   l: 'Sodium', u: ' mg' },
                                { v: nutrition.fiber_g_100g,     l: 'Fiber',  u: ' g' },
                                { v: nutrition.protein_g_100g,   l: 'Protein',u: ' g' },
                            ].filter(n => n.v != null).map((n, i) => (
                                <div key={i} className="nut-chip">
                                    <div className="text-lg font-bold text-gray-800">{Number.isFinite(n.v) ? parseFloat(n.v.toFixed(1)) : n.v}{n.u}</div>
                                    <div className="text-[11px] text-gray-400">{n.l}</div>
                                </div>
                            ))}
                        </div>
                        <p className="text-[10px] text-gray-400 mt-2 text-right">
                            Source: {nutrition.source || 'OpenFoodFacts'}
                        </p>
                    </div>
                )}

                {/* Ingredients list */}
                <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.12s' }}>
                    <h2 className="text-lg font-bold mb-3 text-gray-800">
                        Detected Ingredients ({ingredients.length})
                    </h2>
                    <div className="grid sm:grid-cols-2 gap-2">
                        {ingredients.map((ing, i) => (
                            <div key={i} className="flex items-center justify-between bg-gray-50 border border-gray-100 rounded-xl px-3 py-2 text-sm">
                                <div>
                                    <span className="text-gray-800 font-medium capitalize">{ing.name_canonical}</span>
                                    {ing.notes && <span className="text-gray-400 ml-2 text-xs">({ing.notes})</span>}
                                </div>
                                <div className="flex gap-1 flex-wrap justify-end">
                                    {ing.tags.slice(0, 3).map((t, j) => (
                                        <span key={j} className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500 border border-gray-200">
                                            {t}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Umbrella Terms */}
                {umbrella_terms.length > 0 && (
                    <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.14s' }}>
                        <h2 className="text-lg font-bold mb-2 text-amber-700">Umbrella Terms</h2>
                        <p className="text-gray-400 text-xs mb-2">
                            These are vague labels whose exact composition is unknown.
                        </p>
                        <div className="flex flex-wrap gap-2">
                            {umbrella_terms.map((t, i) => (
                                <span key={i} className="badge-warning text-xs">{t}</span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Allergen Statements */}
                {allergen_statements.length > 0 && (
                    <div className="glass-strong p-6 mb-4 animate-slide-up bg-red-50/50" style={{ animationDelay: '0.16s' }}>
                        <h2 className="text-lg font-bold mb-2 text-red-700">Allergen Statements</h2>
                        <ul className="text-gray-600 text-sm space-y-1">
                            {allergen_statements.map((s, i) => <li key={i}>&#x2022; {s}</li>)}
                        </ul>
                    </div>
                )}

                {/* Evidence */}
                {evidence.length > 0 && (
                    <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.18s' }}>
                        <h2 className="text-lg font-bold mb-3 text-gray-800">Evidence & Citations</h2>
                        <div className="space-y-3 max-h-64 overflow-y-auto custom-scrollbar">
                            {evidence.map((e, i) => (
                                <div key={i} className="bg-gray-50 border border-gray-100 rounded-xl p-3">
                                    <div className="flex items-start gap-2">
                                        <span className="text-xs text-gray-400 font-mono shrink-0">{e.citation_id}</span>
                                        <div>
                                            <a
                                                href={e.source_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-indigo-600 hover:underline text-sm font-medium"
                                            >
                                                {e.title}
                                            </a>
                                            <p className="text-gray-400 text-xs mt-1">{e.snippet}</p>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* -- Disclaimer ---------------------- */}
                <p className="text-center text-xs text-gray-400 mb-4">{disclaimer}</p>

                {/* -- Action row (removed big chat button) -- */}
                <div className="flex items-center justify-center pb-20">
                    <button onClick={onReset} className="btn-primary text-base px-8 py-3">
                        Scan Another Product
                    </button>
                </div>
            </div>

            {/* -- Persistent Chat Launcher (always visible) -- */}
            <ChatPanel sessionId={session_id} productName={product?.name} />
        </div>
    );
};

export default ResultsPage;
