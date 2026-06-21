import os
import lancedb
from lancedb.pydantic import pydantic_to_schema, LanceModel, Vector
from lancedb.embeddings import get_registry
from pydantic import Field
from datetime import datetime, timezone
from src.config import settings

# Initialize embeddings model (multilingual and open, without HF 401 errors)
registry = get_registry().get("sentence-transformers")
embedder = registry.create(name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

class UserFact(LanceModel):
    fact_text: str = embedder.SourceField()
    vector: Vector(embedder.ndims()) = embedder.VectorField()
    importance_weight: float = 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

db = None
tbl = None

def init_vector_db():
    global db, tbl
    os.makedirs(settings.lancedb_path, exist_ok=True)
    db = lancedb.connect(settings.lancedb_path)
    
    if "user_facts" not in db.table_names():
        tbl = db.create_table("user_facts", schema=UserFact)
    else:
        tbl = db.open_table("user_facts")

def add_fact(text: str, weight: float = 1.0):
    if tbl is None:
        return
    tbl.add([{
        "fact_text": text, 
        "importance_weight": weight,
        "created_at": datetime.now(timezone.utc)
    }])

def search_facts(query: str, limit: int = 5):
    if tbl is None:
        return []
    # Search by vector generated from the query
    results = tbl.search(query).limit(limit).to_list()
    return results
