// Mock rules removed — all data now served from the Black Book API.
// This file is kept for type re-exports only.

export type RuleStatus = 'active' | 'pending' | 'rejected';
export type RuleType = 'glossary' | 'style' | 'grammar' | 'forbidden_term';

export interface TranslationRule {
    id: string;
    source_term: string;
    target_term: string;
    type: RuleType;
    status: RuleStatus;
    context: string;
    confidence: number;
    detected_at: string;
    client_id?: string;
}

export const MOCK_RULES: TranslationRule[] = [];
