# Note-Taking App Integration - AI-Powered Design

**Project:** Steve's Note-Taking System Integration
**Purpose:** Capture recruiter notes with AI-powered organization and cross-system intelligence
**Status:** Design Phase
**Est. Effort:** 2-3 weeks development + 1 week testing

---

## 🎯 Executive Summary

Build an AI-powered note-taking system integrated into the Well Intake ecosystem that:
1. **Captures notes** from Steve and other recruiters during calls, meetings, research
2. **AI analyzes** content to auto-tag candidates/deals and extract insights
3. **Links intelligently** to existing CRM records (candidates, deals, companies)
4. **Surfaces information** via Teams Bot natural language queries
5. **Feeds content ideas** into Content Studio for marketing

**Key Innovation:** Notes become a **source of truth** that improves accuracy across all systems.

---

## 🏗️ Architecture Decision: Extend Well Intake API (Recommended)

**Rationale:**
- ✅ Reuse existing infrastructure (PostgreSQL, Redis, Azure OpenAI)
- ✅ Immediate access to candidate/deal context
- ✅ Zero additional Azure costs
- ✅ Unified authentication with Teams Bot
- ✅ Faster time-to-market (2-3 weeks vs 4-6 weeks standalone)

**Alternative (Not Recommended):** Standalone microservice would require:
- New Container App deployment
- Separate database or schema
- Additional API integration layer
- Higher operational complexity

---

## 📊 Database Schema Design

### Core Tables

```sql
-- Main notes table
CREATE TABLE notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content
    content TEXT NOT NULL,                        -- Raw note content
    content_embedding VECTOR(1536),                -- For semantic search

    -- AI Analysis Results
    ai_summary TEXT,                               -- GPT-5 generated summary
    ai_tags TEXT[],                                -- Auto-extracted tags
    sentiment_score FLOAT,                         -- -1.0 (negative) to 1.0 (positive)
    key_insights TEXT[],                           -- Extracted insights
    action_items JSONB,                            -- [{text, priority, due_date}]

    -- Relationships (auto-detected by AI)
    candidate_id UUID REFERENCES candidates(id),   -- Link to candidate
    deal_id UUID REFERENCES deals(id),             -- Link to deal
    company_name TEXT,                             -- Mentioned company
    contact_names TEXT[],                          -- People mentioned

    -- Metadata
    created_by UUID REFERENCES users(id) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    source VARCHAR(50),                            -- 'manual', 'voice_call', 'teams_meeting'

    -- Search optimization
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', content || ' ' || COALESCE(ai_summary, ''))
    ) STORED
);

-- Indexes for performance
CREATE INDEX idx_notes_created_by ON notes(created_by);
CREATE INDEX idx_notes_candidate_id ON notes(candidate_id);
CREATE INDEX idx_notes_deal_id ON notes(deal_id);
CREATE INDEX idx_notes_created_at ON notes(created_at DESC);
CREATE INDEX idx_notes_search_vector ON notes USING GIN(search_vector);
CREATE INDEX idx_notes_embedding ON notes USING ivfflat (content_embedding vector_cosine_ops);

-- Note attachments (future)
CREATE TABLE note_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID REFERENCES notes(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_type VARCHAR(50),
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Note sharing/collaboration (future)
CREATE TABLE note_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID REFERENCES notes(id) ON DELETE CASCADE,
    shared_with UUID REFERENCES users(id),
    permission VARCHAR(20),  -- 'view', 'edit'
    shared_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔌 API Endpoints

### New Routes: `/api/notes/*`

```python
# app/api/notes/routes.py

from fastapi import APIRouter, Depends, HTTPException
from app.models import Note, NoteCreate, NoteUpdate, NoteAIAnalysis
from app.services.note_service import NoteService
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/notes", tags=["notes"])

@router.post("/", response_model=Note)
async def create_note(
    note: NoteCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new note with automatic AI analysis.

    Steps:
    1. Store raw note content
    2. Generate embedding for semantic search
    3. AI analyzes content (GPT-5-mini)
    4. Auto-detect candidate/deal links
    5. Extract action items
    6. Return note with AI insights
    """
    service = NoteService()
    return await service.create_with_ai_analysis(note, current_user.id)


@router.get("/{note_id}", response_model=Note)
async def get_note(
    note_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific note by ID"""
    service = NoteService()
    note = await service.get_by_id(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.get("/", response_model=List[Note])
async def list_notes(
    candidate_id: Optional[str] = None,
    deal_id: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """
    List notes with optional filters.
    Supports pagination and filtering by candidate, deal, or tags.
    """
    service = NoteService()
    return await service.list_notes(
        user_id=current_user.id,
        candidate_id=candidate_id,
        deal_id=deal_id,
        tags=tags,
        limit=limit,
        offset=offset
    )


@router.get("/search/", response_model=List[Note])
async def search_notes(
    query: str,
    search_type: str = Query("hybrid", regex="^(semantic|keyword|hybrid)$"),
    limit: int = Query(20, le=50),
    current_user: User = Depends(get_current_user)
):
    """
    Search notes using semantic similarity or keyword search.

    search_type options:
    - 'semantic': Vector similarity search (finds conceptually similar notes)
    - 'keyword': Full-text search (exact keyword matching)
    - 'hybrid': Combines both approaches (recommended)
    """
    service = NoteService()
    return await service.search(
        query=query,
        user_id=current_user.id,
        search_type=search_type,
        limit=limit
    )


@router.put("/{note_id}", response_model=Note)
async def update_note(
    note_id: str,
    note_update: NoteUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a note. Triggers re-analysis if content changed.
    """
    service = NoteService()
    return await service.update(note_id, note_update, current_user.id)


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user)
):
    """Soft delete a note"""
    service = NoteService()
    await service.delete(note_id, current_user.id)
    return {"status": "deleted", "note_id": note_id}


@router.post("/{note_id}/analyze", response_model=NoteAIAnalysis)
async def reanalyze_note(
    note_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger AI re-analysis of a note.
    Useful when relationships or context change.
    """
    service = NoteService()
    return await service.reanalyze(note_id, current_user.id)


@router.get("/candidates/{candidate_id}/notes", response_model=List[Note])
async def get_candidate_notes(
    candidate_id: str,
    limit: int = Query(20, le=50),
    current_user: User = Depends(get_current_user)
):
    """Get all notes related to a specific candidate"""
    service = NoteService()
    return await service.get_by_candidate(candidate_id, current_user.id, limit)


@router.get("/deals/{deal_id}/notes", response_model=List[Note])
async def get_deal_notes(
    deal_id: str,
    limit: int = Query(20, le=50),
    current_user: User = Depends(get_current_user)
):
    """Get all notes related to a specific deal"""
    service = NoteService()
    return await service.get_by_deal(deal_id, current_user.id, limit)
```

---

## 🤖 AI Analysis Pipeline

### NoteService Implementation

```python
# app/services/note_service.py

import openai
from app.integrations import get_openai_client
from app.database import get_db_connection
from sentence_transformers import SentenceTransformer

class NoteService:
    def __init__(self):
        self.openai = get_openai_client()
        # Use Azure OpenAI embedding model
        self.embedding_model = "text-embedding-ada-002"

    async def create_with_ai_analysis(self, note: NoteCreate, user_id: str):
        """
        Create note with full AI analysis pipeline
        """
        # Step 1: Generate embedding for semantic search
        embedding = await self._generate_embedding(note.content)

        # Step 2: AI analysis with GPT-5
        ai_analysis = await self._analyze_content(note.content, user_id)

        # Step 3: Auto-detect candidate/deal relationships
        relationships = await self._detect_relationships(
            note.content,
            ai_analysis["entities"],
            user_id
        )

        # Step 4: Store in database
        db = await get_db_connection()
        result = await db.execute("""
            INSERT INTO notes (
                content, content_embedding, ai_summary, ai_tags,
                sentiment_score, key_insights, action_items,
                candidate_id, deal_id, company_name, contact_names,
                created_by, source
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
        """,
            note.content,
            embedding,
            ai_analysis["summary"],
            ai_analysis["tags"],
            ai_analysis["sentiment"],
            ai_analysis["insights"],
            ai_analysis["action_items"],
            relationships.get("candidate_id"),
            relationships.get("deal_id"),
            relationships.get("company_name"),
            relationships.get("contact_names"),
            user_id,
            note.source or "manual"
        )

        return result.fetchone()

    async def _analyze_content(self, content: str, user_id: str):
        """
        Analyze note content with GPT-5
        """
        prompt = f"""
        Analyze this recruiter's note and extract structured information:

        Note: {content}

        Return JSON with:
        {{
            "summary": "2-sentence summary",
            "tags": ["tag1", "tag2", ...],
            "sentiment": 0.0 to 1.0,
            "key_insights": ["insight1", "insight2"],
            "action_items": [
                {{"text": "action", "priority": "high/medium/low", "due_date": "YYYY-MM-DD or null"}}
            ],
            "entities": {{
                "people": ["name1", "name2"],
                "companies": ["company1"],
                "roles": ["role1", "role2"],
                "skills": ["skill1", "skill2"]
            }}
        }}

        Tags should be: candidate name, company, skill, meeting type, or topic.
        Sentiment: 0=negative, 0.5=neutral, 1=positive
        """

        response = await self.openai.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing recruiting notes."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1  # Low temp for accuracy
        )

        return json.loads(response.choices[0].message.content)

    async def _detect_relationships(self, content: str, entities: dict, user_id: str):
        """
        Auto-detect links to existing candidates/deals based on content
        """
        db = await get_db_connection()
        relationships = {}

        # Check for candidate matches
        for person_name in entities.get("people", []):
            candidate = await db.fetchone("""
                SELECT id, full_name FROM candidates
                WHERE created_by = $1
                AND similarity(full_name, $2) > 0.6
                ORDER BY similarity(full_name, $2) DESC
                LIMIT 1
            """, user_id, person_name)

            if candidate:
                relationships["candidate_id"] = candidate["id"]
                break

        # Check for deal matches
        for company in entities.get("companies", []):
            deal = await db.fetchone("""
                SELECT id, company_name FROM deals
                WHERE created_by = $1
                AND similarity(company_name, $2) > 0.6
                ORDER BY created_at DESC
                LIMIT 1
            """, user_id, company)

            if deal:
                relationships["deal_id"] = deal["id"]
                relationships["company_name"] = company
                break

        relationships["contact_names"] = entities.get("people", [])

        return relationships

    async def _generate_embedding(self, text: str):
        """Generate embedding for semantic search"""
        response = await self.openai.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.data[0].embedding

    async def search(self, query: str, user_id: str, search_type: str = "hybrid", limit: int = 20):
        """
        Search notes using semantic or keyword search
        """
        db = await get_db_connection()

        if search_type == "semantic" or search_type == "hybrid":
            # Generate embedding for query
            query_embedding = await self._generate_embedding(query)

            # Vector similarity search
            semantic_results = await db.fetch("""
                SELECT *,
                    1 - (content_embedding <=> $1::vector) AS similarity
                FROM notes
                WHERE created_by = $2
                ORDER BY content_embedding <=> $1::vector
                LIMIT $3
            """, query_embedding, user_id, limit)

        if search_type == "keyword" or search_type == "hybrid":
            # Full-text search
            keyword_results = await db.fetch("""
                SELECT *,
                    ts_rank(search_vector, plainto_tsquery('english', $1)) AS rank
                FROM notes
                WHERE created_by = $2
                AND search_vector @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC
                LIMIT $3
            """, query, user_id, limit)

        if search_type == "hybrid":
            # Combine and deduplicate results
            combined = self._merge_search_results(semantic_results, keyword_results)
            return combined[:limit]
        elif search_type == "semantic":
            return semantic_results
        else:
            return keyword_results
```

---

## 🔗 Teams Bot Integration

### Add Notes Queries to Teams Bot

```python
# app/api/teams/routes.py - Add to existing natural language handler

NOTES_INTENTS = [
    "show notes about {candidate}",
    "find notes mentioning {keyword}",
    "what did I write about {company}",
    "my notes from last week",
    "action items from my notes"
]

async def handle_notes_query(query: str, user_email: str):
    """
    Handle natural language queries about notes
    """
    # Detect intent
    if "action items" in query.lower():
        return await get_action_items_from_notes(user_email)

    elif "last week" in query.lower() or "recent" in query.lower():
        return await get_recent_notes(user_email, days=7)

    else:
        # Semantic search
        note_service = NoteService()
        results = await note_service.search(
            query=query,
            user_id=user_email,
            search_type="hybrid",
            limit=5
        )

        return format_notes_as_adaptive_card(results)
```

---

## 📱 Frontend Integration Options

### Option A: Web Interface (Content Studio)
Add "Notes" section to studio.thewell.solutions:
- Rich text editor for note creation
- Inline candidate/deal tagging
- Search with autocomplete
- AI insights displayed in sidebar

### Option B: Teams Bot Interface
Text-based note creation via Teams:
```
User: @TalentWell add note: Great call with John Smith at Morgan Stanley.
       Very interested in VP role. Follow up next week.

Bot: ✅ Note saved! AI detected:
     • Linked to: John Smith (Candidate #1234)
     • Company: Morgan Stanley
     • Action Item: Follow up next week (Priority: Medium)
     • Tags: #candidate-call #vp-role #interested
```

### Option C: Outlook Add-in (Future)
"Quick Note" button in addin/taskpane.html:
- Capture notes while viewing emails
- Auto-link to candidate from email context
- One-click save to database

**Recommendation:** Start with Option B (Teams Bot) - fastest to market, aligns with Steve's workflow.

---

## 🎯 Steve's Workflow Example

### Before (Manual Process):
1. Steve takes notes in OneNote/Notepad during call
2. Manually copies info to Zoho CRM
3. Tries to remember details weeks later
4. Searches multiple places for context

### After (AI-Powered Integration):
1. Steve: "@TalentWell note: Jane Doe at Goldman, looking for compliance role, available in 30 days"
2. AI analyzes: Links to Jane Doe candidate record, extracts "30 days" timeline, tags #compliance
3. Teams Bot: "✅ Saved! Linked to Jane Doe. Timeline: 30 days. Want me to set a reminder?"
4. Later: "@TalentWell what did I write about Jane?" → Instant retrieval with full context

---

## 📈 Success Metrics

**Week 1-2 (MVP):**
- ✅ Basic note creation and retrieval APIs
- ✅ Simple AI tagging (no embedding yet)
- ✅ Teams Bot text-based interface
- Target: 10 notes/day captured

**Week 3-4 (Full Features):**
- ✅ Semantic search with embeddings
- ✅ Auto-linking to candidates/deals
- ✅ Action item extraction
- Target: 50 notes/day, 80% auto-linked correctly

**Month 2-3 (Optimization):**
- ✅ Content Studio web interface
- ✅ Voice-to-note integration (future with Voice Platform)
- ✅ Note-driven content ideas
- Target: 200+ notes/day, used in weekly digest generation

---

## 💰 Cost Impact

**Infrastructure:** $0 (uses existing resources)
**Azure OpenAI:**
- GPT-5-mini: ~$0.25/1M tokens
- Embeddings: ~$0.10/1M tokens
- Est. 50 notes/day × 500 tokens/note × 30 days = 750K tokens/month = **$0.37/month**

**Total Additional Cost:** ~$0.50/month (negligible)

---

## 🚀 Implementation Timeline

**Week 1:**
- Database schema creation
- API endpoints (basic CRUD)
- Simple AI tagging

**Week 2:**
- Teams Bot integration
- Semantic search setup
- Auto-linking logic

**Week 3:**
- Testing with Steve
- Bug fixes and refinements
- Performance optimization

**Week 4:**
- Production deployment
- User training
- Monitoring setup

**Total:** 2-3 weeks to MVP, 4 weeks to full production

---

**Document Status:** Ready for Implementation
**Next Step:** Review with Steve, gather workflow requirements, begin database schema creation
**Contact:** daniel.romitelli@emailthewell.com
