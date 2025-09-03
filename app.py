import streamlit as st
import requests
import time
import threading
from datetime import datetime

# PhantomBuster API integration
class PhantomController:
    def __init__(self, api_key, agent_id):
        self.api_key = api_key
        self.agent_id = agent_id
        self.headers = {
            'Content-Type': 'application/json',
            'x-phantombuster-key': api_key,
        }
        self.data = f'{{"id":"{agent_id}"}}'
        self.is_active = False
        self.launch_count = 0
        self.max_launches = 0
        self.automation_running = False
        self.thread = None
        self.status_check_interval = 30  # seconds between status checks
    
    def check_status(self):
        try:
            # Fetch agent status from PhantomBuster API
            response = requests.get(
                f'https://api.phantombuster.com/api/v2/agents/fetch?id={self.agent_id}',
                headers=self.headers
            )
            
            if response.status_code == 200:
                agent_data = response.json()
                status = agent_data.get('status', 'unknown')
                
                # Consider the phantom active if it's in running, launching, or waiting status
                self.is_active = status in ['running', 'launching', 'waiting']
                return self.is_active
            else:
                st.error(f"Error checking status: {response.status_code}")
                return False
                
        except Exception as e:
            st.error(f"Error checking phantom status: {str(e)}")
            return False
    
    def launch_phantom(self):
        try:
            response = requests.post(
                'https://api.phantombuster.com/api/v2/agents/launch',
                headers=self.headers,
                data=self.data
            )
            
            if response.status_code == 200:
                self.is_active = True
                self.launch_count += 1
                return True
            else:
                st.error(f"Error launching phantom: {response.status_code}")
                return False
                
        except Exception as e:
            st.error(f"Error launching phantom: {str(e)}")
            return False
    
    def start_automation(self, max_launches):
        self.max_launches = max_launches
        self.automation_running = True
        
        def run_automation():
            while (self.automation_running and 
                  (self.max_launches == 0 or self.launch_count < self.max_launches)):
                
                # Check current status
                current_status = self.check_status()
                
                # If not active, launch the phantom
                if not current_status:
                    self.launch_phantom()
                
                # Wait before checking again
                time.sleep(self.status_check_interval)
            
            self.automation_running = False
        
        # Start the automation in a separate thread
        self.thread = threading.Thread(target=run_automation)
        self.thread.daemon = True
        self.thread.start()
    
    def stop_automation(self):
        self.automation_running = False

# Streamlit UI
def main():
    st.set_page_config(
        page_title="Phantom Automation Dashboard",
        layout="wide"
    )
    
    st.title("👻 Phantom Automation Dashboard")
    st.markdown("Monitor and control your PhantomBuster agents with this dashboard.")
    
    # Initialize session state
    if 'controller' not in st.session_state:
        st.session_state.controller = None
    if 'api_key' not in st.session_state:
        st.session_state.api_key = ""
    if 'agent_id' not in st.session_state:
        st.session_state.agent_id = ""
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        api_key = st.text_input(
            "PhantomBuster API Key",
            type="password",
            value=st.session_state.api_key,
            help="You can find your API key in your PhantomBuster account settings"
        )
        
        agent_id = st.text_input(
            "Agent ID",
            value=st.session_state.agent_id,
            help="The ID of your phantom agent"
        )
        
        if st.button("Save Configuration"):
            if api_key and agent_id:
                st.session_state.api_key = api_key
                st.session_state.agent_id = agent_id
                st.session_state.controller = PhantomController(api_key, agent_id)
                st.success("Configuration saved!")
            else:
                st.error("Please provide both API Key and Agent ID")
        
        st.divider()
        
        if st.session_state.controller:
            st.subheader("Automation Control")
            max_launches = st.number_input(
                "Number of times to activate",
                min_value=0,
                max_value=100,
                value=5,
                help="Set to 0 for unlimited launches (until stopped manually)"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Start Automation") and not st.session_state.controller.automation_running:
                    st.session_state.controller.start_automation(max_launches)
                    st.rerun()
            
            with col2:
                if st.button("Stop Automation") and st.session_state.controller.automation_running:
                    st.session_state.controller.stop_automation()
                    st.rerun()
            
            st.divider()
            st.subheader("Manual Control")
            if st.button("Launch Phantom Once"):
                if st.session_state.controller.launch_phantom():
                    st.success("Phantom launched successfully!")
                st.rerun()
            
            if st.button("Check Status"):
                status = st.session_state.controller.check_status()
                status_text = "Active" if status else "Inactive"
                st.info(f"Phantom status: {status_text}")
    
    # Main content area
    if st.session_state.controller:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Current Status")
            
            # Display status with color coding
            status_color = "green" if st.session_state.controller.is_active else "red"
            status_text = "Active" if st.session_state.controller.is_active else "Inactive"
            
            st.markdown(
                f"**Phantom Status:** <span style='color:{status_color}; font-size: 1.5em;'>{status_text}</span>", 
                unsafe_allow_html=True
            )
            
            st.metric("Total Launches", st.session_state.controller.launch_count)
            
            if st.session_state.controller.max_launches > 0:
                st.metric("Max Launches Set", st.session_state.controller.max_launches)
                progress = min(st.session_state.controller.launch_count / st.session_state.controller.max_launches, 1.0)
                st.progress(progress)
            else:
                st.metric("Max Launches Set", "Unlimited")
            
            if st.session_state.controller.automation_running:
                st.success("Automation is running")
            else:
                st.info("⏸ Automation is stopped")
        
        with col2:
            st.subheader("Activity Log")
            log_container = st.container(height=300)
            
            with log_container:
                # Display recent activity (simulated for now)
                if st.session_state.controller.launch_count > 0:
                    for i in range(st.session_state.controller.launch_count):
                        st.write(f"{datetime.now().strftime('%H:%M:%S')} - Launch #{i+1} completed")
                
                if not st.session_state.controller.automation_running and st.session_state.controller.max_launches > 0 and st.session_state.controller.launch_count >= st.session_state.controller.max_launches:
                    st.success("All requested launches completed!")
        
        # Instructions section
        st.divider()
        st.subheader("How It Works")

        
        # Auto-refresh the UI every 10 seconds if automation is running
        if st.session_state.controller.automation_running:
            time.sleep(10)
            st.rerun()
    
    else:
        st.info("Please configure your PhantomBuster API Key and Agent ID in the sidebar to get started.")
        
        # Display help information
        st.subheader("Getting Started")


if __name__ == "__main__":
    main()
