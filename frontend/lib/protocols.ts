export interface Protocol {
    id: string;
    name: string;
    description: string;
    archetype: 'SAFETY_CRITICAL' | 'ANALYTICAL' | 'INFORMATIONAL';
    tier: 'TIER_A' | 'TIER_B' | 'TIER_C';
    target_languages: string[];
    governance_features: string[];
}

export interface ClientProfile {
    id: string;
    name: string;
    products: {
        id: string;
        name: string;
        protocols: Protocol[];
    }[];
}

// In a real app, this would come from GET /api/v1/clients
export const MOCK_CLIENTS: ClientProfile[] = [
    {
        id: "cli-001",
        name: "BioCorp Pharmaceuticals",
        products: [
            {
                id: "prod-001",
                name: "CardioFix (Atorvastatin)",
                protocols: [
                    {
                        id: "proto-jpn-001",
                        name: "Japan PMDA Submission",
                        description: "High-strictness protocol for regulatory approval in Japan.",
                        archetype: "SAFETY_CRITICAL",
                        tier: "TIER_A",
                        target_languages: ["ja"],
                        governance_features: ["Dosage Guard", "Term Consistency", "Double Blind Audit"]
                    },
                    {
                        id: "proto-eu-002",
                        name: "EU Patient Leaflet",
                        description: "Standard readability protocol for EMA compliance.",
                        archetype: "INFORMATIONAL",
                        tier: "TIER_B",
                        target_languages: ["fr", "de", "es", "it"],
                        governance_features: ["Readability Score", "Term Consistency"]
                    }
                ]
            },
            {
                id: "prod-002",
                name: "NeuroCalm",
                protocols: []
            }
        ]
    },
    {
        id: "cli-002",
        name: "MediLife Devices",
        products: [
            {
                id: "prod-003",
                name: "Surgical Robot X1",
                protocols: [
                    {
                        id: "proto-if-001",
                        name: "Instructions for Use (IFU)",
                        description: "Safety critical device manual translation.",
                        archetype: "SAFETY_CRITICAL",
                        tier: "TIER_A",
                        target_languages: ["zh", "ko", "ja"],
                        governance_features: ["Safety Warning Guard", "Unit Conversion"]
                    }
                ]
            }
        ]
    }
];
