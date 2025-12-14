import streamlit as st
import pandas as pd
import requests
import time
import plotly.express as px

# --- CẤU HÌNH ---
st.set_page_config(page_title="Load Balancer Monitor", layout="wide")
LB_URL = "http://127.0.0.1:8000"
SERVER_PRICES = {"Fast (8001)": 10, "Medium (8002)": 5, "Slow (8003)": 2}

st.title("🎛️ Load Balancer Dashboard")

# --- SIDEBAR ---
st.sidebar.header("Control Panel")

# [CẬP NHẬT] Thêm 3 thuật toán mới vào danh sách lựa chọn
algo_option = st.sidebar.selectbox(
    "1. Chọn thuật toán:",
    (
        'round_robin', 
        'least_connection', 
        'weighted_response_time',
        'peak_ewma',   # Mới
        'p2c',         # Mới
        'adaptive'     # Mới
    )
)

if st.sidebar.button("Áp dụng thuật toán"):
    try:
        requests.post(f"{LB_URL}/config", json={"algorithm": algo_option})
        st.sidebar.success(f"Đã chuyển: {algo_option}")
    except: 
        st.sidebar.error("Lỗi kết nối tới Load Balancer!")

st.sidebar.markdown("---")
st.sidebar.header("Optimization (Caching)")
cache_prob = st.sidebar.slider("🎯 Tỷ lệ Cache Hit giả lập (%)", 0, 100, 10)
if st.sidebar.button("Cập nhật tỷ lệ Cache"):
    try:
        requests.post(f"{LB_URL}/config", json={"cache_probability": cache_prob})
        st.sidebar.success(f"Đã đặt tỷ lệ Cache: {cache_prob}%")
    except: 
        st.sidebar.error("Lỗi kết nối!")

st.sidebar.markdown("---")
st.sidebar.header("Simulation")
num_requests = st.sidebar.slider("Số lượng request:", 1, 1000, 50)
if st.sidebar.button("🚀 Bắn Request"):
    progress_bar = st.sidebar.progress(0)
    for i in range(num_requests):
        try: 
            # Timeout cực ngắn để bắn nhanh, không cần đợi phản hồi
            requests.get(LB_URL, timeout=0.1) 
        except: 
            pass
        progress_bar.progress((i + 1) / num_requests)
    st.sidebar.success("Hoàn thành!")

# --- GIAO DIỆN CHÍNH (FIXED LAYOUT) ---
@st.fragment(run_every=2)
def update_dashboard():
    try:
        # Timeout thấp để không treo UI khi load balancer bận
        response = requests.get(f"{LB_URL}/stats", timeout=0.5)
        data = response.json()
        servers = data['servers']
        
        # --- METRICS ---
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        
        kpi1.metric("Thuật toán", data['algorithm'].upper())
        kpi2.metric("Tổng Request", data['total_requests'])
        
        prob_setting = data.get('cache_probability', 0) * 100
        real_cache_rate = 0
        if data['total_requests'] > 0:
            real_cache_rate = (data['cache_hits'] / data['total_requests']) * 100
        kpi4.metric("Cache (Set/Real)", f"{prob_setting:.0f}% / {real_cache_rate:.1f}%")

        # Tìm server tốt nhất (chỉ tính những server khỏe mạnh)
        active_healthy_servers = [s for s in servers if s.get('total_handled', 0) > 0 and s.get('health_status') == 'healthy']
        if active_healthy_servers:
            fastest_server = min(active_healthy_servers, key=lambda x: x['avg_response_time'])
            kpi3.metric("Server tốt nhất", fastest_server['name'], 
                        delta=f"{fastest_server['avg_response_time']:.3f}s", delta_color="inverse")
        else:
            kpi3.metric("Server tốt nhất", "N/A")

        cost = data.get('current_cost_per_hour', 0)
        kpi5.metric("Chi phí", f"${cost}/giờ", delta_color="inverse")

        st.markdown("---")

        # --- TRẠNG THÁI SERVER (HIỂN THỊ CRASH) ---
        st.subheader("🛠️ Quản lý Tài nguyên & Sức khỏe")
        cols = st.columns(3)
        for idx, s in enumerate(servers):
            with cols[idx]:
                # Logic hiển thị trạng thái
                health = s.get('health_status', 'healthy')
                
                if not s['active']:
                    status_text = "🔴 Stopped (Manual)"
                    box_type = "info" # Màu xanh dương/xám
                elif health == 'crashed':
                    status_text = "💥 CRASHED (Recovering...)"
                    box_type = "error" # Màu đỏ
                else:
                    status_text = "🟢 Running"
                    box_type = "success" # Màu xanh lá

                st.write(f"**{s['name']}**")
                
                # Hiển thị hộp trạng thái màu sắc
                if box_type == "error":
                    st.error(status_text)
                elif box_type == "success":
                    st.success(status_text)
                else:
                    st.info(status_text)
                
                price = SERVER_PRICES.get(s['name'], 0)
                st.caption(f"Chi phí: ${price}/h")
                
                # Nút Bật/Tắt
                if s['active']:
                    if st.button(f"Tắt {s['name']}", key=f"btn_off_{idx}"):
                        requests.post(f"{LB_URL}/toggle_server", json={"name": s['name'], "action": "off"})
                        st.rerun()
                else:
                    if st.button(f"Bật {s['name']}", key=f"btn_on_{idx}"):
                        requests.post(f"{LB_URL}/toggle_server", json={"name": s['name'], "action": "on"})
                        st.rerun()

        st.markdown("---")

        # --- BIỂU ĐỒ ---
        df = pd.DataFrame(servers)
        if 'cpu_usage' not in df.columns: df['cpu_usage'] = 0

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📊 Phân bố tải (Backend)")
            # Biểu đồ hiển thị tổng số request đã xử lý
            fig_load = px.bar(df, x='name', y='total_handled', color='name')
            fig_load.update_yaxes(minallowed=0)
            st.plotly_chart(fig_load, use_container_width=True, key="fixed_chart_load")
        
        with col2:
            st.subheader("⏱️ Độ trễ (Latency)")
            # Biểu đồ hiển thị thời gian phản hồi trung bình
            fig_latency = px.bar(df, x='avg_response_time', y='name', orientation='h',
                                 color='avg_response_time', color_continuous_scale='RdYlGn_r')
            st.plotly_chart(fig_latency, use_container_width=True, key="fixed_chart_latency")

        st.subheader("🔥 Tài nguyên hệ thống (CPU Usage)")
        # Biểu đồ CPU cực kỳ quan trọng cho thuật toán 'adaptive'
        fig_cpu = px.bar(df, x='name', y='cpu_usage', color='cpu_usage',
                         range_y=[0, 100], color_continuous_scale='RdYlGn_r', 
                         text_auto=True)
        st.plotly_chart(fig_cpu, use_container_width=True, key="fixed_chart_cpu")

    except Exception as e:
        # SỬA LỖI GIẬT: Dùng toast thay vì st.error để không đổi layout khi request failed
        st.toast(f"⚠️ Đang kết nối lại... ({str(e)[:20]}...)", icon="⏳")

if __name__ == "__main__":
    update_dashboard()