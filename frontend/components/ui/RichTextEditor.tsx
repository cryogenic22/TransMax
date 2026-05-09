import { useEditor, EditorContent, type Editor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { Table } from '@tiptap/extension-table'
import TableRow from '@tiptap/extension-table-row'
import TableCell from '@tiptap/extension-table-cell'
import TableHeader from '@tiptap/extension-table-header'
import { Bold, Italic, List, ListOrdered, Table as TableIcon, Columns, Rows, Trash2 } from 'lucide-react'
import { cn } from "@/lib/utils"

interface RichTextEditorProps {
    value: string
    onChange: (html: string) => void
    editable?: boolean
    placeholder?: string
    className?: string
}

const MenuBar = ({ editor }: { editor: Editor | null }) => {
    if (!editor) return null

    return (
        <div className="flex flex-wrap items-center gap-1 p-2 border-b bg-slate-50 rounded-t-lg">
            <button
                onClick={() => editor.chain().focus().toggleBold().run()}
                className={cn("p-1.5 rounded hover:bg-slate-200 transition-colors", editor.isActive('bold') && "bg-slate-200 text-blue-600")}
                title="Bold"
            >
                <Bold size={16} />
            </button>
            <button
                onClick={() => editor.chain().focus().toggleItalic().run()}
                className={cn("p-1.5 rounded hover:bg-slate-200 transition-colors", editor.isActive('italic') && "bg-slate-200 text-blue-600")}
                title="Italic"
            >
                <Italic size={16} />
            </button>
            <div className="w-px h-4 bg-slate-300 mx-1" />
            <button
                onClick={() => editor.chain().focus().toggleBulletList().run()}
                className={cn("p-1.5 rounded hover:bg-slate-200 transition-colors", editor.isActive('bulletList') && "bg-slate-200 text-blue-600")}
                title="Bullet List"
            >
                <List size={16} />
            </button>
            <button
                onClick={() => editor.chain().focus().toggleOrderedList().run()}
                className={cn("p-1.5 rounded hover:bg-slate-200 transition-colors", editor.isActive('orderedList') && "bg-slate-200 text-blue-600")}
                title="Ordered List"
            >
                <ListOrdered size={16} />
            </button>
            <div className="w-px h-4 bg-slate-300 mx-1" />
            <button
                onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
                className="p-1.5 rounded hover:bg-slate-200 transition-colors"
                title="Insert Table"
            >
                <TableIcon size={16} />
            </button>
            {editor.can().addColumnAfter() && (
                <>
                    <button onClick={() => editor.chain().focus().addColumnAfter().run()} className="p-1.5 rounded hover:bg-slate-200" title="Add Column"><Columns size={14} /></button>
                    <button onClick={() => editor.chain().focus().addRowAfter().run()} className="p-1.5 rounded hover:bg-slate-200" title="Add Row"><Rows size={14} /></button>
                    <button onClick={() => editor.chain().focus().deleteTable().run()} className="p-1.5 rounded hover:bg-slate-200 text-red-500" title="Delete Table"><Trash2 size={14} /></button>
                </>
            )}
        </div>
    )
}

export function RichTextEditor({ value, onChange, editable = true, placeholder: _placeholder, className }: RichTextEditorProps) {
    const editor = useEditor({
        extensions: [
            StarterKit,
            Table.configure({ resizable: true }),
            TableRow,
            TableHeader,
            TableCell,
        ],
        content: value,
        editable: editable,
        onUpdate: ({ editor }) => {
            onChange(editor.getHTML())
        },
        editorProps: {
            attributes: {
                class: cn("prose prose-sm max-w-none p-4 min-h-[150px] outline-none", className)
            }
        },
        immediatelyRender: false,
    })

    // Update content if value changes externally (and isn't just a re-render loop)
    // Note: In a real app, careful handling of this is needed to avoid cursor jumps.
    // For this simple case, we trust 'value' is stable or we accept minor re-renders.

    return (
        <div className="border rounded-lg bg-white overflow-hidden focus-within:ring-2 focus-within:ring-blue-500/20 transition-all">
            {editable && <MenuBar editor={editor} />}
            <div className="max-h-[500px] overflow-y-auto w-full">
                <EditorContent editor={editor} />
            </div>
            <style jsx global>{`
                .ProseMirror {
                    outline: none;
                }
                .ProseMirror table {
                    border-collapse: collapse;
                    margin: 0;
                    overflow: hidden;
                    table-layout: fixed;
                    width: 100%;
                }
                .ProseMirror td,
                .ProseMirror th {
                    border: 2px solid #ced4da;
                    box-sizing: border-box;
                    min-width: 1em;
                    padding: 3px 5px;
                    vertical-align: top;
                    position: relative;
                }
                .ProseMirror th {
                    font-weight: bold;
                    text-align: left;
                    background-color: #f1f3f5;
                }
                .ProseMirror ul {
                    list-style-type: disc;
                    padding-left: 1.5em;
                }
                .ProseMirror ol {
                    list-style-type: decimal;
                    padding-left: 1.5em;
                }
            `}</style>
        </div>
    )
}
