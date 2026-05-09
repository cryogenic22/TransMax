"use client"

import React, { useEffect, useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { LayoutDashboard, List, ShieldCheck, Book, Building2 } from 'lucide-react'
import { DashboardView } from '@/components/control_views/DashboardView'
import { JobsView } from '@/components/control_views/JobsView'
import { ComplianceView } from '@/components/control_views/ComplianceView'
import { AssetsView } from '@/components/control_views/AssetsView'

export default function ControlTowerPage() {
    return (
        <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-slate-400">Loading...</div>}>
            <ControlTowerPageInner />
        </Suspense>
    )
}

function ControlTowerPageInner() {
    const searchParams = useSearchParams()
    const router = useRouter()
    const currentTab = searchParams.get('tab') || 'overview'

    const setActiveTab = (tab: string) => {
        router.push(`/workspace/control?tab=${tab}`)
    }

    return (
        <div className="max-w-7xl mx-auto p-4 md:p-8 min-h-screen font-sans">
            {/* Header */}
            <div className="flex items-center gap-3 mb-8">
                <div className="p-2 bg-slate-900 rounded-lg text-white shadow-lg shadow-slate-900/20">
                    <Building2 size={24} />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Control Tower</h1>
                    <p className="text-slate-500 text-sm">Unified command center for operations, governance, and assets.</p>
                </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex items-center gap-1 bg-slate-100/50 p-1 rounded-xl mb-8 w-fit border border-slate-200">
                <button
                    onClick={() => setActiveTab('overview')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${currentTab === 'overview' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
                        }`}
                >
                    <LayoutDashboard size={16} />
                    Overview
                </button>
                <button
                    onClick={() => setActiveTab('jobs')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${currentTab === 'jobs' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
                        }`}
                >
                    <List size={16} />
                    Jobs
                </button>
                <button
                    onClick={() => setActiveTab('compliance')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${currentTab === 'compliance' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
                        }`}
                >
                    <ShieldCheck size={16} />
                    Compliance & Audit
                </button>
                <button
                    onClick={() => setActiveTab('assets')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${currentTab === 'assets' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
                        }`}
                >
                    <Book size={16} />
                    Assets
                </button>
            </div>

            {/* View Content */}
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                {currentTab === 'overview' && <DashboardView />}
                {currentTab === 'jobs' && <JobsView />}
                {currentTab === 'compliance' && <ComplianceView />}
                {currentTab === 'assets' && <AssetsView />}
            </div>
        </div>
    )
}
