#!/usr/bin/env python3
"""
Example client for PM-KISAN Chat Data Extraction API
"""

import requests
import json
from typing import Optional

class ChatAPIClient:
    def __init__(self, base_url: str = "http://localhost:8003"):
        self.base_url = base_url
        self.session_id: Optional[str] = None
    
    def start_chat(self, scheme_code: str = "pm-kisan") -> dict:
        """Start a new chat session"""
        response = requests.post(
            f"{self.base_url}/chat",
            json={
                "user_input": "",  # Empty input to get welcome message
                "scheme_code": scheme_code
            }
        )
        response.raise_for_status()
        data = response.json()
        self.session_id = data["session_id"]
        return data
    
    def send_message(self, message: str) -> dict:
        """Send a message to the chat system"""
        if not self.session_id:
            raise ValueError("No active session. Call start_chat() first.")
        
        response = requests.post(
            f"{self.base_url}/chat",
            json={
                "session_id": self.session_id,
                "user_input": message
            }
        )
        response.raise_for_status()
        return response.json()
    
    def get_status(self) -> dict:
        """Get current session status"""
        if not self.session_id:
            raise ValueError("No active session.")
        
        response = requests.get(f"{self.base_url}/sessions/{self.session_id}/status")
        response.raise_for_status()
        return response.json()
    
    def get_farmer_data(self) -> dict:
        """Get complete farmer data (only when collection is complete)"""
        if not self.session_id:
            raise ValueError("No active session.")
        
        response = requests.get(f"{self.base_url}/sessions/{self.session_id}/farmer-data")
        response.raise_for_status()
        return response.json()
    
    def delete_session(self):
        """Delete the current session"""
        if not self.session_id:
            return
        
        response = requests.delete(f"{self.base_url}/sessions/{self.session_id}")
        response.raise_for_status()
        self.session_id = None
    
    def developer_action(self, action: str, target: str = None) -> dict:
        """Perform developer action (requires developer mode)"""
        if not self.session_id:
            raise ValueError("No active session.")
        
        headers = {"X-Developer-Mode": "true"}
        payload = {"action": action}
        if target:
            payload["target"] = target
        
        response = requests.post(
            f"{self.base_url}/chat/{self.session_id}/dev-action",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    
    def send_message_dev(self, message: str) -> dict:
        """Send message with developer mode enabled"""
        if not self.session_id:
            raise ValueError("No active session.")
        
        headers = {"X-Developer-Mode": "true"}
        response = requests.post(
            f"{self.base_url}/chat",
            json={
                "session_id": self.session_id,
                "user_input": message
            },
            headers=headers
        )
        response.raise_for_status()
        return response.json()

def demo_conversation():
    """Demo conversation showing the API usage"""
    client = ChatAPIClient()
    
    print("🚀 Starting PM-KISAN Chat Demo...")
    
    # Start chat
    response = client.start_chat()
    print(f"\n🤖 Assistant: {response['assistant_response']}")
    print(f"📊 Stage: {response['stage']}")
    
    # Simulate conversation
    test_inputs = [
        "My name is Rajesh Kumar",
        "I am 45 years old",
        "I live in Village Rampur, District Meerut, UP",
        # Skip to family (you can add more basic info inputs)
        "I have a wife Sita who is 40 years old and a son Ravi who is 16 years old",
        "No more family members",
        "No" * 7,  # Answer no to all exclusion criteria
        "No special provisions needed"
    ]
    
    for user_input in test_inputs:
        response = client.send_message(user_input)
        print(f"\n👤 You: {user_input}")
        print(f"🤖 Assistant: {response['assistant_response']}")
        print(f"📊 Stage: {response['stage']} | Complete: {response['is_complete']}")
        
        if response['is_complete']:
            print("\n✅ Data collection complete!")
            farmer_data = response['farmer_data']
            print(f"🚜 Farmer Data Ready for EFR Upload:")
            print(json.dumps(farmer_data, indent=2))
            break
    
    # Clean up
    client.delete_session()
    print("\n🧹 Session cleaned up")

if __name__ == "__main__":
    demo_conversation() 