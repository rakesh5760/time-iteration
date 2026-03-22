import streamlit as st
import pandas as pd
import time
import threading
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Configuration ---
EXCEL_FILE = "iteration_data.xlsx"
TARGET_URL = "https://time.is"
DEBUG_PORT = 9222

# --- State Management ---
class EngineState:
    def __init__(self):
        self.is_running = False
        self.stop_event = threading.Event()
        self.last_execution = "Never"
        self.iteration_count = 0
        self.logs = []
        self.lock = threading.Lock()

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        with self.lock:
            self.logs.append(full_msg)
            if len(self.logs) > 50:
                self.logs.pop(0)
            print(full_msg)

    def set_running(self, running):
        self.is_running = running

    def increment_count(self):
        with self.lock:
            self.iteration_count += 1

    def set_last_execution(self, ts):
        self.last_execution = ts

if "engine" not in st.session_state:
    st.session_state.engine = EngineState()

engine = st.session_state.engine

# --- Logic ---
def get_driver():
    """Connects to the already running Chrome instance."""
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    try:
        # Suppress logging
        options.add_argument("--log-level=3") 
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        raise Exception(f"Failed to connect to Chrome on port {DEBUG_PORT}. Error: {e}")

def save_to_excel(extracted_time, extracted_date):
    """Appends data to iteration_data.xlsx."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_data = {
        "Timestamp": [timestamp],
        "Extracted Time": [extracted_time],
        "Extracted Date": [extracted_date]
    }
    df_new = pd.DataFrame(new_data)
    
    try:
        if os.path.exists(EXCEL_FILE):
            df_existing = pd.read_excel(EXCEL_FILE)
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
            df_final.to_excel(EXCEL_FILE, index=False)
        else:
            df_new.to_excel(EXCEL_FILE, index=False)
        return True
    except Exception as e:
        engine.log(f"Excel Error: {e}")
        return False

def iteration_loop(interval_minutes, stop_event):
    """Background loop for data extraction."""
    engine.log("Starting iteration loop...")
    driver = None
    try:
        driver = get_driver()
        engine.log("Connected to Chrome.")
        
        while not stop_event.is_set():
            try:
                engine.log(f"Iteration {engine.iteration_count + 1} starting...")
                driver.get(TARGET_URL)
                
                wait = WebDriverWait(driver, 15)
                time_el = wait.until(EC.presence_of_element_located((By.ID, "clock0_bg")))
                date_el = wait.until(EC.presence_of_element_located((By.ID, "dd")))
                
                t_str = time_el.text
                d_str = date_el.text.strip().replace("\n", " ")
                
                if save_to_excel(t_str, d_str):
                    engine.log(f"Extracted: {t_str} | {d_str}")
                    engine.increment_count()
                    engine.set_last_execution(datetime.now().strftime("%H:%M:%S"))
                
                # Check for stop event while waiting
                sleep_seconds = interval_minutes * 60
                engine.log(f"Waiting {interval_minutes} minutes for next iteration...")
                for _ in range(int(sleep_seconds)):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
                
            except Exception as e:
                engine.log(f"Loop Error: {e}")
                time.sleep(5)
    except Exception as e:
        engine.log(f"Critical Error: {e}")
    finally:
        engine.log("Iteration loop stopped.")
        engine.set_running(False)

# --- Streamlit UI ---
st.set_page_config(page_title="Iteration Engine", page_icon="⏱️", layout="wide")

st.title("⏱️ Iteration Engine")
st.write("Monitor [time.is](https://time.is) and log data to Excel automatically.")

with st.sidebar:
    st.header("Control Panel")
    iteration_time = st.number_input("Iteration Interval (minutes)", min_value=0.1, value=1.0, step=0.1)
    
    if not engine.is_running:
        if st.button("▶️ Start Iteration", width="stretch", type="primary"):
            engine.set_running(True)
            engine.stop_event.clear()
            engine.iteration_count = 0
            engine.logs = [] # Clear logs on start
            
            thread = threading.Thread(
                target=iteration_loop, 
                args=(iteration_time, engine.stop_event),
                daemon=True
            )
            thread.start()
            st.rerun()
    else:
        if st.button("⏹️ Stop Iteration", width="stretch", type="secondary"):
            engine.stop_event.set()
            # Note: loop will set is_running to False when it exits
            st.rerun()

# --- Dashboard ---
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Status", "Running" if engine.is_running else "Stopped")
with c2:
    st.metric("Iteration Count", engine.iteration_count)
with c3:
    st.metric("Last Execution", engine.last_execution)
with c4:
    st.metric("Interval", f"{iteration_time}m")

st.divider()

# Logs & Data View
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Live Logs")
    with engine.lock:
        log_text = "\n".join(engine.logs[::-1])
    st.code(log_text if log_text else "Waiting for start...", language="bash")

with col_right:
    st.subheader("Data Preview")
    if os.path.exists(EXCEL_FILE):
        try:
            df = pd.read_excel(EXCEL_FILE)
            st.dataframe(df.tail(10), width="stretch")
            st.download_button(
                label="Download Excel",
                data=open(EXCEL_FILE, "rb"),
                file_name=EXCEL_FILE,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"Could not load preview: {e}")
    else:
        st.info("Excel file will appear once the first iteration completes.")

# Auto-refresh UI
if engine.is_running:
    time.sleep(2)
    st.rerun()
