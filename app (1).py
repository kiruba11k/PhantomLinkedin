
import time
import threading
import requests
import streamlit as st
from datetime import datetime
from typing import Optional

# ==============================
# Helpers & State
# ==============================

def init_state():
    if "is_running" not in st.session_state:
        st.session_state.is_running = False
    if "stop_flag" not in st.session_state:
        st.session_state.stop_flag = False
    if "activations_done" not in st.session_state:
        st.session_state.activations_done = 0
    if "logs" not in st.session_state:
        st.session_state.logs = []
    if "thread" not in st.session_state:
        st.session_state.thread = None

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    st.session_state.logs.append(line)

def get_secret(name: str, fallback: Optional[str] = None) -> Optional[str]:
    # Reads from Streamlit secrets if available, else fallback
    try:
        return st.secrets.get(name, fallback)
    except Exception:
        return fallback

# ==============================
# PhantomBuster API functions
# ==============================

def get_phantom_status(api_key: str, phantom_id: str) -> Optional[str]:
    url = f"https://api.phantombuster.com/api/v2/agents/fetch?id={phantom_id}"
    headers = {
        "X-Phantombuster-Key-1": api_key,
        "Content-Type": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("status")
        else:
            log(f"⚠️ Failed to fetch status (HTTP {r.status_code}): {r.text[:200]}")
            return None
    except requests.RequestException as e:
        log(f"❌ Error fetching status: {e}")
        return None

def launch_phantom(api_key: str, phantom_id: str) -> bool:
    url = f"https://api.phantombuster.com/api/v2/agents/launch?id={phantom_id}"
    headers = {
        "X-Phantombuster-Key-1": api_key,
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(url, headers=headers, timeout=30)
        if r.status_code == 200:
            return True
        else:
            log(f"⚠️ Launch failed (HTTP {r.status_code}): {r.text[:200]}")
            return False
    except requests.RequestException as e:
        log(f"❌ Error launching phantom: {e}")
        return False

# ==============================
# Automation Logic (in a thread)
# ==============================

def automation_loop(api_key: str, phantom_id: str, run_count: int, poll_seconds: int, idle_only: bool):
    log("🚀 Automation thread started.")
    try:
        while not st.session_state.stop_flag and st.session_state.activations_done < run_count:
            status = get_phantom_status(api_key, phantom_id)
            if status is None:
                # API error, wait and retry
                time.sleep(poll_seconds)
                continue

            # When idle_only=True, only launch if not running
            if idle_only:
                if status != "running":
                    next_idx = st.session_state.activations_done + 1
                    log(f"▶️ Launching Phantom (activation {next_idx}/{run_count}) — status currently '{status}'.")
                    ok = launch_phantom(api_key, phantom_id)
                    if ok:
                        st.session_state.activations_done += 1
                        log("✅ Launch requested successfully.")
                    else:
                        log("❌ Launch request failed.")
                else:
                    log("⏳ Phantom is running. Waiting...")
            else:
                # Always try launching up to run_count times (regardless of status)
                next_idx = st.session_state.activations_done + 1
                log(f"▶️ Launching Phantom (activation {next_idx}/{run_count}) — status '{status}'.")
                ok = launch_phantom(api_key, phantom_id)
                if ok:
                    st.session_state.activations_done += 1
                    log("✅ Launch requested successfully.")
                else:
                    log("❌ Launch request failed.")

            # Sleep between polls to avoid rate limits and busy-looping
            slept = 0
            while slept < poll_seconds and not st.session_state.stop_flag:
                time.sleep(1)
                slept += 1

    except Exception as e:
        log(f"💥 Unexpected error in automation loop: {e}")
    finally:
        st.session_state.is_running = False
        st.session_state.thread = None
        log("🛑 Automation thread stopped.")

# ==============================
# UI
# ==============================

st.set_page_config(page_title="Phantom Auto-Activator", page_icon="🪄", layout="wide")
init_state()

st.title("🪄 Phantom Auto-Activator")
st.caption("Launch your Phantom repeatedly without schedules — it re-launches when inactive, up to N times.")

with st.sidebar:
    st.header("⚙️ Settings")
    # Try to get API key from secrets first, else ask user
    secret_api = get_secret("PHANTOMBUSTER_API_KEY")
    api_key_input = st.text_input("PhantomBuster API Key", value=secret_api or "", type="password", help="You can also add this to Streamlit Cloud Secrets as PHANTOMBUSTER_API_KEY")
    phantom_id = st.text_input("Phantom ID", value=get_secret("PHANTOM_ID", ""))
    run_count = st.number_input("How many activations?", min_value=1, max_value=9999, value=5, step=1)
    poll_seconds = st.number_input("Check interval (seconds)", min_value=5, max_value=3600, value=60, step=5, help="How often to poll status and/or re-attempt launch.")
    idle_only = st.checkbox("Only launch when inactive (recommended)", value=True)

    colA, colB = st.columns(2)
    with colA:
        start_btn = st.button("▶️ Start", type="primary", use_container_width=True)
    with colB:
        stop_btn = st.button("🛑 Stop", use_container_width=True)

    clear_btn = st.button("🧹 Clear Logs", help="Clear in-memory logs.")

# Handle actions
if clear_btn:
    st.session_state.logs = []
    st.session_state.activations_done = 0
    log("🧹 Logs cleared.")

if stop_btn and st.session_state.is_running:
    st.session_state.stop_flag = True
    log("🛑 Stop requested.")

if start_btn:
    if st.session_state.is_running:
        log("ℹ️ Already running.")
    else:
        if not api_key_input or not phantom_id:
            st.error("Please provide API Key and Phantom ID to start.")
        else:
            st.session_state.stop_flag = False
            st.session_state.is_running = True
            # Reset counters if user wants a fresh run
            st.session_state.activations_done = 0

            # Launch background thread
            t = threading.Thread(
                target=automation_loop,
                args=(api_key_input, phantom_id, int(run_count), int(poll_seconds), bool(idle_only)),
                daemon=True
            )
            st.session_state.thread = t
            t.start()
            log("🔄 Automation started.")

# Main area
left, right = st.columns([2, 1])
with left:
    st.subheader("📜 Live Logs")
    st.write("\n".join(st.session_state.logs) or "No logs yet.")
    st.download_button(
        "⬇️ Download logs",
        data="\n".join(st.session_state.logs).encode("utf-8"),
        file_name=f"phantom_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
        use_container_width=True
    )

with right:
    st.subheader("📊 Progress")
    st.metric("Activations done", value=st.session_state.activations_done)
    st.progress(min(st.session_state.activations_done / max(1, int(run_count)), 1.0))
    status_placeholder = st.empty()

    # Show current status if user has provided creds
    if (getattr(st.session_state, "last_status_check", 0) + 5) < time.time() and api_key_input and phantom_id:
        status = get_phantom_status(api_key_input, phantom_id)
        st.session_state.last_status_check = time.time()
    else:
        status = None
    st.caption("Current Phantom status (best-effort):")
    st.code(status or "unknown", language="text")

st.divider()
st.markdown(
    """
**Tips**
- Add your `PHANTOMBUSTER_API_KEY` (and optional `PHANTOM_ID`) to **Streamlit Cloud → App settings → Secrets** so you don't have to type them each time.
- Keep `Only launch when inactive` ON to match your desired behavior precisely.
- Increase the `Check interval` if you see rate limit errors.
"""
)
