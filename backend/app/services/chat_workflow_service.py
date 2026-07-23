"""
FULL FILE — replace your existing backend/app/services/chat_workflow_service.py.

Only change vs. your current version: the `_generate_node` citation-building
block now also captures `file_id` (from the chunk's metadata, so the
frontend knows which PDF to fetch) and a short `snippet` of the actual
matched text (so the frontend can highlight it on the rendered page).
Nothing else changed — same decompose -> retrieve -> generate pipeline,
same prompts, same round-robin source grouping.
"""
import re
import json
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from operator import add

from langgraph.graph import StateGraph, START, END

from app.core.entities.chat import ChatAnswer, Citation
from app.core.entities.document import DocumentChunk
from app.core.interfaces.llm_client import ILLMClient
from app.services.retrieval_service import RetrievalService

FOLLOWUP_DELIMITER = "###FOLLOWUPS###"


class AgentState(TypedDict):
    query: str
    user_id: str
    session_id: str
    chat_history: Annotated[list, add]
    sub_queries: List[str]
    retrieved_docs: List[DocumentChunk]
    response: str
    follow_up_questions: List[str]
    citations: List[Dict[str, Any]]
    selected_file_ids: List[str]


class ChatWorkflowService:

    def __init__(
        self,
        llm_client: ILLMClient,
        retrieval_service: RetrievalService,
        top_k_per_query: int,
        final_docs_per_query: int,
        max_total_context_docs: int,
    ):
        self._llm = llm_client
        self._retrieval = retrieval_service
        self._top_k_per_query = top_k_per_query
        self._final_docs_per_query = final_docs_per_query
        self._max_total_context_docs = max_total_context_docs
        self._graph = self._build_graph()

    def run(self, query: str, user_id: str, session_id: str, selected_file_ids: Optional[List[str]] = None) -> ChatAnswer:
        initial_state: AgentState = {
            "query": query,
            "user_id": user_id,
            "session_id": session_id,
            "selected_file_ids": selected_file_ids or [],
            "chat_history": [],
            "sub_queries": [],
            "retrieved_docs": [],
            "response": "",
            "follow_up_questions": [],
            "citations": [],
        }
        result = self._graph.invoke(initial_state)
        return ChatAnswer(
            response_text=result.get("response", "No answer generated."),
            sub_queries_used=result.get("sub_queries", []),
            follow_up_questions=result.get("follow_up_questions", []),
            citations=[Citation(**c) for c in result.get("citations", [])],
        )

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("decompose", self._decompose_node)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("generate", self._generate_node)

        workflow.add_edge(START, "decompose")
        workflow.add_edge("decompose", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    def _decompose_node(self, state: AgentState) -> Dict[str, Any]:
        print(f"\n[Workflow] Stage 0: Decomposing query for User: {state['user_id']}...")
        sub_queries = self._decompose_query(state["query"], state["chat_history"])
        print(f"   -> Sub-Queries Generated: {sub_queries}")
        return {"sub_queries": sub_queries}

    def _decompose_query(self, query: str, chat_history: List[str]) -> List[str]:
        history_str = "\n".join(chat_history[-6:]) if chat_history else "No prior history."
        decomposition_prompt = (
            "You are an advanced Query Rewriter and Decomposition engine optimized for dense financial data retrieval.\n"
            "Your task is to produce 1 to 3 optimized search queries for analyzing financial annual reports based on the user question.\n\n"
            "CRITICAL: If the question compares, contrasts, or asks about MULTIPLE named entities/companies "
            "(e.g. 'compare Tata and Mahindra', 'net profit for both companies'), you MUST generate one separate "
            "sub-query PER entity, each explicitly naming that entity (e.g. 'Tata Motors net profit', "
            "'Mahindra net profit') — never a single merged query that risks one entity's data being outranked "
            "and dropped entirely from the retrieved context.\n\n"
            "OUTPUT REQUIREMENT:\nReturn ONLY a JSON list of strings, nothing else. Do not wrap it in markdown fences.\n\n"
            f"Chat History:\n{history_str}\n\nRaw User Input: {query}"
        )
        try:
            raw = self._llm.complete([("user", decomposition_prompt)]).strip()
            raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
            queries = json.loads(raw)
            if isinstance(queries, list) and len(queries) > 0:
                return queries[:3]
        except Exception as e:
            print(f" Query optimization failed ({e}), falling back to raw query.")
        return [query]

    def _retrieve_node(self, state: AgentState) -> Dict[str, Any]:
        print("[Workflow] Stage 1: Executing multi-doc hybrid search loop...")
        docs_by_source: Dict[str, List[DocumentChunk]] = {}
        seen = set()

        selected_file_ids = state.get("selected_file_ids") or None

        for sub_q in state["sub_queries"]:
            candidates = self._retrieval.hybrid_search(
                query=sub_q,
                user_id=state["user_id"],
                top_k=self._top_k_per_query,
                file_ids=selected_file_ids,
            )
            if not candidates:
                continue

            print(f"[Workflow] Stage 2: Cross-Encoder filtering for: '{sub_q}'")
            verified = self._retrieval.reranker.rerank(sub_q, candidates, self._final_docs_per_query)

            for doc in verified:
                key = (doc.source, doc.page, doc.content[:80])
                if key not in seen:
                    seen.add(key)
                    docs_by_source.setdefault(doc.source, []).append(doc)

        all_final_docs: List[DocumentChunk] = []
        sources = list(docs_by_source.keys())
        idx = 0
        while any(docs_by_source.values()):
            src = sources[idx % len(sources)]
            if docs_by_source[src]:
                all_final_docs.append(docs_by_source[src].pop(0))
            idx += 1
            if idx > 10000:
                break

        all_final_docs = all_final_docs[: self._max_total_context_docs]
        if all_final_docs:
            print(f"   -> Context Pipeline Ready. Top Segment Match: {all_final_docs[0].source}, Page {all_final_docs[0].page}\n")
        return {"retrieved_docs": all_final_docs}

    def _generate_node(self, state: AgentState) -> Dict[str, Any]:
        if not state["retrieved_docs"]:
            return {
                "response": "Data could not be localized within any current report segments.",
                "chat_history": [],
                "follow_up_questions": [],
                "citations": [],
            }

        context_blocks = []
        for i, d in enumerate(state["retrieved_docs"], start=1):
            context_blocks.append(f"[CHUNK {i} | Source: {d.source} | Page: {d.page}]\n{d.content}")
        context_str = "\n\n".join(context_blocks)

        citations: List[Dict[str, Any]] = self._build_citations(state["retrieved_docs"])

        system_prompt = self._build_system_prompt()
        user_prompt = f"Context:\n{context_str}\n\nQuestion: {state['query']}"

        raw_content = self._llm.complete([("system", system_prompt), ("user", user_prompt)])
        answer_text, follow_up_questions = self._split_answer_and_followups(raw_content)

        return {
            "response": answer_text,
            "chat_history": [f"User: {state['query']}", f"Bot: {answer_text}"],
            "follow_up_questions": follow_up_questions,
            "citations": citations,
        }

    @staticmethod
    def _build_citations(retrieved_docs: List[DocumentChunk], max_citations: int = 3) -> List[Dict[str, Any]]:
        """
        Builds the citation payload the frontend uses to open the PDF
        viewer panel: which file (`file_id`), which page (`page`), and a
        short `snippet` of the actual chunk text so the frontend can find
        and highlight that exact passage on the rendered page instead of
        just jumping to the page with nothing highlighted.

        The snippet strips the internal "ATTENTION LLM: FILE: ... | PAGE:
        ..." scaffolding line the parser prepends to every chunk (see
        pdf_parser.py) — that line is retrieval/prompt plumbing, not real
        document text, and would never actually appear on the rendered PDF
        page, so searching for it client-side would never match anything.
        """
        citations: List[Dict[str, Any]] = []
        seen_keys = set()

        for d in retrieved_docs:
            key = (d.source, d.page)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            body = d.content
            marker = "\n"
            if body.startswith("ATTENTION LLM:"):
                # First line is the "FILE: ... | PAGE: ..." scaffold; the
                # real extracted text starts right after it.
                parts = body.split("\n", 1)
                body = parts[1] if len(parts) > 1 else ""

            body = body.split("### Extracted Document Tables:")[0]  # drop trailing table markdown
            body = body.strip()

            # Table-derived chunks have their numbers rearranged into
            # markdown "| ... | ... |" cells that never appear verbatim on
            # the actual rendered PDF page (the page shows a real table
            # layout, not pipe-delimited text) — searching for that text
            # on the page can never succeed, so skip the highlight attempt
            # entirely rather than sending a snippet that's guaranteed not
            # to match. The frontend still scrolls to the correct page.
            if d.metadata.get("has_table"):
                snippet = None
            else:
                # 24 words (not the whole chunk) — long enough to be a
                # distinctive fingerprint that won't collide with an
                # unrelated repeated phrase elsewhere on the page, short
                # enough that the frontend's fuzzy line-matcher can still
                # tolerate a few OCR/spacing mismatches and find it.
                snippet = " ".join(body.split()[:24]) or None

            citations.append({
                "source": d.source,
                "page": d.page,
                "file_id": d.metadata.get("file_id"),
                "snippet": snippet,
            })

            if len(citations) >= max_citations:
                break

        return citations

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You are an expert precision financial and legal auditor. Your task is to answer the user's question with absolute data integrity.\n"
            "Use ONLY the facts and structural context provided.\n\n"
            "CRITICAL RULE : If the data can be printed in the table format then print it, but do not try to print every answer in a table format."
            "CRITICAL RULE 1: If a metric or number in the text is accompanied by modifiers like 'over', 'more than', 'approx', or 'nearly', "
            "you MUST include that modifier in your final answer.\n"
            "CRITICAL RULE 2: If the context contains a Markdown table or data blocks relevant to the user's question, you MUST present the data "
            "using a clean, standard Markdown table layout. \n"
            "CRITICAL: Every row of your markdown table MUST be on its own line, separated by an actual physical newline carriage return (\\n). "
            "NEVER combine rows side-by-side using spaces, words, or double pipes '||'. Each row must start with '|' and end with '|\\n'.\n"
            "Leave exactly one blank newline before and after the table entirely.\n"
            "CRITICAL RULE 4: SOURCE TABLE INTEGRITY. Tables extracted from the source PDF may have merged or multi-row headers that got "
            "flattened, or a header row whose column count doesn't match the data rows below it. Do NOT reproduce a malformed table "
            "structure verbatim. Instead: identify each data value's actual meaning from the surrounding labels and context, and rebuild a "
            "clean table with one label per row/column. If you cannot confidently determine which header a given number belongs to, state "
            "the number as prose with its label instead of forcing it into an uncertain table cell — never guess a header-to-value pairing.\n"
            "NEVER copy a chunk's raw '| ... | ... |' markdown syntax directly into your answer unedited — always reformat into a clean "
            "table of your own construction, using only the labels and values you can confidently pair.\n"
            "CRITICAL RULE 3: ANTI-HALLUCINATION GUARD. Do not answer anything not provided in the text.\n\n"
            "CRITICAL RULE 6: NO INTERNAL LEAKAGE. The words 'CHUNK', 'chunk', 'context', 'the provided context', 'the given information', "
            "'the provided text', and any [CHUNK N | Source: ... | Page: ...] labels are internal retrieval scaffolding for YOUR reference "
            "only — the user must NEVER see them. Never write phrases like 'According to CHUNK 3' or 'based on the provided context' or "
            "'reviewing the provided chunks'. Instead write as if you personally read the full report — e.g. 'The report states...', "
            "'According to the FY24 annual report...', or just state the fact directly with no meta-reference to how you found it.\n"
            "CRITICAL RULE 7: DIRECT ANSWER STYLE. Do not narrate your search process (e.g. 'To answer this, we need to look at...', "
            "'Let's check if this matches...', 'Upon reviewing...'). Give the final answer directly and confidently. If the answer isn't "
            "available, say so in one concise sentence (e.g. 'The report doesn't specify this figure.') — do not walk through a multi-step "
            "process of what you tried and failed to find before concluding that.\n\n"
            "CRITICAL RULE 5: FOLLOW-UP QUESTIONS. After your complete answer, on its own new line, output exactly the delimiter "
            f"{FOLLOWUP_DELIMITER} followed immediately by a JSON list of exactly 3 short follow-up questions (each under 12 words) "
            "that the user is likely to ask next, answerable from this same context. Do not repeat the original question. "
            "Output nothing else after the JSON list — no markdown fences, no commentary. If you cannot think of 3 good follow-ups "
            f"grounded in this context, output {FOLLOWUP_DELIMITER} followed by an empty JSON list []."
        )

    @staticmethod
    def _split_answer_and_followups(raw_content: str):
        if FOLLOWUP_DELIMITER not in raw_content:
            return raw_content.strip(), []

        answer_part, _, followup_part = raw_content.partition(FOLLOWUP_DELIMITER)
        answer_part = answer_part.strip()

        followup_part = followup_part.strip()
        followup_part = re.sub(r"^```(json)?|```$", "", followup_part, flags=re.MULTILINE).strip()

        try:
            questions = json.loads(followup_part)
            if isinstance(questions, list):
                return answer_part, [str(q).strip() for q in questions if str(q).strip()][:3]
        except Exception as e:
            print(f" Follow-up question parsing failed ({e}), returning answer without follow-ups.")

        return answer_part, []
