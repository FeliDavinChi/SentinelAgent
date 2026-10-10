import os
import glob
import re
from datetime import datetime, date
from sqlalchemy import create_engine, text

# Try PostgreSQL first, otherwise automatically fallback to SQLite for local standalone execution
PG_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://sentinel_app:12345678@localhost:5432/sentinelagent")
SQLITE_URL = "sqlite:///sentinel.db"

def get_engine():
    try:
        engine = create_engine(PG_URL, connect_args={"connect_timeout": 1})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return engine, "postgres"
    except Exception:
        engine = create_engine(SQLITE_URL)
        return engine, "sqlite"

engine, DB_DIALECT = get_engine()

CLEARANCE_MAP = {
    "Internal": 1,
    "Confidential": 2,
    "Restricted": 3
}

def clearance_level(c):
    return CLEARANCE_MAP.get(c, 1)

def init_db():
    with engine.connect() as conn:
        if DB_DIALECT == "postgres":
            # PostgreSQL tables and schema
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(50) PRIMARY KEY,
                    role VARCHAR(50) NOT NULL,
                    department VARCHAR(50) NOT NULL,
                    clearance VARCHAR(50) NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    document_id VARCHAR(50) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    department VARCHAR(50) NOT NULL,
                    classification VARCHAR(50) NOT NULL,
                    owner VARCHAR(50) NOT NULL,
                    version VARCHAR(20) NOT NULL,
                    effective_date DATE NOT NULL,
                    content TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_logs (
                    request_id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    question TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rows_returned INTEGER NOT NULL,
                    rls_enforced BOOLEAN NOT NULL,
                    verification_status VARCHAR(50) NOT NULL,
                    final_status VARCHAR(50) NOT NULL
                );
            """))
        else:
            # SQLite tables
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    department TEXT NOT NULL,
                    clearance TEXT NOT NULL
                );
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    department TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    version TEXT NOT NULL,
                    effective_date TEXT NOT NULL,
                    content TEXT NOT NULL
                );
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    rows_returned INTEGER NOT NULL,
                    rls_enforced BOOLEAN NOT NULL,
                    verification_status TEXT NOT NULL,
                    final_status TEXT NOT NULL
                );
            """))
        conn.commit()

        # Seed demo users
        users = [
            ("U102", "Finance Associate", "Finance", "Internal"),
            ("U301", "Finance Manager", "Finance", "Confidential"),
            ("U505", "Finance Executive", "Finance", "Restricted"),
            ("U205", "Marketing Associate", "Marketing", "Internal"),
        ]
        for uid, role, dept, clr in users:
            existing = conn.execute(text("SELECT user_id FROM users WHERE user_id = :uid"), {"uid": uid}).fetchone()
            if not existing:
                conn.execute(
                    text("INSERT INTO users (user_id, role, department, clearance) VALUES (:uid, :role, :dept, :clr)"),
                    {"uid": uid, "role": role, "dept": dept, "clr": clr}
                )
        conn.commit()

    # Automatically scan and seed documents from /documents directory
    seed_documents_from_files()

def parse_markdown_metadata(file_path):
    metadata = {}
    content_lines = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for line in lines:
        match = re.match(r"^#\s*([^:]+):\s*(.+)$", line.strip())
        if match and not content_lines:
            key = match.group(1).strip().lower().replace(" ", "_")
            val = match.group(2).strip()
            metadata[key] = val
        else:
            content_lines.append(line)
            
    content = "".join(content_lines).strip()
    return metadata, content

from document_rag.schemas import DocumentMetadata, PageText
from document_rag.chunker import chunk_pages
from document_rag.retriever import default_search_service

rag_service = default_search_service()

def index_into_rag_store(doc_id, title, dept, classification, owner, version, eff_date, content):
    try:
        meta = DocumentMetadata(
            document_id=doc_id,
            title=title,
            department=dept,
            classification=classification,
            owner=owner,
            version=version,
            effective_date=str(eff_date)
        )
        pages = [PageText(document_id=doc_id, page_number=1, text=content)]
        chunks = chunk_pages(pages, meta)
        existing_ids = set(rag_service.store._items.keys())
        new_chunks = [c for c in chunks if c.chunk_id not in existing_ids]
        if new_chunks:
            rag_service.store.add(new_chunks)
    except Exception as e:
        pass

def seed_documents_from_files():
    doc_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "documents")
    if not os.path.exists(doc_dir):
        return

    files = glob.glob(os.path.join(doc_dir, "*.md")) + glob.glob(os.path.join(doc_dir, "*.txt"))
    with engine.connect() as conn:
        for fpath in files:
            meta, body = parse_markdown_metadata(fpath)
            doc_id = meta.get("document_id", os.path.splitext(os.path.basename(fpath))[0])
            title = meta.get("title", os.path.basename(fpath))
            dept = meta.get("department", "Finance")
            classification = meta.get("classification", "Internal")
            owner = meta.get("owner", dept)
            version = meta.get("version", "1.0")
            eff_date = meta.get("effective_date", date.today().isoformat())

            # Index into RAG Vector Store
            index_into_rag_store(doc_id, title, dept, classification, owner, version, eff_date, body)

            # Check if exists in SQL database
            exists = conn.execute(
                text("SELECT document_id FROM documents WHERE document_id = :id"),
                {"id": doc_id}
            ).fetchone()
            
            if not exists:
                conn.execute(
                    text("""
                        INSERT INTO documents (document_id, title, department, classification, owner, version, effective_date, content)
                        VALUES (:id, :title, :dept, :cls, :owner, :ver, :date, :content)
                    """),
                    {
                        "id": doc_id,
                        "title": title,
                        "dept": dept,
                        "cls": classification,
                        "owner": owner,
                        "ver": version,
                        "date": eff_date,
                        "content": body
                    }
                )
        conn.commit()

init_db()

def get_user(user_id):
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT user_id, role, department, clearance FROM users WHERE user_id = :uid"),
            {"uid": user_id}
        ).mappings().first()
        return dict(res) if res else None

def get_all_documents():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT document_id, title, department, classification, version, effective_date, content, owner FROM documents")).mappings().all()
        return [dict(r) for r in res]

def get_authorized_documents(user_id):
    user = get_user(user_id)
    if not user:
        return []

    user_dept = user["department"]
    user_clearance = user["clearance"]
    user_lvl = clearance_level(user_clearance)

    all_docs = get_all_documents()
    authorized = []

    for d in all_docs:
        doc_lvl = clearance_level(d["classification"])
        is_owner = (d.get("owner") == user_id)
        # Department check: user can see documents from their department, global HR policies, or uploaded by themselves
        dept_match = (d["department"] == user_dept or d["department"] == "HR" or is_owner)
        # Clearance level check: document classification must be <= user's clearance level (or uploaded by themselves with their clearance)
        clearance_match = (doc_lvl <= user_lvl)

        if (dept_match and clearance_match) or is_owner:
            authorized.append(d)

    return authorized

STOP_WORDS = {
    "what", "are", "the", "how", "much", "for", "about", "and", "from", "this",
    "that", "with", "does", "tell", "any", "our", "all", "can", "you", "give", "show", "who", "when", "where"
}

def get_relevant_documents(user_id, question):
    """
    Search for documents relevant to the question with Multi-Document Comparative Reasoning support.
    Strictly enforce Row-Level Security (RLS) based on the user's authority level (department + clearance).
    Returns (authorized_documents, block_info, partial_blocks)
    """
    user = get_user(user_id)
    if not user:
        return [], {"blocked": True, "reason": "Invalid user ID"}, []

    all_docs = get_all_documents()
    authorized_docs = get_authorized_documents(user_id)
    authorized_ids = {d["document_id"] for d in authorized_docs}

    q_lower = question.lower()
    raw_words = re.findall(r'\b[a-zA-Z0-9_]{3,}\b', q_lower)
    q_words = [w for w in raw_words if w not in STOP_WORDS]

    # Calculate relevance for every document in the enterprise
    doc_scores = {d["document_id"]: 0.0 for d in all_docs}
    for d in all_docs:
        d_id = d["document_id"]
        doc_text = (d["title"] + " " + d["content"]).lower()
        for w in q_words:
            if w in d["title"].lower():
                doc_scores[d_id] += 10.0
            elif w in doc_text:
                doc_scores[d_id] += 4.0

        # Specific direct DOC-ID match
        doc_num_match = re.search(r'doc[-_\s]?([0-9a-fA-F]+)', d_id.lower())
        if doc_num_match:
            raw_num = doc_num_match.group(1).lower()
            if f"doc-{raw_num}" in q_lower or f"doc_{raw_num}" in q_lower or f"doc{raw_num}" in q_lower:
                doc_scores[d_id] += 35.0

        # Semantic / domain-specific anchors
        if any(w in q_lower for w in ["forecast", "revenue", "q4", "gross revenue", "renewals"]):
            if "DOC-101" in d_id:
                doc_scores[d_id] += 15.0
        if any(w in q_lower for w in ["budget", "allocation", "margin", "ebitda", "cost", "r&d spend"]):
            if "DOC-201" in d_id:
                doc_scores[d_id] += 15.0
        if any(w in q_lower for w in ["compensation", "salary", "salaries", "equity", "bonus", "ceo salary", "cfo salary"]):
            if "DOC-301" in d_id:
                doc_scores[d_id] += 15.0
        if any(w in q_lower for w in ["marketing", "campaign", "roadmap", "ad spend", "leads", "mql"]):
            if "DOC-401" in d_id:
                doc_scores[d_id] += 15.0
        if any(w in q_lower for w in ["merger", "acquisition", "m&a", "valuation", "apex", "target"]):
            if "DOC-501" in d_id:
                doc_scores[d_id] += 15.0
        if any(w in q_lower for w in ["conduct", "ethics", "hours", "leave", "vacation", "remote", "rules"]):
            if "DOC-601" in d_id:
                doc_scores[d_id] += 15.0

    # Direct RAG Vector Similarity Retrieval Integration
    try:
        rag_hits = rag_service.search_documents(question, top_k=8).get("results", [])
        for hit in rag_hits:
            hit_id = hit["document_id"]
            hit_score = hit.get("score", 0.0)
            if hit_score > 0.02 and hit_id in doc_scores:
                doc_scores[hit_id] += hit_score * 40.0
    except Exception as e:
        print("Notice: Vector retrieval scoring notice:", e)

    all_scored = [(doc_scores[d["document_id"]], d) for d in all_docs if doc_scores[d["document_id"]] > 0]
    all_scored.sort(key=lambda x: x[0], reverse=True)

    if not all_scored:
        return [], None, []

    is_comparison = any(term in q_lower for term in [
        "compare", "comparison", "versus", "vs", "difference", "between", "both", "across", "contrast"
    ]) or (len([s for s in all_scored if s[0] >= 15.0]) >= 2)

    auth_scored = [(score, d) for score, d in all_scored if d["document_id"] in authorized_ids]
    unauth_scored = [(score, d) for score, d in all_scored if d["document_id"] not in authorized_ids]

    # If NO authorized documents match at all, but unauthorized documents do:
    if not auth_scored and unauth_scored:
        top_unauth_score, top_unauth_doc = unauth_scored[0]
        block_info = {
            "blocked": True,
            "target_id": top_unauth_doc["document_id"],
            "target_title": top_unauth_doc["title"],
            "target_classification": top_unauth_doc["classification"],
            "target_department": top_unauth_doc["department"],
            "user_clearance": user["clearance"],
            "user_department": user["department"]
        }
        return [], block_info, []

    # Detect partial RLS blocks (restricted documents that matched or were requested)
    partial_blocks = []
    for score, doc in unauth_scored:
        if score >= 10.0 or is_comparison:
            partial_blocks.append({
                "document_id": doc["document_id"],
                "title": doc["title"],
                "classification": doc["classification"],
                "department": doc["department"],
                "required_clearance": doc["classification"],
                "user_clearance": user["clearance"],
                "reason": f"Clearance '{user['clearance']}' is insufficient for '{doc['classification']}' classification."
            })

    # If not an explicit comparison and the #1 match is unauthorized and far exceeds any authorized doc:
    if not is_comparison and unauth_scored and all_scored[0][1]["document_id"] not in authorized_ids:
        top_unauth = all_scored[0][1]
        top_auth_score = auth_scored[0][0] if auth_scored else 0
        if all_scored[0][0] > (top_auth_score * 1.5):
            block_info = {
                "blocked": True,
                "target_id": top_unauth["document_id"],
                "target_title": top_unauth["title"],
                "target_classification": top_unauth["classification"],
                "target_department": top_unauth["department"],
                "user_clearance": user["clearance"],
                "user_department": user["department"]
            }
            return [], block_info, []

    # Select top authorized documents
    max_docs = 4 if is_comparison else 3
    auth_results = [d for score, d in auth_scored[:max_docs]]

    return auth_results, None, partial_blocks

def save_document(user_id, document_id, title, department, classification, owner, version, effective_date, content):
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO documents (document_id, title, department, classification, owner, version, effective_date, content)
                VALUES (:id, :title, :dept, :cls, :owner, :ver, :date, :content)
            """),
            {
                "id": document_id,
                "title": title,
                "dept": department,
                "cls": classification,
                "owner": owner,
                "ver": version,
                "date": effective_date,
                "content": content
            }
        )
        conn.commit()
    # Index into RAG Vector Store
    index_into_rag_store(document_id, title, department, classification, owner, version, effective_date, content)

def log_audit(user_id, question, rows_returned, rls_enforced, verification_status, final_status):
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO audit_logs (user_id, question, rows_returned, rls_enforced, verification_status, final_status)
                VALUES (:uid, :q, :rows, :rls, :v_status, :f_status)
            """),
            {
                "uid": user_id,
                "q": question,
                "rows": rows_returned,
                "rls": rls_enforced,
                "v_status": verification_status,
                "f_status": final_status
            }
        )
        conn.commit()

def get_audit_logs(user_id=None):
    with engine.connect() as conn:
        if user_id:
            res = conn.execute(
                text("SELECT request_id, user_id, question, timestamp, rows_returned, rls_enforced, verification_status, final_status FROM audit_logs WHERE user_id = :uid ORDER BY request_id DESC LIMIT 50"),
                {"uid": user_id}
            ).mappings().all()
        else:
            res = conn.execute(
                text("SELECT request_id, user_id, question, timestamp, rows_returned, rls_enforced, verification_status, final_status FROM audit_logs ORDER BY request_id DESC LIMIT 50")
            ).mappings().all()
        return [dict(r) for r in res]