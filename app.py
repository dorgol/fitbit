import streamlit as st
from datetime import datetime
from src.core.context_assembly import ContextAssembler
from src.core.conversation_orchestrator import create_conversation_orchestrator
from src.memory.database import get_db_session

# Page config
st.set_page_config("Fitbit AI Debugger", layout="wide")
st.title("🧠 Fitbit AI Debugging Interface")

# Sidebar - Select user ID
st.sidebar.header("Select User")
user_id = st.sidebar.number_input("User ID", min_value=1, step=1)

# Load context
assembler = ContextAssembler()
if st.sidebar.button("Load Context"):
    with st.spinner("Assembling context..."):
        try:
            context = assembler.assemble_full_context(user_id)
            st.session_state.context = context
            st.success("Context loaded.")
        except Exception as e:
            st.error(f"Error: {e}")

# Load conversation orchestrator
orchestrator = create_conversation_orchestrator()

# Tabs for functionality
tabs = st.tabs(["💬 Chat", "🧠 Prompt", "📊 Health Data", "⚙️ Debug Info"])

# Tab 1: Chat
with tabs[0]:
    st.subheader("Conversational Interface")

    # Initialize session state storage
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None

    # Display conversation
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    prompt = st.chat_input("Ask something about your health")
    if prompt:
        st.chat_message("user").write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Generating response..."):
            start = datetime.now()
            result = orchestrator.workflow.invoke({
                "user_id": str(user_id),
                "user_message": prompt,
                "messages": st.session_state.messages,
                "conversation_id": st.session_state.conversation_id,
                "assembled_context": st.session_state.get("context", {}),
                "system_prompt": "",
                "response": "",
                "error": None,
                "should_update_memory": False,
                "stop_conversation": False
            })
            duration = (datetime.now() - start).total_seconds()

            response = result.get("response")
            error = result.get("error")

            if error:
                st.error(error)
            else:
                st.chat_message("assistant").write(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.session_state.conversation_id = result.get("conversation_id")
                st.info(f"⏱ Response time: {duration:.2f} seconds")

# Tab 2: Prompt Inspection
with tabs[1]:
    st.subheader("Prompt Breakdown")
    if "context" not in st.session_state:
        st.info("Please load context from the sidebar first.")
    else:
        context = st.session_state.context
        sections = [
            ("base_character", "🎭 Base Character"),
            ("health_data", "📊 Health Data"),
            ("insights", "🧠 Insights"),
            ("user_context", "👤 User Context"),
            ("external_context", "🌤️ External Context"),
            ("knowledge", "📚 Knowledge Base"),
            ("guidelines", "⚙️ Guidelines")
        ]

        for key, label in sections:
            st.markdown(f"#### {label}")
            try:
                prompt_piece = assembler.available_sections[key].generate(context)
                st.code(prompt_piece.strip(), language="markdown")
            except Exception as e:
                st.error(f"Error in section {key}: {e}")

        # Full prompt
        st.markdown("---")
        st.markdown("### 🧵 Full Prompt Sent to LLM")
        full_prompt = assembler.build_system_prompt(context)
        st.text_area("Complete Prompt", full_prompt, height=300)
        st.caption(f"Total characters: {len(full_prompt)}")

# Tab 3: Health Data
with tabs[2]:
    st.subheader("📈 User Health Data")
    from src.memory.database import HealthMetric
    import pandas as pd
    import plotly.express as px
    from datetime import timedelta

    def get_user_health_data(uid: int, days_back: int = 14):
        session = get_db_session()
        cutoff = datetime.now() - timedelta(days=days_back)
        metrics = session.query(HealthMetric).filter(
            HealthMetric.user_id == uid,
            HealthMetric.timestamp >= cutoff
        ).order_by(HealthMetric.timestamp).all()
        session.close()
        return pd.DataFrame([{
            "timestamp": m.timestamp,
            "metric_type": m.metric_type,
            "value": m.value
        } for m in metrics])

    if user_id:
        days = st.slider("Days Back", 7, 30, 14)
        df = get_user_health_data(user_id, days_back=days)
        if df.empty:
            st.warning("No data available for this user.")
        else:
            for mtype in df["metric_type"].unique():
                fig = px.line(
                    df[df["metric_type"] == mtype],
                    x="timestamp", y="value", title=f"{mtype.title()} Over Time"
                )
                st.plotly_chart(fig, use_container_width=True)

            with st.expander("Raw Data Table"):
                st.dataframe(df)

# Tab 4: System Info
with tabs[3]:
    st.subheader("System Debug Info")
    if "context" in st.session_state:
        raw = st.session_state.context.get("raw_data", {})
        st.markdown("**User Profile**")
        st.json(raw.get("user_profile", {}))

        st.markdown("**Recent Metrics**")
        st.json(raw.get("recent_metrics", {}))

        st.markdown("**Insights**")
        st.json(st.session_state.context.get("insights", {}))

        st.markdown("**Highlights**")
        st.json(st.session_state.context.get("highlights", {}))

        st.markdown("**External Data**")
        st.json(st.session_state.context.get("external_data", {}))

        st.markdown("**Knowledge**")
        st.json(st.session_state.context.get("knowledge", {}))
    else:
        st.info("No context loaded.")
