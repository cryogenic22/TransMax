"use client"

import { FolderOpen, FileText, Plus } from "lucide-react"
import { useParams } from "next/navigation"

export default function ProjectDetailPage() {
    const params = useParams()
    const projectId = params.id as string

    const project = {
        id: projectId,
        name: projectId === "pharma-translations" ? "Pharma Translations" : `Project ${projectId}`,
        documents: [
            { id: "mounjaro-pil", name: "Mounjaro PIL", status: "in-progress", languages: ["German", "French"] },
            { id: "ozempic-spc", name: "Ozempic SPC", status: "completed", languages: ["Spanish"] },
        ]
    }

    return (
        <div style={{ padding: "2rem", maxWidth: "1000px", margin: "0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.5rem" }}>
                <div style={{ width: "48px", height: "48px", background: "linear-gradient(135deg, #4285f4, #1a73e8)", borderRadius: "12px", display: "flex", alignItems: "center", justifyContent: "center", color: "white" }}>
                    <FolderOpen size={24} />
                </div>
                <div>
                    <h1 style={{ fontSize: "1.5rem", fontWeight: 500, margin: 0 }}>{project.name}</h1>
                    <p style={{ color: "#666", margin: 0, fontSize: "0.875rem" }}>{project.documents.length} documents</p>
                </div>
            </div>

            <button style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.625rem 1rem", background: "linear-gradient(135deg, #4285f4, #1a73e8)", color: "white", border: "none", borderRadius: "8px", cursor: "pointer", marginBottom: "1.5rem", fontSize: "0.875rem", fontWeight: 500 }}>
                <Plus size={16} />
                Add Document
            </button>

            <div style={{ background: "white", borderRadius: "16px", border: "1px solid #e5e5e5", overflow: "hidden" }}>
                {project.documents.map(doc => (
                    <a href={`/workspace/documents/${doc.id}`} key={doc.id} style={{ display: "flex", alignItems: "center", gap: "1rem", padding: "1rem 1.5rem", borderBottom: "1px solid #f0f0f0", textDecoration: "none", color: "inherit" }}>
                        <FileText size={20} style={{ color: "#666" }} />
                        <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 500 }}>{doc.name}</div>
                            <div style={{ fontSize: "0.8125rem", color: "#999" }}>{doc.languages.join(", ")}</div>
                        </div>
                        <span style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem", borderRadius: "4px", background: doc.status === "completed" ? "#dcfce7" : "#fef3c7", color: doc.status === "completed" ? "#166534" : "#92400e" }}>
                            {doc.status}
                        </span>
                    </a>
                ))}
            </div>
        </div>
    )
}
