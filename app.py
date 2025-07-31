"""
Fitbit Conversational AI - Streamlit Frontend

A comprehensive interface showcasing the 6-layer memory system and conversation capabilities.
"""

import streamlit as st
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import time

# Add src to path
sys.path.append('src')

try:
    from memory.database import DatabaseManager, User, HealthMetric, Conversation, Insight, Highlight, get_db_session
    from core.conversation_orchestrator import chat_with_user, create_conversation_orchestrator
    from core.context_assembly import ContextAssembler
    from memory.external_data import ExternalDataManager
    from utils.mock_data import MockDataGenerator
except ImportError as e:
    st.error(f"Import error: {e}")
    st.error("Make sure you're running from the project root directory")
    st.stop()

# Page configuration
st.set_page_config(
    page_title="Fitbit AI Assistant",
    page_icon="🏃‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #00D4AA 0%, #007BE0 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 10px;
    }
    
    .user-message {
        background: #e3f2fd;
        margin-left: 2rem;
    }
    
    .assistant-message {
        background: #f5f5f5;
        margin-right: 2rem;
    }
    
    .context-section {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid #00D4AA;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
        background-color: #f0f2f6;
        border-radius: 4px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #00D4AA;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = {}
if 'current_user_id' not in st.session_state:
    st.session_state.current_user_id = None
if 'conversation_id' not in st.session_state:
    st.session_state.conversation_id = {}

def reset_user_session():
    """Reset session data when switching users"""
    if st.session_state.current_user_id:
        # Initialize user-specific data if not exists
        user_id = str(st.session_state.current_user_id)
        if user_id not in st.session_state.conversation_history:
            st.session_state.conversation_history[user_id] = []
        if user_id not in st.session_state.conversation_id:
            st.session_state.conversation_id[user_id] = None

def get_current_user_conversation_history():
    """Get conversation history for current user"""
    if not st.session_state.current_user_id:
        return []
    user_id = str(st.session_state.current_user_id)
    if user_id not in st.session_state.conversation_history:
        st.session_state.conversation_history[user_id] = []
    return st.session_state.conversation_history[user_id]

def get_current_user_conversation_id():
    """Get conversation ID for current user"""
    if not st.session_state.current_user_id:
        return None
    user_id = str(st.session_state.current_user_id)
    if user_id not in st.session_state.conversation_id:
        st.session_state.conversation_id[user_id] = None
    return st.session_state.conversation_id[user_id]

def set_current_user_conversation_id(conv_id):
    """Set conversation ID for current user"""
    if st.session_state.current_user_id:
        user_id = str(st.session_state.current_user_id)
        st.session_state.conversation_id[user_id] = conv_id

@st.cache_data
def get_users():
    """Get all users from database"""
    session = get_db_session()
    try:
        users = session.query(User).all()
        return [(user.id, f"User {user.id} ({user.location})") for user in users]
    finally:
        session.close()

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_user_health_data(user_id: int, days_back: int = 14):
    """Get health data for visualization"""
    session = get_db_session()
    try:
        cutoff_date = datetime.now() - timedelta(days=days_back)

        metrics = session.query(HealthMetric).filter(
            HealthMetric.user_id == user_id,
            HealthMetric.timestamp >= cutoff_date
        ).order_by(HealthMetric.timestamp).all()

        data = []
        for metric in metrics:
            data.append({
                'date': metric.timestamp.date(),
                'datetime': metric.timestamp,
                'metric_type': metric.metric_type,
                'value': metric.value,
                'extra_data': metric.extra_data or {}
            })

        return pd.DataFrame(data)
    finally:
        session.close()

@st.cache_data(ttl=300)
def get_user_context_data(user_id: int):
    """Get complete user context for visualization"""
    try:
        assembler = ContextAssembler()
        context = assembler.assemble_full_context(user_id)
        return context
    except Exception as e:
        st.error(f"Error loading context: {e}")
        return {}

def render_health_charts(df: pd.DataFrame):
    """Render interactive health data charts"""
    if df.empty:
        st.warning("No health data available")
        return

    # Steps chart
    steps_data = df[df['metric_type'] == 'steps'].copy()
    if not steps_data.empty:
        fig_steps = px.line(
            steps_data,
            x='date',
            y='value',
            title='Daily Steps',
            labels={'value': 'Steps', 'date': 'Date'}
        )
        fig_steps.add_hline(y=10000, line_dash="dash", line_color="green",
                           annotation_text="10K Goal")
        fig_steps.update_layout(height=300)
        st.plotly_chart(fig_steps, use_container_width=True)

    # Sleep and Heart Rate
    sleep_data = df[df['metric_type'] == 'sleep_duration'].copy()
    hr_data = df[df['metric_type'] == 'heart_rate'].copy()

    if not sleep_data.empty or not hr_data.empty:
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Sleep Duration (hours)', 'Heart Rate (bpm)'),
            vertical_spacing=0.1
        )

        if not sleep_data.empty:
            sleep_by_date = sleep_data.groupby('date')['value'].first().reset_index()
            fig.add_trace(
                go.Scatter(x=sleep_by_date['date'], y=sleep_by_date['value'],
                          mode='lines+markers', name='Sleep Duration',
                          line=dict(color='blue')),
                row=1, col=1
            )
            fig.add_hline(y=7, line_dash="dash", line_color="green", row=1, col=1)
            fig.add_hline(y=9, line_dash="dash", line_color="green", row=1, col=1)

        if not hr_data.empty:
            # Show only resting HR for clarity
            resting_hr = hr_data[
                hr_data['extra_data'].apply(lambda x: x.get('reading_type') == 'resting' if x else False)
            ]
            if not resting_hr.empty:
                hr_by_date = resting_hr.groupby('date')['value'].mean().reset_index()
                fig.add_trace(
                    go.Scatter(x=hr_by_date['date'], y=hr_by_date['value'],
                              mode='lines+markers', name='Resting HR',
                              line=dict(color='red')),
                    row=2, col=1
                )

        fig.update_layout(height=500, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

def render_context_visualization(context_data: dict):
    """Render the 6-layer memory system visualization"""

    # Layer 1: Raw Data
    st.markdown("### 🗃️ Layer 1: Raw Health Data")
    with st.expander("Raw Data Details", expanded=False):
        raw_data = context_data.get('raw_data', {})
        if raw_data:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**User Profile:**")
                profile = raw_data.get('user_profile', {})
                if profile:
                    st.json(profile)

            with col2:
                st.markdown("**Recent Metrics Summary:**")
                metrics = raw_data.get('recent_metrics', {})
                if metrics:
                    for metric, values in metrics.items():
                        if values:
                            avg_val = sum(values) / len(values)
                            st.metric(
                                metric.replace('_', ' ').title(),
                                f"{avg_val:.1f}",
                                f"Last {len(values)} days"
                            )

    # Layer 2: Generated Insights
    st.markdown("### 🧠 Layer 2: AI-Generated Insights")
    insights = context_data.get('insights', [])
    if insights:
        for insight in insights[:3]:  # Show top 3
            confidence = insight.get('confidence', 0)
            category = insight.get('category', 'general').replace('_', ' ').title()

            st.markdown(f"""
            <div class="context-section">
                <strong>{category}</strong> (Confidence: {confidence:.0%})<br>
                {insight.get('finding', 'No finding available')}
                <br><small>Timeframe: {insight.get('timeframe', 'unknown')}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No insights generated yet. Run the insights processor.")

    # Layer 3: Conversation Highlights
    st.markdown("### 💭 Layer 3: Conversation Memory")
    highlights = context_data.get('highlights', {})
    if highlights and highlights.get('structured_data'):
        structured = highlights['structured_data']

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Health Context:**")
            health_fields = ['allergies', 'health_concerns', 'medications', 'family_health']
            for field in health_fields:
                value = structured.get(field)
                if value:
                    st.markdown(f"• **{field.replace('_', ' ').title()}:** {value}")

        with col2:
            st.markdown("**Lifestyle & Preferences:**")
            lifestyle_fields = ['work_schedule', 'exercise_preferences', 'goals_mentioned']
            for field in lifestyle_fields:
                value = structured.get(field)
                if value:
                    st.markdown(f"• **{field.replace('_', ' ').title()}:** {value}")

        if highlights.get('unstructured_notes'):
            st.markdown("**Additional Notes:**")
            st.markdown(f"_{highlights['unstructured_notes']}_")
    else:
        st.info("No conversation highlights yet. Have some conversations to build context.")

    # Layer 4: External Context
    st.markdown("### 🌤️ Layer 4: External Context")
    external = context_data.get('external_data', {})
    if external and external.get('weather'):
        weather = external['weather']

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Temperature", f"{weather.get('temperature', 'N/A')}°C")
        with col2:
            st.metric("Condition", weather.get('condition', 'N/A'))
        with col3:
            st.metric("Air Quality", weather.get('air_quality', 'N/A'))
        with col4:
            st.metric("Humidity", f"{weather.get('humidity', 'N/A')}%")

        if weather.get('recommendations'):
            st.markdown("**Activity Recommendations:**")
            for rec in weather['recommendations']:
                st.markdown(f"• {rec}")
    else:
        st.info("No external context available.")

    # Layer 5: Knowledge Base
    st.markdown("### 📚 Layer 5: Health Knowledge")
    knowledge = context_data.get('knowledge', [])
    if knowledge:
        for item in knowledge[:2]:  # Show top 2
            topic = item.get('topic', '').replace('_', ' ').title()
            content = item.get('content', '')
            source = item.get('source', '')

            st.markdown(f"""
            <div class="context-section">
                <strong>{topic}</strong><br>
                {content}
                <br><small>Source: {source}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Knowledge base is empty. Add health knowledge entries.")

    # Layer 6: System Prompt (preview)
    st.markdown("### ⚙️ Layer 6: Generated System Prompt")
    with st.expander("View System Prompt", expanded=False):
        assembler = ContextAssembler()
        system_prompt = assembler.build_system_prompt(context_data)
        st.text_area("System Prompt Preview", system_prompt, height=200)
        st.caption(f"Prompt length: {len(system_prompt)} characters")

def render_chat_interface():
    """Render the main chat interface"""

    if not st.session_state.current_user_id:
        st.warning("Please select a user from the sidebar first.")
        return

    # Reset user session data when user changes
    reset_user_session()

    # Get current user's conversation history
    conversation_history = get_current_user_conversation_history()

    # Chat history
    st.markdown("### 💬 Conversation")

    chat_container = st.container()

    with chat_container:
        if not conversation_history:
            st.info("Start a conversation by typing a message below!")

        for message in conversation_history:
            role = message.get('role', 'unknown')
            content = message.get('content', '')

            if role == 'user':
                st.markdown(f"""
                <div class="chat-message user-message">
                    <strong>You:</strong> {content}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="chat-message assistant-message">
                    <strong>Assistant:</strong> {content}
                </div>
                """, unsafe_allow_html=True)

    # Chat input
    st.markdown("---")

    col1, col2, col3 = st.columns([6, 1, 1])

    with col1:
        user_input = st.text_input(
            "Ask your health assistant:",
            placeholder="Type your question here...",
            label_visibility="collapsed",
            key=f"chat_input_{st.session_state.current_user_id}"
        )

    with col2:
        if st.button("Send", type="primary") and user_input:
            handle_user_message(user_input)

    with col3:
        if st.button("Clear Chat"):
            user_id = str(st.session_state.current_user_id)
            st.session_state.conversation_history[user_id] = []
            st.session_state.conversation_id[user_id] = None
            st.rerun()

def handle_user_message(message: str):
    """Handle a user message and get AI response"""

    if not st.session_state.current_user_id:
        st.error("No user selected")
        return

    user_id = str(st.session_state.current_user_id)

    # Get current user's conversation history
    conversation_history = get_current_user_conversation_history()

    # Add user message to history
    conversation_history.append({
        'role': 'user',
        'content': message
    })
    st.session_state.conversation_history[user_id] = conversation_history

    # Show thinking spinner
    with st.spinner("Thinking..."):
        start_time = time.time()

        try:
            # Get AI response
            result = chat_with_user(
                user_id,
                message,
                get_current_user_conversation_id()
            )

            response_time = time.time() - start_time

            if result['error']:
                st.error(f"Error: {result['error']}")
                return

            # Add assistant response to history
            conversation_history.append({
                'role': 'assistant',
                'content': result['response']
            })
            st.session_state.conversation_history[user_id] = conversation_history

            # Update conversation ID for current user
            set_current_user_conversation_id(result['conversation_id'])

            # Show response time
            st.success(f"Response generated in {response_time:.2f} seconds")

        except Exception as e:
            st.error(f"Error generating response: {e}")

    # Rerun to update the chat
    st.rerun()

def render_system_info():
    """Render system information and health checks"""

    st.markdown("### 🔧 System Information")

    # Database health check
    try:
        db_manager = DatabaseManager()
        db_healthy = db_manager.health_check()

        st.metric("Database Status", "✅ Connected" if db_healthy else "❌ Error")
    except Exception as e:
        st.metric("Database Status", f"❌ Error: {e}")

    # LLM health check
    try:
        orchestrator = create_conversation_orchestrator()
        llm_available = orchestrator.is_available()

        st.metric("LLM Status", "✅ Available" if llm_available else "❌ Unavailable")
    except Exception as e:
        st.metric("LLM Status", f"❌ Error: {e}")

    # Data statistics
    session = get_db_session()
    try:
        user_count = session.query(User).count()
        conversation_count = session.query(Conversation).count()
        insight_count = session.query(Insight).count()
        highlight_count = session.query(Highlight).count()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Users", user_count)
        with col2:
            st.metric("Conversations", conversation_count)
        with col3:
            st.metric("Insights", insight_count)
        with col4:
            st.metric("Highlights", highlight_count)

    finally:
        session.close()

    # Session information
    st.markdown("### 📊 Session Information")
    if st.session_state.current_user_id:
        user_id = str(st.session_state.current_user_id)
        conversation_history = get_current_user_conversation_history()
        conversation_id = get_current_user_conversation_id()

        st.info(f"Current User: {st.session_state.current_user_id}")
        st.info(f"Conversation ID: {conversation_id}")
        st.info(f"Messages in session: {len(conversation_history)}")
    else:
        st.info("No user selected")

    # Data management
    st.markdown("### 🛠️ Data Management")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Generate Mock Data"):
            with st.spinner("Generating mock data..."):
                try:
                    generator = MockDataGenerator()
                    user_ids = generator.generate_all_raw_data(num_users=3, days_back=21)
                    st.success(f"Generated data for users: {user_ids}")
                    st.cache_data.clear()  # Clear cache to see new data
                except Exception as e:
                    st.error(f"Error generating data: {e}")

    with col2:
        if st.button("Update Weather Data"):
            with st.spinner("Updating weather data..."):
                try:
                    manager = ExternalDataManager()
                    results = manager.run_daily_update()
                    st.success(f"Weather update complete: {results}")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Error updating weather: {e}")

def main():
    """Main application function"""

    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🏃‍♂️ Fitbit AI Health Assistant</h1>
        <p>Personalized health insights powered by 6-layer memory architecture</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar - User selection
    st.sidebar.markdown("### 👤 User Selection")

    users = get_users()
    if not users:
        st.sidebar.warning("No users found. Generate mock data first.")
        st.sidebar.button("Generate Mock Data", key="sidebar_mock_data")
    else:
        selected_user = st.sidebar.selectbox(
            "Select User:",
            options=[None] + users,
            format_func=lambda x: "Select a user..." if x is None else x[1],
            key="user_selector"
        )

        if selected_user:
            # Check if user changed
            if st.session_state.current_user_id != selected_user[0]:
                st.session_state.current_user_id = selected_user[0]
                # Clear any cached data for the new user
                st.cache_data.clear()
                st.rerun()  # Refresh to show new user's data

        # User info
        if st.session_state.current_user_id:
            session = get_db_session()
            try:
                user = session.query(User).filter(User.id == st.session_state.current_user_id).first()
                if user:
                    st.sidebar.markdown(f"**Age:** {user.age}")
                    st.sidebar.markdown(f"**Location:** {user.location}")
                    st.sidebar.markdown(f"**Goals:** {', '.join(user.goals or [])}")
            finally:
                session.close()

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "📊 Health Data", "🧠 AI Context", "⚙️ System"])

    with tab1:
        render_chat_interface()

    with tab2:
        if st.session_state.current_user_id:
            st.markdown("### 📈 Your Health Data")

            # Date range selector
            days_back = st.slider("Days to show:", 7, 30, 14)

            # Get and display data
            df = get_user_health_data(st.session_state.current_user_id, days_back)

            if not df.empty:
                render_health_charts(df)

                # Raw data table
                with st.expander("Raw Data Table", expanded=False):
                    st.dataframe(df, use_container_width=True)
            else:
                st.info("No health data available for this user.")
        else:
            st.warning("Please select a user to view health data.")

    with tab3:
        if st.session_state.current_user_id:
            st.markdown("### 🔍 AI Context Visualization")
            st.markdown("This shows exactly what data the AI uses to personalize responses:")

            with st.spinner("Loading context..."):
                context_data = get_user_context_data(st.session_state.current_user_id)
                render_context_visualization(context_data)
        else:
            st.warning("Please select a user to view AI context.")

    with tab4:
        render_system_info()

if __name__ == "__main__":
    main()
