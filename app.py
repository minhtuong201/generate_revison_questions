from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import math
import numpy as np

# Import Langchain components
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from openai import OpenAI

### WE DO NOT USE COSINE SIMILARITY IN THIS CODE, FOR STABILITY WE SET AS A LOW THRESHOLD -10 ###
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", -10))  # Minimum similarity score

# Parameters for revision question generation from environment variables
N = int(os.getenv("REVISION_QUESTIONS_N", 5))  # Generate after every N questions
O = int(os.getenv("REVISION_QUESTIONS_O", 2))   # Overlap factor
MAX_REVISION_QUESTIONS = int(os.getenv("MAX_REVISION_QUESTIONS", 10))  # Maximum number of revision questions
MAX_ADDED_QUESTIONS = int(os.getenv("MAX_ADDED_QUESTIONS", 2))  # Maximum added revision questions (each time generate)

# Load environment variables from .env file
load_dotenv()

# Set OpenAI API key 
api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")

# Initialize OpenAI client for direct API calls
openai_client = OpenAI(api_key=api_key)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# Initialize SentenceTransformer model globally with error handling
try:
    from sentence_transformers import SentenceTransformer
    sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
    similarity_enabled = True
except ImportError:
    print("SentenceTransformer not installed. Course relevance checks will be disabled.")
    similarity_enabled = False

# In-memory data storage (would use a database in production)
users = {
    'demo': {'password': 'password'},
    'test': {'password': 'test123'}
}

courses = [
    {'id': '1', 'title': 'Mathematics', 'description': 'Algebra, Probability, and Topology etc.'},
    {'id': '2', 'title': 'Art & Music', 'description': 'Art, Drawing, and Masterpiece etc.'},
    {'id': '3', 'title': 'Computer Science', 'description': 'Programming, AI, and Data Structures etc.'},
    {'id': '4', 'title': 'Cybersecurity & Blockchain', 'description': 'Cybersecurity, Blockchain, and Cryptocurrency etc.'},
    {'id': '5', 'title': 'VietNam', 'description': 'Anything about Vietnam, and other related countries'}

]

# Store full chat history (including AI responses)
chat_history = {}  # Format: {user_id-course_id: [messages]}
question_counts = {}  # Format: {user_id-course_id: count}
revision_questions = {}  # Format: {user_id-course_id: [questions]}

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('courses_page'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Simple validation
        if not username or not password:
            flash('Please enter both username and password')
            return redirect(url_for('index'))
        
        # For demonstration - allow any login
        # In a real app, you would check against a database
        if username in users and users[username]['password'] == password:
            session['user_id'] = username
            return redirect(url_for('courses_page'))
        else:
            # For demo purposes, let any login succeed
            session['user_id'] = username
            return redirect(url_for('courses_page'))
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/courses')
def courses_page():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    return render_template('courses.html', courses=courses)

@app.route('/chat/<course_id>')
def chat(course_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    session_key = f"{user_id}-{course_id}"
    
    # Get course info
    course = next((c for c in courses if c['id'] == course_id), None)
    if not course:
        flash('Course not found')
        return redirect(url_for('courses_page'))
    
    # Initialize chat history if needed
    if session_key not in chat_history:
        chat_history[session_key] = []
    
    # Initialize question count if needed
    if session_key not in question_counts:
        question_counts[session_key] = 0
    
    # Initialize revision questions if needed
    if session_key not in revision_questions:
        revision_questions[session_key] = []
    
    return render_template(
        'chat.html', 
        course=course, 
        chat_history=chat_history[session_key],
        question_count=question_counts[session_key],
        revision_questions=revision_questions[session_key],
        next_revision_at=calculate_next_revision(question_counts[session_key])
    )

@app.route('/api/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    user_message = data.get('message', '').strip()
    course_id = data.get('course_id', '')
    
    if not user_message or not course_id:
        return jsonify({'error': 'Message or course ID missing'}), 400
    
    user_id = session['user_id']
    session_key = f"{user_id}-{course_id}"
    
    # Get course info
    course = next((c for c in courses if c['id'] == course_id), None)
    if not course:
        return jsonify({'error': 'Course not found'}), 404
    
    # Check course relevance if similarity module is enabled
    is_relevant = True
    if similarity_enabled:
        try:
            similarity = check_course_relevance(user_message, course)
            is_relevant = similarity >= RELEVANCE_THRESHOLD
        except Exception as e:
            print(f"Error checking relevance: {str(e)}")
            # Continue with the message if relevance check fails
            is_relevant = True
    
    # Handle irrelevant messages by returning a fixed response
    if not is_relevant:
        return Response(
            stream_irrelevant_response(course),
            content_type='text/event-stream'
        )
    
    # Initialize if needed
    if session_key not in chat_history:
        chat_history[session_key] = []
    if session_key not in question_counts:
        question_counts[session_key] = 0
    if session_key not in revision_questions:
        revision_questions[session_key] = []
    
    # FIFO implementation for 5 Q&A limit: If already at 5 pairs (10 messages), remove oldest pair
    if len(chat_history[session_key]) >= 10:  # 5 pairs of messages
        # Remove the oldest Q&A pair (first user message and first AI response)
        chat_history[session_key].pop(0)  # Remove oldest user message
        chat_history[session_key].pop(0)  # Remove oldest AI response
    
    # Store user message in chat history
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chat_history[session_key].append({
        'role': 'user',
        'content': user_message,
        'timestamp': timestamp
    })
        
    # Increment question count
    question_counts[session_key] += 1
    
    # Always use streaming for responses, passing the current question count
    return Response(
        generate_ai_stream(user_message, course_id, session_key),
        content_type='text/event-stream'
    )

### WE DONT NEED BELOW FUNCTION, THEY ALWAYS RELEVANCE BECAUSE THRESHOLD IS -10 ###
def check_course_relevance(message, course):
    """
    Check if the message is relevant to the course using sentence embeddings.
    
    Args:
        message: User's message
        course: Course object with description
    
    Returns:
        float: Cosine similarity score between message and course description
    """
    # Check if we have enhanced course content
    course_content = course.get('expanded_description', course.get('description', ''))
    course_title = course.get('title', '')
    
    # Add course title to make the relevance check more robust
    course_text = f"{course_title}. {course_content}"
    
    # Encode the sentences
    try:
        emb1, emb2 = sentence_model.encode([message, course_text])
        
        # Compute cosine similarity
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        similarity = dot_product / (norm1 * norm2)
        
        print(f"Relevance check - Message: '{message}', Course: '{course_title}', Similarity: {similarity}")
        return similarity
    except Exception as e:
        print(f"Error computing similarity: {str(e)}")
        # Default to allowing the message if there's an error
        return 1.0

### WE DONT NEED BELOW FUNCTION, THEY ALWAYS RELEVANCE BECAUSE THRESHOLD IS -10 ###
def stream_irrelevant_response(course):
    """
    Stream a fixed response for irrelevant questions without using AI API.
    
    Args:
        course: The course object
    
    Yields:
        Streamed response chunks
    """
    # Create a fixed response message
    irrelevant_message = f"I'm sorry, but your question doesn't appear to be related to {course['title']}. " \
                          f"This chatbot is specifically designed to help with questions about {course['title']}. " \
                          f"Please ask a question related to {course['description']} for me to assist you effectively."
    
    # Split the message into words to simulate streaming
    words = irrelevant_message.split()
    
    for i, word in enumerate(words):
        # Add appropriate punctuation/spacing
        if i < len(words) - 1 and word not in [".", ",", "!", "?", ":", ";"]:
            word_to_send = word + " "
        else:
            word_to_send = word
        
        # Stream the word
        yield f"data: {json.dumps({'chunk': word_to_send})}\n\n"
        
    # Send end of stream marker with is_irrelevant flag
    yield f"data: {json.dumps({'end': True, 'is_irrelevant': True})}\n\n"

def generate_ai_stream(user_message, course_id, session_key):
    """
    Generates a streaming AI response and yields chunks as they become available.
    """
    # Get course information for context
    course = next((c for c in courses if c['id'] == course_id), None)
    course_title = course['title'] if course else "this course"
    course_desc = course['description'] if course else ""
    
    system_message = (
        f"You are an AI tutor specializing in {course_title}. "
        f"Your role is to provide helpful, accurate, and educational responses to student questions about {course_title}: {course_desc}. "
        f"Keep your responses clear, informative, and focused on helping the student. "
        f"If a student asks about unrelated topics, redirect them by message starting with 'ERROR 444: '"
    )
    
    try:
        # Prepare messages including chat history
        messages = [{"role": "system", "content": system_message}]
        
        # Add previous exchanges from chat history
        history_messages = []
        for msg in chat_history[session_key][:-1]:  # Exclude the most recent user message
            if msg.get('role') in ['user', 'assistant']:
                history_messages.append({"role": msg.get('role'), "content": msg.get('content', '')})
        
        # Add history if there are messages
        if history_messages:
            messages.extend(history_messages)
        
        # Add the current user message
        messages.append({"role": "user", "content": user_message})
        
        # Create streaming response
        stream = openai_client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
            temperature=0.7
        )
        
        full_response = ""
        buffer = ""
        
        # Process the stream word by word
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                
                # Add to buffer and check for words
                buffer += content
                words = buffer.split(" ")
                
                # If we have more than one word or the content ends with space
                if len(words) > 1 or buffer.endswith(" "):
                    for i, word in enumerate(words[:-1] if not buffer.endswith(" ") else words):
                        if word:  # Skip empty words
                            # Send word with space at the end except for punctuation
                            word_to_send = word + " "
                            yield f"data: {json.dumps({'chunk': word_to_send})}\n\n"
                    
                    # Keep the last word in buffer if content doesn't end with space
                    if not buffer.endswith(" ") and words:
                        buffer = words[-1]
                    else:
                        buffer = ""
        
        # Send any remaining buffer
        if buffer:
            yield f"data: {json.dumps({'chunk': buffer})}\n\n"
        
        if 'ERROR 444' in full_response:
            # Remove the last user message from history 
            chat_history[session_key].pop(0)
            question_counts[session_key] -= 1

        else:
            # Store the full response in chat history
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            chat_history[session_key].append({
                'role': 'assistant',
                'content': full_response,
                'timestamp': timestamp
            })
            # Check if we need to generate revision questions based on question count
            generate_revisions = False
            next_revision_at = calculate_next_revision(question_counts[session_key])
            if question_counts[session_key] == next_revision_at:
                generate_revisions = True
                generate_revision_questions(session_key)
            
            # Signal the end of the stream and send any additional data
            data = {
                'end': True,
                'question_count': question_counts[session_key],
                'generate_revisions': generate_revisions,
                'next_revision_at': next_revision_at
            }
            yield f"data: {json.dumps(data)}\n\n"

        
    except Exception as e:
        print("Error in streaming response:", str(e))
        import traceback
        traceback.print_exc()
        error_msg = "I'm sorry, I couldn't process your question due to a technical issue. Please try again later."
        yield f"data: {json.dumps({'error': error_msg})}\n\n"

# [Rest of the functions remain unchanged]

@app.route('/api/generate_revision', methods=['POST'])
def manual_revision():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    course_id = data.get('course_id', '')
    
    if not course_id:
        return jsonify({'error': 'Course ID missing'}), 400
    
    user_id = session['user_id']
    session_key = f"{user_id}-{course_id}"
    
    # Initialize if needed
    if session_key not in chat_history or not chat_history[session_key]:
        return jsonify({'error': 'No chat history to generate revisions from'}), 400
    
    if session_key not in revision_questions:
        revision_questions[session_key] = []
    
    try:
        generate_revision_questions(session_key)
        # Add this line to include the revision questions in the response
        return jsonify({
            'success': True,
            'revision_questions': revision_questions[session_key]
        })
    except Exception as e:
        print(f"Error in manual revision API endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e) or "An error occurred while generating revision questions"
        })

@app.route('/api/clear_chat', methods=['POST'])
def clear_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    course_id = data.get('course_id', '')
    
    if not course_id:
        return jsonify({'error': 'Course ID missing'}), 400
    
    user_id = session['user_id']
    session_key = f"{user_id}-{course_id}"
    
    # Clear chat data for this course
    if session_key in chat_history:
        chat_history[session_key] = []
    
    if session_key in question_counts:
        question_counts[session_key] = 0
    
    # Explicitly clear revision questions for this session
    if session_key in revision_questions:
        revision_questions[session_key] = []
    
    return jsonify({
        'success': True,
        'message': 'Chat cleared successfully'
    })

def generate_revision_questions(session_key):
    """
    Generates or updates multiple-choice revision questions using OpenAI API.
    Uses the complete chat history and maintains existing questions where relevant.
    """
    # Extract course_id from session_key
    parts = session_key.split('-')
    if len(parts) < 2:
        print(f"Invalid session key format: {session_key}")
        return []
    
    course_id = parts[1]  # Assuming format is "user_id-course_id"
    
    # Get course information
    course = next((c for c in courses if c['id'] == course_id), None)
    if not course:
        print(f"Course not found for ID: {course_id}")
        return []
    
    course_title = course['title']
    course_desc = course.get('expanded_description', course.get('description', ''))
    
    # Check if we have any chat history
    if session_key not in chat_history or not chat_history[session_key]:
        print(f"No chat history found for session: {session_key}")
        return []
    
    # Format the complete chat history
    formatted_history = []
    for msg in chat_history[session_key]:
        role = msg.get('role', '')
        content = msg.get('content', '')
        
        if role == 'user':
            formatted_history.append(f"Student: {content}")
        elif role == 'assistant':
            formatted_history.append(f"Tutor: {content}")
    
    # Join the formatted history with line breaks
    complete_conversation = "\n\n".join(formatted_history)
    
    # Get the existing questions (if any)
    existing_questions = []
    existing_questions_formatted = ""
    question_count = 0
    
    if session_key in revision_questions and revision_questions[session_key]:
        existing_questions = revision_questions[session_key]
        question_count = len(revision_questions[session_key])

        # Format existing questions for the prompt
        existing_questions_formatted = "Current revision questions:\n\n"
        for i, q in enumerate(existing_questions):
            existing_questions_formatted += f"{i+1}. {q.get('question', '')}\n"
            
            # Add options
            for key, value in q.get('options', {}).items():
                existing_questions_formatted += f"{key}) {value}\n"
            
            # Add correct answer
            existing_questions_formatted += f"Correct answer: {q.get('correct', '')}\n\n"
    
    # System prompt for generating or updating multiple-choice questions
    system_message = f"""You are a tutor specializing in {course_title}.
    
    I will provide you with:
    1. A complete conversation between a student and a tutor about {course_title}: {course_desc}
    2. Any existing revision questions (if available)
    
    Your task is to create or update a set of multiple-choice questions. If existing questions are provided,
    review them and:
    - Keep those that are still relevant to the conversation
    - Modify any that need updating based on new information
    - Add new questions to cover important concepts from the latest conversations
    - Remove any questions that are redundant or too similar to each other
       
    Each question should:
    1. Have exactly 4 options (a, b, c, d)
    2. Have ONE correct answer
    3. Be relevant to the topics discussed in the context of {course_title}: {course_desc}
    4. Be directly related to the conversation between the student and tutor
    5. Be clear and straightforward
    6. Avoid duplication of concepts already covered by other questions
    7. If no new question can be derived from the conversation, simply return the previous set of questions.
    
    Format each question as:
    1. [Question]
    a) [Option]
    b) [Option]
    c) [Option]
    d) [Option]
    Correct answer: [letter]"""
    
    # User message content
    user_message = f"Here is the conversation between the student and tutor about {course_title}:\n\n{complete_conversation}\n\n"
    
    # Add existing questions if available
    if existing_questions_formatted:
        user_message += existing_questions_formatted
        user_message += f"\nPlease review and update these questions based on the entire conversation. Ensure the questions complement each other and avoid redundancy. The new list must have no more than {min(MAX_ADDED_QUESTIONS + question_count, MAX_REVISION_QUESTIONS)} questions.\n"
    else:
        user_message += f"\nThere are no existed questions. Please create up to {MAX_ADDED_QUESTIONS + 1} appropriate multiple-choice questions based on this conversation.\n"
    
    try:
        print(f"Attempting to generate/update revision questions for {course_title} with OpenAI API...")
        # Call the OpenAI API
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1500,
            temperature=0.7
        )
        print("System message:")
        print(system_message)
        print("User message:")
        print(user_message)
        # Parse the response
        response_text = response.choices[0].message.content
        print(f"Successfully generated/updated revision questions for {course_title}")
        
        # Parse the response to extract structured questions
        questions = []
        current_q = {}
        
        for line in response_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Check if this is the start of a new question
            if line[0].isdigit() and '.' in line[:3]:
                if current_q and 'question' in current_q and 'options' in current_q and 'correct' in current_q:
                    questions.append(current_q)
                current_q = {'question': line.split('. ', 1)[1].strip(), 'options': {}}
            
            # Check if this is an option (a, b, c, d)
            elif line.lower().startswith(('a)', 'b)', 'c)', 'd)')):
                key = line[0].lower()
                value = line[3:].strip() if len(line) > 3 else ""
                if value:
                    current_q.setdefault('options', {})[key] = value
            
            # Check if this is the correct answer
            elif 'correct answer:' in line.lower():
                current_q['correct'] = line.split(':', 1)[1].strip().lower()
        
        # Add the last question if it's complete
        if current_q and 'question' in current_q and 'options' in current_q and 'correct' in current_q:
            questions.append(current_q)
        
        # Update revision questions, limiting to MAX_REVISION_QUESTIONS
        revision_questions[session_key] = questions[:MAX_REVISION_QUESTIONS]
        
    except Exception as e:
        print(f"Error generating/updating revision questions: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        # Re-raise the exception to be handled by the caller
        raise Exception(f"Error generating/updating revision questions: {str(e)}")

def calculate_next_revision(question_count):
    """Calculate at which question count the next revision will be generated"""
    if question_count <= N:
        return N
    index = math.ceil((question_count - N) / (N-O))
    return N + (N-O) * index

if __name__ == '__main__':
    app.run(debug=True)