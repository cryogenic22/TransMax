export type LanguageTier = "tier1" | "tier2" | "tier3"

export interface Language {
    code: string
    name: string
    tier: LanguageTier
}

const LANGUAGES: Language[] = [
    // Tier 1 — Deep Quality (15)
    { code: "en", name: "English", tier: "tier1" },
    { code: "es", name: "Spanish (Español)", tier: "tier1" },
    { code: "zh", name: "Chinese (Simplified / 中文)", tier: "tier1" },
    { code: "zh-tw", name: "Chinese (Traditional / 繁體中文)", tier: "tier1" },
    { code: "ja", name: "Japanese (日本語)", tier: "tier1" },
    { code: "ar", name: "Arabic (العربية)", tier: "tier1" },
    { code: "fr", name: "French (Standard / Français)", tier: "tier1" },
    { code: "fr-ca", name: "French (Canada / Canadien)", tier: "tier1" },
    { code: "de", name: "German (Deutsch)", tier: "tier1" },
    { code: "pt", name: "Portuguese (Português)", tier: "tier1" },
    { code: "pt-br", name: "Portuguese (Brazilian)", tier: "tier1" },
    { code: "pt-pt", name: "Portuguese (European)", tier: "tier1" },
    { code: "ru", name: "Russian (Русский)", tier: "tier1" },
    { code: "it", name: "Italian (Italiano)", tier: "tier1" },
    { code: "ko", name: "Korean (한국어)", tier: "tier1" },

    // Tier 2 — Standard (18)
    { code: "hi", name: "Hindi (हिन्दी)", tier: "tier2" },
    { code: "ta", name: "Tamil (தமிழ்)", tier: "tier2" },
    { code: "bn", name: "Bengali (বাংলা)", tier: "tier2" },
    { code: "vi", name: "Vietnamese (Tiếng Việt)", tier: "tier2" },
    { code: "tr", name: "Turkish (Türkçe)", tier: "tier2" },
    { code: "pl", name: "Polish (Polski)", tier: "tier2" },
    { code: "nl", name: "Dutch (Nederlands)", tier: "tier2" },
    { code: "th", name: "Thai (ไทย)", tier: "tier2" },
    { code: "id", name: "Indonesian (Bahasa)", tier: "tier2" },
    { code: "el", name: "Greek (Ελληνικά)", tier: "tier2" },
    { code: "sv", name: "Swedish (Svenska)", tier: "tier2" },
    { code: "da", name: "Danish (Dansk)", tier: "tier2" },
    { code: "no", name: "Norwegian (Norsk)", tier: "tier2" },
    { code: "fi", name: "Finnish (Suomi)", tier: "tier2" },
    { code: "cs", name: "Czech (Čeština)", tier: "tier2" },
    { code: "ro", name: "Romanian (Română)", tier: "tier2" },
    { code: "hu", name: "Hungarian (Magyar)", tier: "tier2" },
    { code: "uk", name: "Ukrainian (Українська)", tier: "tier2" },

    // Tier 3 — Basic (5)
    { code: "he", name: "Hebrew (עברית)", tier: "tier3" },
    { code: "fa", name: "Persian (فارسی)", tier: "tier3" },
    { code: "ms", name: "Malay (Bahasa Melayu)", tier: "tier3" },
    { code: "tl", name: "Tagalog (Filipino)", tier: "tier3" },
    { code: "sw", name: "Swahili (Kiswahili)", tier: "tier3" },
]

export function getAllLanguages(): Language[] {
    return [...LANGUAGES].sort((a, b) => a.name.localeCompare(b.name))
}

export function getLanguagesByTier(tier: LanguageTier): Language[] {
    return LANGUAGES.filter(l => l.tier === tier).sort((a, b) => a.name.localeCompare(b.name))
}

export function getLanguageByCode(code: string): Language | undefined {
    return LANGUAGES.find(l => l.code === code)
}

export function getLanguageName(code: string): string {
    return LANGUAGES.find(l => l.code === code)?.name ?? code
}

export function asValueLabel(langs?: Language[]): { value: string; label: string }[] {
    return (langs ?? getAllLanguages()).map(l => ({ value: l.code, label: l.name }))
}
