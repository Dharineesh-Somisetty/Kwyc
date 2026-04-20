import { useState } from 'react';
import ChatPanel from './ChatPanel';
import NutritionStatusBadge from './NutritionStatusBadge';
import UnknownIngredientsBanner from './UnknownIngredientsBanner';

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

/* -- Strip inline citation tokens from text -- */
const stripCitations = (text) => {
    if (!text) return '';
    return text
        .replace(/\[kb:[^\]]*\]/gi, '')
        .replace(/\[(INFO|WARN|ERROR|NOTE|REF|CITE)[^\]]*\]/gi, '')
        .replace(/\[\d+\]/g, '')
        .replace(/\s{2,}/g, ' ')
        .trim();
};

/* -- Convert summary paragraph into 2-3 bullet points -- */
const summaryToBullets = (text) => {
    if (!text) return [];
    const cleaned = stripCitations(text);
    const lines = cleaned.split('\n').map(l => l.replace(/^[-•*]\s*/, '').trim()).filter(l => l.length > 10);
    if (lines.length >= 2) return lines.slice(0, 3);
    const sentences = cleaned.match(/[^.!?]+[.!?]+(?:\s|$)/g) || [cleaned];
    return sentences.slice(0, 3).map(s => s.trim()).filter(s => s.length > 10);
};

/* -- Nutrient level label -- */
const getNutrientLevel = (value, warnThreshold, max) => {
    if (value == null) return { text: '—', colorClass: 'text-gray-400' };
    if (warnThreshold != null && value > warnThreshold) return { text: 'EXCESSIVE', colorClass: 'text-cn-tertiary font-bold' };
    const pct = value / max;
    if (pct > 0.6) return { text: 'HIGH', colorClass: 'text-orange-600 font-bold' };
    if (pct > 0.3) return { text: 'MODERATE', colorClass: 'text-gray-500' };
    return { text: 'NEGLIGIBLE', colorClass: 'text-gray-400' };
};

/* -- Segmented toggle pill component ------------ */
const ViewToggle = ({ view, onChange }) => (
    <div className="inline-flex items-center bg-gray-100 border border-gray-200 rounded-full p-0.5">
        {[{ key: 'serving', label: 'Per serving' }, { key: '100g', label: 'Per 100g' }].map((t) => (
            <button
                key={t.key}
                onClick={() => onChange(t.key)}
                className={`px-3 py-1 rounded-full text-xs font-semibold transition-all duration-200 ${
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

    const defaultView = product_score?.primary_nutrition_view || '100g';
    const [nutritionView, setNutritionView] = useState(defaultView);
    const [showAllIngredients, setShowAllIngredients] = useState(false);
    const [showAllFlags, setShowAllFlags] = useState(false);
    const [showRawInsight, setShowRawInsight] = useState(false);

    /* Portion info */
    const portionInfo = product_score?.portion_info;
    const isPortionSensitive = portionInfo?.portion_sensitive ?? false;

    /* Dual nutrition scores */
    const nutScore100g = product_score?.nutrition_score_100g;
    const nutScoreServing = product_score?.nutrition_score_serving;
    const hasBothViews = nutScore100g != null && nutScoreServing != null;

    /* Active view score */
    const activeNutScore = nutritionView === 'serving' ? nutScoreServing : nutScore100g;

    /* Display score */
    const displayScore = activeNutScore?.score ?? product_score?.score ?? 50;
    const displayGrade = activeNutScore?.grade ?? product_score?.grade ?? 'C';

    const nutritionStatus = apiNutritionStatus || deriveNutritionStatus(product, product_score, nutrition);

    /* Resolve split scoring objects */
    const nutScoreObj  = product_score?.nutrition_score;
    const procObj      = product_score?.processing;
    const procBadge    = procObj || product_score?.processing_badge;
    const procLevel    = procBadge?.level;
    const procScore    = procObj?.processing_score;
    const procSignals  = procBadge?.signals ?? [];
    const procDetails  = procObj?.details ?? [];

    /* Processing status */
    const upfSignalsPresent = procLevel === 'upf_signals' || procSignals.length > 0;
    const processingStatus = procScore != null
        ? processingStatusFromScore(procScore, upfSignalsPresent)
        : procLevel
            ? (fallbackBadge[procLevel] || fallbackBadge.processed)
            : null;

    /* Active reasons/penalties */
    const activeReasons = activeNutScore?.reasons ?? product_score?.reasons ?? [];
    const activePenalties = activeNutScore?.penalties ?? product_score?.penalties ?? [];

    /* Nutrient grid — 4 key metrics */
    const buildNutrientGrid = () => {
        if (nutritionView === 'serving' && nutrition_per_serving) {
            return [
                { label: 'SUGAR',   value: nutrition_per_serving.total_sugars_g,  unit: 'g', max: 50,  warnThreshold: 12,   barColor: '#a7344c' },
                { label: 'FAT',     value: nutrition_per_serving.total_fat_g,      unit: 'g', max: 80,  warnThreshold: 20,   barColor: '#ef4444' },
                { label: 'PROTEIN', value: nutrition_per_serving.protein_g,        unit: 'g', max: 50,  warnThreshold: null, barColor: '#27ae60' },
                { label: 'CARBS',   value: nutrition_per_serving.total_carbs_g,    unit: 'g', max: 100, warnThreshold: null, barColor: '#27ae60' },
            ];
        }
        return [
            { label: 'SUGAR',   value: nutrition?.sugars_g_100g,    unit: 'g', max: 50,  warnThreshold: 12,   barColor: '#a7344c' },
            { label: 'SAT FAT', value: nutrition?.sat_fat_g_100g,   unit: 'g', max: 40,  warnThreshold: 10,   barColor: '#ef4444' },
            { label: 'PROTEIN', value: nutrition?.protein_g_100g,   unit: 'g', max: 50,  warnThreshold: null, barColor: '#27ae60' },
            { label: 'CARBS',   value: null,                         unit: 'g', max: 100, warnThreshold: null, barColor: '#27ae60' },
        ];
    };
    const nutrientGrid = buildNutrientGrid();

    /* Clinical insight bullets (citation-stripped) */
    const insightBullets = summaryToBullets(personalized_summary);

    /* Grade text color */
    const gradeTextColor =
        displayGrade === 'A' || displayGrade === 'B' ? 'text-emerald-500' :
        displayGrade === 'C' ? 'text-amber-500' :
        displayGrade === 'D' ? 'text-orange-500' : 'text-cn-tertiary';

    /* Match card theme */
    const isPoorMatch = displayScore < 40;
    const isFairMatch = displayScore >= 40 && displayScore < 70;
    const matchBg       = isPoorMatch ? 'bg-[#ffd9dc]' : isFairMatch ? 'bg-amber-50'    : 'bg-emerald-50';
    const matchText     = isPoorMatch ? 'text-[#670021]' : isFairMatch ? 'text-amber-900'  : 'text-emerald-900';
    const matchIconBg   = isPoorMatch ? 'bg-[#ffb2bb]/60' : isFairMatch ? 'bg-amber-100'   : 'bg-emerald-100';
    const matchIconFg   = isPoorMatch ? 'text-[#a7344c]'  : isFairMatch ? 'text-amber-700' : 'text-emerald-700';
    const matchBtnBg    = isPoorMatch ? 'bg-[#670021] hover:bg-[#400011]' : isFairMatch ? 'bg-amber-700 hover:bg-amber-800' : 'bg-emerald-700 hover:bg-emerald-800';
    const matchLabel    = isPoorMatch ? 'Poor Match' : isFairMatch ? 'Fair Match' : 'Good Match';

    /* Glow decoration color */
    const glowColor =
        displayGrade === 'A' || displayGrade === 'B' ? 'bg-emerald-400' :
        displayGrade === 'C' ? 'bg-amber-400' :
        displayGrade === 'D' ? 'bg-orange-400' : 'bg-cn-tertiary';

    return (
        <div className="min-h-screen bg-bg1 text-gray-800">
            <div className="mx-auto max-w-4xl px-4 py-8 custom-scrollbar">

                {/* -- Back button ---------------------- */}
                <button
                    onClick={onReset}
                    aria-label="Back to scan"
                    className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-brandDeep mb-8 transition-colors min-h-[44px]"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                    </svg>
                    Back to scan
                </button>

                {/* ╔══════════════════════════════════════╗
                   ║  1 — HERO PRODUCT SECTION            ║
                   ╚══════════════════════════════════════╝ */}
                <section className="mb-10 flex flex-col sm:flex-row gap-6 items-center sm:items-end animate-fade-in">
                    {/* Circular product image */}
                    <div className="flex-shrink-0 w-28 h-28 sm:w-36 sm:h-36 rounded-full overflow-hidden bg-gray-100 border border-gray-200 shadow-sm flex items-center justify-center">
                        {product?.image_url ? (
                            <img
                                src={product.image_url}
                                alt={product?.name || 'Product'}
                                className="w-full h-full object-cover"
                            />
                        ) : (
                            <svg className="w-12 h-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                            </svg>
                        )}
                    </div>

                    {/* Product info */}
                    <div className="flex-grow text-center sm:text-left">
                        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Product Analysis</p>
                        <h1 className="font-headline text-3xl sm:text-4xl lg:text-5xl font-extrabold text-gray-900 leading-tight tracking-tight mb-3">
                            {product?.name || 'Product Analysis'}
                        </h1>
                        {product?.brand && (
                            <p className="text-sm text-gray-500 font-medium mb-3">{product.brand}</p>
                        )}
                        <div className="flex flex-wrap gap-2 justify-center sm:justify-start">
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
                        {product?.barcode && (
                            <p className="text-xs text-gray-400 mt-2 font-mono tracking-wide">Barcode {product.barcode}</p>
                        )}
                        <div className="mt-2 flex flex-wrap gap-2 justify-center sm:justify-start">
                            <NutritionStatusBadge status={nutritionStatus} source={nutrition_source} />
                            {scoredForName && (
                                <span className="text-xs text-brandDeep font-medium">Scored for: {scoredForName}</span>
                            )}
                        </div>
                    </div>
                </section>

                {/* Unknown Ingredients Banner */}
                {product_score && (
                    <UnknownIngredientsBanner productScore={product_score} />
                )}

                {/* ╔══════════════════════════════════════╗
                   ║  2 — BENTO GRID                      ║
                   ╚══════════════════════════════════════╝ */}
                {product_score && (
                    <>
                        {/* Row 1: Wellness Score (8/12) | Match Card (4/12) */}
                        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-4 animate-slide-up">

                            {/* Wellness Score */}
                            <div className="lg:col-span-8 glass-strong p-8 relative overflow-hidden">
                                <div className="flex items-center justify-between mb-1">
                                    <h2 className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">Wellness Score</h2>
                                    {hasBothViews && <ViewToggle view={nutritionView} onChange={setNutritionView} />}
                                </div>

                                <div className="flex items-baseline gap-5 mt-2">
                                    <span className={`font-headline font-black leading-none tracking-tighter ${gradeTextColor}`}
                                          style={{ fontSize: 'clamp(6rem, 14vw, 11rem)' }}>
                                        {displayGrade}
                                    </span>
                                    <div>
                                        <p className={`text-4xl font-bold font-headline ${gradeTextColor}`}>
                                            {Math.round(displayScore)}
                                            <span className="text-xl font-normal text-gray-400">/100</span>
                                        </p>
                                        <p className="text-sm text-gray-500 leading-relaxed mt-2 max-w-[26ch]">
                                            {displayScore >= 85 ? 'Excellent – a very nutritious choice.' :
                                             displayScore >= 70 ? 'Good – solid nutritional profile.' :
                                             displayScore >= 55 ? 'Fair – some nutritional concerns.' :
                                             displayScore >= 40 ? 'Poor – notable nutritional drawbacks.' :
                                             'This product lacks key nutrients and contains levels of processed ingredients that exceed recommended intake.'}
                                        </p>
                                        {isPortionSensitive && portionInfo?.note && (
                                            <p className="mt-2 text-xs text-gray-400 italic">{portionInfo.note}</p>
                                        )}
                                    </div>
                                </div>

                                {/* Sub-scores */}
                                {nutScoreObj && (
                                    <div className="mt-6 flex gap-5 text-xs text-gray-400 border-t border-gray-100 pt-4">
                                        <span>Nutrition: <span className="text-gray-700 font-semibold">{nutScoreObj.score}</span>/100</span>
                                        {procScore != null && (
                                            <span>Processing: <span className="text-gray-700 font-semibold">{procScore}</span>/100</span>
                                        )}
                                    </div>
                                )}

                                {/* Decorative glow */}
                                <div className={`absolute -right-10 -bottom-10 w-52 h-52 rounded-full blur-3xl opacity-10 pointer-events-none ${glowColor}`} />
                            </div>

                            {/* Match Card */}
                            <div className={`lg:col-span-4 rounded-3xl p-8 flex flex-col items-center justify-center text-center ${matchBg}`}>
                                <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-5 ${matchIconBg}`}>
                                    {isPoorMatch ? (
                                        <svg className={`w-8 h-8 ${matchIconFg}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                        </svg>
                                    ) : isFairMatch ? (
                                        <svg className={`w-8 h-8 ${matchIconFg}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                                        </svg>
                                    ) : (
                                        <svg className={`w-8 h-8 ${matchIconFg}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                    )}
                                </div>
                                <h3 className={`font-headline text-2xl font-bold mb-2 ${matchText}`}>{matchLabel}</h3>
                                <p className={`text-sm leading-relaxed ${matchText} opacity-80`}>
                                    {health_goal
                                        ? (displayScore >= 70
                                            ? 'Aligns with your goal:'
                                            : 'Does not align with your goal:')
                                        : (displayScore >= 70
                                            ? 'Meets your wellness standards.'
                                            : 'Does not meet wellness standards.')}
                                    {health_goal && (
                                        <><br /><strong className="opacity-100">&ldquo;{health_goal}&rdquo;</strong></>
                                    )}
                                </p>
                                <button
                                    onClick={onReset}
                                    className={`mt-6 px-6 py-3 rounded-full text-sm font-bold text-white transition-all active:scale-95 ${matchBtnBg}`}
                                >
                                    Find Alternatives
                                </button>
                            </div>
                        </div>

                        {/* Row 2: Red Flags (5/12) | Nutrient Profile (7/12) */}
                        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-4 animate-slide-up" style={{ animationDelay: '0.06s' }}>

                            {/* Red Flags */}
                            <div className="lg:col-span-5 glass-strong p-8">
                                <h3 className="font-headline text-base font-bold text-gray-800 mb-6 flex items-center gap-2">
                                    <svg className="w-5 h-5 text-cn-tertiary flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                                    </svg>
                                    {flags.some(f => f.severity === 'high' || f.severity === 'warn') ? 'Red Flags' : 'Flags'}
                                </h3>

                                {flags.length === 0 ? (
                                    <p className="text-sm text-gray-400">No flags detected.</p>
                                ) : (
                                    <>
                                        <ul className="space-y-5">
                                            {(showAllFlags ? flags : flags.slice(0, 3)).map((f, i) => {
                                                const isHigh = f.severity === 'high';
                                                const isWarn = f.severity === 'warn';
                                                const iconBg  = isHigh ? 'bg-red-100'    : isWarn ? 'bg-amber-100' : 'bg-gray-100';
                                                const iconFg  = isHigh ? 'text-red-600'  : isWarn ? 'text-amber-600' : 'text-gray-500';
                                                /* Use the first related ingredient as the title (more readable), fallback to type */
                                                const title = f.related_ingredients?.[0] || f.type.replace(/_/g, ' ');
                                                return (
                                                    <li key={i} className="flex items-start gap-4">
                                                        <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${iconBg}`}>
                                                            {isHigh || isWarn ? (
                                                                <svg className={`w-4 h-4 ${iconFg}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                                                                </svg>
                                                            ) : (
                                                                <svg className={`w-4 h-4 ${iconFg}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                                </svg>
                                                            )}
                                                        </div>
                                                        <div>
                                                            <h4 className="font-headline font-bold text-gray-800 text-sm capitalize">{title}</h4>
                                                            <p className="text-xs text-gray-500 leading-tight mt-0.5">{f.message}</p>
                                                        </div>
                                                    </li>
                                                );
                                            })}
                                        </ul>
                                        {flags.length > 3 && (
                                            <button
                                                onClick={() => setShowAllFlags(v => !v)}
                                                className="mt-5 text-xs font-semibold text-cn-primary hover:underline"
                                            >
                                                {showAllFlags ? 'Show less' : `View all (${flags.length})`}
                                            </button>
                                        )}
                                    </>
                                )}
                            </div>

                            {/* Nutrient Profile */}
                            <div className="lg:col-span-7 glass-strong p-8">
                                <div className="flex items-center justify-between mb-8">
                                    <h3 className="font-headline text-base font-bold text-gray-800">Nutrient Profile</h3>
                                    <span className="text-xs text-gray-400">{nutritionView === 'serving' ? 'per serving' : 'per 100 g'}</span>
                                </div>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
                                    {nutrientGrid.map((c, i) => {
                                        const val = c.value;
                                        const pct = val != null ? Math.min(100, (val / c.max) * 100) : 0;
                                        const isWarn = c.warnThreshold != null && val != null && val > c.warnThreshold;
                                        const level = getNutrientLevel(val, c.warnThreshold, c.max);
                                        return (
                                            <div key={i} className="flex flex-col">
                                                <span className={`font-headline text-4xl font-bold ${isWarn ? 'text-cn-tertiary' : 'text-gray-800'}`}>
                                                    {val != null ? parseFloat(val.toFixed(0)) : '--'}
                                                    {val != null && <span className="text-xl font-normal text-gray-400">{c.unit}</span>}
                                                </span>
                                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mt-1">{c.label}</span>
                                                <div className="w-full h-1 bg-gray-200 mt-3 rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full rounded-full transition-all duration-700"
                                                        style={{ width: `${pct}%`, backgroundColor: isWarn ? '#a7344c' : c.barColor }}
                                                    />
                                                </div>
                                                <span className={`text-[10px] mt-1.5 ${level.colorClass}`}>{level.text}</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    </>
                )}

                {/* ╔══════════════════════════════════════╗
                   ║  3 — CLINICAL INSIGHT (bullets)      ║
                   ╚══════════════════════════════════════╝ */}
                {(personalized_summary || activeReasons.length > 0) && (
                    <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.1s' }}>
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-bold text-gray-800 font-headline">Clinical Insight</h2>
                            {personalized_summary && (
                                <button
                                    onClick={() => setShowRawInsight(v => !v)}
                                    className="text-xs text-gray-400 hover:text-brandDeep transition-colors px-2 py-1 rounded-lg hover:bg-gray-100"
                                >
                                    {showRawInsight ? '← Summary' : 'Full Details'}
                                </button>
                            )}
                        </div>

                        {processingStatus && (
                            <p className="text-sm text-gray-600 mb-4">
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

                        {showRawInsight ? (
                            <p className="text-gray-600 leading-relaxed whitespace-pre-wrap text-sm">
                                {personalized_summary}
                            </p>
                        ) : (
                            <ul className="space-y-3">
                                {(insightBullets.length > 0 ? insightBullets : activeReasons.slice(0, 3)).map((bullet, i) => (
                                    <li key={i} className="flex items-start gap-3 text-sm text-gray-700">
                                        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-red-100 flex items-center justify-center mt-0.5">
                                            <svg className="w-3 h-3 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01" />
                                            </svg>
                                        </span>
                                        <span className="leading-snug">{bullet}</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                )}

                {/* ╔══════════════════════════════════════╗
                   ║  4 — SCORE DETAILS (all collapsed)   ║
                   ╚══════════════════════════════════════╝ */}
                {product_score && (activeReasons.length > 0 || activePenalties.length > 0 || procSignals.length > 0 || procDetails.length > 0 || product_score.personalized_conflicts?.length > 0 || product_score.uncertainties?.length > 0) && (
                    <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.12s' }}>
                        <h2 className="text-sm font-bold text-gray-500 uppercase tracking-widest mb-2">Score Details</h2>
                        <div className="divide-y divide-gray-100">
                            {activeReasons.length > 0 && (
                                <details className="group py-1">
                                    <summary className="flex items-center gap-2 text-sm font-semibold text-gray-700 cursor-pointer select-none py-2 list-none">
                                        <svg className="w-4 h-4 text-gray-400 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                        Key Factors ({activeReasons.length})
                                        <span className="text-xs font-normal text-gray-400">· {nutritionView === 'serving' ? 'per serving' : 'per 100g'}</span>
                                    </summary>
                                    <ul className="mt-2 mb-1 ml-6 space-y-1 text-xs text-gray-600">
                                        {activeReasons.map((r, i) => <li key={i}>• {r}</li>)}
                                    </ul>
                                </details>
                            )}
                            {activePenalties.length > 0 && (
                                <details className="group py-1">
                                    <summary className="flex items-center gap-2 text-sm font-semibold text-red-600 cursor-pointer select-none py-2 list-none">
                                        <svg className="w-4 h-4 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                        Penalty Details ({activePenalties.length})
                                    </summary>
                                    <ul className="mt-2 mb-1 ml-6 space-y-1 text-xs text-gray-500">
                                        {activePenalties.map((p, i) => <li key={i}>• {p}</li>)}
                                    </ul>
                                </details>
                            )}
                            {procSignals.length > 0 && (
                                <details className="group py-1">
                                    <summary className="flex items-center gap-2 text-sm font-semibold text-orange-600 cursor-pointer select-none py-2 list-none">
                                        <svg className="w-4 h-4 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                        Processing Signals ({procSignals.length})
                                    </summary>
                                    <ul className="mt-2 mb-1 ml-6 space-y-1 text-xs text-gray-500">
                                        {procSignals.map((s, i) => <li key={i}>• {s}</li>)}
                                    </ul>
                                </details>
                            )}
                            {procDetails.length > 0 && (
                                <details className="group py-1">
                                    <summary className="flex items-center gap-2 text-sm font-semibold text-gray-500 cursor-pointer select-none py-2 list-none">
                                        <svg className="w-4 h-4 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                        Processing Details ({procDetails.length})
                                    </summary>
                                    <ul className="mt-2 mb-1 ml-6 space-y-1 text-xs text-gray-400">
                                        {procDetails.map((d, i) => <li key={i}>• {d}</li>)}
                                    </ul>
                                </details>
                            )}
                            {product_score.personalized_conflicts?.length > 0 && (
                                <details className="group py-1">
                                    <summary className="flex items-center gap-2 text-sm font-semibold text-amber-700 cursor-pointer select-none py-2 list-none">
                                        <svg className="w-4 h-4 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                        Personal Conflicts ({product_score.personalized_conflicts.length})
                                    </summary>
                                    <ul className="mt-2 mb-1 ml-6 space-y-1 text-xs text-amber-600">
                                        {product_score.personalized_conflicts.map((c, i) => <li key={i}>• {c}</li>)}
                                    </ul>
                                </details>
                            )}
                            {product_score.uncertainties?.length > 0 && (
                                <details className="group py-1">
                                    <summary className="flex items-center gap-2 text-sm font-semibold text-gray-600 cursor-pointer select-none py-2 list-none">
                                        <svg className="w-4 h-4 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                        Uncertainties ({product_score.uncertainties.length})
                                    </summary>
                                    <ul className="mt-2 mb-1 ml-6 space-y-1 text-xs text-gray-500">
                                        {product_score.uncertainties.map((u, i) => <li key={i}>• {u}</li>)}
                                    </ul>
                                </details>
                            )}
                        </div>
                    </div>
                )}

                {/* ╔══════════════════════════════════════╗
                   ║  5 — INGREDIENT FORENSIC             ║
                   ╚══════════════════════════════════════╝ */}
                <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.14s' }}>
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-bold text-gray-800 font-headline">Ingredient Forensic</h2>
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
                                            {ing.notes && <p className="text-gray-400 text-xs mt-0.5">{ing.notes}</p>}
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
                                                <span className="text-[10px] px-2.5 py-1 rounded-full bg-amber-100 text-amber-700 border border-amber-200 font-bold uppercase tracking-wide">Unknown</span>
                                            )}
                                            {concern === 'high' && (
                                                <span className="text-[10px] px-2.5 py-1 rounded-full bg-red-100 text-red-700 border border-red-200 font-bold uppercase tracking-wide">High Concern</span>
                                            )}
                                            {concern === 'allergen' && (
                                                <span className="text-[10px] px-2.5 py-1 rounded-full bg-amber-100 text-amber-700 border border-amber-200 font-bold uppercase tracking-wide">Allergen Risk</span>
                                            )}
                                            {concern === 'warn' && (
                                                <span className="text-[10px] px-2.5 py-1 rounded-full bg-orange-100 text-orange-700 border border-orange-100 font-bold uppercase tracking-wide">Low Concern</span>
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

                {/* ╔══════════════════════════════════════╗
                   ║  6 — SECONDARY DETAILS (collapsed)   ║
                   ╚══════════════════════════════════════╝ */}
                {(nutrition || umbrella_terms.length > 0 || allergen_statements.length > 0 || evidence.length > 0) && (
                    <div className="glass-strong p-6 mb-4 animate-slide-up" style={{ animationDelay: '0.16s' }}>
                        <div className="divide-y divide-gray-100">
                            {nutrition && (
                                <details className="group py-1">
                                    <summary className="flex items-center gap-2 text-sm font-semibold text-gray-700 cursor-pointer select-none py-2 list-none">
                                        <svg className="w-4 h-4 text-gray-400 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                        Nutrition per 100 g
                                    </summary>
                                    <div className="mt-3 mb-2 grid grid-cols-2 sm:grid-cols-3 gap-2">
                                        {[
                                            { v: nutrition.energy_kcal_100g, l: 'kcal',    u: '' },
                                            { v: nutrition.sugars_g_100g,    l: 'Sugars',  u: ' g' },
                                            { v: nutrition.sat_fat_g_100g,   l: 'Sat Fat', u: ' g' },
                                            { v: nutrition.sodium_mg_100g,   l: 'Sodium',  u: ' mg' },
                                            { v: nutrition.fiber_g_100g,     l: 'Fiber',   u: ' g' },
                                            { v: nutrition.protein_g_100g,   l: 'Protein', u: ' g' },
                                        ].filter(n => n.v != null).map((n, i) => (
                                            <div key={i} className="nut-chip">
                                                <div className="text-lg font-bold text-gray-800">{Number.isFinite(n.v) ? parseFloat(n.v.toFixed(1)) : n.v}{n.u}</div>
                                                <div className="text-[11px] text-gray-400">{n.l}</div>
                                            </div>
                                        ))}
                                    </div>
                                    <p className="text-[10px] text-gray-400 text-right">Source: {nutrition.source || 'OpenFoodFacts'}</p>
                                </details>
                            )}
                            {umbrella_terms.length > 0 && (
                                <details className="group py-1">
                                    <summary className="flex items-center gap-2 text-sm font-semibold text-amber-700 cursor-pointer select-none py-2 list-none">
                                        <svg className="w-4 h-4 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                        Umbrella Terms ({umbrella_terms.length})
                                    </summary>
                                    <p className="text-xs text-gray-400 mt-2 mb-1">Vague labels whose exact composition is unknown.</p>
                                    <div className="flex flex-wrap gap-2 mb-2">
                                        {umbrella_terms.map((t, i) => (
                                            <span key={i} className="badge-warning text-xs">{t}</span>
                                        ))}
                                    </div>
                                </details>
                            )}
                            {allergen_statements.length > 0 && (
                                <details className="group py-1">
                                    <summary className="flex items-center gap-2 text-sm font-semibold text-red-700 cursor-pointer select-none py-2 list-none">
                                        <svg className="w-4 h-4 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                        Allergen Statements ({allergen_statements.length})
                                    </summary>
                                    <ul className="text-gray-600 text-sm space-y-1 mt-2 mb-1">
                                        {allergen_statements.map((s, i) => <li key={i}>• {s}</li>)}
                                    </ul>
                                </details>
                            )}
                            {evidence.length > 0 && (
                                <details className="group py-1">
                                    <summary className="flex items-center gap-2 text-sm font-semibold text-gray-700 cursor-pointer select-none py-2 list-none">
                                        <svg className="w-4 h-4 text-gray-400 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                        Evidence & Citations ({evidence.length})
                                    </summary>
                                    <div className="mt-3 mb-2 space-y-3 max-h-64 overflow-y-auto custom-scrollbar">
                                        {evidence.map((e, i) => (
                                            <div key={i} className="bg-gray-50 border border-gray-100 rounded-xl p-3">
                                                <div className="flex items-start gap-2">
                                                    <span className="text-xs text-gray-400 font-mono shrink-0">{e.citation_id}</span>
                                                    <div>
                                                        <a href={e.source_url} target="_blank" rel="noopener noreferrer"
                                                           className="text-brandDeep hover:underline text-sm font-medium">
                                                            {e.title}
                                                        </a>
                                                        <p className="text-gray-400 text-xs mt-1">{e.snippet}</p>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </details>
                            )}
                        </div>
                    </div>
                )}

                {/* -- Disclaimer ---------------------- */}
                <p className="text-center text-xs text-gray-400 mb-4">{disclaimer}</p>

                {/* -- Action row ---------------------- */}
                <div className="flex items-center justify-center pb-8">
                    <button onClick={onReset} className="btn-primary text-base px-8 py-3 min-h-[48px]">
                        Scan Another Product
                    </button>
                </div>
            </div>

            {/* -- Persistent Chat Launcher -- */}
            <ChatPanel sessionId={session_id} productName={product?.name} />
        </div>
    );
};

export default ResultsPage;
