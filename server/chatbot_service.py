import os
import time
import uuid
import random
import google.generativeai as genai
from dotenv import load_dotenv
from action_handler import ActionHandler

load_dotenv()

class MultilingualChatbot:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print("⚠️ GEMINI_API_KEY not set; Gemini disabled. Using fallback responses only.")
            self.model = None
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                print("✅ Gemini AI initialized successfully")
            except Exception as e:
                print(f"❌ Failed to initialize Gemini AI: {str(e)}")
                self.model = None

        self.sessions = {}
        self.action_handler = ActionHandler()

    def get_session(self, user_id, user_type='buyer'):
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                "id": str(uuid.uuid4()),
                "userId": user_id,
                "userType": user_type,
                "language": "en",
                "conversationHistory": [],
                "createdAt": time.time()
            }
        return self.sessions[user_id]

    def process_message(self, user_id, message, user_type='buyer', db_context=None):
        db_context = db_context or {}
        session = self.get_session(user_id, user_type)
        
        session["conversationHistory"].append({
            "role": "user",
            "content": message,
            "timestamp": time.time(),
            "language": session["language"]
        })
        
        intent = self.action_handler.parse_intent(message, user_type, db_context.get("products", []), db_context.get("orders", []))
        if intent and intent.get("action") and intent.get("confidence", 0) > 0.7:
            result = self.action_handler.execute_action(intent, user_id, user_type)
            if result and result.get("success"):
                response_text = result["message"]
                session["conversationHistory"].append({"role": "assistant", "content": response_text})
                return {
                    "success": True, 
                    "response": response_text,
                    "sessionId": session["id"],
                    "language": session["language"]
                }
                
        if not self.model:
            response_text = "I'm having some technical difficulties, but I can help you! Please try your question again."
            if user_type == "seller":
                response_text = "I'm experiencing some technical difficulties, but I'm here to help manage your store."
        else:
            try:
               response = self.model.generate_content(f"You are an AI assistant for a store. User message: {message}. Provide a helpful response.")
               response_text = response.text
            except Exception as e:
               response_text = f"Error generating response: {str(e)}"
               
        session["conversationHistory"].append({"role": "assistant", "content": response_text})       
        return {
            "success": True, 
            "response": response_text,
            "sessionId": session["id"],
            "language": session["language"]
        }

    def search_products(self, query, products, language='en'):
        if not query or not products:
            return []
            
        q_lower = query.lower()
        results = []
        for p in products:
            fields = [
                p.get("name", ""),
                p.get(f"name_{language}", ""),
                p.get("description", ""),
                p.get(f"description_{language}", "")
            ]
            if any(q_lower in str(f).lower() for f in fields if f):
                results.append(p)
        return results

    def generate_recommendations(self, product, all_products, limit=3):
        try:
            price = float(product.get("price", 0) or 0)
        except (ValueError, TypeError):
            price = 0.0
            
        min_p, max_p = price * 0.7, price * 1.3
        
        recs = []
        for p in all_products:
            try:
                p_price = float(p.get("price", 0) or 0)
            except (ValueError, TypeError):
                p_price = 0.0
            try:
                p_stock = int(p.get("stock", 0) or 0)
            except (ValueError, TypeError):
                p_stock = 0
                
            if p.get("id") != product.get("id") and min_p <= p_price <= max_p and p_stock > 0:
                recs.append(p)
                
        random.shuffle(recs)
        return recs[:limit]

chatbot = MultilingualChatbot()
