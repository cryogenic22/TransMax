import type { Metadata } from "next"
import "./workspace.css"
import TopNavigation from "@/components/TopNavigation"

export const metadata: Metadata = {
    title: "Workspace | TransMax",
    description: "Professional pharmaceutical translation workspace",
}

import WorkspaceShell from "@/components/WorkspaceShell"

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
