"use client"
import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { GlassCard } from '@/components/ui/GlassCard'
import { api } from '@/lib/api'
import { CheckCircle2, AlertTriangle, ShieldAlert, BookOpen, Activity, ThumbsUp, ThumbsDown, MessageSquarePlus } from 'lucide-react'
import { CopyButton } from '@/components/ui/CopyButton'
import { ConfidenceMeter } from '@/components/ui/ConfidenceMeter'
import { LanguageSelector } from '@/components/ui/LanguageSelector'
import { getAllLanguages, getLanguageName } from '@/lib/languages'

// ─── Tool API response shapes (TMX-3614-types-extended) ───────────────────
// Frozen to the backend contract at app/api/tools.py. If the backend shape
// drifts the type-check fails before runtime drift can land.

interface Violation {
    category: string
    severity: string
    message: string
}
interface AuditReport {
    status: string
    max_severity: string
    violations: Violation[]
}
interface BackTranslationResult {
    back_translation: string
    drift_score?: number | null
}
interface MatrixResult {
    results: Record<string, string>
}

export default function ToolsPage() {
    const [activeTab, setActiveTab] = useState<'audit' | 'backtrans' | 'matrix'>('audit')

    // Quality Auditor State
    const [auditSource, setAuditSource] = useState('')
    const [auditTrans, setAuditTrans] = useState('')
    const [auditTgtLang, setAuditTgtLang] = useState('fr')
    const [auditReport, setAuditReport] = useState<AuditReport | null>(null)
    const [auditLoading, setAuditLoading] = useState(false)

    // Back-Translation State
    const [backTransText, setBackTransText] = useState('')
    const [backSourceRef, setBackSourceRef] = useState('')
    const [backLang, setBackLang] = useState('auto')
    const [backResult, setBackResult] = useState<BackTranslationResult | null>(null)
    const [backLoading, setBackLoading] = useState(false)

    // Matrix State
    const [matrixText, setMatrixText] = useState('')
    const [matrixLangs, setMatrixLangs] = useState<string[]>(['fr', 'de', 'es', 'it', 'ja'])
    const [matrixResult, setMatrixResult] = useState<MatrixResult | null>(null)
    const [matrixLoading, setMatrixLoading] = useState(false)


    return (
        <div style={{ padding: "2rem", maxWidth: "1200px", margin: "0 auto" }}>
            <header style={{ marginBottom: "2rem" }}>
                <h1 style={{ fontSize: "2rem", fontWeight: 600, color: "#202124", display: "flex", alignItems: "center", gap: "12px" }}>
                    <div className="p-2 bg-blue-600 rounded-lg text-white">
                        <Activity size={24} />
                    </div>
                    Translation Toolkit
                </h1>
                <p style={{ color: "#5f6368" }}>Professional utilities for validation, auditing, and ad-hoc translation.</p>
            </header>

            {/* Navigation Tabs */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', overflowX: 'auto', paddingBottom: '4px' }}>
                <TabButton
                    active={activeTab === 'audit'}
                    onClick={() => setActiveTab('audit')}
                    icon={<ShieldAlert size={18} />}
                    label="Quality Auditor"
                />
                <TabButton
                    active={activeTab === 'backtrans'}
                    onClick={() => setActiveTab('backtrans')}
                    icon={<Activity size={18} />}
                    label="Back-Translation"
                />
                <TabButton
                    active={activeTab === 'matrix'}
                    onClick={() => setActiveTab('matrix')}
                    icon={<BookOpen size={18} />}
                    label="Multi-Lingual Matrix"
                />
            </div>

            {/* Tool Content */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.2 }}
                >
                    {activeTab === 'audit' && (
                        <QualityAuditor
                            source={auditSource} setSource={setAuditSource}
                            trans={auditTrans} setTrans={setAuditTrans}
                            tgtLang={auditTgtLang} setTgtLang={setAuditTgtLang}
                            report={auditReport} setReport={setAuditReport}
                            loading={auditLoading} setLoading={setAuditLoading}
                        />
                    )}
                    {activeTab === 'backtrans' && (
                        <BackTranslationVerifier
                            text={backTransText} setText={setBackTransText}
                            sourceRef={backSourceRef} setSourceRef={setBackSourceRef}
                            lang={backLang} setLang={setBackLang}
                            result={backResult} setResult={setBackResult}
                            loading={backLoading} setLoading={setBackLoading}
                        />
                    )}
                    {activeTab === 'matrix' && (
                        <TranslationMatrix
                            text={matrixText} setText={setMatrixText}
                            langs={matrixLangs} setLangs={setMatrixLangs}
                            result={matrixResult} setResult={setMatrixResult}
                            loading={matrixLoading} setLoading={setMatrixLoading}
                        />
                    )}
                </motion.div>
            </AnimatePresence>
        </div>
    )
}

// --- Components ---

interface TabButtonProps {
    active: boolean
    onClick: () => void
    icon: React.ReactNode
    label: string
}
function TabButton({ active, onClick, icon, label }: TabButtonProps) {
    return (
        <button
            onClick={onClick}
            style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '10px 20px',
                borderRadius: '8px',
                border: 'none',
                background: active ? '#e8f0fe' : 'transparent',
                color: active ? '#1a73e8' : '#5f6368',
                cursor: 'pointer',
                fontWeight: 500,
                transition: 'all 0.2s',
                whiteSpace: 'nowrap'
            }}
        >
            {icon} {label}
        </button>
    )
}

export function FeedbackControls({ source, target, targetLang }: { source: string, target: string, targetLang: string }) {
    const [status, setStatus] = useState<'idle' | 'up' | 'down'>('idle')
    const [showModal, setShowModal] = useState(false)
    const [correction, setCorrection] = useState('')

    const handleVote = async (type: 'positive' | 'negative') => {
        if (type === 'positive') {
            setStatus('up')
            try {
                await api.knowledge.submitFeedback({
                    source_text: source,
                    target_text: target,
                    rating: 'positive',
                    target_language: targetLang
                })
            } catch (e) { console.error(e) }
        } else {
            setStatus('down')
            setShowModal(true)
        }
    }

    const handleSubmitCorrection = async () => {
        try {
            await api.knowledge.submitFeedback({
                source_text: source,
                target_text: target,
                corrected_text: correction,
                rating: 'negative',
                target_language: targetLang
            })
            setShowModal(false)
            alert("Feedback submitted to Black Book!")
        } catch (e) { console.error(e) }
    }

    return (
        <div className="flex gap-2 items-center">
            <span className="text-xs text-slate-400 mr-1">Rate:</span>
            <button
                onClick={() => handleVote('positive')}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${status === 'up' ? 'bg-green-100 text-green-700' : 'bg-slate-50 text-slate-500 hover:bg-green-50 hover:text-green-600'}`}
                title="Good translation"
            >
                <ThumbsUp size={14} /> Good
            </button>
            <button
                onClick={() => handleVote('negative')}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${status === 'down' ? 'bg-red-100 text-red-700' : 'bg-slate-50 text-slate-500 hover:bg-red-50 hover:text-red-600'}`}
                title="Report issue"
            >
                <ThumbsDown size={14} /> Issue
            </button>

            {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                    <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6" onClick={e => e.stopPropagation()}>
                        <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                            <MessageSquarePlus className="text-blue-600" />
                            Submit Correction
                        </h3>
                        <p className="text-sm text-slate-500 mb-4">
                            Help us improve. Your correction handles reinforcement learning for future translations.
                        </p>

                        <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">Suggested Correction</label>
                        <textarea
                            className="w-full p-3 border rounded-lg mb-4 text-sm focus:ring-2 ring-blue-500 outline-none"
                            rows={4}
                            placeholder="Enter the correct translation here..."
                            value={correction}
                            onChange={e => setCorrection(e.target.value)}
                            autoFocus
                        />

                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => setShowModal(false)}
                                className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSubmitCorrection}
                                disabled={!correction}
                                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                            >
                                Submit Rule
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

interface QualityAuditorProps {
    source: string
    setSource: (v: string) => void
    trans: string
    setTrans: (v: string) => void
    tgtLang: string
    setTgtLang: (v: string) => void
    report: AuditReport | null
    setReport: (v: AuditReport | null) => void
    loading: boolean
    setLoading: (v: boolean) => void
}
function QualityAuditor({ source, setSource, trans, setTrans, tgtLang, setTgtLang, report, setReport, loading, setLoading }: QualityAuditorProps) {
    const handleAudit = async () => {
        setLoading(true)
        try {
            const res = await api.tools.audit(source, trans, tgtLang)
            setReport(res as AuditReport)
        } catch (e) {
            console.error(e)
        } finally {
            setLoading(false)
        }
    }

    return (
        <GlassCard>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
                <div>
                    <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Source Text</div>
                    <textarea
                        value={source}
                        onChange={e => setSource(e.target.value)}
                        rows={6}
                        placeholder="Original text..."
                        style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid #ddd' }}
                    />
                </div>
                <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', alignItems: 'center' }}>
                        <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Translated Text</div>
                        <LanguageSelector
                            value={tgtLang}
                            onChange={v => setTgtLang(v)}
                            className="min-w-[160px]"
                        />
                    </div>
                    <textarea
                        value={trans}
                        onChange={e => setTrans(e.target.value)}
                        rows={6}
                        placeholder="Translation to check..."
                        style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid #ddd' }}
                    />
                </div>
            </div>

            <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                <button
                    onClick={handleAudit}
                    disabled={loading || !source || !trans}
                    style={{
                        padding: '10px 24px',
                        background: '#ea4335',
                        color: 'white',
                        border: 'none',
                        borderRadius: '24px',
                        cursor: (loading || !source) ? 'not-allowed' : 'pointer',
                        opacity: (loading || !source) ? 0.5 : 1,
                        display: 'flex', alignItems: 'center', gap: '8px', margin: '0 auto'
                    }}
                >
                    {loading ? 'Auditing...' : <><ShieldAlert size={18} /> Run Quality Checks</>}
                </button>
            </div>

            {report && (
                <div style={{ padding: '1.5rem', background: '#f8f9fa', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
                        <div style={{
                            fontSize: '1.2rem', fontWeight: 600,
                            color: report.status === 'PASS' ? '#188038' : '#d93025',
                            display: 'flex', alignItems: 'center', gap: '8px'
                        }}>
                            {report.status === 'PASS' ? <CheckCircle2 /> : <AlertTriangle />}
                            Result: {report.status}
                        </div>
                        <div style={{ fontSize: '0.9rem', color: '#5f6368' }}>
                            Max Severity: <strong style={{ textTransform: 'capitalize' }}>{report.max_severity}</strong>
                        </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                        {report.violations.length === 0 ? (
                            <div style={{ color: '#188038', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <CheckCircle2 size={16} /> No defects found.
                            </div>
                        ) : (
                            report.violations.map((v, i) => (
                                <div key={i} style={{
                                    padding: '12px',
                                    background: 'white',
                                    borderLeft: `4px solid ${v.severity === 'critical' ? '#d93025' : v.severity === 'high' ? '#f29900' : '#1a73e8'}`,
                                    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                                    borderRadius: '0 4px 4px 0'
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                        <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{v.category}</span>
                                        <span style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: '#5f6368' }}>{v.severity}</span>
                                    </div>
                                    <div style={{ color: '#3c4043' }}>{v.message}</div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            )}
        </GlassCard>
    )
}

interface BackTranslationVerifierProps {
    text: string
    setText: (v: string) => void
    sourceRef: string
    setSourceRef: (v: string) => void
    lang: string
    setLang: (v: string) => void
    result: BackTranslationResult | null
    setResult: (v: BackTranslationResult | null) => void
    loading: boolean
    setLoading: (v: boolean) => void
}
function BackTranslationVerifier({ text, setText, sourceRef, setSourceRef, lang, setLang, result, setResult, loading, setLoading }: BackTranslationVerifierProps) {
    const handleRun = async () => {
        setLoading(true)
        try {
            const res = await api.tools.backTranslate(text, lang, sourceRef || undefined)
            setResult(res)
        } catch (e) { console.error(e) }
        finally { setLoading(false) }
    }

    return (
        <GlassCard>
            <div style={{ display: 'flex', gap: '2rem', flexDirection: 'column' }}>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <LanguageSelector
                        value={lang}
                        onChange={v => setLang(v)}
                        includeAuto={true}
                        className="min-w-[200px]"
                    />
                    <span style={{ color: '#5f6368' }}>text back to English</span>
                </div>

                <textarea
                    value={text}
                    onChange={e => setText(e.target.value)}
                    placeholder="Paste foreign text here (e.g. German output)..."
                    rows={4}
                    style={{ padding: '1rem', borderRadius: '8px', border: '1px solid #ddd' }}
                />

                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '-1rem' }}>
                    <div style={{ height: '1px', flex: 1, background: '#eee' }}></div>
                    <span style={{ color: '#aaa', fontSize: '0.9rem' }}>(Optional) Compare with Original Source</span>
                    <div style={{ height: '1px', flex: 1, background: '#eee' }}></div>
                </div>

                <textarea
                    value={sourceRef}
                    onChange={e => setSourceRef(e.target.value)}
                    placeholder="Original English text (if available) for Semantic Drift Check..."
                    rows={3}
                    style={{ padding: '1rem', borderRadius: '8px', border: '1px solid #ddd' }}
                />

                <button
                    onClick={handleRun}
                    disabled={loading || !text}
                    style={{ margin: '0 auto', padding: '10px 32px', borderRadius: '24px', border: 'none', background: '#34a853', color: 'white', cursor: 'pointer', display: 'flex', gap: '8px', alignItems: 'center' }}
                >
                    {loading ? 'Verifying...' : <><Activity size={18} /> Reverse Verify</>}
                </button>

                {result && (
                    <div style={{ marginTop: '2rem', padding: '1.5rem', background: '#f1f3f4', borderRadius: '8px', position: 'relative' }}>
                        <div className="absolute top-2 right-2">
                            <CopyButton text={result.back_translation} />
                        </div>
                        <h4 style={{ margin: '0 0 1rem 0', color: '#202124' }}>English Back-Translation:</h4>
                        <div style={{ fontSize: '1.1rem', marginBottom: '1.5rem', fontStyle: 'italic', color: '#3c4043' }}>
                            &ldquo;{result.back_translation}&rdquo;
                        </div>

                        {result.drift_score !== undefined && result.drift_score !== null && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                <div style={{ fontWeight: 600 }}>Semantic Drift Score:</div>
                                <ConfidenceMeter score={result.drift_score} className="scale-100" />
                                <span style={{ fontSize: '0.9rem', color: '#5f6368' }}>
                                    (100 = Perfect Meaning Match)
                                </span>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </GlassCard>
    )
}

interface TranslationMatrixProps {
    text: string
    setText: (v: string) => void
    langs: string[]
    setLangs: (v: string[]) => void
    result: MatrixResult | null
    setResult: (v: MatrixResult | null) => void
    loading: boolean
    setLoading: (v: boolean) => void
}
function TranslationMatrix({ text, setText, langs, setLangs, result, setResult, loading, setLoading }: TranslationMatrixProps) {
    // Configurable 5 languages for matrix

    const handleRun = async () => {
        setLoading(true)
        try {
            const res = await api.tools.matrix(text, langs)
            setResult(res as MatrixResult)
        } catch (e) { console.error(e) }
        finally { setLoading(false) }
    }

    const toggleLang = (code: string) => {
        if (langs.includes(code)) {
            setLangs(langs.filter(l => l !== code))
        } else {
            if (langs.length < 5) {
                setLangs([...langs, code])
            }
        }
    }

    return (
        <GlassCard>
            <div style={{ marginBottom: '2rem' }}>
                <div style={{ marginBottom: '1rem' }}>
                    <label className="text-sm font-semibold text-slate-500 uppercase block mb-2">Select Target Languages (Max 5)</label>
                    <div className="flex flex-wrap gap-2">
                        {getAllLanguages().map(l => (
                            <button
                                key={l.code}
                                onClick={() => toggleLang(l.code)}
                                className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${langs.includes(l.code)
                                    ? "bg-blue-100 text-blue-700 border-blue-200"
                                    : "bg-white text-slate-600 border-slate-200 hover:border-blue-300"
                                    }`}
                            >
                                {l.name}
                            </button>
                        ))}
                    </div>
                    {langs.length > 0 && <div className="text-xs text-slate-400 mt-2">Selected: {langs.join(', ')}</div>}
                </div>

                <textarea
                    value={text}
                    onChange={e => setText(e.target.value)}
                    placeholder="Enter text to translate..."
                    rows={3}
                    style={{ width: '100%', padding: '1rem', borderRadius: '8px', border: '1px solid #ddd' }}
                />

                <div style={{ textAlign: 'center' }}>
                    <button
                        onClick={handleRun}
                        disabled={loading || !text || langs.length === 0}
                        style={{ marginTop: '1rem', padding: '10px 32px', borderRadius: '24px', border: 'none', background: '#a142f4', color: 'white', cursor: 'pointer', opacity: (loading || !text) ? 0.7 : 1 }}
                    >
                        {loading ? 'Generating Matrix...' : 'Generate Matrix'}
                    </button>
                </div>
            </div>

            {loading && <div>Generating parallel translations...</div>}

            {result && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
                    {langs.map((l: string) => (
                        <div key={l} style={{ padding: '1rem', background: 'white', borderRadius: '8px', border: '1px solid #eee', position: 'relative' }}>
                            <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: '#5f6368', textTransform: 'uppercase', display: 'flex', justifyContent: 'space-between' }}>
                                {getLanguageName(l)}
                                <CopyButton text={result.results[l] || ''} />
                            </div>
                            <div style={{ fontSize: '1.1rem', color: '#202124' }}>
                                {result.results[l] || '...'}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </GlassCard>
    )
}
