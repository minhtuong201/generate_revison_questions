// Updated chat.js for streaming-only implementation with FIFO chat history
document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatContainer = document.getElementById('chat-container');
    const courseId = document.getElementById('course-id').value;
    const clearChatBtn = document.getElementById('clear-chat');
    const generateRevisionBtn = document.getElementById('generate-revision');
    const questionCountElement = document.getElementById('question-count');
    const nextRevisionElement = document.getElementById('next-revision');
    
    // Queue for handling multiple messages
    const streamQueue = [];
    let isStreaming = false;
    
    // Initialize page scrolling
    window.scrollTo({
        top: document.body.scrollHeight,
        behavior: 'auto'
    });
    
    // Helper function to append a message to the chat
    function appendMessage(role, content, shouldScroll = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = content;
        messageDiv.appendChild(contentDiv);
        chatContainer.appendChild(messageDiv);
        
        if (shouldScroll) {
            // Scroll the entire window to bottom
            window.scrollTo({
                top: document.body.scrollHeight,
                behavior: 'smooth'
            });
        }
        
        return { messageDiv, contentDiv };
    }

    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
    
    // Format text with line breaks
    function formatText(text) {
        if (!text) return '';
        const escaped = escapeHtml(text);
        return escaped.replace(/\n/g, '<br>');
    }
    
    // Process streaming response
    // Add this to your existing chat.js to handle irrelevant questions

    // Update the processStream function to handle the is_irrelevant flag
    async function processStream(response) {
        isStreaming = true;
        
        const { messageDiv, contentDiv } = appendMessage('ai', '');
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        try {
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const text = decoder.decode(value);
                const lines = text.split('\n\n');
                
                for (const line of lines) {
                    if (line.startsWith('data:')) {
                        try {
                            const data = JSON.parse(line.slice(5));
                            
                            // Handle chunk of content
                            if (data.chunk) {
                                buffer += data.chunk;
                                contentDiv.innerHTML = formatText(buffer);
                                
                                // Scroll as content comes in
                                window.scrollTo({
                                    top: document.body.scrollHeight,
                                    behavior: 'smooth'
                                });
                            }
                            
                            // Handle end of stream and additional data
                            if (data.end) {
                                contentDiv.innerHTML = formatText(buffer);
                                
                                // If the message was irrelevant, mark it visually
                                if (data.is_irrelevant) {
                                    // Mark the message with an irrelevant class
                                    messageDiv.classList.add('irrelevant-message');
                                    
                                    // Add an indicator that this question was off-topic
                                    const irrelevantBadge = document.createElement('div');
                                    irrelevantBadge.className = 'irrelevant-badge';
                                    irrelevantBadge.textContent = 'Not course-related';
                                    messageDiv.insertBefore(irrelevantBadge, contentDiv);
                                    
                                    // Also mark the user's message
                                    const userMessages = document.querySelectorAll('.user-message');
                                    if (userMessages.length > 0) {
                                        const lastUserMessage = userMessages[userMessages.length - 1];
                                        
                                        // Remove the last user message from the DOM since we won't count it
                                        lastUserMessage.parentNode.removeChild(lastUserMessage);
                                    }
                                    
                                    // Make sure the custom message is styled appropriately
                                    messageDiv.style.backgroundColor = '#fff8e1'; // Light amber background
                                    messageDiv.style.borderLeftColor = '#ffc107'; // Amber border
                                } else {
                                    // Regular message handling
                                    // Update question count and next revision if provided
                                    if (data.question_count !== undefined && questionCountElement) {
                                        questionCountElement.textContent = data.question_count;
                                    }
                                    
                                    if (data.next_revision_at !== undefined && nextRevisionElement) {
                                        nextRevisionElement.textContent = data.next_revision_at;
                                    }
                                    
                                    // Check if we should show revision questions - UPDATE HERE
                                    if (data.generate_revisions) {
                                        // Instead of reloading, fetch the revision questions
                                        fetchAndUpdateRevisionQuestions();
                                    }
                                }
                                
                                // Final scroll
                                window.scrollTo({
                                    top: document.body.scrollHeight,
                                    behavior: 'smooth'
                                });
                            }
                            
                            // Handle errors
                            if (data.error) {
                                contentDiv.innerHTML = `<div class="error">${data.error}</div>`;
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error reading stream:', error);
            contentDiv.innerHTML += '<div class="error">Error reading response stream</div>';
        } finally {
            isStreaming = false;
            
            if (streamQueue.length > 0) {
                const nextStream = streamQueue.shift();
                processStream(nextStream);
            }
        }
    }

    // Add CSS for irrelevant message styling
    const irrelevantStyles = document.createElement('style');
    irrelevantStyles.textContent = `
    .irrelevant-message {
        background-color: #fff8e1 !important; /* Light amber background */
        border-left: 3px solid #ffc107 !important; /* Amber border */
    }

    .irrelevant-badge {
        background-color: #ffc107;
        color: #333;
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 10px;
        margin-bottom: 5px;
        display: inline-block;
        font-weight: bold;
    }
    `;
    document.head.appendChild(irrelevantStyles);
    // Handle chat form submission
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const userMessage = userInput.value.trim();
        if (!userMessage) return;
        
        userInput.disabled = true;
        appendMessage('user', escapeHtml(userMessage));
        userInput.value = '';
        
        try {
            // Add loading indication
            const loadingIndicator = document.createElement('div');
            loadingIndicator.className = 'ai-message loading-message';
            loadingIndicator.innerHTML = '<div class="loading-dots">Thinking<span>.</span><span>.</span><span>.</span></div>';
            chatContainer.appendChild(loadingIndicator);
            
            window.scrollTo({
                top: document.body.scrollHeight,
                behavior: 'smooth'
            });
            
            // Send message to server - always streaming
            const response = await fetch('/api/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: userMessage,
                    course_id: courseId
                })
            });
            
            // Remove loading indicator
            chatContainer.removeChild(loadingIndicator);
            
            // Process response
            if (isStreaming) {
                streamQueue.push(response);
            } else {
                processStream(response);
            }
        } catch (error) {
            console.error('Error sending message:', error);
            appendMessage('ai', '<div class="error">Error: Could not connect to the server. Please try again.</div>');
        } finally {
            userInput.disabled = false;
            userInput.focus();
        }
    });
    
    // Clear chat functionality
    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', async function() {
            if (confirm('Are you sure you want to clear the chat history?')) {
                try {
                    const response = await fetch('/api/clear_chat', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            course_id: courseId
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        // Clear chat messages
                        chatContainer.innerHTML = '';
                        appendMessage('ai', 'Chat history has been cleared. How can I help you with your studies?');
                        
                        // Reset question count display
                        if (questionCountElement) {
                            questionCountElement.textContent = '0';
                        }
                        
                        // Reset next revision display
                        if (nextRevisionElement) {
                            nextRevisionElement.textContent = '5'; // Default N value
                        }
                        
                        // Hide and clear revision questions section
                        const revisionSection = document.getElementById('revision-section');
                        if (revisionSection) {
                            revisionSection.style.display = 'none';
                        }
                        
                        // Clear the content of the revision questions container
                        const revisionQuestionsContainer = document.getElementById('revision-questions-container');
                        if (revisionQuestionsContainer) {
                            revisionQuestionsContainer.innerHTML = '';
                        }
                    } else {
                        alert('Failed to clear chat history. Please try again.');
                    }
                } catch (error) {
                    console.error('Error clearing chat:', error);
                    alert('Error clearing chat history. Please try again.');
                }
            }
        });
    }

    // Generate revision button
    if (generateRevisionBtn) {
        generateRevisionBtn.addEventListener('click', async function() {
            try {
                generateRevisionBtn.disabled = true;
                generateRevisionBtn.textContent = 'Generating...';
                
                const response = await fetch('/api/generate_revision', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        course_id: courseId
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Instead of reloading, update the revision questions section
                    updateRevisionQuestions(data.revision_questions);
                } else {
                    alert('Failed to generate revision questions: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error generating revision:', error);
                alert('Error generating revision questions. Please try again.');
            } finally {
                generateRevisionBtn.disabled = false;
                generateRevisionBtn.textContent = 'Generate Revision';
            }
        });
    }

    // Add this new function to update revision questions without page reload
    function updateRevisionQuestions(questions) {
        // Show the revision section if hidden
        const revisionSection = document.getElementById('revision-section');
        if (revisionSection) {
            revisionSection.style.display = 'block';
        }
        
        // Get the container for revision questions
        const container = document.getElementById('revision-questions-container');
        if (!container) return;
        
        // Clear the existing content
        container.innerHTML = '';
        
        // Add heading
        const heading = document.createElement('h3');
        heading.textContent = 'Revision Questions';
        container.appendChild(heading);
        
        // Add questions
        questions.forEach((question, index) => {
            const questionDiv = document.createElement('div');
            questionDiv.className = 'revision-question';
            questionDiv.id = `question-${index}`;
            
            // Question text
            const questionText = document.createElement('div');
            questionText.className = 'question-text';
            questionText.textContent = `${index + 1}. ${question.question}`;
            questionDiv.appendChild(questionText);
            
            // Options container
            const optionsDiv = document.createElement('div');
            optionsDiv.className = 'options';
            
            // Add each option
            for (const [key, value] of Object.entries(question.options)) {
                const optionDiv = document.createElement('div');
                optionDiv.className = 'option';
                
                const label = document.createElement('label');
                
                const radio = document.createElement('input');
                radio.type = 'radio';
                radio.value = key;
                radio.name = `question${index}`;
                radio.setAttribute('data-correct', key === question.correct ? 'true' : 'false');
                
                const optionText = document.createTextNode(`${key}) ${value}`);
                
                label.appendChild(radio);
                label.appendChild(optionText);
                optionDiv.appendChild(label);
                optionsDiv.appendChild(optionDiv);
            }
            
            questionDiv.appendChild(optionsDiv);
            
            // Add answer div
            const answerDiv = document.createElement('div');
            answerDiv.className = 'answer';
            answerDiv.style.display = 'none';
            answerDiv.textContent = `Correct answer: ${question.correct}`;
            questionDiv.appendChild(answerDiv);
            
            // Add incorrect answer div
            const incorrectDiv = document.createElement('div');
            incorrectDiv.className = 'incorrect-answer';
            incorrectDiv.style.display = 'none';
            incorrectDiv.textContent = 'Incorrect! Please try again.';
            questionDiv.appendChild(incorrectDiv);
            
            // Add check answer button
            const checkBtn = document.createElement('button');
            checkBtn.className = 'check-answer';
            checkBtn.setAttribute('data-index', index);
            checkBtn.textContent = 'Check Answer';
            questionDiv.appendChild(checkBtn);
            
            // Add try again button
            const tryAgainBtn = document.createElement('button');
            tryAgainBtn.className = 'try-again';
            tryAgainBtn.setAttribute('data-index', index);
            tryAgainBtn.style.display = 'none';
            tryAgainBtn.textContent = 'Try Again';
            questionDiv.appendChild(tryAgainBtn);
            
            container.appendChild(questionDiv);
        });
        
        // Setup event handlers for the new buttons
        setupMultipleChoiceQuestions();
    }

    async function fetchAndUpdateRevisionQuestions() {
        try {
            const response = await fetch('/api/generate_revision', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    course_id: courseId
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                updateRevisionQuestions(data.revision_questions);
            }
        } catch (error) {
            console.error('Error fetching revision questions:', error);
        }
    }

    // Set up multiple choice questions
    function setupMultipleChoiceQuestions() {
        // After page load, find all radio buttons and ensure proper grouping
        const questionDivs = document.querySelectorAll('.revision-question');
        
        // For each question, ensure all its radio buttons have a unique name per question
        questionDivs.forEach(questionDiv => {
            const questionId = questionDiv.id.split('-')[1]; // Extract ID from "question-X"
            const radioButtons = questionDiv.querySelectorAll('input[type="radio"]');
            
            // Set the correct name attribute for all radio buttons in this question
            radioButtons.forEach(radio => {
                radio.setAttribute('name', `question${questionId}`);
            });
        });
        
        // Set up check answer buttons
        document.querySelectorAll('.check-answer').forEach(button => {
            button.addEventListener('click', function() {
                const questionIndex = this.getAttribute('data-index');
                const questionDiv = document.getElementById(`question-${questionIndex}`);
                
                if (!questionDiv) {
                    console.error(`Question container not found: question-${questionIndex}`);
                    return;
                }
                
                // Get the selected radio button
                const selectedRadio = questionDiv.querySelector(`input[name="question${questionIndex}"]:checked`);
                
                if (!selectedRadio) {
                    alert('Please select an answer first.');
                    return;
                }
                
                // Check if correct
                const isCorrect = selectedRadio.getAttribute('data-correct') === 'true';
                
                if (isCorrect) {
                    // Show correct answer, hide incorrect message
                    questionDiv.querySelector('.answer').style.display = 'block';
                    questionDiv.querySelector('.incorrect-answer').style.display = 'none';
                    
                    // Add correct class
                    questionDiv.classList.add('correct');
                    
                    // Hide buttons
                    this.style.display = 'none';
                    const tryAgainButton = questionDiv.querySelector('.try-again');
                    if (tryAgainButton) {
                        tryAgainButton.style.display = 'none';
                    }
                } else {
                    // Show incorrect message
                    questionDiv.querySelector('.incorrect-answer').style.display = 'block';
                    
                    // Hide check button, show try again
                    this.style.display = 'none';
                    const tryAgainButton = questionDiv.querySelector('.try-again');
                    if (tryAgainButton) {
                        tryAgainButton.style.display = 'block';
                    }
                }
                
                // Record answer
                try {
                    fetch('/api/record_answer', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            course_id: courseId,
                            question_index: questionIndex,
                            selected_answer: selectedRadio.value,
                            is_correct: isCorrect
                        })
                    });
                } catch (error) {
                    console.error('Error recording answer:', error);
                }
            });
        });
        
        // Set up try again buttons
        document.querySelectorAll('.try-again').forEach(button => {
            button.addEventListener('click', function() {
                const questionIndex = this.getAttribute('data-index');
                const questionDiv = document.getElementById(`question-${questionIndex}`);
                
                if (!questionDiv) {
                    console.error(`Question container not found: question-${questionIndex}`);
                    return;
                }
                
                // Clear all radio buttons for this question
                const radioButtons = questionDiv.querySelectorAll(`input[name="question${questionIndex}"]`);
                radioButtons.forEach(radio => {
                    radio.checked = false;
                });
                
                // Hide incorrect message
                questionDiv.querySelector('.incorrect-answer').style.display = 'none';
                
                // Show check button, hide try again
                this.style.display = 'none';
                const checkButton = questionDiv.querySelector('.check-answer');
                if (checkButton) {
                    checkButton.style.display = 'block';
                }
            });
        });
    }
    
    // Call setup function for multiple choice questions
    setupMultipleChoiceQuestions();
    
    // Add loading animation styles
    const loadingStyles = document.createElement('style');
    loadingStyles.textContent = `
    .loading-message {
        padding: 12px 18px;
        min-height: 24px;
    }
    
    .loading-dots {
        display: inline-block;
        color: #666;
        font-weight: 500;
    }
    
    .loading-dots span {
        display: inline-block;
        animation: loadingDots 1.4s infinite ease-in-out both;
    }
    
    .loading-dots span:nth-child(1) {
        animation-delay: 0s;
    }
    
    .loading-dots span:nth-child(2) {
        animation-delay: 0.2s;
    }
    
    .loading-dots span:nth-child(3) {
        animation-delay: 0.4s;
    }
    
    @keyframes loadingDots {
        0%, 80%, 100% { opacity: 0; }
        40% { opacity: 1; }
    }
    
    .error {
        padding: 10px 12px;
        background-color: #ffebee;
        color: #c62828;
        border-radius: 4px;
        margin: 0.5em 0;
        border-left: 3px solid #e53935;
    }
    `;
    document.head.appendChild(loadingStyles);
    
    // Focus input field
    userInput.focus();
});