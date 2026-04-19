class ActionHandler:
    def check_confirmation(self, message, user_id):
        return None

    def execute_action(self, intent, user_id, user_type):
        return {"success": False, "message": "Action execution not implemented mapping."}
        
    def parse_intent(self, message, user_type, products, orders):
        return {"action": None, "confidence": 0}
