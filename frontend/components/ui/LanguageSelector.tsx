"use client"

import * as React from "react"
import { Check, ChevronsUpDown, Search } from "lucide-react"
import { cn } from "@/lib/utils"
import { asValueLabel } from "@/lib/languages"

interface LanguageSelectorProps {
    value: string
    onChange: (value: string) => void
    className?: string
    includeAuto?: boolean
    languages?: { value: string; label: string }[]
}

export function LanguageSelector({ value, onChange, className, includeAuto = false, languages }: LanguageSelectorProps) {
    const [open, setOpen] = React.useState(false)
    const [search, setSearch] = React.useState("")
    const wrapperRef = React.useRef<HTMLDivElement>(null)

    const effectiveLanguages = languages ?? asValueLabel()

    const filtered = effectiveLanguages.filter(l =>
        l.label.toLowerCase().includes(search.toLowerCase()) ||
        l.value.toLowerCase().includes(search.toLowerCase())
    )

    const selectedLabel = value === 'auto' ? "✨ Detect Language" : (effectiveLanguages.find(l => l.value === value)?.label || "Select language...")

    // Click outside to close
    React.useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
                setOpen(false)
            }
        }
        document.addEventListener("mousedown", handleClickOutside)
        return () => document.removeEventListener("mousedown", handleClickOutside)
    }, [])

    return (
        <div className={cn("relative", className)} ref={wrapperRef}>
            <button
                onClick={() => setOpen(!open)}
                className="w-full min-w-[180px] flex items-center justify-between px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500/10 transition-all shadow-sm"
            >
                <div className="flex items-center gap-2 truncate">
                    {selectedLabel}
                </div>
                <ChevronsUpDown size={14} className="text-slate-400 opacity-50" />
            </button>

            {open && (
                <div className="absolute top-full left-0 right-0 mt-2 z-50 bg-white border border-slate-200 rounded-xl shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 origin-top">
                    <div className="p-2 border-b border-slate-100 bg-slate-50/50">
                        <div className="relative">
                            <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
                            <input
                                autoFocus
                                type="text"
                                placeholder="Search..."
                                className="w-full pl-8 pr-3 py-1.5 text-sm bg-white border border-slate-200 rounded-md focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 focus:outline-none transition-all placeholder:text-slate-400"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                            />
                        </div>
                    </div>

                    <div className="max-h-[240px] overflow-y-auto p-1 scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent">
                        {includeAuto && (search === "" || "detect language".includes(search.toLowerCase())) && (
                            <button
                                onClick={() => { onChange('auto'); setOpen(false); setSearch("") }}
                                className={cn(
                                    "w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg transition-colors text-left mb-1",
                                    value === 'auto' ? "bg-indigo-50 text-indigo-700 font-medium" : "hover:bg-slate-50 text-slate-700"
                                )}
                            >
                                <span className="flex items-center gap-2">✨ Detect Language</span>
                                {value === 'auto' && <Check size={14} />}
                            </button>
                        )}

                        {filtered.length === 0 ? (
                            <div className="p-4 text-xs text-center text-slate-400 italic">No language found.</div>
                        ) : (
                            filtered.map((lang) => (
                                <button
                                    key={lang.value}
                                    onClick={() => {
                                        onChange(lang.value)
                                        setOpen(false)
                                        setSearch("")
                                    }}
                                    className={cn(
                                        "w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg transition-colors text-left",
                                        value === lang.value ? "bg-blue-50 text-blue-700 font-medium" : "hover:bg-slate-50 text-slate-700"
                                    )}
                                >
                                    <span>{lang.label}</span>
                                    {value === lang.value && <Check size={14} />}
                                </button>
                            ))
                        )}
                    </div>
                    <style jsx>{`
                        .scrollbar-thin::-webkit-scrollbar {
                            width: 6px;
                        }
                        .scrollbar-thin::-webkit-scrollbar-track {
                            background: transparent;
                        }
                        .scrollbar-thin::-webkit-scrollbar-thumb {
                            background-color: #cbd5e1;
                            border-radius: 20px;
                        }
                    `}</style>
                </div>
            )}
        </div>
    )
}
