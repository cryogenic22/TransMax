"use client"
import React, { useState } from 'react'
import { Copy, Check } from 'lucide-react'

export function CopyButton({ text }: { text: string }) {
    const [copied, setCopied] = useState(false)

    const handleCopy = async () => {
        if (!text) return
        try {
            await navigator.clipboard.writeText(text)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        } catch (err) {
            console.error('Failed to copy!', err)
        }
    }

    return (
        <button
            onClick={handleCopy}
            title="Copy to clipboard"
            className="p-1 hover:bg-slate-100 rounded transition-colors"
            style={{
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: copied ? '#188038' : '#9ca3af',
                transition: 'color 0.2s',
            }}
        >
            {copied ? <Check size={16} /> : <Copy size={16} />}
        </button>
    )
}
