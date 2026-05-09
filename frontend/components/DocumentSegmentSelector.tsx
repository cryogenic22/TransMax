"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight, FileText, Check, Minus, Languages, Loader2 } from "lucide-react"
import { LanguageSelector } from "@/components/ui/LanguageSelector"

interface Segment {
    id: string
    text: string
    selected: boolean
    type: "heading" | "paragraph" | "list-item" | "table-cell"
}

interface Section {
    id: string
    title: string
    expanded: boolean
    selected: "all" | "some" | "none"
    segments: Segment[]
}

interface DocumentPreviewProps {
    documentName: string
    sections: Section[]
    onSectionsChange: (sections: Section[]) => void
    onTranslate: (selectedSegmentIds: string[]) => void
    isTranslating?: boolean
}

export default function DocumentSegmentSelector({
    documentName,
    sections,
    onSectionsChange,
    onTranslate,
    isTranslating = false
}: DocumentPreviewProps) {
    const [targetLanguage, setTargetLanguage] = useState("de")

    const toggleSection = (sectionId: string) => {
        const updated = sections.map(s =>
            s.id === sectionId ? { ...s, expanded: !s.expanded } : s
        )
        onSectionsChange(updated)
    }

    const toggleSectionSelection = (sectionId: string) => {
        const updated = sections.map(s => {
            if (s.id !== sectionId) return s

            const allSelected = s.segments.every(seg => seg.selected)
            const newSelected = !allSelected

            return {
                ...s,
                selected: newSelected ? "all" as const : "none" as const,
                segments: s.segments.map(seg => ({ ...seg, selected: newSelected }))
            }
        })
        onSectionsChange(updated)
    }

    const toggleSegment = (sectionId: string, segmentId: string) => {
        const updated = sections.map(s => {
            if (s.id !== sectionId) return s

            const newSegments = s.segments.map(seg =>
                seg.id === segmentId ? { ...seg, selected: !seg.selected } : seg
            )

            const allSelected = newSegments.every(seg => seg.selected)
            const noneSelected = newSegments.every(seg => !seg.selected)

            return {
                ...s,
                selected: allSelected ? "all" as const : noneSelected ? "none" as const : "some" as const,
                segments: newSegments
            }
        })
        onSectionsChange(updated)
    }

    const selectAll = () => {
        const updated = sections.map(s => ({
            ...s,
            selected: "all" as const,
            segments: s.segments.map(seg => ({ ...seg, selected: true }))
        }))
        onSectionsChange(updated)
    }

    const selectNone = () => {
        const updated = sections.map(s => ({
            ...s,
            selected: "none" as const,
            segments: s.segments.map(seg => ({ ...seg, selected: false }))
        }))
        onSectionsChange(updated)
    }

    const getSelectedCount = () => {
        return sections.reduce((acc, s) => acc + s.segments.filter(seg => seg.selected).length, 0)
    }

    const getTotalCount = () => {
        return sections.reduce((acc, s) => acc + s.segments.length, 0)
    }

    const getSelectedIds = () => {
        return sections.flatMap(s => s.segments.filter(seg => seg.selected).map(seg => seg.id))
    }

    const SectionCheckbox = ({ selected }: { selected: "all" | "some" | "none" }) => (
        <div className={`section-checkbox ${selected}`}>
            {selected === "all" && <Check size={12} />}
            {selected === "some" && <Minus size={12} />}
        </div>
    )

    return (
        <div className="segment-selector">
            {/* Header */}
            <div className="selector-header">
                <div className="header-info">
                    <FileText size={20} />
                    <div>
                        <h2>{documentName}</h2>
                        <p>{getTotalCount()} segments extracted</p>
                    </div>
                </div>
                <div className="header-actions">
                    <button onClick={selectAll} className="text-btn">Select All</button>
                    <button onClick={selectNone} className="text-btn">Clear</button>
                </div>
            </div>

            {/* Sections */}
            <div className="sections-list">
                {sections.map(section => (
                    <div key={section.id} className="section">
                        <div className="section-header" onClick={() => toggleSection(section.id)}>
                            <button
                                className="section-checkbox-btn"
                                onClick={(e) => { e.stopPropagation(); toggleSectionSelection(section.id); }}
                            >
                                <SectionCheckbox selected={section.selected} />
                            </button>

                            <span className="section-toggle">
                                {section.expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                            </span>

                            <span className="section-title">{section.title}</span>
                            <span className="section-count">
                                {section.segments.filter(s => s.selected).length}/{section.segments.length}
                            </span>
                        </div>

                        {section.expanded && (
                            <div className="segments-list">
                                {section.segments.map(segment => (
                                    <div
                                        key={segment.id}
                                        className={`segment ${segment.selected ? "selected" : ""}`}
                                        onClick={() => toggleSegment(section.id, segment.id)}
                                    >
                                        <div className={`segment-checkbox ${segment.selected ? "checked" : ""}`}>
                                            {segment.selected && <Check size={10} />}
                                        </div>
                                        <span className={`segment-type ${segment.type}`}>
                                            {segment.type === "heading" ? "H" : segment.type === "list-item" ? "•" : "¶"}
                                        </span>
                                        <p className="segment-text">{segment.text}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {/* Footer */}
            <div className="selector-footer">
                <div className="selection-summary">
                    <strong>{getSelectedCount()}</strong> of {getTotalCount()} segments selected
                </div>
                <div className="footer-actions">
                    <LanguageSelector
                        value={targetLanguage}
                        onChange={setTargetLanguage}
                    />
                    <button
                        className="translate-btn"
                        disabled={getSelectedCount() === 0 || isTranslating}
                        onClick={() => onTranslate(getSelectedIds())}
                    >
                        {isTranslating ? (
                            <>
                                <Loader2 size={16} className="spinning" />
                                Translating...
                            </>
                        ) : (
                            <>
                                <Languages size={16} />
                                Translate Selected
                            </>
                        )}
                    </button>
                </div>
            </div>

            <style jsx>{`
                .segment-selector {
                    background: white;
                    border: 1px solid #e5e5e5;
                    border-radius: 16px;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                    max-height: 70vh;
                }

                .selector-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 1rem 1.5rem;
                    border-bottom: 1px solid #e5e5e5;
                    background: #fafafa;
                }

                .header-info {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                }

                .header-info h2 {
                    font-size: 1rem;
                    font-weight: 500;
                    margin: 0;
                }

                .header-info p {
                    font-size: 0.8125rem;
                    color: #666;
                    margin: 0;
                }

                .header-actions {
                    display: flex;
                    gap: 1rem;
                }

                .text-btn {
                    background: none;
                    border: none;
                    color: #1a73e8;
                    font-size: 0.875rem;
                    cursor: pointer;
                    font-weight: 500;
                }

                .text-btn:hover {
                    text-decoration: underline;
                }

                .sections-list {
                    flex: 1;
                    overflow-y: auto;
                }

                .section {
                    border-bottom: 1px solid #f0f0f0;
                }

                .section-header {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    padding: 0.75rem 1rem;
                    cursor: pointer;
                    transition: background 0.15s;
                }

                .section-header:hover {
                    background: #f8f8f8;
                }

                .section-checkbox-btn {
                    background: none;
                    border: none;
                    padding: 0;
                    cursor: pointer;
                }

                .section-checkbox {
                    width: 18px;
                    height: 18px;
                    border: 2px solid #ccc;
                    border-radius: 4px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    transition: all 0.15s;
                }

                .section-checkbox.all {
                    background: #1a73e8;
                    border-color: #1a73e8;
                }

                .section-checkbox.some {
                    background: #1a73e8;
                    border-color: #1a73e8;
                }

                .section-toggle {
                    color: #666;
                }

                .section-title {
                    flex: 1;
                    font-weight: 500;
                    font-size: 0.9375rem;
                }

                .section-count {
                    font-size: 0.75rem;
                    color: #999;
                    background: #f0f0f0;
                    padding: 0.125rem 0.5rem;
                    border-radius: 10px;
                }

                .segments-list {
                    background: #fafafa;
                    border-top: 1px solid #f0f0f0;
                }

                .segment {
                    display: flex;
                    align-items: flex-start;
                    gap: 0.625rem;
                    padding: 0.625rem 1rem 0.625rem 2.5rem;
                    cursor: pointer;
                    transition: background 0.15s;
                    border-bottom: 1px solid #f0f0f0;
                }

                .segment:hover {
                    background: #f0f0f0;
                }

                .segment.selected {
                    background: #e8f0fe;
                }

                .segment-checkbox {
                    width: 16px;
                    height: 16px;
                    border: 2px solid #ccc;
                    border-radius: 3px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    flex-shrink: 0;
                    margin-top: 2px;
                }

                .segment-checkbox.checked {
                    background: #1a73e8;
                    border-color: #1a73e8;
                }

                .segment-type {
                    width: 20px;
                    height: 20px;
                    background: #e0e0e0;
                    border-radius: 4px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 0.625rem;
                    font-weight: 600;
                    color: #666;
                    flex-shrink: 0;
                }

                .segment-type.heading {
                    background: #fef3c7;
                    color: #92400e;
                }

                .segment-text {
                    flex: 1;
                    font-size: 0.875rem;
                    line-height: 1.5;
                    margin: 0;
                    color: #333;
                }

                .selector-footer {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 1rem 1.5rem;
                    border-top: 1px solid #e5e5e5;
                    background: white;
                }

                .selection-summary {
                    font-size: 0.875rem;
                    color: #666;
                }

                .footer-actions {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                }

                .language-select {
                    padding: 0.5rem 0.75rem;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    font-size: 0.875rem;
                    background: white;
                }

                .translate-btn {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    padding: 0.625rem 1.25rem;
                    background: linear-gradient(135deg, #4285f4, #1a73e8);
                    color: white;
                    border: none;
                    border-radius: 24px;
                    font-size: 0.875rem;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s;
                }

                .translate-btn:hover:not(:disabled) {
                    transform: translateY(-1px);
                    box-shadow: 0 4px 12px rgba(26, 115, 232, 0.3);
                }

                .translate-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .spinning {
                    animation: spin 1s linear infinite;
                }

                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    )
}
