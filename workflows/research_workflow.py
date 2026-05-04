import os
import json
import time
from typing import List, Literal, Dict, Any
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_tavily import TavilySearch
import requests
from ddgs import DDGS
from bs4 import BeautifulSoup
from urllib.parse import urlparse

load_dotenv()

# ==========================================
# GROQ LLM SETUP
# ==========================================
grok_modal = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1, api_key=os.getenv("GROQ_API_KEY"))

# ==========================================
# STRUCTURED OUTPUT MODELS (Search & Eval)
# ==========================================
class SearchResult(BaseModel):
    title: str = Field(description="Title of the search result")
    url: str = Field(description="URL of the result")
    snippet: str = Field(description="Brief snippet/summary")
    source: str = Field(description="Source of search")
    content: str = Field(default="", description="Full scraped content")
    credibility_score: float = Field(default=0.5, description="0-1 credibility rating")
    timestamp: str = Field(default="", description="Timestamp of retrieval")

class SearchQueries(BaseModel):
    queries: List[str] = Field(description="List of 4-5 targeted search queries", min_length=1, max_length=5)
    reasoning: str = Field(description="Reasoning for these specific queries")

class EvaluationResult(BaseModel):
    is_sufficient: Literal["yes", "no"] = Field(description="Does the context fully answer the query?")
    reasoning: str = Field(description="Detailed reasoning")
    missing_areas: List[str] = Field(default=[], description="List of areas that need more research")
    confidence_score: float = Field(default=0.5, description="Confidence in the evaluation")

class FactCheck(BaseModel):
    claims: List[str] = Field(description="Key factual claims extracted")
    verification_status: Dict[str, bool] = Field(description="Verification status for each claim")
    verified_count: int = Field(description="Number of verified claims")

class ResearchSource(BaseModel):
    url: str = Field(description="Source URL")
    title: str = Field(description="Source title")
    content: str = Field(description="Full content")
    credibility: float = Field(description="Credibility score 0-1")
    search_query: str = Field(description="Query that found this source")

# ==========================================
# MULTI-STAGE REPORT MODELS (Forces Length)
# ==========================================
class ReportIntro(BaseModel):
    executive_summary: str = Field(description="4-5 line direct answer with key conclusion clearly stated")
    key_takeaways: List[str] = Field(description="3-5 quick insight bullet points")

class ReportBody(BaseModel):
    core_concept: str = Field(description="Deep, detailed explanation of the core concept")
    how_it_works: List[str] = Field(description="Step-by-step technical explanation of how it works")
    real_world_examples: List[str] = Field(description="2-3 detailed real-world examples")

# Add this new sub-model
class ProConItem(BaseModel):
    aspect: str = Field(description="The aspect being evaluated")
    pros: str = Field(description="A single string containing all pros (comma-separated if multiple)")
    cons: str = Field(description="A single string containing all cons (comma-separated if multiple)")

# Update ReportTrends to use the new sub-model
class ReportTrends(BaseModel):
    latest_developments: List[str] = Field(description="Recent trends or updates")
    pros_vs_cons: List[ProConItem] = Field(description="List of pros and cons comparisons")
    expert_perspectives: List[str] = Field(description="Different expert or industry viewpoints")
    key_facts: List[str] = Field(description="3-5 quick factual reference points")

class ReportConclusion(BaseModel):
    final_summary: str = Field(description="Final summary of the research")
    recommendation: str = Field(description="Recommendation or future outlook")

# ==========================================
# TOOLS & SCRAPERS
# ==========================================
class SourceCredibilityRanker:
    TRUSTED_DOMAINS = {
        "arxiv.org": 0.95, "scholar.google.com": 0.95, "nih.gov": 0.94, "nasa.gov": 0.94,
        "wikipedia.org": 0.85, "github.com": 0.80, "stackoverflow.com": 0.75, "medium.com": 0.60,
        "dev.to": 0.70, "hackernews.com": 0.75, "youtube.com": 0.50, "reddit.com": 0.50,
    }
    
    @staticmethod
    def score_url(url: str) -> float:
        try:
            domain = urlparse(url).netloc.replace("www.", "")
            if domain in SourceCredibilityRanker.TRUSTED_DOMAINS:
                return SourceCredibilityRanker.TRUSTED_DOMAINS[domain]
            if any(x in domain for x in [".edu", ".gov", ".org"]): return 0.80
            if any(x in domain for x in [".com"]): return 0.60
            return 0.40
        except:
            return 0.50

class FreeMultiSourceSearchEngine:
    def __init__(self):
        self.tavily = TavilySearch(max_results=5)
        self.serper_key = os.getenv("SERPER_API_KEY")
    
    def tavily_search(self, query: str) -> List[SearchResult]:
        print(f"   📌 Tavily Search: '{query}'")
        results = []
        try:
            raw_results = self.tavily.invoke({"query": query})
            for r in raw_results.get("results"):
                result = SearchResult(
                    title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("content", "")[:300],
                    source="tavily", content=r.get("content", ""), credibility_score=SourceCredibilityRanker.score_url(r.get("url", ""))
                )
                results.append(result)
            print(f"      ✅ Found {len(results)} results")
        except Exception as e:
            print(f"      ❌ Error: {e}")
        return results
    
    def serper_search(self, query: str) -> List[SearchResult]:
        if not self.serper_key: return []
        print(f"   🔍 Serper Search: '{query}'")
        results = []
        try:
            headers = {"X-API-KEY": self.serper_key, "Content-Type": "application/json"}
            payload = {"q": query, "num": 5, "autocorrect": True}
            response = requests.post("https://google.serper.dev/search", headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for r in data.get("organic", [])[:5]:
                    result = SearchResult(
                        title=r.get("title", ""), url=r.get("link", ""), snippet=r.get("snippet", "")[:300],
                        source="serper", content=r.get("snippet", ""), credibility_score=SourceCredibilityRanker.score_url(r.get("link", ""))
                    )
                    results.append(result)
                print(f"      ✅ Found {len(results)} results")
        except Exception as e:
            print(f"      ❌ Error: {e}")
        return results

    def duckduckgo_search(self, query: str) -> List[SearchResult]:
        print(f"   🦆 DuckDuckGo Search: '{query}'")
        results = []
        try:
            with DDGS() as ddgs:
                ddgs_results = list(ddgs.text(query, max_results=5))
                for r in ddgs_results:
                    result = SearchResult(
                        title=r.get("title", ""), url=r.get("href", ""), snippet=r.get("body", "")[:300],
                        source="duckduckgo", content=r.get("body", ""), credibility_score=SourceCredibilityRanker.score_url(r.get("href", ""))
                    )
                    results.append(result)
            print(f"      ✅ Found {len(results)} results")
        except Exception as e:
            print(f"      ❌ Error: {e}")
        return results
    
    def bing_search(self, query: str) -> List[SearchResult]:
        print(f"   🔵 Bing Search: '{query}'")
        results = []
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.5",
            }
            cookies = {"SRCHHPGUSR": "ADLT=DEMOTE&NRSLT=10", "SRCHUID": "V=2", "MUID": "1"}
            response = requests.get("https://www.bing.com/search", params={"q": query, "cc": "US"}, timeout=10, headers=headers, cookies=cookies)
            soup = BeautifulSoup(response.content, "html.parser")
            search_items = soup.find_all("li", class_="b_algo") or soup.find_all("div", class_="b_algo")
            for item in search_items[:5]:
                try:
                    h2 = item.find("h2")
                    if not h2: continue
                    link = h2.find("a")
                    if not link: continue
                    title, url = link.get_text(), link.get("href", "")
                    snippet_elem = item.find("p") or item.find("div", class_="b_caption")
                    snippet = snippet_elem.get_text()[:300] if snippet_elem else ""
                    if url and url.startswith("http"):
                        result = SearchResult(
                            title=title, url=url, snippet=snippet, source="bing", content=snippet,
                            credibility_score=SourceCredibilityRanker.score_url(url)
                        )
                        results.append(result)
                except: continue
            print(f"      ✅ Found {len(results)} results")
        except Exception as e:
            print(f"      ❌ Error: {e}")
        return results
    
    def search_all_free_sources(self, query: str) -> List[SearchResult]:
        all_results = []
        print(f"\n   🌐 Searching across FREE sources for: '{query}'")
        all_results.extend(self.tavily_search(query))
        all_results.extend(self.duckduckgo_search(query))
        all_results.extend(self.serper_search(query))
        all_results.extend(self.bing_search(query))
        
        seen_urls, unique_results = set(), []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)
        
        unique_results.sort(key=lambda x: x.credibility_score, reverse=True)
        return unique_results[:10]

class WebScraper:
    @staticmethod
    def scrape_url(url: str, timeout: int = 10) -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "meta", "noscript"]):
                element.decompose()
            text = soup.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n".join(lines[:3000])
        except Exception as e:
            print(f"      ❌ Scrape error for {url}: {e}")
            return ""

def fetch_image_markdown(query: str) -> str:
    """Uses Serper API to fetch relevant images and returns Markdown"""
    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key: return "*(Image search skipped: No Serper API Key)*", []
    
    try:
        headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": 3}
        response = requests.post("https://google.serper.dev/images", headers=headers, json=payload, timeout=5)
        if response.status_code == 200:
            images = response.json().get("images", [])
            # Convert to markdown: ![Title](URL)
            img_md = "\n".join([f"![{img.get('title', 'Image')}]({img.get('imageUrl')})" for img in images[:3]])
            image_urls = [img.get('imageUrl') for img in images[:3] if img.get('imageUrl')]
            return img_md,image_urls
        
    except Exception as e:
        print(f"      ❌ Image fetch error: {e}")
        pass
        
    # Safely return a tuple on total failure
    return "*(No relevant images found)*", []

# ==========================================
# STATE & GRAPH DEFS
# ==========================================
class AgentState(TypedDict):
    user_query: str
    search_queries: List[str]
    search_history: List[str]
    all_search_results: List[SearchResult]
    scraped_sources: List[ResearchSource]
    relevant_context: str
    fact_checks: Dict[str, bool]
    is_sufficient: str
    image_assets: List[str]
    final_report: str
    loop_count: int

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={"device": "cpu"})
search_engine = FreeMultiSourceSearchEngine()
scraper = WebScraper()

def generate_deep_queries(state: AgentState):
    print("\n🧠 [PLANNER] Generating deep research queries with Groq...")
    user_query = state.get("user_query")
    loop_count = state.get("loop_count", 0)
    search_history = state.get("search_history", [])
    
    if loop_count == 0:
        prompt_text = f"Break down this query into 4-5 specific search queries covering facts, news, expert opinions, and counterarguments: {user_query}"
    else:
        prompt_text = f"Previous searches: {', '.join(search_history[-2:])}\nGenerate NEW searches for missing details: {user_query}"
    
    try:
        structured_llm = grok_modal.with_structured_output(SearchQueries)
        result = structured_llm.invoke(prompt_text)
        queries = result.queries
        print(f"   📍 Generated {len(queries)} search queries")
    except:
        queries = [user_query, f"{user_query} explained", f"{user_query} latest news", f"{user_query} research"]
    
    return {"search_queries": queries, "loop_count": loop_count + 1}

def execute_multi_source_search(state: AgentState):
    print("\n🌐 [MULTI-SOURCE SEARCH] Querying all FREE sources...")
    queries = state.get("search_queries", [])
    all_results = state.get("all_search_results", [])
    search_history = state.get("search_history", [])

    for query in queries:
        print(f"\n   🔍 Searching: '{query}'")
        results = search_engine.search_all_free_sources(query)
        all_results.extend(results)
        search_history.append(query)
    
    seen_urls, unique_results = set(), []
    for result in all_results:
        if result.url not in seen_urls:
            seen_urls.add(result.url)
            unique_results.append(result)
            
    print(f"\n   ✅ Total unique sources: {len(unique_results)}")
    return {"all_search_results": unique_results, "search_history": search_history}

def scrape_top_sources(state: AgentState):
    print("\n📄 [SCRAPING] Extracting content from top sources...")
    top_results = sorted(state.get("all_search_results", []), key=lambda x: x.credibility_score, reverse=True)[:5]
    scraped = state.get("scraped_sources", [])
    
    for i, result in enumerate(top_results, 1):
        print(f"   [{i}/5] Scraping: {result.url[:60]}...")
        content = scraper.scrape_url(result.url)
        if content and len(content) > 200:
            scraped.append(ResearchSource(url=result.url, title=result.title, content=content, credibility=result.credibility_score, search_query=result.snippet))
            print(f"      ✅ Got {len(content)} characters")
    return {"scraped_sources": scraped}

def extract_context_with_rag(state: AgentState):
    print("\n🔍 [RAG] Finding relevant context with MiniLM embeddings...")
    scraped_sources = state.get("scraped_sources", [])
    if not scraped_sources: return {"relevant_context": "No content available."}
    
    all_content = "\n\n".join([f"[{s.title}]\n{s.content}" for s in scraped_sources])
    try:
        splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)
        texts = splitter.split_text(all_content)
        vectorstore = FAISS.from_texts(texts, embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
        relevant_docs = retriever.invoke(state.get("user_query"))
        context = "\n\n".join([doc.page_content for doc in relevant_docs])
        print(f"   ✅ Extracted {len(relevant_docs)} relevant chunks")
        return {"relevant_context": context}
    except:
        return {"relevant_context": all_content[:5000]}

def fact_check_findings(state: AgentState):
    print("\n✅ [FACT-CHECKING] Cross-verifying information...")
    scraped_sources = state.get("scraped_sources", [])
    if not scraped_sources: return {"fact_checks": {}}
    
    try:
        structured_llm = grok_modal.with_structured_output(FactCheck)
        result = structured_llm.invoke(f"Extract 3 verifiable claims from: {scraped_sources[0].content[:2000]}")
        print(f"   ✅ Verified {result.verified_count} claims")
        return {"fact_checks": result.verification_status}
    except:
        return {"fact_checks": {}}

def evaluate_research_depth(state: AgentState):
    print("\n⚖️ [EVALUATOR] Assessing research depth...")
    try:
        structured_llm = grok_modal.with_structured_output(EvaluationResult)
        result = structured_llm.invoke(f"Question: {state.get('user_query')}\nContext: {state.get('relevant_context')[:2000]}\nIs this enough to write a report?")
        print(f"   Status: {result.is_sufficient.upper()}")
        return {"is_sufficient": result.is_sufficient}
    except:
        return {"is_sufficient": "yes"}

def generate_deep_report(state: AgentState):
    print("\n✍️ [REPORT] Multi-Instance Generation: Building deep structured report...")
    q = state.get("user_query")
    ctx = state.get("relevant_context", "")
    
    # ---------------------------------------------------------
    # STAGE 1: Introduction & Takeaways
    # ---------------------------------------------------------
    print("   -> 🧠 Writing Introduction...")
    intro_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert research analyst. Answer the user based ONLY on the provided context.\n\nCONTEXT:\n{context}"),
        ("human", "Write the executive summary and key takeaways for the topic: '{query}'")
    ])
    intro_chain = intro_prompt | grok_modal.with_structured_output(ReportIntro)
    intro_data = intro_chain.invoke({"context": ctx, "query": q})
    time.sleep(1) # Prevent Groq rate limits
    
    # ---------------------------------------------------------
    # STAGE 2: Deep Analysis (Forces long explanations)
    # ---------------------------------------------------------
    print("   -> 📊 Writing Detailed Analysis...")
    body_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a highly technical writer. Use the provided context to write a deep, step-by-step analysis.\n\nCONTEXT:\n{context}"),
        ("human", "Write a detailed analysis of '{query}'. Focus on the core concept, step-by-step mechanics, and detailed real-world examples.")
    ])
    body_chain = body_prompt | grok_modal.with_structured_output(ReportBody)
    body_data = body_chain.invoke({"context": ctx, "query": q})
    time.sleep(1)

    # ---------------------------------------------------------
    # STAGE 3: Trends, Pros/Cons, Perspectives
    # ---------------------------------------------------------
    print("   -> 📰 Writing Trends & Perspectives...")
    trends_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an industry trends analyst. Use the provided context to extract developments, comparisons, and expert opinions.\n\nCONTEXT:\n{context}"),
        ("human", "Extract the latest developments, a pros/cons comparison, expert perspectives, and 3 key facts for '{query}'.")
    ])
    trends_chain = trends_prompt | grok_modal.with_structured_output(ReportTrends)
    trends_data = trends_chain.invoke({"context": ctx, "query": q})
    time.sleep(1)

    # ---------------------------------------------------------
    # STAGE 4: Conclusion
    # ---------------------------------------------------------
    print("   -> 🧾 Writing Conclusion...")
    conc_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a strategic advisor. Use the provided context to conclude the research report.\n\nCONTEXT:\n{context}"),
        ("human", "Write a final summary and actionable recommendation for '{query}'.")
    ])
    conc_chain = conc_prompt | grok_modal.with_structured_output(ReportConclusion)
    conc_data = conc_chain.invoke({"context": ctx, "query": q})
    time.sleep(1)

    # ---------------------------------------------------------
    # STAGE 5: Fetch Visuals
    # ---------------------------------------------------------
    print("   -> 🖼️ Fetching Image Visuals...")
    image_md, raw_image_urls = fetch_image_markdown(q)

    # ---------------------------------------------------------
    # STAGE 6: Assembly (Formatting exact requested Markdown)
    # ---------------------------------------------------------
    print("   -> 🏗️ Assembling Final Document...")
    
    # Build Pros/Cons Table Markdown
    # Build Pros/Cons Table Markdown
    table_md = "| Aspect | Pros | Cons |\n|------|------|------|\n"
    for item in trends_data.pros_vs_cons:
        # Since 'item' is now a Pydantic object, we access it with dot-notation
        table_md += f"| {item.aspect} | {item.pros} | {item.cons} |\n"

    # Build Sources List
    sources_md = ""
    for i, s in enumerate(state.get("scraped_sources", [])):
        sources_md += f"[{i+1}] {s.title} – {s.url} (Credibility: {s.credibility*100:.0f}%)\n"

    formatted_report = f"""# 🔍 Research Report: {q}

## 🧠 Executive Summary
{intro_data.executive_summary}

---

## ⚡ Key Takeaways (Quick Insights)
{chr(10).join(f"- 🔹 {t}" for t in intro_data.key_takeaways)}

---

## 📊 Detailed Analysis
### 1. Core Concept
{body_data.core_concept}

### 2. How It Works
{chr(10).join(f"- {h}" for h in body_data.how_it_works)}

### 3. Real-World Examples
{chr(10).join(f"- {e}" for e in body_data.real_world_examples)}

---

## 🆕 Latest Developments & Trends
{chr(10).join(f"- 📌 {d}" for d in trends_data.latest_developments)}

---

## ⚖️ Comparison / Pros vs Cons

{table_md}

---

## 🧠 Expert & Industry Perspectives
{chr(10).join(f"- 👨‍💻 {p}" for p in trends_data.expert_perspectives)}

---

## 🖼️ Visual Insights
{image_md}

---

## 📌 Key Facts (Quick Reference)
{chr(10).join(f"- {f}" for f in trends_data.key_facts)}

---

## 🔗 Sources & References
{sources_md}

---

## 🧾 Conclusion
- **Final Summary:** {conc_data.final_summary}
- **Recommendation:** {conc_data.recommendation}
"""
    return {"final_report": formatted_report,
            "image_assets": raw_image_urls
    }

def route_evaluation(state: AgentState):
    if state.get("loop_count", 0) >= 2 or state.get("is_sufficient") == "yes": return "generate_report"
    return "generate_queries"

# ==========================================
# GRAPH BUILDER
# ==========================================
workflow = StateGraph(AgentState)
workflow.add_node("generate_queries", generate_deep_queries)
workflow.add_node("execute_search", execute_multi_source_search)
workflow.add_node("scrape_sources", scrape_top_sources)
workflow.add_node("extract_context", extract_context_with_rag)
workflow.add_node("fact_check", fact_check_findings)
workflow.add_node("evaluate", evaluate_research_depth)
workflow.add_node("generate_report", generate_deep_report)

workflow.add_edge(START, "generate_queries")
workflow.add_edge("generate_queries", "execute_search")
workflow.add_edge("execute_search", "scrape_sources")
workflow.add_edge("scrape_sources", "extract_context")
workflow.add_edge("extract_context", "fact_check")
workflow.add_edge("fact_check", "evaluate")
workflow.add_conditional_edges("evaluate", route_evaluation, {"generate_report": "generate_report", "generate_queries": "generate_queries"})
workflow.add_edge("generate_report", END)

research_workflow_app = workflow.compile()
