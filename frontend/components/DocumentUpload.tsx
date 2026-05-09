"use client"

import React, { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileText, CheckCircle, Loader2 } from 'lucide-react'
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface DocumentUploadProps {
    onUpload: (file: File) => void
    isUploading: boolean
}

export function DocumentUpload({ onUpload, isUploading }: DocumentUploadProps) {
    const [isDragActive, setIsDragActive] = useState(false)
    const [selectedFile, setSelectedFile] = useState<File | null>(null)

    const handleDrag = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        if (e.type === "dragenter" || e.type === "dragover") {
            setIsDragActive(true)
        } else if (e.type === "dragleave") {
            setIsDragActive(false)
        }
    }, [])

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragActive(false)

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setSelectedFile(e.dataTransfer.files[0])
        }
    }, [])

    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault()
        if (e.target.files && e.target.files[0]) {
            setSelectedFile(e.target.files[0])
        }
    }, [])

    const handleUploadClick = () => {
        if (selectedFile) onUpload(selectedFile)
    }

    return (
        <div className="w-full max-w-xl mx-auto p-4">
            <Card
                className={cn(
                    "relative overflow-hidden border-2 border-dashed transition-all duration-300 p-8 flex flex-col items-center justify-center min-h-[300px] cursor-pointer bg-black/5 backdrop-blur-sm",
                    isDragActive ? "border-primary bg-primary/5 scale-[1.02]" : "border-muted-foreground/20 hover:border-primary/50",
                    "rounded-xl"
                )}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
            >
                <input
                    type="file"
                    className={cn(
                        "absolute inset-0 w-full h-full opacity-0 cursor-pointer z-50",
                        selectedFile ? "pointer-events-none hidden" : ""
                    )}
                    onChange={handleChange}
                    accept=".pdf,.docx,.txt"
                    disabled={isUploading}
                />

                <AnimatePresence mode="wait">
                    {!selectedFile ? (
                        <motion.div
                            key="prompt"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="text-center space-y-4"
                        >
                            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                                <Upload className="w-8 h-8 text-primary" />
                            </div>
                            <h3 className="text-xl font-semibold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
                                Upload Document
                            </h3>
                            <p className="text-sm text-muted-foreground max-w-xs mx-auto">
                                Drag & drop your PDF, DOCX, or TXT file here, or click to browse.
                            </p>
                        </motion.div>
                    ) : (
                        <motion.div
                            key="selected"
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9 }}
                            className="text-center space-y-6 z-10 relative" // z-10 to stay above input but input is z-50... wait via pointer-events
                        >
                            {/* Note: The input covers everything, so clicking "Upload" might trigger file select if we aren't careful.
                  We need to disable the input when file is selected or structure differently. 
                  Actually, simple fix: Make input hidden when file selected, or z-index swap.
              */}

                            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center mx-auto ring-1 ring-white/20">
                                <FileText className="w-10 h-10 text-primary" />
                            </div>

                            <div>
                                <p className="font-medium text-lg">{selectedFile.name}</p>
                                <p className="text-xs text-muted-foreground uppercase tracking-wider mt-1">
                                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                                </p>
                            </div>

                            <div className="flex gap-3 justify-center pt-4">
                                <Button
                                    variant="outline"
                                    onClick={(e) => {
                                        e.preventDefault() // Stop input trigger
                                        setSelectedFile(null)
                                    }}
                                    className="z-[60] relative"
                                >
                                    Replace
                                </Button>
                                <Button
                                    onClick={(e) => {
                                        e.preventDefault()
                                        handleUploadClick()
                                    }}
                                    disabled={isUploading}
                                    className="z-[60] relative bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white shadow-lg shadow-blue-500/25"
                                >
                                    {isUploading ? (
                                        <>
                                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                            Ingesting...
                                        </>
                                    ) : (
                                        <>
                                            <Upload className="w-4 h-4 mr-2" />
                                            Process with AI
                                        </>
                                    )}
                                </Button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Dynamic Background Effect */}
                {isDragActive && (
                    <motion.div
                        layoutId="active-bg"
                        className="absolute inset-0 bg-blue-500/5 z-0"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                    />
                )}
            </Card>
        </div>
    )
}
