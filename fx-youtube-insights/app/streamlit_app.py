# path: app/streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.schema import DatabaseManager
from etl.rollup import WeeklyRollup

# Page configuration
st.set_page_config(
    page_title="FX YouTube Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply Japanese font
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<style>
    html, body, [class*="css"] {
        font-family: 'Zen Kaku Gothic New', sans-serif !important;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 1rem;
        text-align: center;
    }
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 5px solid #1f77b4;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        margin: 0.5rem 0;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        margin-bottom: 0.25rem;
    }
    .judgement-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 500;
        margin: 0.5rem 0;
    }
    .badge-industry { background: #fff3cd; color: #856404; }
    .badge-content { background: #f8d7da; color: #721c24; }
    .badge-winning { background: #d4edda; color: #155724; }
    .badge-mixed { background: #e2e3e5; color: #383d41; }
    .badge-no-data { background: #f1f3f4; color: #5f6368; }
</style>
""", unsafe_allow_html=True)

class FXAnalyticsDashboard:
    def __init__(self):
        self.db = DatabaseManager()
        self.rollup = WeeklyRollup()
        self.jst = pytz.timezone('Asia/Tokyo')
        
        # Initialize database if needed
        self.db.initialize_schema()
        
        # Check if we have data, if not create dummy data
        self._ensure_data()
    
    def _ensure_data(self):
        """Ensure we have data to display"""
        with self.db.connect() as conn:
            result = conn.execute("SELECT COUNT(*) FROM weekly_metrics").fetchone()
            
        if result[0] == 0:
            # No data found, insert dummy data and calculate metrics
            st.info("データがありません。ダミーデータを作成中...")
            self.db.insert_dummy_data()
            self.rollup.calculate_weekly_metrics()
    
    def render(self):
        """Render the main dashboard"""
        # Header
        st.markdown('<div class="main-header">📊 FX YouTube 週次動向分析</div>', 
                   unsafe_allow_html=True)
        
        # Sidebar
        self._render_sidebar()
        
        # Get current week data
        week_start, week_end = self.rollup._get_week_boundaries(datetime.now(self.jst))
        
        # Main content
        col1, col2 = st.columns([2, 1])
        
        with col1:
            self._render_kpi_cards(week_start)
            self._render_comparison_chart(week_start)
            self._render_top_videos_table(week_start)
        
        with col2:
            self._render_judgement_panel(week_start)
            self._render_channel_selection()
    
    def _render_sidebar(self):
        """Render sidebar with controls"""
        st.sidebar.title("📋 コントロールパネル")
        
        # Data refresh button
        if st.sidebar.button("🔄 データ更新", key="refresh"):
            with st.spinner("データを更新中..."):
                self.rollup.calculate_weekly_metrics()
            st.sidebar.success("データが更新されました")
            st.rerun()
        
        # Week selection
        st.sidebar.subheader("📅 週選択")
        current_week = datetime.now(self.jst).date()
        weeks_back = st.sidebar.selectbox(
            "何週間前？",
            options=[0, 1, 2, 3, 4],
            format_func=lambda x: f"今週" if x == 0 else f"{x}週間前"
        )
        
        st.sidebar.subheader("ℹ️ 情報")
        st.sidebar.info(f"""
        **更新時刻**: {datetime.now(self.jst).strftime('%Y-%m-%d %H:%M')} JST
        
        **判定ロジック**:
        - 🌊 業界要因: 全体 < -10% かつ Z > -1.0
        - 🎯 コンテンツ要因: 全体 -5%~+5% かつ Z < -1.0  
        - 🏆 勝ち: Z > +1.0
        - 🔄 複合: その他
        """)
    
    def _render_kpi_cards(self, week_start):
        """Render KPI cards"""
        st.subheader("📊 今週の主要指標")
        
        # Get industry metrics
        with self.db.connect() as conn:
            industry_data = conn.execute("""
                SELECT 
                    views_delta_week,
                    delta_pct
                FROM weekly_metrics 
                WHERE scope = 'industry' AND entity_id = 'all' 
                AND week_start = ?
            """, [week_start]).fetchone()
            
            # Get previous week for comparison
            prev_week_start = week_start - timedelta(days=7)
            industry_prev = conn.execute("""
                SELECT 
                    views_delta_week,
                    delta_pct
                FROM weekly_metrics 
                WHERE scope = 'industry' AND entity_id = 'all' 
                AND week_start = ?
            """, [prev_week_start]).fetchone()
        
        if industry_data:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">業界総視聴増分</div>
                    <div class="metric-value" style="color: #1f77b4;">
                        {:.1f}万回
                    </div>
                </div>
                """.format(industry_data[0] / 10000), unsafe_allow_html=True)
            
            with col2:
                delta_color = "#28a745" if industry_data[1] > 0 else "#dc3545"
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">業界週次増減率</div>
                    <div class="metric-value" style="color: {};">
                        {:+.1f}%
                    </div>
                </div>
                """.format(delta_color, industry_data[1]), unsafe_allow_html=True)
            
            with col3:
                prev_delta = industry_prev[1] if industry_prev else 0
                trend = "📈" if industry_data[1] > prev_delta else "📉"
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">前週対比トレンド</div>
                    <div class="metric-value">
                        {} {:.1f}%
                    </div>
                </div>
                """.format(trend, abs(industry_data[1] - prev_delta)), unsafe_allow_html=True)
            
            with col4:
                # Get video count
                with self.db.connect() as conn:
                    video_count = conn.execute("""
                        SELECT COUNT(*) FROM weekly_metrics 
                        WHERE scope = 'video' AND week_start = ?
                    """, [week_start]).fetchone()[0]
                
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">分析動画数</div>
                    <div class="metric-value" style="color: #6f42c1;">
                        {}本
                    </div>
                </div>
                """.format(video_count), unsafe_allow_html=True)
    
    def _render_comparison_chart(self, week_start):
        """Render industry vs channels comparison chart"""
        st.subheader("📈 業界 vs チャンネル比較")
        
        with self.db.connect() as conn:
            # Get channel data
            channel_data = pd.read_sql("""
                SELECT 
                    wm.entity_id,
                    c.title,
                    wm.views_delta_week,
                    wm.delta_pct,
                    wm.zscore
                FROM weekly_metrics wm
                LEFT JOIN channels c ON wm.entity_id = c.channel_id
                WHERE wm.scope = 'channel' AND wm.week_start = ?
                ORDER BY wm.views_delta_week DESC
                LIMIT 20
            """, conn, params=[week_start])
            
            # Get industry benchmark
            industry_data = conn.execute("""
                SELECT delta_pct FROM weekly_metrics 
                WHERE scope = 'industry' AND entity_id = 'all' 
                AND week_start = ?
            """, [week_start]).fetchone()
        
        if not channel_data.empty and industry_data:
            industry_pct = industry_data[0]
            
            # Create comparison chart
            fig = go.Figure()
            
            # Add industry line
            fig.add_hline(
                y=industry_pct,
                line_dash="dash",
                line_color="red",
                annotation_text=f"業界平均: {industry_pct:.1f}%",
                annotation_position="top left"
            )
            
            # Add channel bars
            colors = ['#28a745' if pct > industry_pct else '#dc3545' 
                     for pct in channel_data['delta_pct']]
            
            fig.add_trace(go.Bar(
                x=channel_data['title'],
                y=channel_data['delta_pct'],
                marker_color=colors,
                text=[f"{pct:.1f}%" for pct in channel_data['delta_pct']],
                textposition='auto',
                hovertemplate='<b>%{x}</b><br>増減率: %{y:.1f}%<br>Z-Score: %{customdata:.2f}<extra></extra>',
                customdata=channel_data['zscore']
            ))
            
            fig.update_layout(
                title="チャンネル別週次増減率",
                xaxis_title="チャンネル",
                yaxis_title="増減率 (%)",
                showlegend=False,
                height=400
            )
            
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
    
    def _render_top_videos_table(self, week_start):
        """Render top videos table"""
        st.subheader("🏆 今週のトップ動画")
        
        with self.db.connect() as conn:
            top_videos = pd.read_sql("""
                SELECT 
                    v.title,
                    c.title as channel_title,
                    wm.views_delta_week,
                    wm.delta_pct,
                    v.published_at,
                    'https://youtube.com/watch?v=' || wm.entity_id as url
                FROM weekly_metrics wm
                LEFT JOIN videos v ON wm.entity_id = v.video_id
                LEFT JOIN channels c ON v.channel_id = c.channel_id
                WHERE wm.scope = 'video' AND wm.week_start = ?
                ORDER BY wm.views_delta_week DESC
                LIMIT 20
            """, conn, params=[week_start])
        
        if not top_videos.empty:
            # Format the data
            top_videos['views_delta_formatted'] = top_videos['views_delta_week'].apply(
                lambda x: f"{x:,}回" if x >= 1000 else f"{x}回"
            )
            top_videos['delta_pct_formatted'] = top_videos['delta_pct'].apply(
                lambda x: f"+{x:.1f}%" if x > 0 else f"{x:.1f}%"
            )
            
            # Create display dataframe
            display_df = pd.DataFrame({
                '動画タイトル': top_videos['title'].str[:50] + '...',
                'チャンネル': top_videos['channel_title'],
                '週次増分': top_videos['views_delta_formatted'],
                '増減率': top_videos['delta_pct_formatted'],
                '公開日': pd.to_datetime(top_videos['published_at']).dt.strftime('%m/%d')
            })
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
    
    def _render_judgement_panel(self, week_start):
        """Render judgement panel for selected channel"""
        st.subheader("🎯 要因分析")
        
        # Get available channels
        with self.db.connect() as conn:
            channels = pd.read_sql("""
                SELECT DISTINCT c.channel_id, c.title
                FROM channels c
                INNER JOIN weekly_metrics wm ON c.channel_id = wm.entity_id
                WHERE wm.scope = 'channel' AND wm.week_start = ?
                ORDER BY c.title
            """, conn, params=[week_start])
        
        if not channels.empty:
            # Channel selector
            selected_channel = st.selectbox(
                "チャンネルを選択:",
                channels['channel_id'].tolist(),
                format_func=lambda x: channels[channels['channel_id'] == x]['title'].iloc[0],
                key="judgement_channel"
            )
            
            if selected_channel:
                # Get judgement
                judgement = self.rollup.get_channel_judgement(selected_channel, week_start)
                
                # Display judgement badge
                badge_class = {
                    'industry_factor': 'badge-industry',
                    'content_factor': 'badge-content', 
                    'winning': 'badge-winning',
                    'mixed': 'badge-mixed',
                    'no_data': 'badge-no-data'
                }.get(judgement['judgement'], 'badge-mixed')
                
                st.markdown(f"""
                <div class="judgement-badge {badge_class}">
                    {judgement['message']}
                </div>
                """, unsafe_allow_html=True)
                
                # Display metrics if available
                if 'industry_delta' in judgement:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            "業界増減率",
                            f"{judgement['industry_delta']:.1f}%"
                        )
                    with col2:
                        st.metric(
                            "Z-Score",
                            f"{judgement['channel_zscore']:.2f}"
                        )
    
    def _render_channel_selection(self):
        """Render channel performance overview"""
        st.subheader("📺 チャンネル一覧")
        
        week_start, _ = self.rollup._get_week_boundaries(datetime.now(self.jst))
        
        with self.db.connect() as conn:
            channels_overview = pd.read_sql("""
                SELECT 
                    c.title,
                    wm.views_delta_week,
                    wm.delta_pct,
                    wm.zscore,
                    CASE 
                        WHEN wm.zscore > 1.0 THEN '🏆'
                        WHEN wm.zscore < -1.0 THEN '📉'
                        ELSE '➖'
                    END as status
                FROM weekly_metrics wm
                LEFT JOIN channels c ON wm.entity_id = c.channel_id
                WHERE wm.scope = 'channel' AND wm.week_start = ?
                ORDER BY wm.zscore DESC
            """, conn, params=[week_start])
        
        if not channels_overview.empty:
            for _, row in channels_overview.iterrows():
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    
                    with col1:
                        st.write(f"**{row['title'][:25]}...**")
                    with col2:
                        delta_color = "normal" if row['delta_pct'] >= 0 else "inverse"
                        st.metric("", f"{row['delta_pct']:.1f}%", delta_color=delta_color)
                    with col3:
                        st.metric("", f"Z: {row['zscore']:.2f}")
                    with col4:
                        st.write(row['status'])

def main():
    """Main application entry point"""
    dashboard = FXAnalyticsDashboard()
    dashboard.render()

if __name__ == "__main__":
    main()