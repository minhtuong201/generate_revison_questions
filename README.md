# AI-Powered Learning Web App with OpenAI GPT-4o mini

This is a Flask-based learning web application that offers a chatbot-based tutoring experience for students. The application uses OpenAI's GPT-4o mini model to generate AI responses and revision questions based on user interactions.

## Features

- **User Authentication**: Simple login system (simulated)
- **Course Selection**: Choose from available courses
- **AI Chat Interface**: Chat with an AI tutor powered by GPT-4o mini
- **Revision Questions**: Automatically generates revision questions using GPT-4o mini
- **Chat History**: Stores only user questions (not AI responses)
- **Clear Function**: Reset chat within the same course

## Setup

### Prerequisites

- Python 3.8+ installed
- OpenAI API key

### Configuration

1. Update the `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

2. (Optional) Adjust other parameters in the `.env` file:
   ```
   MODEL_NAME=gpt-4o-mini  # or another OpenAI model
   REVISION_QUESTIONS_N=10  # Generate after every N questions
   REVISION_QUESTIONS_O=3   # Overlap factor
   MAX_REVISION_QUESTIONS=20  # Maximum revision questions limit
   ```

### Installation

1. Install required packages:
   ```
   pip install -r requirements.txt
   ```

2. Run the application:
   ```
   python app.py
   ```

3. Access the application at [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Usage

1. Log in with any username and password (authentication is simulated for demo purposes)
2. Select a course from the available options
3. Start chatting with the AI tutor powered by GPT-4o mini
4. Revision questions will be generated automatically after every N questions (configurable)
5. Click the "Generate Revision" button to manually generate revision questions
6. Use the "Clear Chat" button to reset the conversation

## Architecture

- **Flask Backend**: Handles authentication, routing, and API calls to OpenAI
- **OpenAI Integration**: Uses GPT-4o mini for generating:
  - AI tutor responses tailored to each course
  - Revision questions based on user's chat history
- **Responsive Frontend**: Modern UI with separate views for login, course selection, and chat

## Revision Question Logic

The system generates revision questions:
- After every N questions (default: 10)
- With an overlap factor O (default: 3)
- Maximum of MAX_REVISION_QUESTIONS (default: 20)
- Using OpenAI to analyze previous user questions and create relevant revision topics

## Future Enhancements

- Database integration for persistent storage
- User registration and profile management
- Custom course content and materials
- Expanded analytics on student learning progress
- Fine-tuned models for specific educational domains
