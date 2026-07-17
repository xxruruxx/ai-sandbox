import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(__file__))
from src.langgraph_agent import app as agent_graph

st.set_page_config(page_title="GazetteAI", page_icon="📰")

st.title("GazetteAI")
st.caption("Agentic news research — grounded in Wikipedia's Current Events Portal, updated daily")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("sources"):
            with st.expander("Sources"):
                for s in msg["sources"]:
                    st.write(f"- [{s['title']}]({s['link']}) — {s['date']}")

question = st.chat_input("Ask about current news...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

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
    with st.chat_message("assistant"):
        with st.status("Agent working...", expanded=False) as status:
            for step in agent_graph.stream(initial_state, stream_mode="values"):
                final_state = step
                if step.get("action"):
                    found = len(step.get("relevant_nodes", []))
                    status.write(f"Found {found} relevant chunk(s) → decided: **{step['action']}**")
                    if step.get("action_reason"):
                        status.write(f"↳ {step['action_reason']}")
            status.update(label="Done", state="complete")

        answer = final_state["final_answer"] if final_state else "Something went wrong."
        st.write(answer)

        sources = []
        if final_state and final_state.get("relevant_nodes"):
            with st.expander("Sources"):
                for node in final_state["relevant_nodes"]:
                    title = node.metadata.get("title", "Unknown")
                    link = node.metadata.get("link", "#")
                    date = node.metadata.get("date", "")
                    st.write(f"- [{title}]({link}) — {date}")
                    sources.append({"title": title, "link": link, "date": date})

    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})