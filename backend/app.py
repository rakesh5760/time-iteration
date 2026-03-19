import os
import time
import threading
import pandas as pd
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Absolute path to frontend
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend'))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

@app.route('/')
def index():
    return app.send_static_file('index.html')

# Global State
class ExtractionState:
    def __init__(self):
        self.driver = None
        self.is_running = False
        self.interval_minutes = 1
        self.last_updated_time = None
        self.latest_data = None
        self.status_message = "Idle"
        self.stop_event = threading.Event()
        self.thread = None

state = ExtractionState()

def get_driver():
    if state.driver is None:
        chrome_options = Options()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--ignore-certificate-errors")
        service = Service(ChromeDriverManager().install())
        state.driver = webdriver.Chrome(service=service, options=chrome_options)
    return state.driver

def extraction_loop():
    driver = get_driver()
    state.status_message = "Extraction Started"
    
    # First iteration: Open page
    try:
        driver.get("https://time.is/")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "clock")))
        extract_data(driver)
    except Exception as e:
        state.status_message = f"Error: {str(e)}"
        state.is_running = False
        return

    while not state.stop_event.is_set():
        state.status_message = f"Waiting for next iteration ({state.interval_minutes} min)..."
        # Sleep in small increments to respond quickly to stop event
        for _ in range(int(state.interval_minutes * 60)):
            if state.stop_event.is_set():
                break
            time.sleep(1)
        
        if state.stop_event.is_set():
            break
            
        state.status_message = "Fetching Data..."
        try:
            driver.refresh()
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "clock")))
            extract_data(driver)
        except Exception as e:
            state.status_message = f"Error during refresh: {str(e)}"
            # Optionally break or continue
            time.sleep(5)

    state.status_message = "Extraction Stopped"
    state.is_running = False

def extract_data(driver):
    try:
        clock_element = driver.find_element(By.ID, "clock")
        current_time = clock_element.text
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        state.latest_data = current_time
        state.last_updated_time = datetime.now().strftime("%H:%M:%S")
        
        # Excel Logging
        excel_file = 'extracted_data.xlsx'
        sheet_name = 'Extraction Log'
        new_data = {'Timestamp': [timestamp], 'Extracted Time': [current_time]}
        df_new = pd.DataFrame(new_data)
        
        try:
            if not os.path.isfile(excel_file):
                df_new.to_excel(excel_file, sheet_name=sheet_name, index=False)
            else:
                with pd.ExcelWriter(excel_file, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                    # Get the existing sheet to append correctly
                    try:
                        df_existing = pd.read_excel(excel_file, sheet_name=sheet_name)
                        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                        df_combined.to_excel(writer, sheet_name=sheet_name, index=False)
                    except Exception as sheet_error:
                        print(f"Sheet error: {sheet_error}. Creating new sheet.")
                        df_new.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"Data saved to Excel: {current_time} at {timestamp}")
        except Exception as excel_err:
            print(f"Critical Excel error: {excel_err}")

        print(f"Extracted Time: {current_time} at {state.last_updated_time}")
    except Exception as e:
        print(f"Extraction failed: {e}")

@app.route('/start', methods=['POST'])
def start():
    if state.is_running:
        return jsonify({"message": "Extraction already running"}), 400
    
    data = request.json
    state.interval_minutes = float(data.get('interval', 1))
    state.stop_event.clear()
    state.is_running = True
    
    state.thread = threading.Thread(target=extraction_loop)
    state.thread.daemon = True
    state.thread.start()
    
    return jsonify({"message": "Extraction started"})

@app.route('/stop', methods=['POST'])
def stop():
    if not state.is_running:
        return jsonify({"message": "Extraction not running"}), 400
    
    state.stop_event.set()
    return jsonify({"message": "Stop signal sent"})

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "is_running": state.is_running,
        "status_message": state.status_message,
        "latest_data": state.latest_data,
        "last_updated_time": state.last_updated_time,
        "interval": state.interval_minutes
    })

if __name__ == '__main__':
    # Ensure backend and frontend directories exist if needed, but here we just run
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
