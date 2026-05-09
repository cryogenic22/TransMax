"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
    FileText,
    Upload,
    Settings,
    ChevronDown,
    ChevronRight,
    Search,
    LayoutDashboard,
    Briefcase,
    Sparkles,
    BookOpen
} from "lucide-react"
import RequireRole from "@/components/auth/RequireRole"

interface SidebarProps {
    recentDocuments?: { id: string; name: string; status: string }[]
}

export default function Sidebar({
    recentDocuments = [],
}: SidebarProps) {
    const pathname = usePathname()
    const [expandedSections, setExpandedSections] = useState<string[]>(["documents"])

    const toggleSection = (section: string) => {
        setExpandedSections(prev =>
            prev.includes(section)
                ? prev.filter(s => s !== section)
                : [...prev, section]
        )
    }

    const isActive = (path: string) => pathname === path
    const isCollapsed = pathname === '/workspace' || pathname === '/'

    return (
        <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
            {/* Search - Logo moved to top navigation */}
            <div className="sidebar-search" style={{ marginTop: "0.5rem", display: isCollapsed ? 'none' : 'block' }}>
                <Search size={16} className="sidebar-search-icon" />
                <input
                    type="text"
                    placeholder="Search documents..."
                    className="sidebar-search-input"
                />
            </div>

            {/* Navigation */}
            <nav className="sidebar-nav">
                {/* Main Links */}
                <div className="sidebar-section">
                    <Link
                        href="/workspace"
                        className={`sidebar-item ${isActive("/workspace") ? "active" : ""}`}
                    >
                        <Sparkles size={18} />
                        <span>Quick Translate</span>
                    </Link>
                    <Link
                        href="/workspace/upload"
                        className={`sidebar-item ${isActive("/workspace/upload") ? "active" : ""}`}
                    >
                        <Upload size={18} />
                        <span>Upload & Translate</span>
                    </Link>

                </div>

                {/* Control Tower Section */}
                <div className="sidebar-section">
                    <div
                        onClick={() => toggleSection("control")}
                        className={`sidebar-item cursor-pointer ${pathname.startsWith("/workspace/control") ? "active" : ""}`}
                        role="button"
                        tabIndex={0}
                    >
                        <LayoutDashboard size={18} />
                        <span>Control Tower</span>
                        {expandedSections.includes("control") ? (
                            <ChevronDown size={14} className="ml-auto" />
                        ) : (
                            <ChevronRight size={14} className="ml-auto" />
                        )}
                    </div>
                    <AnimatePresence>
                        {expandedSections.includes("control") && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="sidebar-section-content"
                            >
                                <Link href="/workspace/control?tab=overview" className="sidebar-subitem">
                                    <span className="sidebar-subitem-dot" />
                                    <span>Overview</span>
                                </Link>
                                <Link href="/workspace/control?tab=jobs" className="sidebar-subitem">
                                    <span className="sidebar-subitem-dot" />
                                    <span>Jobs</span>
                                </Link>
                                <Link href="/workspace/control?tab=compliance" className="sidebar-subitem">
                                    <span className="sidebar-subitem-dot" />
                                    <span>Compliance</span>
                                </Link>
                                <Link href="/workspace/control?tab=assets" className="sidebar-subitem">
                                    <span className="sidebar-subitem-dot" />
                                    <span>Assets</span>
                                </Link>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Knowledge Base */}
                <div className="sidebar-section">
                    <Link
                        href="/workspace/tools"
                        className={`sidebar-item ${isActive("/workspace/tools") ? "active" : ""}`}
                    >
                        <BookOpen size={18} />
                        <span>Black Book</span>
                    </Link>
                </div>

                {/* Toolkit & Other Links */}
                <div className="sidebar-section">
                    <Link
                        href="/workspace/tools"
                        className={`sidebar-item ${isActive("/workspace/tools") ? "active" : ""}`}
                    >
                        <Briefcase size={18} />
                        <span>Toolkit</span>
                    </Link>
                </div>

                <style jsx>{`
                    .sidebar:not(.collapsed) {
                        width: 260px;
                        height: 100%;
                        transition: width 0.3s ease;
                    }
                    .sidebar.collapsed {
                        width: 70px;
                        height: 100%;
                        transition: width 0.3s ease;
                    }
                    .sidebar.collapsed .sidebar-item span {
                        display: none;
                    }
                    .sidebar.collapsed .sidebar-section-header span, 
                    .sidebar.collapsed .sidebar-section-header svg {
                        display: none;
                    }
                    .sidebar.collapsed .sidebar-item {
                        justify-content: center;
                        padding: 12px;
                    }
                    .sidebar.collapsed .sidebar-logo-text {
                        display: none;
                    }
                    /* Show Toolkit link if it was hidden in recent edits (it was not, but checking just in case) */
                `}</style>

                {/* Documents Section */}
                <div className="sidebar-section">
                    <div
                        onClick={() => toggleSection("documents")}
                        className="sidebar-section-header"
                        role="button"
                        tabIndex={0}
                    >
                        <div className="flex items-center gap-2">
                            {expandedSections.includes("documents") ? (
                                <ChevronDown size={14} />
                            ) : (
                                <ChevronRight size={14} />
                            )}
                            <FileText size={16} />
                            <span>Recent Documents</span>
                        </div>
                    </div>
                    <AnimatePresence>
                        {expandedSections.includes("documents") && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="sidebar-section-content"
                            >
                                {recentDocuments.length > 0 ? (
                                    recentDocuments.map(doc => (
                                        <Link
                                            key={doc.id}
                                            href={`/workspace/documents/${doc.id}`}
                                            className="sidebar-subitem"
                                        >
                                            <span className={`sidebar-status-dot ${doc.status}`} />
                                            <span className="truncate">{doc.name}</span>
                                        </Link>
                                    ))
                                ) : (
                                    <div className="sidebar-empty">No documents yet</div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </nav>

            {/* Bottom Actions */}
            <div className="sidebar-footer">
                <RequireRole roles={["admin", "project_manager"]}>
                    <Link href="/settings" className="sidebar-footer-btn subtle">
                        <Settings size={18} />
                        <span>Settings</span>
                    </Link>
                </RequireRole>
            </div>
        </aside >
    )
}
