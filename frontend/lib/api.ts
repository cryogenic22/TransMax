/**
 * TransMax Frontend API Client
 * Maps directly to existing backend APIs at /api/v1/*, /api/documents/*, /api/segments/*
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// === Types (matching backend schemas) ===

export interface Document {
    id: string
    name: string
    file_type: string | null
    status: 'uploaded' | 'processing' | 'translated' | 'in_review' | 'approved'
    source_language: string
    target_language: string | null
    glossary_id?: string | null
    segment_count?: number
    word_count?: number
    page_count?: number
    confidence_score?: number
    total_tokens?: number
    total_cost_usd?: number
    created_at: string
    updated_at: string
}

/**
 * DOCX tracked-change metadata captured at ingestion time (TMX-3700)
 * and surfaced to the reviewer surface (TMX-3702-v1). Authors and
 * dates are deduped + ordered by first occurrence in the source doc.
 */
export interface SegmentRevisions {
    has_insertions: boolean
    has_deletions: boolean
    /** OR of has_moves_from and has_moves_to — kept for back-compat (TMX-3704). */
    has_moves: boolean
    /** TMX-3704: text was relocated AWAY from this block. */
    has_moves_from?: boolean
    /** TMX-3704: text arrived HERE from elsewhere. */
    has_moves_to?: boolean
    /** TMX-3702-counts: per-type revision-mark counts. Optional — older
     * payloads without the n_* keys still type-check. */
    n_insertions?: number
    n_deletions?: number
    n_moves_from?: number
    n_moves_to?: number
    authors: string[]
    dates: string[]
}

/** TMX-3702-counts: total mark count across all types, with safe defaults. */
export function totalRevisionCount(r: SegmentRevisions): number {
    return (r.n_insertions ?? 0) + (r.n_deletions ?? 0) + (r.n_moves_from ?? 0) + (r.n_moves_to ?? 0)
}

/**
 * Element-type-specific facts captured at ingestion time. Keys vary
 * by source format; `revisions` is populated for DOCX-sourced blocks
 * with tracked changes. `section_idx` / `variant` are populated for
 * headers / footers from python-docx sections.
 */
export interface SegmentElementMeta {
    revisions?: SegmentRevisions | null
    section_idx?: number
    variant?: string
    nested?: boolean
    footnote_id?: string | null
    endnote_id?: string | null
    [key: string]: unknown
}

export interface Segment {
    id: string
    document_id: string
    order_index: number
    source_text: string
    translated_text: string | null
    status: 'pending' | 'translated' | 'edited' | 'approved' | 'blocked'
    confidence_score: number | null
    // Quality scoring fields
    validation_score: number | null  // Semantic drift score from back-translation (0-100)
    reverse_translation: string | null  // Back-translation text
    gate_results?: {
        units_ok?: boolean
        negation_ok?: boolean
        pii_redacted?: boolean
        violations?: Array<{
            category: string
            severity: string
            message: string
            suggestion?: string
        }>
    }
    /** TMX-3702: ingestion-time metadata (DOCX revisions, section_idx, etc.). */
    element_meta?: SegmentElementMeta | null
    created_at: string
    updated_at: string
}

export interface Job {
    id: string
    document_id: string
    document_name?: string
    target_language: string
    status: 'queued' | 'processing' | 'completed' | 'failed'
    progress: number
    quality_status?: string
    created_at: string
    completed_at?: string
}

export interface JobResult {
    job_id: string
    document_id: string
    status: string
    translated_segments: Array<{
        segment_id: string
        source_text: string
        translated_text: string
        confidence_score: number
    }>
    quality_scorecard: {
        status: string
        pass_rate: number
        violations: unknown[]
    }
    metrics: {
        total_segments: number
        translated_count: number
        duration_seconds: number
    }
}

export interface AuditBundle {
    job_id: string
    document_id: string
    status: string
    scorecard: unknown
    validation_summary: unknown
    audit_trail: unknown[]
    versions: {
        model: string
        prompts: string
        glossary: string
    }
}

export interface DocumentListResponse {
    items: Document[]
    total: number
    page: number
    page_size: number
}

export interface DeletionRecord {
    id: string
    document_id: string
    document_name: string
    file_type: string | null
    source_language: string | null
    target_language: string | null
    segment_count: number
    status_before_delete: string
    deleted_by: string | null
    reason: string | null
    deleted_at: string
    metadata_snapshot: Record<string, unknown> | null
}

export interface AuditLog {
    id: string
    action: string
    entity_type: string
    entity_id: string
    user_id?: string
    details?: string
    created_at: string
}

export interface TranslateResult {
    request_id: string
    job_id?: string
    decision: string
    translated_text?: string
}

// ─── Knowledge / glossary / tools response shapes ─────────────────────
// (TMX-3614-types-api). Keeping these in api.ts as the single source of
// truth so callers import the type with the data.

export interface Rule {
    rule_id: string
    source_pattern: string
    target_correction: string
    context_tag?: string
    confidence_score?: number
    status: string
    source_language?: string
    target_language?: string
    domain?: string
    is_regex?: boolean
    is_strict?: boolean
    priority?: number
    description?: string
    fire_count?: number
    false_positive_count?: number
    created_by?: string
    created_at?: string
}

export interface Glossary {
    glossary_id: string
    version: string
    is_active: boolean
    meta_json?: { source_language?: string; target_language?: string } | null
    term_count?: number
    created_at?: string
}

export interface GlossaryTerm {
    term_id: string
    source_text: string
    target_text: string
    is_forbidden?: boolean
    allowed_variants?: string[]
}

export interface TrustControl {
    key: string
    label: string
    value: string
    verified: boolean
    detail: string
}

export interface TrustPosture {
    app_env: string
    controls: TrustControl[]
}

export interface RuleAnalytics {
    rule_id: string
    source_pattern: string
    fire_count: number
    false_positive_count: number
    effectiveness: number
}

export interface RuleTestResult {
    would_fire?: boolean
    suggested_action?: string
    source_matches?: unknown[]
    target_has_correction?: boolean
}

export interface SegmentChangelogEntry {
    timestamp: string
    actor?: string
    reason?: string
    before?: string
    after?: string
}

export interface ApiAck {
    status?: string
    message?: string
    [extra: string]: unknown
}

export interface ToolAuditReport {
    status: string
    max_severity: string
    violations: Array<{ category: string; severity: string; message: string }>
}

export interface ToolBackTranslationResult {
    back_translation: string
    drift_score?: number | null
}

export interface ToolMatrixResult {
    results: Record<string, string>
}

export interface ToolUniversalResult {
    translated_text?: string
    // TMX-TOOLS-CONF-HONEST: scoring_available is false when the quality
    // scorer could not run; confidence is then null (NOT a fabricated 90%).
    scoring_available?: boolean
    confidence?: number | null
    score_band?: string
    // Real penalty components from the engine's ConfidenceService
    // (base, deterministic_penalty, semantic_penalty, structural_penalty,
    // process_penalty) — NOT fabricated accuracy/fluency/terminology bars.
    score_breakdown?: {
        base?: number
        deterministic_penalty?: number
        semantic_penalty?: number
        structural_penalty?: number
        process_penalty?: number
    }
    // TMX-QDASH-CONTRACT: the engine's real human-readable reasoning lines.
    breakdown_reasoning?: string[]
    needs_review?: boolean
    review_note?: string
    recommendations?: string[]
    segments?: Array<{ source: string; target: string }>
}

// === Auth token helper ===

function getAuthToken(): string | null {
    if (typeof document === "undefined") return null;
    const match = document.cookie.match(/(^| )transmax_token=([^;]+)/);
    return match ? decodeURIComponent(match[2]) : null;
}

// === API Client ===

class ApiClient {
    private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
        const url = `${API_BASE}${endpoint}`;
        const token = getAuthToken();

        const headers: Record<string, string> = {
            "Content-Type": "application/json",
            ...(options?.headers as Record<string, string> || {}),
        };
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        // Add timeout via AbortController (10 seconds)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        let res: Response;
        try {
            res = await fetch(url, {
                ...options,
                headers,
                signal: controller.signal,
            });
        } catch (err) {
            clearTimeout(timeoutId);
            if (err instanceof Error && err.name === "AbortError") {
                throw new Error("Request timed out. Is the backend server running?");
            }
            throw new Error("Unable to connect to the server. Please ensure the backend is running on " + API_BASE);
        } finally {
            clearTimeout(timeoutId);
        }

        // Handle 401 — redirect to login
        if (res.status === 401 && typeof window !== "undefined") {
            // Only redirect if not already on login page
            if (!window.location.pathname.startsWith("/login")) {
                window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
            }
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `API Error: ${res.status}`);
        }
        return res.json();
    }

    // === Trust posture (real, honestly-labelled compliance signals) ===
    public trust = {
        getPosture: async (): Promise<TrustPosture> => {
            return this.request(`/api/trust/posture`);
        },
    };

    // === Knowledge Base API (Black Book / Trust Center) ===
    public knowledge = {
        /**
         * List translation rules from Black Book
         */
        listRules: async (status?: string): Promise<Rule[]> => {
            let url = `/api/knowledge/rules`;
            if (status) url += `?status=${status}`;
            return this.request(url);
        },

        /**
         * Update rule status (Approve/Reject)
         */
        updateRule: async (ruleId: string, status: string): Promise<ApiAck> => {
            return this.request(`/api/knowledge/rules/${ruleId}`, {
                method: 'PATCH',
                body: JSON.stringify({ status })
            });
        },

        /**
         * List active glossaries
         */
        listGlossaries: async (): Promise<Glossary[]> => {
            return this.request(`/api/knowledge/glossaries`);
        },

        /**
         * POST /api/knowledge/rules - Create a new rule
         */
        createRule: async (data: {
            source_pattern: string,
            target_correction: string,
            context_tag?: string,
            confidence_score?: number,
            source_language?: string,
            target_language?: string,
            domain?: string,
            is_regex?: boolean,
            is_strict?: boolean,
            priority?: number,
            description?: string,
        }): Promise<Rule> => {
            return this.request(`/api/knowledge/rules`, {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        /**
         * DELETE /api/knowledge/rules/{ruleId}
         */
        deleteRule: async (ruleId: string): Promise<ApiAck> => {
            return this.request(`/api/knowledge/rules/${ruleId}`, {
                method: 'DELETE'
            });
        },

        /**
         * POST /api/knowledge/rules/test - Test a rule against sample text
         */
        testRule: async (data: {
            source_pattern: string,
            target_correction: string,
            is_regex: boolean,
            test_source: string,
            test_target: string,
        }): Promise<RuleTestResult> => {
            return this.request(`/api/knowledge/rules/test`, {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        /**
         * GET /api/knowledge/rules/export - Export rules as CSV or JSON
         */
        exportRules: async (format: string = 'csv', domain?: string, status?: string): Promise<Blob> => {
            let url = `/api/knowledge/rules/export?format=${format}`;
            if (domain) url += `&domain=${domain}`;
            if (status) url += `&status=${status}`;

            const token = getAuthToken();
            const headers: Record<string, string> = {};
            if (token) headers["Authorization"] = `Bearer ${token}`;

            const res = await fetch(`${API_BASE}${url}`, { headers });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `API Error: ${res.status}`);
            }
            return res.blob();
        },

        /**
         * POST /api/knowledge/rules/import - Import rules from CSV/JSON file
         */
        importRules: async (file: File): Promise<{ imported: number, skipped: number, errors: string[] }> => {
            const formData = new FormData();
            formData.append('file', file);

            const token = getAuthToken();
            const headers: Record<string, string> = {};
            if (token) headers["Authorization"] = `Bearer ${token}`;

            const res = await fetch(`${API_BASE}/api/knowledge/rules/import`, {
                method: 'POST',
                headers,
                body: formData
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `API Error: ${res.status}`);
            }
            return res.json();
        },

        /**
         * GET /api/knowledge/rules/analytics
         */
        getAnalytics: async (domain?: string, minFires?: number): Promise<RuleAnalytics[]> => {
            let url = `/api/knowledge/rules/analytics`;
            const params: string[] = [];
            if (domain) params.push(`domain=${domain}`);
            if (minFires) params.push(`min_fires=${minFires}`);
            if (params.length) url += `?${params.join('&')}`;
            return this.request(url);
        },

        /**
         * POST /api/knowledge/glossaries/upload
         */
        uploadGlossary: async (file: File, glossaryId: string, version: string, srcLang: string = 'en', tgtLang: string = 'fr'): Promise<ApiAck & { term_count?: number; imported?: number }> => {
            const formData = new FormData();
            formData.append('file', file);

            const token = getAuthToken();
            const headers: Record<string, string> = {};
            if (token) headers["Authorization"] = `Bearer ${token}`;

            const url = `${API_BASE}/api/knowledge/glossaries/upload?glossary_id=${encodeURIComponent(glossaryId)}&version=${encodeURIComponent(version)}&source_language=${srcLang}&target_language=${tgtLang}`;
            const res = await fetch(url, {
                method: 'POST',
                headers,
                body: formData
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `API Error: ${res.status}`);
            }
            return res.json();
        },

        /**
         * GET /api/knowledge/glossaries/{id}/{version}/terms
         */
        getGlossaryTerms: async (glossaryId: string, version: string): Promise<GlossaryTerm[]> => {
            return this.request(`/api/knowledge/glossaries/${encodeURIComponent(glossaryId)}/${encodeURIComponent(version)}/terms`);
        },

        /**
         * PATCH /api/knowledge/glossaries/{id}/{version} - Toggle active, update meta
         */
        updateGlossary: async (glossaryId: string, version: string, data: { is_active?: boolean; meta_json?: Record<string, unknown> }): Promise<ApiAck> => {
            return this.request(`/api/knowledge/glossaries/${encodeURIComponent(glossaryId)}/${encodeURIComponent(version)}`, {
                method: 'PATCH',
                body: JSON.stringify(data)
            });
        },

        /**
         * DELETE /api/knowledge/glossaries/{id}/{version}
         */
        deleteGlossary: async (glossaryId: string, version: string): Promise<ApiAck> => {
            return this.request(`/api/knowledge/glossaries/${encodeURIComponent(glossaryId)}/${encodeURIComponent(version)}`, {
                method: 'DELETE'
            });
        },

        /**
         * POST /api/knowledge/glossaries/{id}/{version}/terms - Add single term
         */
        addTerm: async (glossaryId: string, version: string, term: { source_text: string; target_text: string; is_forbidden?: boolean }): Promise<GlossaryTerm> => {
            return this.request(`/api/knowledge/glossaries/${encodeURIComponent(glossaryId)}/${encodeURIComponent(version)}/terms`, {
                method: 'POST',
                body: JSON.stringify(term)
            });
        },

        /**
         * PATCH /api/knowledge/glossaries/{id}/{version}/terms/{termId}
         */
        updateTerm: async (glossaryId: string, version: string, termId: string, data: { target_text?: string; is_forbidden?: boolean }): Promise<GlossaryTerm> => {
            return this.request(`/api/knowledge/glossaries/${encodeURIComponent(glossaryId)}/${encodeURIComponent(version)}/terms/${encodeURIComponent(termId)}`, {
                method: 'PATCH',
                body: JSON.stringify(data)
            });
        },

        /**
         * DELETE /api/knowledge/glossaries/{id}/{version}/terms/{termId}
         */
        deleteTerm: async (glossaryId: string, version: string, termId: string): Promise<ApiAck> => {
            return this.request(`/api/knowledge/glossaries/${encodeURIComponent(glossaryId)}/${encodeURIComponent(version)}/terms/${encodeURIComponent(termId)}`, {
                method: 'DELETE'
            });
        },

        /**
         * GET /api/knowledge/glossaries/{id}/{version}/export - Download as CSV
         */
        exportGlossary: async (glossaryId: string, version: string): Promise<Blob> => {
            const token = getAuthToken();
            const headers: Record<string, string> = {};
            if (token) headers["Authorization"] = `Bearer ${token}`;
            const res = await fetch(`${API_BASE}/api/knowledge/glossaries/${encodeURIComponent(glossaryId)}/${encodeURIComponent(version)}/export`, { headers });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `API Error: ${res.status}`);
            }
            return res.blob();
        },

        /**
         * POST /api/knowledge/rules/{ruleId}/report-false-positive
         */
        reportFalsePositive: async (ruleId: string): Promise<ApiAck> => {
            return this.request(`/api/knowledge/rules/${ruleId}/report-false-positive`, {
                method: 'POST'
            });
        },

        /**
         * POST /api/knowledge/feedback
         */
        submitFeedback: async (data: {
            source_text: string,
            target_text: string,
            corrected_text?: string,
            rating: 'positive' | 'negative',
            comment?: string,
            target_language: string
        }): Promise<ApiAck> => {
            return this.request(`/api/knowledge/feedback`, {
                method: 'POST',
                body: JSON.stringify(data)
            });
        }
    };

    // === Documents API (/api/documents) ===
    public documents = {
        /**
         * POST /api/documents - Upload and extract document
         */
        upload: async (file: File, sourceLang: string = "en", targetLang?: string, glossaryId?: string): Promise<Document> => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('source_language', sourceLang);
            if (targetLang) formData.append('target_language', targetLang);

            const uploadHeaders: Record<string, string> = {};
            const uploadToken = getAuthToken();
            if (uploadToken) uploadHeaders["Authorization"] = `Bearer ${uploadToken}`;

            let uploadUrl = `${API_BASE}/api/documents`;
            if (glossaryId) uploadUrl += `?glossary_id=${encodeURIComponent(glossaryId)}`;

            const res = await fetch(uploadUrl, {
                method: 'POST',
                headers: uploadHeaders,
                body: formData
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "Upload failed" }));
                throw new Error(err.detail || "Upload failed");
            }
            return res.json();
        },

        /**
         * GET /api/documents - List documents with pagination
         */
        list: async (page = 1, pageSize = 20, status?: string): Promise<DocumentListResponse> => {
            let url = `/api/documents?page=${page}&page_size=${pageSize}`;
            if (status) url += `&status=${status}`;
            return this.request(url);
        },

        /**
         * GET /api/documents/{doc_id} - Get single document
         */
        get: async (id: string): Promise<Document> => {
            return this.request(`/api/documents/${id}`);
        },

        /**
         * PATCH /api/documents/{doc_id} - Update document
         */
        update: async (id: string, data: Partial<Document>): Promise<Document> => {
            return this.request(`/api/documents/${id}`, {
                method: 'PATCH',
                body: JSON.stringify(data),
            });
        },

        /**
         * DELETE /api/documents/{doc_id} - Delete document with audit trail
         */
        delete: async (id: string, reason?: string): Promise<{ deletion_id: string; document_name: string }> => {
            let url = `/api/documents/${id}`;
            if (reason) url += `?reason=${encodeURIComponent(reason)}`;
            return this.request(url, { method: 'DELETE' });
        },

        /**
         * GET /api/documents/deletions - List deletion audit records
         */
        listDeletions: async (): Promise<DeletionRecord[]> => {
            return this.request('/api/documents/deletions');
        },

        /**
         * POST /api/documents/{doc_id}/translate - Start translation job
         * @param segmentIds - Optional array of segment IDs to translate. If omitted, all segments are translated.
         */
        translate: async (docId: string, targetLanguage: string, segmentIds?: string[]): Promise<{ document_id: string; status: string; message: string }> => {
            return this.request(`/api/documents/${docId}/translate`, {
                method: 'POST',
                body: JSON.stringify({
                    target_language: targetLanguage,
                    segment_ids: segmentIds  // Optional: only translate selected segments
                }),
            });
        },

        /**
         * GET /api/documents/{doc_id}/download-translated - Download translated document
         */
        downloadTranslated: async (docId: string): Promise<Blob> => {
            const dlHeaders: Record<string, string> = {};
            const dlToken = getAuthToken();
            if (dlToken) dlHeaders["Authorization"] = `Bearer ${dlToken}`;
            const res = await fetch(`${API_BASE}/api/documents/${docId}/download-translated`, { headers: dlHeaders });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "Download failed" }));
                throw new Error(err.detail || "Download failed");
            }
            return res.blob();
        },

        /**
         * GET /api/documents/{doc_id}/estimate - Pre-translation cost estimate
         */
        estimate: async (docId: string): Promise<{
            segment_count: number;
            word_count: number;
            translation_batches: number;
            total_llm_calls: number;
            estimated_total_tokens: number;
            estimated_cost_usd: number;
            estimated_seconds: number;
            model: string;
        }> => {
            return this.request(`/api/documents/${docId}/estimate`);
        },

        /**
         * GET /api/documents/{doc_id}/audit-export - Export audit certificate
         */
        exportAuditCertificate: async (docId: string): Promise<Blob> => {
            const exportHeaders: Record<string, string> = {};
            const exportToken = getAuthToken();
            if (exportToken) exportHeaders["Authorization"] = `Bearer ${exportToken}`;
            const res = await fetch(`${API_BASE}/api/documents/${docId}/audit-export`, { headers: exportHeaders });
            return res.blob();
        },
    };

    // === Segments API (/api/documents/{doc_id}/segments, /api/segments) ===
    public segments = {
        /**
         * GET /api/documents/{doc_id}/segments - List segments for document
         */
        list: async (docId: string): Promise<Segment[]> => {
            return this.request(`/api/documents/${docId}/segments`);
        },

        /**
         * GET /api/segments/{segment_id} - Get single segment
         */
        get: async (id: string): Promise<Segment> => {
            return this.request(`/api/segments/${id}`);
        },

        /**
         * PATCH /api/segments/{segment_id} - Update segment translation (HITL edit)
         */
        update: async (id: string, translatedText: string, reason: string): Promise<Segment> => {
            return this.request(`/api/segments/${id}`, {
                method: 'PATCH',
                body: JSON.stringify({ translated_text: translatedText, reason }),
            });
        },

        /**
         * POST /api/segments/{segment_id}/reverse - Reverse translate for verification
         */
        reverse: async (id: string): Promise<{ segment_id: string; original_source: string; translated_text: string; reverse_translation: string }> => {
            return this.request(`/api/segments/${id}/reverse`, { method: 'POST' });
        },

        /**
         * GET /api/segments/{segment_id}/changelog - Get segment edit history
         */
        getChangelog: async (id: string): Promise<SegmentChangelogEntry[]> => {
            return this.request(`/api/segments/${id}/changelog`);
        },
    };

    // === Translation Jobs API (/api/v1/translations) ===
    public jobs = {
        /**
         * POST /api/v1/translations - Create translation job (with LLM + quality gates)
         */
        create: async (documentId: string, targetLanguage: string, options?: {
            enforce_glossary?: boolean
            risk_tier?: 'critical' | 'high' | 'medium' | 'low'
            archetype?: string
        }): Promise<{ job_id: string; status: string; message: string }> => {
            return this.request(`/api/v1/translations`, {
                method: 'POST',
                body: JSON.stringify({
                    document_id: documentId,
                    target_language: targetLanguage,
                    ...options
                }),
            });
        },

        /**
         * GET /api/v1/translations - List translation jobs
         */
        list: async (limit = 50, skip = 0): Promise<Job[]> => {
            return this.request(`/api/v1/translations?limit=${limit}&skip=${skip}`);
        },

        /**
         * GET /api/v1/translations/{job_id}/status - Get job status
         */
        getStatus: async (jobId: string): Promise<{ job_id: string; status: string; progress: number }> => {
            return this.request(`/api/v1/translations/${jobId}/status`);
        },

        /**
         * GET /api/v1/translations/{job_id}/result - Get full job result with scorecard
         */
        getResult: async (jobId: string): Promise<JobResult> => {
            return this.request(`/api/v1/translations/${jobId}/result`);
        },

        /**
         * GET /api/v1/translations/{job_id}/audit-bundle - Get regulatory audit bundle
         */
        getAuditBundle: async (jobId: string): Promise<AuditBundle> => {
            return this.request(`/api/v1/translations/${jobId}/audit-bundle`);
        },

        /**
         * GET /api/v1/translations/{job_id}/certificate - Download PDF certificate
         */
        downloadCertificate: async (jobId: string): Promise<Blob> => {
            const certHeaders: Record<string, string> = {};
            const certToken = getAuthToken();
            if (certToken) certHeaders["Authorization"] = `Bearer ${certToken}`;
            const res = await fetch(`${API_BASE}/api/v1/translations/${jobId}/certificate`, { headers: certHeaders });
            return res.blob();
        },
    };

    // === Audit API (/api/v1/audit) ===
    public audit = {
        /**
         * GET /api/v1/audit/{audit_id} - Get audit record
         */
        get: async (auditId: string): Promise<Record<string, unknown>> => {
            return this.request(`/api/v1/audit/${auditId}`);
        },

        /**
         * GET /api/documents/{doc_id}/audit - Get document audit trail
         */
        getDocumentAudit: async (docId: string): Promise<Record<string, unknown>[]> => {
            return this.request(`/api/documents/${docId}/audit`);
        },

        /**
         * GET /api/v1/translations - List recent audit logs (uses jobs as proxy)
         */
        list: async (_options?: { limit?: number }): Promise<AuditLog[]> => {
            // For now return empty - backend doesn't have dedicated audit list endpoint
            // In production this would call a proper audit log endpoint
            return [];
        },
    };

    // === Legacy Quick Translate API (/api/v1/translate) ===
    public translate = {
        /**
         * POST /api/v1/translate - Quick text translation
         */
        text: async (text: string, targetLang: string, sourceLang: string = "en", options?: {
            domain?: string
            audience?: string
            risk_level?: string
        }): Promise<{ request_id: string; job_id: string; decision: string; translated_text?: string }> => {
            return this.request(`/api/v1/translate`, {
                method: 'POST',
                body: JSON.stringify({
                    blocks: [{ text, type: "text" }],
                    source_language: sourceLang,
                    target_language: targetLang,
                    domain: options?.domain || "pharmaceutical",
                    audience: options?.audience || "patient",
                    risk_level: options?.risk_level || "high",
                }),
            });
        },

        /**
         * GET /api/v1/translate/{job_id} - Poll translation status
         */
        getStatus: async (jobId: string): Promise<{ status?: string; translated_text?: string; [extra: string]: unknown }> => {
            return this.request(`/api/v1/translate/${jobId}`);
        },

        /**
         * GET /api/v1/translate/{job_id} - Get job result (alias for getStatus)
         */
        getJob: async (jobId: string): Promise<{ translated_text?: string; status?: string }> => {
            return this.request(`/api/v1/translate/${jobId}`);
        },

        /**
         * POST /api/v1/translate/quick - Synchronous quick translation (no background job)
         */
        quick: async (text: string, targetLang: string, sourceLang: string = "en"): Promise<{
            translated_text: string;
            confidence: number;
            checks: Array<{ label: string; status: string }>;
            source_text: string;
            target_language: string;
        }> => {
            return this.request(`/api/v1/translate/quick`, {
                method: 'POST',
                body: JSON.stringify({
                    text,
                    target_language: targetLang,
                    source_language: sourceLang,
                }),
            });
        },
    };

    // === Translation Toolkit API (/api/tools) ===
    public tools = {
        /**
         * POST /api/tools/audit
         */
        audit: async (sourceText: string, translatedText: string, targetLang: string): Promise<ToolAuditReport> => {
            return this.request(`/api/tools/audit`, {
                method: 'POST',
                body: JSON.stringify({ source_text: sourceText, translated_text: translatedText, target_language: targetLang })
            });
        },

        /**
         * POST /api/tools/back-translate
         */
        backTranslate: async (translatedText: string, targetLang: string, sourceText?: string): Promise<ToolBackTranslationResult> => {
            const endpoint = sourceText ? '/api/tools/back-translate/with-source' : '/api/tools/back-translate';
            const body = sourceText
                ? { source_text: sourceText, translated_text: translatedText, target_language: targetLang }
                : { translated_text: translatedText, target_language: targetLang };

            return this.request(endpoint, {
                method: 'POST',
                body: JSON.stringify(body)
            });
        },

        /**
         * POST /api/tools/translate/universal
         */
        universal: async (text: string, sourceLang: string, targetLang: string): Promise<ToolUniversalResult> => {
            return this.request(`/api/tools/translate/universal`, {
                method: 'POST',
                body: JSON.stringify({ text, source_language: sourceLang, target_language: targetLang })
            });
        },

        /**
         * POST /api/tools/matrix
         */
        matrix: async (text: string, languages: string[]): Promise<ToolMatrixResult> => {
            return this.request(`/api/tools/matrix`, {
                method: 'POST',
                body: JSON.stringify({ text, languages })
            });
        },
    };

    // === Dashboard ===
    public dashboard = {
        stats: async (): Promise<{
            total_documents: number;
            active_jobs: number;
            avg_quality_pct: number | null;
            completed_24h: number;
            total_segments: number;
            translated_segments: number;
            total_tokens: number;
            total_cost_usd: number;
        }> => {
            return this.request('/api/dashboard/stats');
        },
        activity: async (limit: number = 10): Promise<Array<{
            id: string;
            title: string;
            desc: string;
            status: string;
            priority: string;
            target_language: string;
            updated_at: string | null;
        }>> => {
            return this.request(`/api/dashboard/activity?limit=${limit}`);
        },
    };

    // === Health Check ===
    public health = async (): Promise<{ status: string; service: string; version: string }> => {
        return this.request('/health');
    };
}

export const api = new ApiClient();
