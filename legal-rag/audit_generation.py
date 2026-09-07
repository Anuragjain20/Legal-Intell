#!/usr/bin/env python3
"""Audit tool for generation pipeline - captures exact LLM prompts and responses."""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.config.settings import Settings
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider
from src.retrieval.retriever import Retriever
from src.vectorstore.chroma_store import ChromaVectorStore
from src.generation.context_builder import ContextBuilder
from src.generation.llm_service import LLMService, GenerationService
from src.generation.prompt import PromptBuilder
from src.generation.providers import DeepSeekLLMClient
from src.generation.citations import CitationMapper


def audit_generation_pipeline():
    """Capture exact state of generation pipeline for a query."""

    print("\n" + "=" * 120)
    print("GENERATION PIPELINE AUDIT")
    print("=" * 120)

    settings = Settings.from_env(Path(".env"))

    print("\n[CONFIG]")
    print(f"  Embedding Model: {settings.embedding_model}")
    print(f"  LLM Model: {settings.deepseek_model}")
    print(f"  LLM Base URL: {settings.deepseek_base_url}")
    print(f"  Similarity Threshold: {settings.similarity_threshold}")

    # Setup retrieval
    embedding_provider = LocalHuggingFaceEmbeddingProvider()
    chroma_path = Path("data/chroma")
    store = ChromaVectorStore(storage_dir=chroma_path, dimension=384)
    retriever = Retriever(
        embedding_provider=embedding_provider,
        vector_store=store,
        similarity_threshold=settings.similarity_threshold
    )

    # Setup generation (same as app.py)
    context_builder = ContextBuilder()
    llm_client = DeepSeekLLMClient(
        api_key=settings.deepseek_api_key,
        model_name=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        temperature=0.0
    )
    llm_service = LLMService(client=llm_client)
    prompt_builder = PromptBuilder()
    citation_mapper = CitationMapper()
    generation_service = GenerationService(
        llm_service=llm_service,
        context_builder=context_builder,
        prompt_builder=prompt_builder,
        citation_mapper=citation_mapper,
    )

    # The query
    query = "What is consideration?"
    print(f"\n[QUERY]")
    print(f"  Text: '{query}'")

    # Retrieve
    print(f"\n[RETRIEVAL STAGE]")
    print(f"  Retrieving top_k=5 chunks...")
    try:
        retrieval_results = retriever.retrieve(query, top_k=5)
        print(f"  ✓ Retrieved {len(retrieval_results)} chunks")

        for result in retrieval_results:
            print(f"\n  Rank #{result.rank}:")
            print(f"    - Chunk ID: {result.record.chunk_id}")
            print(f"    - Page: {result.record.page_number}")
            print(f"    - Section: {result.record.section}")
            print(f"    - Score: {result.score:.4f}")
            print(f"    - Text (first 80 chars): {result.record.text[:80]}...")

            # Check for Section 2(d)
            if "When, at the desire of the promisor" in result.record.text:
                print(f"    ⭐ THIS IS SECTION 2(d)")
    except Exception as e:
        print(f"  ✗ Retrieval failed: {e}")
        return

    # Build context
    print(f"\n[CONTEXT BUILDING STAGE]")
    try:
        context_obj = context_builder.build(query, retrieval_results)
        print(f"  ✓ Built context from {len(context_obj.sources)} sources")
        print(f"  Context length: {len(context_obj.rendered_context)} characters")

        for source in context_obj.sources:
            print(f"\n  SOURCE_{source.rank}:")
            print(f"    - Chunk ID: {source.chunk_id}")
            print(f"    - Page: {source.page_number}")
            print(f"    - Section: {source.section}")
            print(f"    - Score: {source.score:.4f}")

            if "When, at the desire of the promisor" in source.text:
                print(f"    ⭐ THIS IS SECTION 2(d)")

    except Exception as e:
        print(f"  ✗ Context building failed: {e}")
        return

    # Build prompts (PromptBuilder.build() wraps both)
    print(f"\n[PROMPT BUILDING STAGE]")
    try:
        full_prompt = prompt_builder.build(context_obj)

        print(f"  ✓ Generated full prompt")
        print(f"  Full prompt length: {len(full_prompt)} chars")

    except Exception as e:
        print(f"  ✗ Prompt building failed: {e}")
        return

    # Display full prompt
    print(f"\n[FULL PROMPT SENT TO LLM]")
    print("=" * 120)
    print(full_prompt)
    print("=" * 120)

    # Display LLM call details
    print(f"\n[LLM CALL PARAMETERS]")
    print(f"  Model: {settings.deepseek_model}")
    print(f"  Base URL: {settings.deepseek_base_url}")
    print(f"  Temperature: 0.0 (deterministic)")
    print(f"  Top P: (LangChain ChatOpenAI defaults)")
    print(f"  Max Tokens: (LangChain ChatOpenAI defaults - no override)")

    # Call LLM via the generation service
    print(f"\n[CALLING LLM]")
    print("=" * 120)
    try:
        result = generation_service.answer(query, retrieval_results)
        response = result.answer
        print(response)
        print("=" * 120)
    except Exception as e:
        print(f"✗ LLM call failed: {e}")
        print("=" * 120)
        return

    # Analysis
    print(f"\n[ANALYSIS]")
    print("=" * 120)

    # Check if Section 2(d) is in context
    section_2d_in_context = "When, at the desire of the promisor" in context_obj.rendered_context
    print(f"  Section 2(d) in context: {'✓ YES' if section_2d_in_context else '✗ NO'}")

    # Check if response references Section 2(d)
    section_2d_in_response = any([
        "2(d)" in response,
        "desire of the promisor" in response,
        "has done or abstained" in response,
    ])
    print(f"  Section 2(d) referenced in response: {'✓ YES' if section_2d_in_response else '✗ NO'}")

    # Check what sections are referenced
    for i in range(1, 10):
        if f"Section {i}" in response or f"[{i}]" in response or f"({i})" in response:
            print(f"  - Section {i} mentioned")

    # Check for examples
    if "example" in response.lower() or "illustration" in response.lower():
        print(f"  ⚠ Response includes examples/illustrations")
        print(f"    (This suggests model preferred examples over direct definition)")

    print("=" * 120)

    # Metadata export
    print(f"\n[EXPORTABLE AUDIT DATA]")
    print("=" * 120)

    audit_data = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "config": {
            "embedding_model": settings.embedding_model,
            "llm_model": settings.deepseek_model,
            "llm_base_url": settings.deepseek_base_url,
            "similarity_threshold": settings.similarity_threshold,
        },
        "retrieval": {
            "num_results": len(retrieval_results),
            "results": [
                {
                    "rank": r.rank,
                    "score": float(r.score),
                    "chunk_id": r.record.chunk_id,
                    "page": r.record.page_number,
                    "section": r.record.section,
                    "text_preview": r.record.text[:100],
                    "is_section_2d": "When, at the desire of the promisor" in r.record.text,
                }
                for r in retrieval_results
            ]
        },
        "context": {
            "num_sources": len(context_obj.sources),
            "total_chars": len(context_obj.rendered_context),
            "contains_section_2d": section_2d_in_context,
            "sources": [
                {
                    "rank": s.rank,
                    "chunk_id": s.chunk_id,
                    "page": s.page_number,
                    "section": s.section,
                    "score": float(s.score),
                }
                for s in context_obj.sources
            ]
        },
        "prompt": {
            "full_prompt_sent_to_llm": full_prompt,
        },
        "llm_parameters": {
            "model": settings.deepseek_model,
            "base_url": settings.deepseek_base_url,
            "temperature": 0.0,
            "top_p": "default (LangChain ChatOpenAI)",
            "max_tokens": "default (LangChain ChatOpenAI)",
        },
        "response": {
            "text": response,
            "contains_section_2d": section_2d_in_response,
        }
    }

    json_output = json.dumps(audit_data, indent=2)
    print(json_output)

    # Save to file
    output_file = Path("audit_generation_output.json")
    with open(output_file, "w") as f:
        f.write(json_output)

    print(f"\n✓ Audit data saved to: {output_file}")
    print("=" * 120 + "\n")


if __name__ == "__main__":
    audit_generation_pipeline()
