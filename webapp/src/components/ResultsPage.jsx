import ChatPanel from './ChatPanel';
import ScoreGauge from './ScoreGauge';

const severityColor = {
    high: 'border-red-500 bg-red-500/10 text-red-300',
    warn: 'border-yellow-500 bg-yellow-500/10 text-yellow-300',
    info: 'border-blue-400 bg-blue-400/10 text-blue-300',
};

const severityIcon = { high: '🚨', warn: '⚠️', info: 'ℹ️' };

const ResultsPage = ({ data, onReset }) => {
    const {
        session_id,
        product,
        product_score,
        nutrition,
        ingredients,
        umbrella_terms,
        allergen_statements,
        flags,
        evidence,
        personalized_summary,
        disclaimer,
    } = data;

    return (
        <div className="container mx-auto px-4 py-8 max-w-4xl custom-scrollbar max-h-screen overflow-y-auto">

            {/* Product header */}
            <div className="text-center mb-8 animate-fade-in">
                <h1 className="text-4xl font-display font-bold mb-1 gradient-text">
                    {product?.name || 'Product Analysis'}
                </h1>
                {product?.brand && <p className="text-lg text-gray-300">{product.brand}</p>}
                {product?.barcode && <p className="text-xs text-gray-500 mt-1">Barcode: {product.barcode}</p>}
            </div>

            {/* Product Score */}
            {product_score && (
                <div className="glass-strong p-8 mb-6 text-center animate-slide-up">
                    <h2 className="text-2xl font-bold mb-4 text-white">Product Score</h2>
                    <ScoreGauge score={Math.round(product_score.score)} />
                    <div className="mt-4">
                        <span className={`inline-block px-4 py-1.5 rounded-full text-sm font-bold tracking-wide ${
                            product_score.grade === 'A' ? 'bg-green-500/20 text-green-400' :
                            product_score.grade === 'B' ? 'bg-emerald-500/20 text-emerald-400' :
                            product_score.grade === 'C' ? 'bg-yellow-500/20 text-yellow-400' :
                            product_score.grade === 'D' ? 'bg-orange-500/20 text-orange-400' :
                            'bg-red-500/20 text-red-400'
                        }`}>
                            Grade {product_score.grade}
                        </span>
                    </div>

                    {/* Score breakdown */}
                    <div className="mt-6 text-left max-w-xl mx-auto space-y-4">
                        {product_score.reasons?.length > 0 && (
                            <div>
                                <h3 className="text-sm font-semibold text-gray-200 mb-2">Key Factors</h3>
                                <ul className="space-y-1 text-xs text-gray-300">
                                    {product_score.reasons.slice(0, 5).map((r, i) => (
                                        <li key={i}>• {r}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        {product_score.penalties?.length > 0 && (
                            <details className="group">
                                <summary className="text-sm font-semibold text-red-400 cursor-pointer">✗ Penalty Details ({product_score.penalties.length})</summary>
                                <ul className="mt-2 space-y-1 text-xs text-gray-400">
                                    {product_score.penalties.map((p, i) => (
                                        <li key={i}>• {p}</li>
                                    ))}
                                </ul>
                            </details>
                        )}
                    </div>

                    {product_score.personalized_conflicts?.length > 0 && (
                        <div className="mt-4 text-left max-w-xl mx-auto">
                            <h3 className="text-sm font-semibold text-orange-400 mb-2">⚠ Personal Conflicts</h3>
                            <ul className="space-y-1 text-xs text-gray-300">
                                {product_score.personalized_conflicts.map((c, i) => (
                                    <li key={i}>• {c}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {product_score.uncertainties?.length > 0 && (
                        <div className="mt-4 text-left max-w-xl mx-auto">
                            <h3 className="text-sm font-semibold text-yellow-400 mb-2">? Uncertainties</h3>
                            <ul className="space-y-1 text-xs text-gray-300">
                                {product_score.uncertainties.map((u, i) => (
                                    <li key={i}>• {u}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}

            {/* Nutrition Facts */}
            {nutrition && (
                <div className="glass-strong p-6 mb-6 animate-slide-up" style={{ animationDelay: '0.05s' }}>
                    <h2 className="text-xl font-bold mb-3 text-white flex items-center gap-2">
                        <span>🥗</span> Nutrition per 100 g
                    </h2>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        {nutrition.energy_kcal_100g != null && (
                            <div className="bg-white/5 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold text-white">{nutrition.energy_kcal_100g}</div>
                                <div className="text-xs text-gray-400">kcal</div>
                            </div>
                        )}
                        {nutrition.sugars_g_100g != null && (
                            <div className="bg-white/5 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold text-white">{nutrition.sugars_g_100g} g</div>
                                <div className="text-xs text-gray-400">Sugars</div>
                            </div>
                        )}
                        {nutrition.sat_fat_g_100g != null && (
                            <div className="bg-white/5 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold text-white">{nutrition.sat_fat_g_100g} g</div>
                                <div className="text-xs text-gray-400">Sat Fat</div>
                            </div>
                        )}
                        {nutrition.sodium_mg_100g != null && (
                            <div className="bg-white/5 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold text-white">{nutrition.sodium_mg_100g} mg</div>
                                <div className="text-xs text-gray-400">Sodium</div>
                            </div>
                        )}
                        {nutrition.fiber_g_100g != null && (
                            <div className="bg-white/5 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold text-white">{nutrition.fiber_g_100g} g</div>
                                <div className="text-xs text-gray-400">Fiber</div>
                            </div>
                        )}
                        {nutrition.protein_g_100g != null && (
                            <div className="bg-white/5 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold text-white">{nutrition.protein_g_100g} g</div>
                                <div className="text-xs text-gray-400">Protein</div>
                            </div>
                        )}
                    </div>
                    <p className="text-[10px] text-gray-500 mt-2 text-right">Source: {nutrition.source || 'OpenFoodFacts'}</p>
                </div>
            )}

            {/* Personalized Summary */}
            {personalized_summary && (
                <div className="glass-strong p-6 mb-6 animate-slide-up">
                    <h2 className="text-xl font-bold mb-3 text-white flex items-center gap-2">
                        <span>🧠</span> Personalized Summary
                    </h2>
                    <p className="text-gray-300 leading-relaxed whitespace-pre-wrap text-sm">{personalized_summary}</p>
                </div>
            )}

            {/* Flags */}
            {flags.length > 0 && (
                <div className="mb-6 animate-slide-up" style={{ animationDelay: '0.1s' }}>
                    <h2 className="text-xl font-bold mb-3 text-white">🚩 Flags</h2>
                    <div className="space-y-3">
                        {flags.map((f, i) => (
                            <div key={i} className={`border-l-4 rounded-xl p-4 ${severityColor[f.severity] || severityColor.info}`}>
                                <div className="flex items-start gap-2">
                                    <span className="text-lg">{severityIcon[f.severity] || 'ℹ️'}</span>
                                    <div>
                                        <span className="font-semibold text-sm uppercase tracking-wide">{f.type.replace('_', ' ')}</span>
                                        <p className="mt-1 text-sm">{f.message}</p>
                                        {f.related_ingredients.length > 0 && (
                                            <p className="mt-1 text-xs text-gray-400">Related: {f.related_ingredients.join(', ')}</p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Ingredients list */}
            <div className="glass-strong p-6 mb-6 animate-slide-up" style={{ animationDelay: '0.15s' }}>
                <h2 className="text-xl font-bold mb-3 text-white">🧪 Detected Ingredients ({ingredients.length})</h2>
                <div className="grid sm:grid-cols-2 gap-2">
                    {ingredients.map((ing, i) => (
                        <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 text-sm">
                            <div>
                                <span className="text-white font-medium capitalize">{ing.name_canonical}</span>
                                {ing.notes && <span className="text-gray-500 ml-2 text-xs">({ing.notes})</span>}
                            </div>
                            <div className="flex gap-1 flex-wrap justify-end">
                                {ing.tags.slice(0, 3).map((t, j) => (
                                    <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-gray-400">{t}</span>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Umbrella Terms */}
            {umbrella_terms.length > 0 && (
                <div className="glass-strong p-6 mb-6 animate-slide-up" style={{ animationDelay: '0.2s' }}>
                    <h2 className="text-lg font-bold mb-2 text-yellow-400">🌂 Umbrella Terms</h2>
                    <p className="text-gray-400 text-xs mb-2">These are vague labels whose exact composition is unknown.</p>
                    <div className="flex flex-wrap gap-2">
                        {umbrella_terms.map((t, i) => (
                            <span key={i} className="badge-warning text-xs">{t}</span>
                        ))}
                    </div>
                </div>
            )}

            {/* Allergen Statements */}
            {allergen_statements.length > 0 && (
                <div className="glass-strong p-6 mb-6 animate-slide-up" style={{ animationDelay: '0.25s' }}>
                    <h2 className="text-lg font-bold mb-2 text-red-400">⚠️ Allergen Statements</h2>
                    <ul className="text-gray-300 text-sm space-y-1">
                        {allergen_statements.map((s, i) => <li key={i}>• {s}</li>)}
                    </ul>
                </div>
            )}

            {/* Evidence / Citations */}
            {evidence.length > 0 && (
                <div className="glass-strong p-6 mb-6 animate-slide-up" style={{ animationDelay: '0.3s' }}>
                    <h2 className="text-lg font-bold mb-3 text-white">📚 Evidence & Citations</h2>
                    <div className="space-y-3 max-h-64 overflow-y-auto custom-scrollbar">
                        {evidence.map((e, i) => (
                            <div key={i} className="bg-white/5 rounded-lg p-3">
                                <div className="flex items-start gap-2">
                                    <span className="text-xs text-gray-500 font-mono shrink-0">{e.citation_id}</span>
                                    <div>
                                        <a
                                            href={e.source_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-accent-400 hover:underline text-sm font-medium"
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

            {/* Disclaimer */}
            <p className="text-center text-xs text-gray-500 mb-8">{disclaimer}</p>

            {/* Reset */}
            <div className="text-center pb-8">
                <button onClick={onReset} className="btn-primary text-lg px-8 py-3">
                    Scan Another Product
                </button>
            </div>

            {/* Chat panel */}
            <ChatPanel sessionId={session_id} productName={product?.name} />
        </div>
    );
};

export default ResultsPage;
