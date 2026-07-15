import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(__file__))
from src.langgraph_agent import app as agent_graph

st.set_page_config(page_title="News Research Agent", page_icon="📰")

st.title("News Research Agent")
st.caption("Agentic RAG (LangGraph) over CNN/DailyMail archive — LLM-driven routing with factual guardrails")

question = st.text_input("Ask a question:", placeholder="What happened with the Minneapolis bridge?")

if st.button("Search") and question:
    initial_state = {
        "original_question": question,
        "current_query": question,
        "nodes": [],
        "relevant_nodes": [],
        "attempts": 0,
        "max_attempts": 2,
        "action": "",
        "action_reason": "",
        "final_answer": "",
    }

    final_state = None

    with st.status("Agent working...", expanded=True) as status:
        for step in agent_graph.stream(initial_state, stream_mode="values"):
            final_state = step

            if step.get("nodes") and not step.get("relevant_nodes") and step.get("action") == "":
                status.write(f"Retrieving for: \"{step['current_query']}\"")

            if step.get("action"):
                found = len(step.get("relevant_nodes", []))
                status.write(f"Found {found} relevant chunk(s) → decided: **{step['action']}**")
                if step.get("action_reason"):
                    status.write(f"↳ {step['action_reason']}")

        status.update(label="Agent finished", state="complete")

    st.subheader("Answer")
    st.write(final_state["final_answer"] if final_state else "Something went wrong.")

    if final_state and final_state.get("relevant_nodes"):
        st.subheader("Sources")
        for node in final_state["relevant_nodes"]:
            with st.expander(f"Article {node.metadata.get('id', 'unknown')} (relevance: {node.score:.3f})"):
                st.write(node.text[:500] + "...")