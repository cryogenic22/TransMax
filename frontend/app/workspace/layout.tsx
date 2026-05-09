import type { Metadata } from "next"
import "./workspace.css"
import WorkspaceShell from "@/components/WorkspaceShell"

export const metadata: Metadata = {
    title: "Workspace | TransMax",
    description: "Professional pharmaceutical translation workspace",
}

export default function WorkspaceLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <WorkspaceShell>
            {children}
        </WorkspaceShell>
    )
}
