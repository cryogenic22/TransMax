export type SegmentStatus = 'approved' | 'review_required' | 'rejected' | 'pending';
export type DefectSeverity = 'critical' | 'major' | 'minor' | 'info';

export interface Defect {
    id: string;
    type: string; // e.g., 'numerical_mismatch', 'term_drift'
    severity: DefectSeverity;
    message: string;
    suggestion?: string;
}

export interface AgentReasoning {
    step: string;
    status: 'pass' | 'fail' | 'warn';
    details: string;
    timestamp: string;
}

export interface PharmaSegment {
    id: string;
    index: number;
    source_text: string;
    target_text: string;
    status: SegmentStatus;
    confidence_score: number;
    defects: Defect[];
    reasoning_trace: AgentReasoning[];
}

export const MOCK_PHARMA_JOB: PharmaSegment[] = [
    {
        id: "seg-001",
        index: 1,
        source_text: "CLINICAL STUDY PROTOCOL: A Randomized, Double-Blind, Placebo-Controlled Study.",
        target_text: "PROTOCOL DE L'ÉTUDE CLINIQUE : Étude randomisée, en double aveugle, contrôlée par placebo.",
        status: "approved",
        confidence_score: 0.99,
        defects: [],
        reasoning_trace: [
            { step: "Glossary Check", status: "pass", details: "Matches 'Standard Protocol Header'", timestamp: "10:00:01" }
        ]
    },
    {
        id: "seg-002",
        index: 2,
        source_text: "Administer 10mg of Pembrolizumab intravenously every 3 weeks.",
        target_text: "Administrer 100mg de Pembrolizumab par voie intraveineuse toutes les 3 semaines.",
        status: "review_required",
        confidence_score: 0.20,
        defects: [
            {
                id: "def-01",
                type: "numerical_mismatch",
                severity: "critical",
                message: "Critical Dosage Error: Source '10mg' != Target '100mg'",
                suggestion: "10mg"
            }
        ],
        reasoning_trace: [
            { step: "Numerical Guard", status: "fail", details: "Detected value mismatch (10 vs 100)", timestamp: "10:00:02" }
        ]
    },
    {
        id: "seg-003",
        index: 3,
        source_text: "Patients with severe hypertension should be excluded.",
        target_text: "Les patients souffrant d'hypotension sévère doivent être exclus.",
        status: "review_required",
        confidence_score: 0.45,
        defects: [
            {
                id: "def-02",
                type: "term_mismatch",
                severity: "major",
                message: "Medical Contradiction: 'Hypertension' (High BP) translated as 'Hypotension' (Low BP).",
                suggestion: "hypertension"
            }
        ],
        reasoning_trace: [
            { step: "Medical Terminology", status: "fail", details: "Antonym detection triggered.", timestamp: "10:00:03" }
        ]
    },
    {
        id: "seg-004",
        index: 4,
        source_text: "The primary endpoint is Overall Survival (OS).",
        target_text: "Le critère d'évaluation principal est la Survie Globale (SG).",
        status: "approved",
        confidence_score: 0.98,
        defects: [],
        reasoning_trace: [
            { step: "Acronym Check", status: "pass", details: "OS -> SG (French) verified against glossary.", timestamp: "10:00:04" }
        ]
    },
    {
        id: "seg-005",
        index: 5,
        source_text: "Store at 2°C to 8°C (36°F to 46°F).",
        target_text: "Conserver entre 2°C et 8°C.",
        status: "review_required",
        confidence_score: 0.85,
        defects: [
            {
                id: "def-03",
                type: "omission",
                severity: "minor",
                message: "Fahrenheit conversion omitted (Protocol Requirement 4.2).",
                suggestion: "Conserver entre 2°C et 8°C (36°F à 46°F)."
            }
        ],
        reasoning_trace: [
            { step: "Completeness Check", status: "warn", details: "Parenthetical content missing in target.", timestamp: "10:00:05" }
        ]
    }
];
