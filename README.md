# Multilingual E-Commerce Platform with AI Chatbot

This project is a full-stack, multilingual e-commerce storefront designed for high accessibility and seamless inventory management. Built using modern web technologies, it features an intelligent talking assistant powered by Google's Gemini LLM and utilizes Google Sheets as a serverless database for easy backend management.

## 🚀 Features

- **Storefront & Admin Dashboards**: Complete flow for both Buyers (browsing, asking AI, purchasing) and Sellers (managing inventory, fulfilling orders).
- **Native Multilingual Support**: Dynamic, schema-level language switching for English, Telugu, Hindi, and Tamil without relying on external auto-translate APIs, ensuring 100% human-verified product descriptions.
- **AI Shopping Assistant**: An intelligent chatbot powered by **Google Gemini API** that processes conversational queries to recommend products based on the live inventory.
- **Serverless Admin Database**: Integrates the **Google Sheets API** as a no-code database allowing non-technical store administrators to update product listings using a familiar spreadsheet interface instantly reflecting across the application.

## 🛠 Tech Stack

- **Frontend:** React.js (with `react-i18next` for internationalization)
- **Backend:** Python + FastAPI 
- **Database Layer:** Google Sheets API
- **AI Integration:** Google Gemini API (for NLP and Recommendation generation)

## ⚙️ Architecture Highlights

### Hybrid Localization (i18n)
While standard UI text is translated via frontend JSON dictionary mappings, dynamically generated user content (like Products) exists in the database with explicit, localized columns (`name_te`, `description_hi`), enabling native language toggling.

### Decoupled Data Layer
By utilizing FastAPI alongside an abstracted CRUD handler for Google Sheets, the application is highly decoupled. This allows the backend to be rapidly swapped out for a fully relational database (like PostgreSQL) in the future without altering the frontend or AI chatbot logic.

## 🏃‍♂️ Getting Started

### Prerequisites
- Node.js (v18+)
- Python (v3.10+)
- A Google Cloud Service Account credentials JSON file (to access Google Sheets Database)
- A Google AI Studio API Key (for Gemini)

### Running the Application

1. **Clone the repository:**
   ```bash
   git clone https://github.com/bhanu07-v/EcommerceHub.git
   cd EcommerceHub
   ```

2. **Start the React Frontend:**
   ```bash
   cd client
   npm install
   npm run start
   ```

3. **Start the Python Backend:**
   Open a new terminal window:
   ```bash
   cd server
   python -m venv venv
   venv\Scripts\activate   # (Windows)
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

The application will be running on `http://localhost:3000` and the API Swagger docs will be available at `http://localhost:8000/docs`.
