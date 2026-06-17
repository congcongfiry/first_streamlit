import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import sqlite3
import hashlib
import time
import os
import threading
import tempfile

# ==========================================
# 1. 基础配置与安全设置
# ==========================================
st.set_page_config(page_title="2025手机销售智能系统", layout="wide")

# SQLite全局锁，解决并发写入锁冲突
db_lock = threading.Lock()

# 自动兼容Windows本地 / Linux云端路径
if os.name == "nt":
    # Windows本地：项目根目录
    DB_PATH = "./sales_system.db"
else:
    # Streamlit Cloud：临时可写目录
    DB_PATH = os.path.join(tempfile.gettempdir(), "sales_system.db")

# 自动创建数据库父目录
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir)

# 初始化数据表（程序启动执行一次）
def init_database():
    with db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        c = conn.cursor()
        # 实时销售数据表
        c.execute('''CREATE TABLE IF NOT EXISTS stream_data
                     (timestamp TEXT, units INTEGER, rating REAL)''')
        # 告警日志表
        c.execute('''CREATE TABLE IF NOT EXISTS alerts
                     (timestamp TEXT, alert_msg TEXT, level TEXT)''')
        conn.commit()
        conn.close()

# 程序初始化建表
init_database()

# 模拟用户数据库（实际应用中应存入加密数据库）
USER_DB = {
    "admin": hashlib.sha256("admin123".encode()).hexdigest(),
    "manager": hashlib.sha256("manager888".encode()).hexdigest()
}

def check_password(username, password):
    """校验密码是否正确"""
    hash_pass = hashlib.sha256(password.encode()).hexdigest()
    if username in USER_DB and USER_DB[username] == hash_pass:
        return True
    return False

# ==========================================
# 2. 局部刷新 Fragment 组件 
# ==========================================
# 将 Fragment 独立出来，内部不调用 st.sidebar
@st.fragment(run_every=2.0)
def render_live_content(u_limit, r_limit):
    # A. 产生模拟数据
    units = np.random.randint(5, 55)
    rating = round(np.random.uniform(2.5, 5.0), 1)
    
    # B. 存入数据库（加线程锁防并发冲突）
    with db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO stream_data VALUES (datetime('now'), ?, ?)", (units, rating))
        
        # C. 告警逻辑判断
        if units < u_limit:
            c.execute("INSERT INTO alerts VALUES (datetime('now'), ?, ?)", (f"销量告急: {units}", "High"))
        if rating < r_limit:
            c.execute("INSERT INTO alerts VALUES (datetime('now'), ?, ?)", (f"评分破位: {rating}", "Critical"))
        conn.commit()
        conn.close()

    # D. 渲染 UI 指标
    m1, m2 = st.columns(2)
    m1.metric("当前瞬时销量", units, delta=units - u_limit)
    m2.metric("当前瞬时评分", f"⭐ {rating}", delta=round(rating - r_limit, 1))

    # E. 实时趋势图（统一使用DB_PATH，修复路径不一致bug）
    with db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        chart_df = pd.read_sql_query("SELECT * FROM stream_data ORDER BY timestamp DESC LIMIT 30", conn)
        conn.close()
    if not chart_df.empty:
        st.line_chart(chart_df.set_index('timestamp')['units'], height=250)

# ==========================================
# 3. 页面内容定义
# ==========================================

def show_history_dashboard():
    st.header("📊 2025 全球销售历史洞察")
    try:
        df = pd.read_csv('synthetic_mobile_sales_2025.csv')
        k1, k2, k3 = st.columns(3)
        k1.metric("总营收", f"${df['Revenue_USD'].sum():,.0f}")
        k2.metric("最热品牌", df['Brand'].mode()[0])
        k3.metric("平均评分", f"⭐ {df['Customer_Rating'].mean():.2f}")
        
        c1, c2 = st.columns(2)
        with c1:
            fig1 = px.pie(df, values='Revenue_USD', names='Brand', hole=0.4, title="品牌营收占比")
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            fig2 = px.scatter(df, x="Price_USD", y="Units_Sold", color="Brand", title="价格/销量相关性")
            st.plotly_chart(fig2, use_container_width=True)
    except Exception as e:
        st.warning(f"请确保根目录下有 'synthetic_mobile_sales_2025.csv' 文件，错误：{str(e)}")

def show_realtime_page():
    st.header("🚨 实时运营监控中心")
    # 侧边栏控件放在 Fragment 外部
    st.sidebar.subheader("🛡️ 告警阈值设置")
    u_limit = st.sidebar.slider("最低销量要求", 0, 50, 15, key="units_val")
    r_limit = st.sidebar.slider("最低评分要求", 1.0, 5.0, 3.5, key="rating_val")
    
    # 在主区域调用 Fragment
    render_live_content(u_limit, r_limit)

def show_admin_logs():
    st.header("📜 系统安全日志审计")
    with db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        log_df = pd.read_sql_query("SELECT * FROM alerts ORDER BY timestamp DESC", conn)
        conn.close()
    if not log_df.empty:
        st.dataframe(log_df, use_container_width=True)
    else:
        st.info("暂无日志记录")

# ==========================================
# 4. 主程序路由 (登录逻辑)
# ==========================================

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 欢迎登录销售管理系统")
    with st.container(border=True):
        u = st.text_input("用户名")
        p = st.text_input("密码", type="password")
        if st.button("登录", use_container_width=True):
            p_hash = hashlib.sha256(p.encode()).hexdigest()
            if u in USER_DB and USER_DB[u] == p_hash:
                st.session_state.logged_in = True
                st.session_state.user_role = u
                st.rerun()
            else:
                st.error("用户名或密码错误")
else:
    # 登录后的逻辑
    st.sidebar.title(f"👤 用户: {st.session_state.user_role.upper()}")
    if st.sidebar.button("登出"):
        st.session_state.logged_in = False
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # 菜单分配
    menu_options = ["🏠 历史看板", "🚨 实时监控"]
    if st.session_state.user_role == "admin":
        menu_options.append("📜 日志审计")
    
    choice = st.sidebar.radio("功能导航", menu_options)

    if "历史看板" in choice:
        show_history_dashboard()
    elif "实时监控" in choice:
        show_realtime_page()
    elif "日志审计" in choice:
        show_admin_logs()
