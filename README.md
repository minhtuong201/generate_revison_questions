# AI Tutor Chat App with Revision Generator

An interactive AI-powered chatbot that helps students learn through conversation and auto-generates revision questions. Built with **Flask**, **OpenAI**, and **Langchain**, the app supports multiple courses, dynamic Q&A, and smart revision prompts.

---

## 🚀 Features

- 🔐 Simple login system with session-based authentication
- 🎓 Select from multiple courses (Math, CS, Art, etc.)
- 💬 Real-time chat interface using OpenAI streaming responses
- 📚 Automatically generates multiple-choice revision questions after every few interactions
- 🧠 Uses Langchain and OpenAI for smart, course-specific tutoring
- 🧪 Revision questions can be manually triggered
- 🔄 FIFO chat history (auto-removes oldest messages after 5 questions)
- 🛡️ Rejects irrelevant messages (disabled by default with low similarity threshold)

---

## 📂 Project Structure

```
├── app.py                  # Main Flask app
├── requirements.txt        # Dependencies
├── Procfile                # For deployment (e.g., Render)
├── .gitignore              # Files to exclude from Git
├── templates/              # HTML templates
├── static/                 # CSS, JS, assets
│   └── js/chat.js          # Streaming chat logic
└── .env                    # Environment variables (NOT included in repo)
```

---

## 🛠️ Setup Instructions

### 1. Clone & Setup
```bash
git clone https://github.com/minhtuong201/generate_revison_questions.git
cd generate_revison_questions
python -m venv venv
source venv/bin/activate   # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create `.env`
Create a `.env` file in the root with your OpenAI key and settings:

```env
OPENAI_API_KEY=your-openai-key
MODEL_NAME=gpt-4o-mini
FLASK_SECRET_KEY=your-secret-key
DEBUG=True
REVISION_QUESTIONS_N=5 # Generate after every N questions
REVISION_QUESTIONS_O=2 # Overlap factor
MAX_REVISION_QUESTIONS=10 # Maximum revision question list limit
MAX_ADDED_QUESTIONS=2 # Maximum added revision questions (each time generate)
RELEVANCE_THRESHOLD=-10 # Minimum similarity score (not use any more)
CHAT_HISTORY=5 # Maximum chat history size
```

---

## 🧪 Run Locally

```bash
python app.py
```

Open your browser to `http://localhost:5000`.

---

## ☁️ Deploy on Render

1. Push this repo to GitHub
2. Go to [Render](https://render.com)
3. Create a new Web Service
4. Use:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`

5. Add your `.env` values in the **Environment Variables** section

---

## ✍️ Credits

- Built with [Flask](https://flask.palletsprojects.com/)
- Powered by [OpenAI API](https://platform.openai.com/)
- Utilizes [Langchain](https://www.langchain.com/)

---

## 📜 License

This project is for educational/demo purposes. Replace `demo` logic (e.g., hardcoded users) before using in production.
