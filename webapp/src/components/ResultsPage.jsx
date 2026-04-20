import { useState } from 'react';
import ChatPanel from './ChatPanel';
import ScoreGauge from './ScoreGauge';
import NutritionStatusBadge from './NutritionStatusBadge';
import Sparkline from './Sparkline';
import UnknownIngredientsBanner from './UnknownIngredientsBanner';

/* -- severity helpers (light theme) ------------ */
const severityColor = {
    high: 'border-red-400 bg-red-50 text-red-700',
    warn: 'border-amber-400 bg-amber-50 text-amber-700',
    info: 'border-brandLine bg-brandTint text-brandDeep',
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

/* -- ingredient concern level helper ----------------- */
const getIngredientConcern = (ing, matchInfo, flags) => {
    const name = ing.name_canonical?.toLowerCase() ?? '';
    if (flags.some(f => f.type === 'allergen' && f.related_ingredients.some(r => r.toLowerCase() === name)))
        return 'allergen';
    if (ing.tags.some(t => t.startsWith('upf_indicator_') || t === 'artificial-sweetener' || t === 'artificial_color' || t === 'artificial-color'))
        return 'high';
    if (['artificial_color', 'artificial_sweetener'].includes(matchInfo?.fallback_category))
        return 'high';
    if (flags.some(f => f.severity === 'high' && f.related_ingredients.some(r => r.toLowerCase() === name)))
        return 'high';
    if (['preservative', 'sweetener'].includes(matchInfo?.fallback_category))
        return 'warn';
    return null;
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
                            ? 'bg-brandTint text-brandDeep border border-brandLine shadow-sm'
                            : 'text-gray-500 hover:text-brandDeep'
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
        health_goal,
        disclaimer,
        nutrition_status: apiNutritionStatus,
        nutrition_source,
    } = data;

    /* Determine default view from backend */
    const defaultView = product_score?.primary_nutrition_view || '100g';
    const [nutritionView, setNutritionView] = useState(defaultView);
    const [showAllIngredients, setShowAllIngredients] = useState(false);

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

    /* Build 4-metric nutrient grid */
    const buildNutrientGrid = () => {
        if (nutritionView === 'serving' && nutrition_per_serving) {
            return [
                { label: 'SUGAR',   value: nutrition_per_serving.total_sugars_g,  unit: 'g', max: 50,  warnThreshold: 12, cardClass: 'stat-card-amber',  barColor: '#f59e0b' },
                { label: 'FAT',     value: nutrition_per_serving.total_fat_g,      unit: 'g', max: 80,  warnThreshold: 20, cardClass: 'stat-card-red',    barColor: '#ef4444' },
                { label: 'PROTEIN', value: nutrition_per_serving.protein_g,        unit: 'g', max: 50,  warnThreshold: null, cardClass: 'stat-card-blue', barColor: '#0ea5e9' },
                { label: 'CARBS',   value: nutrition_per_serving.total_carbs_g,    unit: 'g', max: 100, warnThreshold: null, cardClass: 'stat-card-purple', barColor: '#8b5cf6' },
            ];
        }
        return [
            { label: 'SUGAR',   value: nutrition?.sugars_g_100g,    unit: 'g', max: 50,  warnThreshold: 12,   cardClass: 'stat-card-amber',  barColor: '#f59e0b' },
            { label: 'SAT FAT', value: nutrition?.sat_fat_g_100g,   unit: 'g', max: 40,  warnThreshold: 10,   cardClass: 'stat-card-red',    barColor: '#ef4444' },
            { label: 'PROTEIN', value: nutrition?.protein_g_100g,   unit: 'g', max: 50,  warnThreshold: null, cardClass: 'stat-card-blue',   barColor: '#0ea5e9' },
            { label: 'CARBS',   value: null,                         unit: 'g', max: 100, warnThreshold: null, cardClass: 'stat-card-purple', barColor: '#8b5cf6' },
        ];
    };
    const nutrientGrid = buildNutrientGrid();

    /* Active reasons/penalties for the current view */
    const activeReasons = activeNutScore?.reasons ?? product_score?.reasons ?? [];
    const activePenalties = activeNutScore?.penalties ?? product_score?.penalties ?? [];

    return (
        <div className="min-h-screen bg-bg1 text-gray-800">
            <div className="mx-auto max-w-4xl px-4 py-10 custom-scrollbar">

                {/* -- Back button ---------------------- */}
                <button
                    onClick={onReset}
                    aria-label="Back to scan"
                    className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-brandDeep mb-6 transition-colors min-h-[44px]"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                    </svg>
                    Back to scan
                </button>

                {/* ╔══════════════════════════════════════╗
                   ║  1 - HEADER CARD                     ║
                   ╚══════════════════════════════════════╝ */}
                <div className="glass-strong p-6 mb-4 animate-fade-in">
                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-2">Product Analysis</p>

                    {/* Processing + category pill tags */}
                    <div className="flex flex-wrap gap-2 mb-3">
                        {processingStatus && (
                            <span className={`text-[11px] font-bold px-3 py-1 rounded-full border uppercase tracking-wide ${processingStatus.colorClass}`}>
                                {processingStatus.label}
                            </span>
                        )}
                        {product_score?.category && (
                            <span className="text-[11px] font-bold px-3 py-1 rounded-full border border-gray-200 bg-gray-100 text-gray-600 uppercase tracking-wide">
                                {product_score.category}
                            </span>
                        )}
                    </div>

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
                        <p className="mt-2 text-xs text-brandDeep font-medium">
                            Scored for: {scoredForName}
                        </p>
                    )}
                </div>

                {/* ╔══════════════════════════════════════╗
                   ║  ALLERGEN / DIET FLAGS (top priority) ║
                   ╚══════════════════════════════════════╝ */}
                {flags.length > 0 && (
                    <div className="glass-strong p-6 mb-4 animate-fade-in">
                        <h2 className="text-lg font-bold mb-4 text-gray-800 font-headline">
                            {flags.some(f => f.severity === 'high' || f.severity === 'warn') ? 'Red Flags' : 'Flags'}
                        </h2>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            {flags.map((f, i) => {
                                const isHigh = f.severity === 'high';
                                const isWarn = f.severity === 'warn';
                                const cardBg = isHigh ? 'bg-red-50 border-red-100' : isWarn ? 'bg-amber-50 border-amber-100' : 'bg-brandTint border-brandLine';
                                const iconBg = isHigh ? 'bg-red-100' : isWarn ? 'bg-amber-100' : 'bg-brandLine/40';
                                const iconColor = isHigh ? 'text-red-600' : isWarn ? 'text-amber-600' : 'text-brandDeep';
                                const labelColor = isHigh ? 'text-red-700' : isWarn ? 'text-amber-700' : 'text-brandDeep';
                                const bodyColor = isHigh ? 'text-red-600' : isWarn ? 'text-amber-600' : 'text-brandDeep/80';
                                return (
                                    <div key={i} className={`flex items-start gap-3 rounded-2xl border p-4 ${cardBg}`}>
                                        <div className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center ${iconBg}`}>
                                            {isHigh || isWarn ? (
                                                <svg className={`w-4 h-4 ${iconColor}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                                                </svg>
                                            ) : (
                                                <svg className={`w-4 h-4 ${iconColor}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                </svg>
                                            )}
                                        </div>
                                        <div className="min-w-0">
                                            <p className={`text-xs font-bold uppercase tracking-wide mb-0.5 ${labelColor}`}>
                                                {f.type.replace(/_/g, ' ')}
                                            </p>
                                            <p className={`text-xs leading-snug ${bodyColor}`}>{f.message}</p>
                                            {f.related_ingredients.length > 0 && (
                                                <p className="mt-1 text-[10px] text-gray-400">
                                                    {f.related_ingredients.join(', ')}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* ╔══════════════════════════════════════╗
                   ║  UNKNOWN INGREDIENTS BANNER            ║
                   ╚══════════════════════════════════════╝ */}
                {product_score && (
                    <UnknownIngredientsBanner productScore={product_score} />
                )}

                {/* ╔══════════════════════════════════════╗
                   ║  2 - SCORE + STATS (tighter grid)    ║
                   ╚══════════════════════════════════════╝ */}
                {product_score && (
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-4 animate-slide-up">
                        {/* Wellness Score card — redesigned */}
                        <div className="lg:col-span-5 glass-strong p-6">
                            <h2 className="text-lg font-bold mb-4 text-gray-700">Wellness Score</h2>

                            {/* View toggle */}
                            {hasBothViews && (
                                <div className="mb-4">
                                    <ViewToggle view={nutritionView} onChange={setNutritionView} />
                                </div>
                            )}

                            <div className="flex gap-4">
                                {/* Left: Big letter grade */}
                                <div className="flex-1">
                                    <div className={`text-8xl font-extrabold leading-none mb-1 ${
                                        displayGrade === 'A' || displayGrade === 'B' ? 'text-emerald-600' :
                                        displayGrade === 'C' ? 'text-amber-600' :
                                        displayGrade === 'D' ? 'text-orange-600' :
                                        'text-red-600'
                                    }`}>
                                        {displayGrade}
                                    </div>
                                    <div className={`text-2xl font-bold mb-1 ${
                                        displayScore >= 70 ? 'text-emerald-700' :
                                        displayScore >= 40 ? 'text-amber-700' :
                                        'text-red-700'
                                    }`}>
                                        {Math.round(displayScore)}<span className="text-base font-normal text-gray-400">/100</span>
                                    </div>
                                    <p className="text-xs text-gray-500 leading-snug">
                                        {displayScore >= 85 ? 'Excellent – very nutritious choice.' :
                                         displayScore >= 70 ? 'Good – solid nutritional profile.' :
                                         displayScore >= 55 ? 'Fair – some nutritional concerns.' :
                                         displayScore >= 40 ? 'Poor – notable nutritional drawbacks.' :
                                         'Avoid – significant health concerns.'}
                                    </p>

                                    {/* Portion note */}
                                    {isPortionSensitive && portionInfo?.note && (
                                        <p className="mt-2 text-xs text-gray-400 italic leading-relaxed">
                                            {portionInfo.note}
                                            {portionInfo.typical_serving_text && (
                                                <span className="block mt-0.5 text-gray-500 not-italic font-medium">
                                                    Serving: {portionInfo.typical_serving_text}
                                                </span>
                                            )}
                                        </p>
                                    )}
                                </div>

                                {/* Right: Goal match panel */}
                                <div className={`flex-shrink-0 w-36 rounded-2xl p-3 flex flex-col items-center justify-center text-center gap-1.5 ${
                                    displayScore >= 70 ? 'bg-emerald-50 border border-emerald-200' :
                                    displayScore >= 40 ? 'bg-amber-50 border border-amber-200' :
                                    'bg-red-50 border border-red-200'
                                }`}>
                                    {/* Match icon */}
                                    {displayScore >= 70 ? (
                                        <svg className="w-8 h-8 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                    ) : displayScore >= 40 ? (
                                        <svg className="w-8 h-8 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                                        </svg>
                                    ) : (
                                        <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                        </svg>
                                    )}
                                    <span className={`text-xs font-bold ${
                                        displayScore >= 70 ? 'text-emerald-700' :
                                        displayScore >= 40 ? 'text-amber-700' :
                                        'text-red-700'
                                    }`}>
                                        {displayScore >= 70 ? 'Good Match' :
                                         displayScore >= 40 ? 'Fair Match' :
                                         'Poor Match'}
                                    </span>
                                    <p className={`text-[10px] leading-snug ${
                                        displayScore >= 70 ? 'text-emerald-600' :
                                        displayScore >= 40 ? 'text-amber-600' :
                                        'text-red-600'
                                    }`}>
                                        {health_goal
                                            ? (displayScore >= 70
                                                ? `Aligns with your goal: "${health_goal}"`
                                                : `Does not align with your goal: "${health_goal}"`)
                                            : (product_score?.personalized_conflicts?.[0]
                                                || (displayScore >= 70
                                                    ? 'Meets optimal wellness standards.'
                                                    : 'Does not meet optimal wellness standards.'))}
                                    </p>
                                </div>
                            </div>

                            {/* Nutrition sub-score */}
                            {nutScoreObj && (
                                <div className="mt-4 flex gap-5 text-xs text-gray-400">
                                    <span>Nutrition: <span className="text-gray-700 font-semibold">{nutScoreObj.score}</span>/100</span>
                                    {procScore != null && (
                                        <span>Processing: <span className="text-gray-700 font-semibold">{procScore}</span>/100</span>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Nutrient Profile — 4-metric big-number grid */}
                        <div className="lg:col-span-7 flex flex-col">
                            <div className="flex items-center justify-between mb-3">
                                <h2 className="text-lg font-bold text-gray-700 font-headline">Nutrient Profile</h2>
                                <span className="text-xs text-gray-400">
                                    {nutritionView === 'serving' ? 'per serving' : 'per 100 g'}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 gap-3 flex-1">
                                {nutrientGrid.map((c, i) => {
                                    const val = c.value;
                                    const pct = val != null ? Math.min(100, (val / c.max) * 100) : 0;
                                    const isWarn = c.warnThreshold != null && val != null && val > c.warnThreshold;
                                    return (
                                        <div key={i} className={c.cardClass}>
                                            <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-1">{c.label}</p>
                                            <p className="text-4xl font-extrabold font-headline leading-none text-gray-800 mb-0.5">
                                                {val != null ? parseFloat(val.toFixed(1)) : '--'}
                                                <span className="text-base font-normal text-gray-400 ml-1">{c.unit}</span>
                                            </p>
                                            <div className="mt-3 h-1.5 rounded-full bg-gray-200/60 overflow-hidden">
                                                <div
                                                    className="h-full rounded-full transition-all duration-700"
                                                    style={{ width: `${pct}%`, backgroundColor: isWarn ? '#ef4444' : c.barColor }}
                                                />
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
                                                <span className="text-brand mt-0.5">&#x2022;</span>{r}
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

                {/* Clinical Insight */}
                {personalized_summary && (
                    <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.05s' }}>
                        <h2 className="text-lg font-bold mb-3 text-gray-800">Clinical Insight</h2>

                        {/* Processing classification line */}
                        {processingStatus && (
                            <p className="text-sm text-gray-600 mb-3">
                                This product is classified as{' '}
                                <strong className={
                                    upfSignalsPresent || (processingStatus.label || '').toLowerCase().includes('highly') || (processingStatus.label || '').toLowerCase().includes('ultra')
                                        ? 'text-red-600'
                                        : (processingStatus.label || '').toLowerCase().includes('moderately')
                                            ? 'text-amber-600'
                                            : 'text-emerald-600'
                                }>
                                    {processingStatus.label.toLowerCase()}
                                </strong>.
                            </p>
                        )}

                        <p className="text-gray-600 leading-relaxed whitespace-pre-wrap text-sm mb-4">
                            {personalized_summary}
                        </p>

                        {/* 2 key concern mini-cards */}
                        {(() => {
                            const concerns = activeReasons.length > 0
                                ? activeReasons.slice(0, 2)
                                : flags.filter(f => f.severity === 'high').slice(0, 2).map(f => f.message);
                            if (concerns.length === 0) return null;
                            return (
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
                                    {concerns.map((reason, i) => (
                                        <div key={i} className="flex items-start gap-3 bg-red-50 border border-red-100 rounded-xl p-3">
                                            <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-red-100 flex items-center justify-center">
                                                <svg className="w-4 h-4 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                                                </svg>
                                            </div>
                                            <p className="text-xs text-red-700 leading-snug font-medium">{reason}</p>
                                        </div>
                                    ))}
                                </div>
                            );
                        })()}
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

                {/* Ingredient Forensic */}
                <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.12s' }}>
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-bold text-gray-800">Ingredient Forensic</h2>
                        <span className="text-xs text-gray-400 font-medium">{ingredients.length} Total Ingredients</span>
                    </div>
                    <div className="space-y-2">
                        {(showAllIngredients ? ingredients : ingredients.slice(0, 5)).map((ing, i) => {
                            const matchResults = product_score?.ingredient_match?.results || [];
                            const matchInfo = matchResults.find(
                                (m) => m.normalized === ing.name_canonical?.toLowerCase()
                                    || m.raw === ing.name_canonical
                                    || m.raw === ing.name_raw
                            );
                            const matchStatus = matchInfo?.status;
                            const concern = getIngredientConcern(ing, matchInfo, flags);

                            return (
                                <div key={i} className={`rounded-2xl border p-4 transition-all hover:shadow-glass ${
                                    concern === 'high'     ? 'bg-red-50/60 border-red-100' :
                                    concern === 'allergen' ? 'bg-amber-50/60 border-amber-100' :
                                    concern === 'warn'     ? 'bg-orange-50/40 border-orange-100' :
                                    'bg-gray-50 border-gray-100'
                                }`}>
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="min-w-0">
                                            <p className="text-gray-800 font-semibold capitalize text-sm leading-tight">{ing.name_canonical}</p>
                                            {ing.notes && (
                                                <p className="text-gray-400 text-xs mt-0.5">{ing.notes}</p>
                                            )}
                                            {ing.tags?.length > 0 && (
                                                <div className="flex flex-wrap gap-1 mt-1.5">
                                                    {ing.tags.slice(0, 2).map((tag, ti) => (
                                                        <span key={ti} className="text-[9px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium">
                                                            {tag.replace(/_/g, ' ')}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                        <div className="flex flex-col items-end gap-1 shrink-0">
                                            {matchStatus === 'unknown' && (
                                                <span className="text-[10px] px-2.5 py-1 rounded-full bg-amber-100 text-amber-700 border border-amber-200 font-bold uppercase tracking-wide">
                                                    Unknown
                                                </span>
                                            )}
                                            {concern === 'high' && (
                                                <span className="text-[10px] px-2.5 py-1 rounded-full bg-red-100 text-red-700 border border-red-200 font-bold uppercase tracking-wide">
                                                    High Concern
                                                </span>
                                            )}
                                            {concern === 'allergen' && (
                                                <span className="text-[10px] px-2.5 py-1 rounded-full bg-amber-100 text-amber-700 border border-amber-200 font-bold uppercase tracking-wide">
                                                    Allergen Risk
                                                </span>
                                            )}
                                            {concern === 'warn' && (
                                                <span className="text-[10px] px-2.5 py-1 rounded-full bg-orange-100 text-orange-700 border border-orange-100 font-bold uppercase tracking-wide">
                                                    Low Concern
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                    {ingredients.length > 5 && (
                        <button
                            onClick={() => setShowAllIngredients(v => !v)}
                            className="mt-3 w-full flex items-center justify-center gap-2 text-sm font-semibold text-cn-primary bg-cn-surface-container-low hover:bg-cn-surface-container rounded-2xl py-3 transition-colors"
                        >
                            {showAllIngredients ? (
                                <>Show Less <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" /></svg></>
                            ) : (
                                <>View {ingredients.length - 5} More Ingredients <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" /></svg></>
                            )}
                        </button>
                    )}
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
                                                className="text-brandDeep hover:underline text-sm font-medium"
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

                {/* -- Action row -- */}
                <div className="flex items-center justify-center pb-8">
                    <button onClick={onReset} className="btn-primary text-base px-8 py-3 min-h-[48px]">
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
