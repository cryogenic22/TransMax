import sqlite3
import os

DB_PATH = "transmax.db"

def fix_db():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fix Documents
    print("Checking Documents...")
    cursor.execute("SELECT id, status FROM documents")
    docs = cursor.fetchall()
    fixed_docs = 0
    for doc_id, status in docs:
        if "documentstatus" in status.lower() or "DocumentStatus" in status:
            # Extract value. E.g. "DocumentStatus.UPLOADED" -> "uploaded"
            # or "documentstatus.uploaded" -> "uploaded"
            if "." in status:
                new_status = status.split(".")[-1].lower()
                print(f"Fixing Document {doc_id}: {status} -> {new_status}")
                cursor.execute("UPDATE documents SET status = ? WHERE id = ?", (new_status, doc_id))
                fixed_docs += 1
            else:
                print(f"Warning: Weird status format for doc {doc_id}: {status}")

    # Fix Segments
    print("Checking Segments...")
    cursor.execute("SELECT id, status FROM segments")
    segs = cursor.fetchall()
    fixed_segs = 0
    for seg_id, status in segs:
        if "segmentstatus" in status.lower() or "SegmentStatus" in status:
             if "." in status:
                new_status = status.split(".")[-1].lower()
                # print(f"Fixing Segment {seg_id}: {status} -> {new_status}") # Too noisy
                cursor.execute("UPDATE segments SET status = ? WHERE id = ?", (new_status, seg_id))
                fixed_segs += 1

    conn.commit()
    conn.close()
    print(f"Fixed {fixed_docs} documents and {fixed_segs} segments.")

if __name__ == "__main__":
    fix_db()
