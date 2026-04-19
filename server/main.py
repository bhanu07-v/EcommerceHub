import os
import uuid
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Request, Depends, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from google_sheets_api import db

load_dotenv()

app = FastAPI(title="EcommerceHub API Server")

# Allow requests from all common local dev ports, much like the Express setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event
@app.on_event("startup")
def startup_event():
    try:
        db.initialize()
    except Exception as e:
        print("Failed to initialize Google Sheets DB on startup:", e)

# Models
class SignupRequest(BaseModel):
    firstName: str
    lastName: str
    email: str
    password: str
    userType: str
    phone: str

class LoginRequest(BaseModel):
    email: str
    password: str
    userType: str

class CartAddRequest(BaseModel):
    buyerId: str
    productId: str
    quantity: int

class CartUpdateRequest(BaseModel):
    quantity: int

class ProductUpdate(BaseModel):
    pass # Accept arbitrary dict fields in endpoint to match JS behavior

class OrderStatusUpdate(BaseModel):
    status: str

# Base routes
@app.get("/api/test")
def test_endpoint():
    return {"success": True, "message": "Server is running!"}

@app.get("/")
def home():
    return "EcommerceHub API Server is running!"

# Auth routes
@app.post("/api/auth/signup")
def signup(req: SignupRequest):
    try:
        existing_user = db.find_user_by_email(req.email)
        if existing_user:
            return {"success": False, "message": "Email already registered"}
        
        user_data = req.model_dump()
        user = db.create_user(user_data)
        
        user_response = {
            "id": user.get("id"),
            "firstName": req.firstName,
            "lastName": req.lastName,
            "email": req.email,
            "userType": req.userType
        }
        return {"success": True, "user": user_response}
    except Exception as e:
        return {"success": False, "message": f"Signup failed: {str(e)}"}

@app.post("/api/auth/login")
def login(req: LoginRequest):
    try:
        user = db.find_user_by_email(req.email)
        if not user:
            return {"success": False, "message": "User not found"}
        
        if user.get("password") != req.password:
            return {"success": False, "message": "Invalid password"}
            
        if user.get("userType") != req.userType:
            return {"success": False, "message": "Invalid user type"}
            
        user_response = {
            "id": user.get("id"),
            "firstName": user.get("firstName"),
            "lastName": user.get("lastName"),
            "email": user.get("email"),
            "userType": user.get("userType")
        }
        return {"success": True, "user": user_response}
    except Exception as e:
        return {"success": False, "message": f"Login failed: {str(e)}"}

# Products route
@app.get("/api/products")
def get_products(sellerId: Optional[str] = None):
    try:
        products = db.get_all_products()
        filtered_products = []
        
        for p in products:
            if sellerId and str(p.get("sellerId")) != sellerId:
                continue
                
            # Formatting as required by the frontend
            prod_id = str(p.get("id", ""))
            name = str(p.get("name", "Unknown Product"))
            price = float(p.get("price", 0) or 0)
            stock = int(p.get("stock", 0) or 0)
            cost = float(p.get("cost", 0) or 0)
            sales = int(p.get("sales", 0) or 0)
            
            # Simple PQI logic ported from node
            margin_pct = float(((price - cost) / price * 100.0) if price > 0 else 0.0)
            margin_score = max(0.0, min(100.0, margin_pct))
            sales_score = max(0.0, min(100.0, float(sales) / 500.0 * 100.0))
            stock_score = max(0.0, min(100.0, float(stock) / 100.0 * 100.0))
            
            pqi_raw = float((0.4 * margin_score) + (0.3 * sales_score) + (0.1 * stock_score) + 20.0)
            pqi = float(round(pqi_raw / 20.0 * 10.0) / 10.0)  # scale to 1-5 roughly
            pqi = max(1.0, min(5.0, pqi))
            
            formatted_p = {
                **p,
                "id": prod_id,
                "name": name,
                "price": price,
                "stock": stock,
                "cost": cost,
                "sales": sales,
                "originalPrice": p.get("originalPrice") or round(price * 1.3),
                "pqi": pqi,
                "reviewCount": 0 # Defaulting for now
            }
            if name != "Unknown Product" and name.strip() != "" and price > 0 and stock >= 0:
                filtered_products.append(formatted_p)
                
        return {"success": True, "products": filtered_products}
    except Exception as e:
        return {"success": False, "message": f"Failed to fetch products: {str(e)}", "products": []}

@app.post("/api/products")
def create_product(product_data: dict):
    try:
        product = db.create_product(product_data)
        return {"success": True, "product": product}
    except Exception as e:
        return {"success": False, "message": f"Failed to create product: {str(e)}"}

@app.put("/api/products/{productId}")
def update_product(productId: str, product_data: dict):
    try:
        updated_product = db.update_product(productId, product_data)
        if updated_product:
            return {"success": True, "product": updated_product, "message": "Product updated successfully"}
        return {"success": False, "message": "Product not found"}
    except Exception as e:
        return {"success": False, "message": f"Failed to update product: {str(e)}"}

# Cart routes
@app.post("/api/cart")
def add_to_cart(req: CartAddRequest):
    try:
        item = db.add_to_cart(req.buyerId, req.productId, req.quantity)
        return {"success": True, "item": item, "message": "Item added to cart successfully"}
    except Exception as e:
        return {"success": False, "message": f"Failed to add to cart: {str(e)}"}

@app.get("/api/cart/{buyerId}")
def get_cart(buyerId: str):
    try:
        items = db.get_cart_items(buyerId)
        db_products = db.get_all_products()
        product_map = {str(p.get("id")): p for p in db_products}
        
        valid_items = []
        for item in items:
            p_id = str(item.get("productId", ""))
            product = product_map.get(p_id)
            if product:
                product_copy = dict(product)
                product_copy["price"] = float(product_copy.get("price", 0) or 0)
                product_copy["stock"] = int(product_copy.get("stock", 0) or 0)
                product_copy["originalPrice"] = product_copy.get("originalPrice", round(product_copy["price"] * 1.3))
                
                valid_items.append({
                    "id": item.get("id"),
                    "buyerId": item.get("buyerId"),
                    "productId": p_id,
                    "quantity": int(item.get("quantity", 1)),
                    "addedAt": item.get("addedAt"),
                    "product": product_copy
                })
        return {"success": True, "items": valid_items}
    except Exception as e:
        return {"success": False, "message": f"Failed to fetch cart: {str(e)}", "items": []}

@app.put("/api/cart/{cartId}")
def update_cart_item(cartId: str, req: CartUpdateRequest):
    try:
        if req.quantity <= 0:
            db.remove_from_cart(cartId)
            return {"success": True, "item": None, "message": "Item removed"}
        else:
            item = db.update_cart_item(cartId, req.quantity)
            if item:
                return {"success": True, "item": item, "message": "Item updated"}
            return {"success": False, "message": "Item not found"}
    except Exception as e:
        return {"success": False, "message": f"Failed to update cart: {str(e)}"}

@app.delete("/api/cart/{cartId}")
def delete_cart_item(cartId: str):
    try:
        success = db.remove_from_cart(cartId)
        return {"success": success, "message": "Item removed successfully" if success else "Item not found"}
    except Exception as e:
        return {"success": False, "message": f"Failed to remove item: {str(e)}"}

# Order routes
@app.post("/api/orders")
def create_order(order_data: dict):
    try:
        order = db.create_order(order_data)
        return {"success": True, "order": order}
    except Exception as e:
        return {"success": False, "message": f"Failed to create order: {str(e)}"}

@app.get("/api/orders/buyer/{buyerId}")
def get_orders_by_buyer(buyerId: str):
    try:
        orders = db.get_orders_by_buyer(buyerId)
        return {"success": True, "orders": orders}
    except Exception as e:
        return {"success": False, "message": f"Failed to fetch orders: {str(e)}", "orders": []}

@app.get("/api/orders/seller/{sellerId}")
def get_orders_by_seller(sellerId: str):
    try:
        orders = db.get_orders_by_seller(sellerId)
        return {"success": True, "orders": orders}
    except Exception as e:
        return {"success": False, "message": f"Failed to fetch orders: {str(e)}", "orders": []}

@app.put("/api/orders/{orderId}/status")
def update_order_status(orderId: str, req: OrderStatusUpdate):
    try:
        db_order = db.update_order_status(orderId, req.status)
        if db_order:
            return {"success": True, "message": "Status updated properly"}
        return {"success": False, "message": "Order not found"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# Chatbot routes
from chatbot_service import chatbot

class ChatMessage(BaseModel):
    userId: str
    message: str
    userType: Optional[str] = "buyer"
    language: Optional[str] = "en"
    dbContext: Optional[dict] = {}
    sellerId: Optional[str] = None

class ChatSearch(BaseModel):
    query: str
    language: Optional[str] = "en"
    userType: Optional[str] = "buyer"
    
class ChatRecommendation(BaseModel):
    productId: str
    userId: Optional[str] = None
    limit: Optional[int] = 5

@app.post("/api/chatbot/message")
def chatbot_message(req: ChatMessage):
    try:
        final_context = req.dbContext
        if not final_context or (not final_context.get("products") and not final_context.get("orders")):
            try:
                products = db.get_all_products()
                orders = []
                if req.userType == "seller":
                    orders = db.get_orders_by_seller(req.sellerId or req.userId)
                
                final_context = {
                    "products": [{"id": p.get("id"), "name": p.get("name"), "price": float(p.get("price", 0) or 0), "stock": int(p.get("stock", 0) or 0)} for p in products],
                    "orders": [{"id": o.get("id"), "status": o.get("status"), "total": o.get("total")} for o in orders]
                }
            except Exception:
                final_context = {"products": [], "orders": []}
                
        result = chatbot.process_message(req.userId, req.message, req.userType, final_context)
        return result
    except Exception as e:
        return {
            "success": False,
            "response": "I'm experiencing technical difficulties. Please try again in a moment.",
            "error": str(e)
        }

@app.post("/api/chatbot/voice")
def chatbot_voice(userId: str = Form(...), userType: str = Form("buyer"), audio: UploadFile = File(...)):
    # Placeholder for voice processing
    return {
        "success": True,
        "response": "Voice message processing is placeholder. Please send text.",
        "transcribedText": "[Voice message received]",
        "language": "en"
    }

@app.get("/api/chatbot/history/{userId}")
def chatbot_history(userId: str):
    session = chatbot.get_session(userId)
    return {"success": True, "history": session.get("conversationHistory", [])}

@app.delete("/api/chatbot/history/{userId}")
def clear_history(userId: str):
    if userId in chatbot.sessions:
        chatbot.sessions[userId]["conversationHistory"] = []
        return {"success": True, "message": "Conversation history cleared"}
    return {"success": False, "message": "No conversation found"}

@app.post("/api/chatbot/search")
def chatbot_search(req: ChatSearch):
    try:
        products = db.get_all_products()
        results = chatbot.search_products(req.query, products, req.language)
        return {
            "success": True,
            "query": req.query,
            "results": results[:10],
            "totalFound": len(results)
        }
    except Exception as e:
        return {"success": False, "message": str(e), "results": []}

@app.post("/api/chatbot/recommendations")
def chatbot_recommendations(req: ChatRecommendation):
    try:
        products = db.get_all_products()
        target = next((p for p in products if p.get("id") == req.productId), None)
        if not target:
            return {"success": False, "message": "Product not found"}
            
        recs = chatbot.generate_recommendations(target, products, req.limit)
        return {"success": True, "productId": req.productId, "recommendations": recs, "count": len(recs)}
    except Exception as e:
        return {"success": False, "message": str(e), "recommendations": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=3001, reload=True)
