# Database Deployment & Scalability Guide

## 🔄 Switching Back to PostgreSQL
Switching between SQLite (Development) and PostgreSQL (Production) is designed to be seamless. The application uses **SQLAlchemy**, which abstracts the underlying database differences.

### Steps to Switch
1. **Ensure PostgreSQL is Running**
   - Typically via Docker: `docker-compose up -d db`
   - Or a managed service (AWS RDS, Supabase, etc.)

2. **Update `.env` configuration**
   Open your `.env` file and comment out the SQLite line, and uncomment the PostgreSQL line:

   ```bash
   # Development (SQLite)
   # DATABASE_URL=sqlite:///./transmax.db
   
   # Production (PostgreSQL)
   DATABASE_URL=postgresql://user:password@localhost:5432/transmax
   ```

3. **Initialize Database**
   Restart the backend. The `init_db()` function will automatically detect the new connection and create the necessary tables in PostgreSQL.

---

## ⚖️ SQLite vs. PostgreSQL for TransMax

| Feature | SQLite (Current) | PostgreSQL (Recommended for Prod) |
|---------|------------------|-----------------------------------|
| **Setup** | Zero-config, single file. Excellent for dev. | Requires server/container setup. |
| **Concurrency** | Low. Database locked during writes. | High. MVCC handles concurrent users well. |
| **Vector Search** | Limited support (via extensions). | **Native `pgvector` support.** |
| **Scalability** | Good for <10k hits/day. | Scales to millions of hits/day. |

### ⚠️ Critical Consideration: Vector Search (Translation Memory)
TransMax uses **Translation Memory (TM)** and **RAG** (Retrieval-Augmented Generation) to improve translation quality.
- **PostgreSQL**: We use the `pgvector` extension for high-performance semantic search.
- **SQLite**: We currently use a basic fallback or in-memory search. 
- **Recommendation**: For heavy production use with large Translation Memories, **PostgreSQL is required** to maintain performance.

## 🚀 Production Checklist
- [ ] Set `DEBUG=False` in `.env`
- [ ] Use PostgreSQL with `pgvector` installed
- [ ] Run behind a reverse proxy (Nginx/Traefik) or cloud load balancer
- [ ] Set secure `SECRET_KEY`
