"""
AI Assistant module for StudyOS
Simplified implementation with flat database structure
"""
import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from config import config
from utils import logger
# Import will be done in __init__ to handle errors gracefully
# Remove global Firebase client - will be initialized when needed

class AIAssistant:
    """Simplified AI Assistant class with flat database structure"""

    def __init__(self):
        """Initialize AI Assistant with Gemini API"""
        self.ai_available = False
        self.model = None
        self.genai = None
        self.error_message = None
        self.model_name = None
        
        try:
            # Check if API key is set
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key or not api_key.strip():
                self.error_message = "GEMINI_API_KEY environment variable is not set or is empty"
                logger.error(self.error_message)
                print(f"AI INIT ERROR: {self.error_message}")
                return
                
            # Set the API key in the environment
            os.environ['GOOGLE_API_KEY'] = api_key.strip()
            
            # Import the Google Generative AI package
            try:
                import google.generativeai as genai
                self.genai = genai
                logger.info("Successfully imported google.generativeai")
            except ImportError as e:
                self.error_message = "Required package not installed. Please run: pip install google-genai"
                logger.error(f"{self.error_message}: {str(e)}")
                print(f"AI IMPORT ERROR: {self.error_message}")
                return
            
            # Configure the API
            try:
                genai.configure(api_key=api_key.strip())
                logger.info("Successfully configured Gemini API")
            except Exception as e:
                self.error_message = f"Failed to configure Gemini API: {str(e)}"
                logger.error(self.error_message, exc_info=True)
                print(f"AI CONFIG ERROR: {self.error_message}")
                return

            try:
                # Try to list models, but don't fail if it's not available
                try:
                    available_models = genai.list_models()
                    logger.info("Successfully connected to Gemini API")
                    logger.info(f"Available models: {[m.name for m in available_models]}")
                except AttributeError:
                    logger.warning("list_models() not available in this version of google-genai")
                    # Use known working models
                    model_names = [
                        'models/gemini-2.5-flash',
                        'models/gemini-2.5-pro',
                        'models/gemini-2.0-flash',
                        'models/gemini-flash-latest'
                    ]
                    logger.info(f"Using default models: {model_names}")
                
                # Set the API key in the environment for future use
                os.environ['GOOGLE_API_KEY'] = api_key.strip()
                logger.info("Successfully configured Gemini API")
            except Exception as e:
                self.error_message = f"Failed to configure Gemini API: {str(e)}"
                logger.error(self.error_message, exc_info=True)
                print(f"AI CONFIG ERROR: {self.error_message}")
                return  # Properly return None from __init__
            
            # Define the models to try in order of preference
            model_names = [
                'models/gemini-2.5-flash',  # Latest and most capable model
                'models/gemini-2.5-pro',    # Alternative model
                'models/gemini-2.0-flash',  # Fallback model
                'models/gemini-flash-latest'  # Always points to latest flash model
            ]
            
            # Log the models we'll try to use
            logger.info(f"Will try to initialize with models: {model_names}")
            
            # Check if we have any models to try
            if not model_names:
                self.error_message = "No models available to initialize"
                logger.error(self.error_message)
                return
            
            for model_name in model_names:
                try:
                    logger.info(f"Attempting to initialize model: {model_name}")
                    
                    try:
                        # Initialize the model with default settings first
                        logger.info(f"Initializing model: {model_name}")
                        
                        # Try with minimal configuration first
                        self.model = genai.GenerativeModel(model_name=model_name)
                        
                        # Test the connection with a simple prompt
                        logger.info("Testing model with a simple prompt...")
                        chat = self.model.start_chat(history=[])
                        response = chat.send_message(
                            "Hello, please respond with 'Ready' if you can hear me.",
                            stream=False
                        )
                        
                        # If we get here, the model is working
                        logger.info(f"Successfully initialized model: {model_name}")
                        
                    except Exception as model_error:
                        error_msg = f"Failed to initialize model {model_name}: {str(model_error)}"
                        logger.error(error_msg)
                        continue  # Try the next model
                    
                    if response and hasattr(response, 'text'):
                        logger.info(f"Successfully initialized with model: {model_name}")
                        logger.info(f"Model response: {response.text}")
                        print(f"AI SUCCESS: Initialized with model {model_name}")
                        self.ai_available = True
                        self.model_name = model_name
                        self.chat = chat  # Store chat session for future use
                        return  # Properly return None from __init__
                    
                    logger.warning(f"Model {model_name} responded with empty content")
                    self.error_message = f"Model {model_name} returned empty response"
                        
                except Exception as model_error:
                    import traceback
                    error_details = str(model_error)
                    error_trace = traceback.format_exc()
                    logger.error(f"Failed to initialize model {model_name}: {error_details}")
                    logger.error(f"Error trace: {error_trace}")
                    print(f"MODEL ERROR ({model_name}): {error_details[:200]}")
                    print(f"Full error available in logs")
                    continue
            
            # If we get here, no models worked
            self.error_message = (
                "Failed to initialize any available Gemini model. "
                "Please check your API key and internet connection. "
                "Make sure your API key has access to the Gemini API."
            )
            logger.error(self.error_message)
            print(f"AI MODEL ERROR: {self.error_message}")
            # No return needed here - just let the function end naturally
            
        except Exception as e:
            self.error_message = f"Unexpected error during initialization: {str(e)}"
            logger.error(self.error_message)
            print(f"AI INIT ERROR: {self.error_message}")
            import traceback
            traceback.print_exc()
            
        self.ai_available = False

    def _get_db(self):
        """Get Firebase Firestore client - import from already initialized firebase_config"""
        try:
            # Import the already initialized database client from firebase_config
            from firebase_config import db
            return db
        except Exception as e:
            logger.error(f"Failed to get Firebase client from firebase_config: {str(e)}")
            # Fallback: try to get it directly (should work if Firebase is initialized)
            try:
                from firebase_admin import firestore
                return firestore.client()
            except Exception as fallback_error:
                logger.error(f"Fallback Firebase client also failed: {str(fallback_error)}")
                raise

    def get_academic_context(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format user's academic context for AI prompts"""
        context = {
            "purpose": user_data.get('purpose'),
            "subjects": [],
            "grade": None,
            "board": None,
            "academic_progress": {},
            "exam_history": [],
            "goals": user_data.get('goals', []),
            "time_studied": user_data.get('time_studied', 0)
        }

        # Extract academic details based on purpose
        if user_data.get('purpose') == 'high_school' and user_data.get('highschool'):
            hs = user_data['highschool']
            context["grade"] = hs.get('grade')
            context["board"] = hs.get('board')
            # Get subjects from syllabus
            from templates.academic_data import get_syllabus
            syllabus = get_syllabus('highschool', hs.get('board'), hs.get('grade'))
            context["subjects"] = list(syllabus.keys()) if syllabus else []

        elif user_data.get('purpose') == 'exam_prep' and user_data.get('exam'):
            context["exam_type"] = user_data['exam'].get('type')
            # Get subjects from syllabus
            from templates.academic_data import get_syllabus
            syllabus = get_syllabus('exam', user_data['exam'].get('type'))
            context["subjects"] = list(syllabus.keys()) if syllabus else []

        elif user_data.get('purpose') == 'after_tenth' and user_data.get('after_tenth'):
            at = user_data['after_tenth']
            context["grade"] = at.get('grade')
            context["stream"] = at.get('stream')
            context["subjects"] = at.get('subjects', [])
            # Get subjects from syllabus
            from templates.academic_data import get_syllabus
            syllabus = get_syllabus('after_tenth', 'CBSE', at.get('grade'), at.get('subjects', []))
            context["subjects"] = list(syllabus.keys()) if syllabus else at.get('subjects', [])

        # Get progress data
        from app import calculate_academic_progress
        progress = calculate_academic_progress(user_data)
        context["academic_progress"] = {
            "overall": progress.get('overall', 0),
            "by_subject": progress.get('by_subject', {}),
            "momentum": progress.get('momentum', 0),
            "consistency": progress.get('consistency', 0),
            "readiness": progress.get('readiness', 0)
        }

        # Get recent exam results
        exam_results = user_data.get('exam_results', [])
        context["exam_history"] = exam_results[-5:] if exam_results else []  # Last 5 exams

        return context

    def save_message(self, uid: str, chatbot_type: str, role: str, content: str):
        """Save a chat message to the active thread for this chatbot type"""
        try:
            # Validate inputs
            if chatbot_type not in ['planning', 'doubt']:
                raise ValueError("Invalid chatbot type")
            if role not in ['user', 'assistant']:
                raise ValueError("Invalid role")

            # Get user data for timezone
            from app import get_user_data
            from utils.timezone import get_current_time_for_user
            user_data = get_user_data(uid)
            if not user_data:
                raise ValueError("User data not found")

            # Get active thread for this chatbot type
            active_thread_id = self.get_active_thread_id(uid, chatbot_type)
            if not active_thread_id:
                # Create default thread if none exists
                active_thread_id = self.create_default_thread(uid, chatbot_type)
                logger.info(f"Created default thread {active_thread_id} for {chatbot_type}")

            # Save message to thread document
            message_data = {
                'role': role,
                'content': content,
                'timestamp': get_current_time_for_user(user_data)  # Use user's timezone
            }

            # Use flat structure: users/{uid}/ai_conversations/{chatbot_type}_{thread_id}
            thread_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_{active_thread_id}')
            messages_ref = thread_ref.collection('messages')
            messages_ref.add(message_data)

            # Update thread metadata
            from firebase_admin import firestore
            thread_ref.update({
                'last_message_at': get_current_time_for_user(user_data),  # Use user's timezone
                'message_count': firestore.Increment(1)
            })

            logger.info(f"Message saved successfully for {chatbot_type} thread {active_thread_id}")
            return active_thread_id

        except Exception as e:
            logger.error(f"Error saving message: {str(e)}", exc_info=True)
            raise

    def get_active_thread_id(self, uid: str, chatbot_type: str) -> str:
        """Get the active thread ID for a chatbot type"""
        try:
            # Check for active thread document
            active_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_active_thread')
            active_doc = active_ref.get()

            if active_doc.exists:
                thread_id = active_doc.to_dict().get('thread_id')
                if thread_id:
                    # Verify thread still exists
                    thread_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_{thread_id}')
                    if thread_ref.get().exists:
                        return thread_id

            # No valid active thread found
            return None

        except Exception as e:
            logger.error(f"Error getting active thread: {str(e)}")
            return None

    def create_default_thread(self, uid: str, chatbot_type: str) -> str:
        """Create a default thread for a chatbot type"""
        try:
            # Get user data for timezone
            from app import get_user_data
            from utils.timezone import get_current_time_for_user
            user_data = get_user_data(uid)
            if not user_data:
                raise ValueError("User data not found")

            import uuid
            thread_id = str(uuid.uuid4())

            thread_data = {
                'thread_id': thread_id,
                'title': f"{chatbot_type.title()} Assistant",
                'chatbot_type': chatbot_type,
                'created_at': get_current_time_for_user(user_data),  # Use user's timezone
                'last_message_at': get_current_time_for_user(user_data),  # Use user's timezone
                'message_count': 0
            }

            # Create thread document
            thread_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_{thread_id}')
            thread_ref.set(thread_data)

            # Set as active thread
            active_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_active_thread')
            active_ref.set({'thread_id': thread_id})

            logger.info(f"Created default thread {thread_id} for {chatbot_type}")
            return thread_id

        except Exception as e:
            logger.error(f"Error creating default thread: {str(e)}")
            raise

    def get_conversation_history(self, uid: str, chatbot_type: str, thread_id: str = None, limit: int = 50):
        """Get conversation history for a chatbot type and optional specific thread"""
        try:
            # Get user data for timezone formatting
            from app import get_user_data
            from utils.timezone import format_timestamp_for_user
            user_data = get_user_data(uid)
            if not user_data:
                logger.warning(f"User data not found for {uid}")
                return []

            # Use provided thread_id or get active thread
            target_thread_id = thread_id or self.get_active_thread_id(uid, chatbot_type)
            if not target_thread_id:
                logger.warning(f"No thread found for {chatbot_type}")
                return []

            # Get messages from the target thread
            thread_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_{target_thread_id}')
            messages_ref = thread_ref.collection('messages')

            # Get messages ordered by timestamp (newest first)
            from firebase_admin import firestore
            query = messages_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit)
            messages = []

            for doc in query.stream():
                msg_data = doc.to_dict()
                messages.append({
                    'role': msg_data['role'],
                    'content': msg_data['content'],
                    'timestamp': msg_data['timestamp']  # Keep original UTC timestamp
                })

            # Return in chronological order (oldest first)
            messages.reverse()
            logger.info(f"Retrieved {len(messages)} messages for {chatbot_type} thread {target_thread_id}")
            return messages

        except Exception as e:
            logger.error(f"Error loading conversation history: {str(e)}", exc_info=True)
            return []

    def get_user_threads(self, uid: str, chatbot_type: str):
        """Get all threads for a user and chatbot type"""
        try:
            # Get user data for timezone formatting
            from app import get_user_data
            from utils.timezone import format_timestamp_for_user
            user_data = get_user_data(uid)
            if not user_data:
                logger.warning(f"User data not found for {uid}")
                return []

            conversations_ref = self._get_db().collection('users').document(uid).collection('ai_conversations')

            threads = []
            # Find all thread documents for this chatbot type
            for doc in conversations_ref.stream():
                doc_id = doc.id
                # Check if this is a thread document for our chatbot type
                if doc_id.startswith(f'{chatbot_type}_') and not doc_id.endswith('_active_thread') and not doc_id.endswith('_threads_list'):
                    thread_data = doc.to_dict()
                    thread_data['thread_id'] = thread_data.get('thread_id', doc_id.split('_', 1)[1])
                    threads.append(thread_data)

            # Sort by last message (most recent first)
            threads.sort(key=lambda x: x.get('last_message_at', ''), reverse=True)
            logger.info(f"Found {len(threads)} threads for {chatbot_type}")
            return threads

        except Exception as e:
            logger.error(f"Error getting user threads: {str(e)}", exc_info=True)
            return []

    def create_new_thread(self, uid: str, chatbot_type: str, title: str = None) -> str:
        """Create a new conversation thread"""
        try:
            # Get user data for timezone
            from app import get_user_data
            from utils.timezone import get_current_time_for_user
            user_data = get_user_data(uid)
            if not user_data:
                raise ValueError("User data not found")

            import uuid
            thread_id = str(uuid.uuid4())

            if not title:
                title = f"New {chatbot_type.title()} Conversation"

            thread_data = {
                'thread_id': thread_id,
                'title': title,
                'chatbot_type': chatbot_type,
                'created_at': get_current_time_for_user(user_data),  # Use user's timezone
                'last_message_at': get_current_time_for_user(user_data),  # Use user's timezone
                'message_count': 0
            }

            # Create thread document
            thread_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_{thread_id}')
            thread_ref.set(thread_data)

            # Set as active thread (this automatically switches to the new thread)
            active_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_active_thread')
            active_ref.set({'thread_id': thread_id})

            logger.info(f"Created new thread {thread_id} for {chatbot_type}")
            return thread_id

        except Exception as e:
            logger.error(f"Error creating new thread: {str(e)}", exc_info=True)
            raise

    def switch_thread(self, uid: str, chatbot_type: str, thread_id: str) -> bool:
        """Switch active thread for a chatbot type"""
        try:
            # Verify thread exists
            thread_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_{thread_id}')
            if not thread_ref.get().exists:
                logger.warning(f"Thread {thread_id} does not exist for {chatbot_type}")
                return False

            # Update active thread
            active_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_active_thread')
            active_ref.set({'thread_id': thread_id})

            logger.info(f"Switched to thread {thread_id} for {chatbot_type}")
            return True

        except Exception as e:
            logger.error(f"Error switching thread: {str(e)}", exc_info=True)
            return False

    def delete_thread(self, uid: str, chatbot_type: str, thread_id: str) -> bool:
        """Delete a conversation thread"""
        try:
            # Don't allow deletion of active thread
            active_thread_id = self.get_active_thread_id(uid, chatbot_type)
            if active_thread_id == thread_id:
                logger.warning(f"Cannot delete active thread {thread_id}")
                return False

            # Delete thread document and all its messages
            thread_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_{thread_id}')

            # Delete all messages first
            messages_ref = thread_ref.collection('messages')
            from firebase_admin import firestore
            batch = self._get_db().batch()
            for msg_doc in messages_ref.stream():
                batch.delete(msg_doc.reference)

            # Delete thread document
            batch.delete(thread_ref)
            batch.commit()

            logger.info(f"Deleted thread {thread_id} for {chatbot_type}")
            return True

        except Exception as e:
            logger.error(f"Error deleting thread: {str(e)}", exc_info=True)

    def rename_thread(self, uid: str, chatbot_type: str, thread_id: str, new_title: str) -> bool:
        """Rename a conversation thread"""
        try:
            # Validate inputs
            if chatbot_type not in ['planning', 'doubt']:
                raise ValueError("Invalid chatbot type")
            if not new_title or not new_title.strip():
                raise ValueError("Title cannot be empty")

            # Verify thread exists
            thread_ref = self._get_db().collection('users').document(uid).collection('ai_conversations').document(f'{chatbot_type}_{thread_id}')
            if not thread_ref.get().exists:
                logger.warning(f"Thread {thread_id} does not exist for {chatbot_type}")
                return False

            # Update thread title
            thread_ref.update({'title': new_title.strip()})

            logger.info(f"Renamed thread {thread_id} for {chatbot_type} to '{new_title.strip()}'")
            return True

        except Exception as e:
            logger.error(f"Error renaming thread: {str(e)}", exc_info=True)
            return False



    def format_sclera_thread_as_text(self, thread_data: dict, messages: list) -> str:
        """Format sclera thread as plain text"""
        lines = []
        lines.append(f"SCLERA AI Conversation: {thread_data.get('title', 'Untitled')}")
        lines.append(f"Mode: {thread_data.get('mode', 'Unknown').replace('_', ' ').title()}")
        lines.append(f"Created: {thread_data.get('created_at', 'Unknown')}")
        lines.append("-" * 50)

        for msg in messages:
            timestamp = msg['timestamp'][:19] if msg.get('timestamp') else 'Unknown'
            role = "AI" if msg['role'] == 'assistant' else "You"
            lines.append(f"[{timestamp}] {role}: {msg['content']}")

        lines.append("-" * 50)
        return "\n".join(lines)

    def format_sclera_thread_as_markdown(self, thread_data: dict, messages: list) -> str:
        """Format sclera thread as plain text (removed markdown formatting)"""
        lines = []
        lines.append(f"{thread_data.get('title', 'Untitled')}")
        lines.append(f"Mode: {thread_data.get('mode', 'Unknown').replace('_', ' ').title()}")
        lines.append(f"Created: {thread_data.get('created_at', 'Unknown')}")
        lines.append("-" * 50)

        for msg in messages:
            timestamp = msg['timestamp'][:19] if msg.get('timestamp') else 'Unknown'
            if msg['role'] == 'assistant':
                lines.append(f"SCLERA AI ({timestamp}):")
            else:
                lines.append(f"You ({timestamp}):")
            lines.append(f"{msg['content']}")
            lines.append("")

        return "\n".join(lines)

    def generate_planning_response(self, message: str, context: Dict[str, Any]) -> str:
        """Generate a response for academic planning queries"""
        try:
            if not self.ai_available or not hasattr(self, 'model') or not self.model:
                error_msg = "AI Assistant is not properly initialized. "
                if hasattr(self, 'error_message'):
                    error_msg += f"Error: {self.error_message}"
                logger.error(error_msg)
                return "I'm sorry, but the AI Assistant is currently unavailable. Please try again later."
            
            # Create a prompt with context
            prompt = self._build_planning_prompt(message, context)
            
            # Generate response
            response = self.model.generate_content(prompt)
            
            # Process and return the response
            if hasattr(response, 'text') and response.text.strip():
                return response.text.strip()
            else:
                logger.warning("Received empty response from model")
                return "I didn't receive a valid response. Could you please rephrase your question?"
                
        except Exception as e:
            error_msg = f"Error in generate_planning_response: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (
                "I encountered an unexpected error while processing your request. "
                "The issue has been logged and will be investigated. "
                "Please try again later or contact support if the problem persists."
            )
            
    def generate_doubt_response(self, message: str, context: Dict[str, Any]) -> str:
        """Generate a response for doubt resolution"""
        try:
            if not self.ai_available or not hasattr(self, 'model') or not self.model:
                error_msg = "AI Assistant is not properly initialized. "
                if hasattr(self, 'error_message'):
                    error_msg += f"Error: {self.error_message}"
                logger.error(error_msg)
                return "I'm sorry, but the AI Assistant is currently unavailable. Please try again later."
            
            # Create a prompt with context
            prompt = self._build_doubt_prompt(message, context)
            
            # Generate response
            response = self.model.generate_content(prompt)
            
            # Process and return the response
            if hasattr(response, 'text') and response.text.strip():
                return response.text.strip()
            else:
                logger.warning("Received empty response from model")
                return "I didn't receive a valid response. Could you please rephrase your question?"
                
        except Exception as e:
            error_msg = f"Error in generate_doubt_response: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (
                "I encountered an unexpected error while processing your doubt. "
                "The issue has been logged and will be investigated. "
                "Please try again later or contact support if the problem persists."
            )

    def _generate_smart_planning_fallback(self, message: str, context: Dict[str, Any]) -> str:
        """Generate an intelligent planning response without AI"""
        user_name = context.get('user_name', 'Student')
        purpose = context.get('purpose', 'academic planning')
        grade = context.get('grade', 'your level')
        subjects = context.get('subjects', ['various subjects'])

        return f"""Here's your personalized study plan, {user_name}!

**📊 Your Academic Profile:**
- **Level:** {purpose.title()} ({grade})
- **Focus Areas:** {', '.join(subjects[:3])}{' and more' if len(subjects) > 3 else ''}

**📅 Weekly Study Schedule:**
Based on your request "{message[:100]}{'...' if len(message) > 100 else ''}", here's a structured approach:

**Monday-Wednesday (Core Learning):**
• **Morning (9-11 AM):** Focus on primary subjects - dedicate 2 hours to core concepts
• **Afternoon (2-4 PM):** Practice problems and exercises for reinforcement
• **Evening (7-8 PM):** Quick review of day's learning (30 minutes per subject)

**Thursday (Assessment Day):**
• **Morning:** Practice tests and quizzes
• **Afternoon:** Analyze performance and identify weak areas
• **Evening:** Plan next week's focus areas

**Friday-Saturday (Deep Dive):**
• **Morning:** Tackle challenging topics with extended study sessions
• **Afternoon:** Group study or peer discussions
• **Evening:** Light review and relaxation

**Sunday (Review & Planning):**
• **Morning:** Weekly assessment and progress tracking
• **Afternoon:** Plan next week and set specific goals
• **Evening:** Preview upcoming topics

**🎯 Success Strategies:**
1. **Active Recall:** Test yourself regularly on key concepts
2. **Spaced Repetition:** Review material at increasing intervals
3. **Pomodoro Technique:** 25-minute focused sessions with 5-minute breaks
4. **Goal Setting:** Set SMART goals for each study session
5. **Progress Tracking:** Maintain a study journal to monitor improvement

**📚 Resources to Consider:**
• Textbook exercises and chapter summaries
• Online practice platforms for your subjects
• Study group discussions for peer learning
• Educational YouTube channels for visual explanations

**💡 Pro Tip:** Start with your most challenging subject when energy levels are highest, typically morning hours. Adjust this schedule based on your natural rhythm and commitments.

Would you like me to create a more detailed plan for a specific subject or time period?"""

    def _generate_smart_doubt_fallback(self, message: str, context: Dict[str, Any]) -> str:
        """Generate an intelligent doubt resolution response without AI"""
        user_name = context.get('user_name', 'Student')
        purpose = context.get('purpose', 'academic')
        grade = context.get('grade', 'your level')
        subjects = context.get('subjects', [])

        # Extract key terms from the question for better responses
        question_lower = message.lower()
        math_keywords = ['math', 'algebra', 'geometry', 'calculus', 'equation', 'formula']
        science_keywords = ['physics', 'chemistry', 'biology', 'science']
        language_keywords = ['english', 'grammar', 'literature', 'writing']

        response_type = 'general'
        if any(keyword in question_lower for keyword in math_keywords):
            response_type = 'math'
        elif any(keyword in question_lower for keyword in science_keywords):
            response_type = 'science'
        elif any(keyword in question_lower for keyword in language_keywords):
            response_type = 'language'

        base_response = f"""I understand you're asking about: "{message[:100]}{'...' if len(message) > 100 else ''}"

Let me help you break this down step by step, {user_name}!

**📚 Context & Level:**
- **Academic Level:** {purpose.title()} ({grade})
- **Relevant Subjects:** {', '.join(subjects[:3])}{' and others' if len(subjects) > 3 else 'General academic support'}

"""

        if response_type == 'math':
            base_response += """
**🔢 Mathematical Approach:**
1. **Identify the Problem Type:** Is this algebra, geometry, calculus, or word problems?
2. **Key Concepts:** Break down the fundamental principles involved
3. **Step-by-Step Solution:** Work through each part systematically
4. **Common Mistakes:** Watch for these frequent errors
5. **Practice Similar Problems:** Apply the same method to related questions

**📐 Helpful Tips:**
• Draw diagrams for geometry problems
• Substitute values to check your work
• Look for patterns in similar problems
• Use estimation to verify answers make sense

"""
        elif response_type == 'science':
            base_response += """
**🧪 Scientific Method:**
1. **Observe & Question:** What are you observing?
2. **Research Background:** Key concepts and definitions
3. **Form Hypothesis:** What do you think is happening?
4. **Test & Experiment:** Design a systematic approach
5. **Analyze Results:** What do the findings tell you?
6. **Draw Conclusions:** Explain what you learned

**🔬 Lab & Study Tips:**
• Focus on understanding concepts, not just memorizing
• Practice drawing diagrams and flowcharts
• Relate concepts to real-world applications
• Use mnemonic devices for complex terminology

"""
        else:
            base_response += """
**📖 Study Approach:**
1. **Read Carefully:** Identify the main question and key terms
2. **Break it Down:** Divide complex ideas into smaller parts
3. **Connect Concepts:** How does this relate to what you already know?
4. **Examples & Applications:** Look for real-world connections
5. **Practice & Review:** Apply the concepts through practice

**✨ Learning Strategies:**
• Highlight key terms and definitions
• Summarize paragraphs in your own words
• Create mind maps for complex topics
• Teach the concept to someone else
• Use flashcards for important facts

"""

        base_response += f"""
**📚 Recommended Resources:**
• Your textbook chapters on related topics
• Online tutorials and video explanations
• Practice worksheets and sample problems
• Study group discussions for peer learning
• Educational apps and interactive platforms

**💡 Need More Help?**
• Try rephrasing your question if something isn't clear
• Share specific examples of what you're struggling with
• Ask about related concepts you want to understand better
• Request practice problems at your level

**🎯 Remember:** Every expert was once a beginner. Learning happens through questions and persistence!

Would you like me to explain a specific part in more detail or help with a similar concept?"""

        return base_response

    def _build_planning_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """Build a comprehensive planning prompt for Gemini"""
        prompt_parts = [
            "You are an AI Study Planning Assistant. Help students create effective study plans and academic strategies.",
            "",
            "STUDENT CONTEXT:",
            f"- Purpose: {context.get('purpose', 'Not specified')}",
            f"- Current Grade/Level: {context.get('grade', 'Not specified')}",
            f"- Subjects: {', '.join(context.get('subjects', []))}",
            f"- Academic Progress: Overall {context.get('academic_progress', {}).get('overall', 0)}% complete",
            f"- Recent Exam Performance: {len(context.get('exam_history', []))} exams on record",
            f"- Study Goals: {len(context.get('goals', []))} active goals",
            f"- Daily Study Time: {context.get('time_studied', 0)} minutes",
            "",
            "INSTRUCTION:",
            "Provide personalized, actionable study planning advice. Focus on:",
            "- Creating realistic study schedules",
            "- Subject prioritization based on progress",
            "- Revision strategies and practice techniques",
            "- Time management and productivity tips",
            "- Goal setting and tracking progress",
            "- Exam preparation strategies",
            "",
            "Keep responses practical, encouraging, and tailored to the student's current situation.",
            "Use the student's academic data to make recommendations more relevant.",
            "IMPORTANT: Do NOT use any markdown formatting. Avoid asterisks (**), hashes (#), emojis, or any special characters for formatting. Respond in plain text only.",
            "",
            f"STUDENT MESSAGE: {message}",
            "",
            "RESPONSE:"
        ]

        return "\n".join(prompt_parts)

    def _build_doubt_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """Build a comprehensive doubt-resolution prompt for Gemini"""
        prompt_parts = [
            "You are an AI Academic Doubt Resolver. Help students understand complex academic concepts and answer subject-specific questions.",
            "",
            "STUDENT CONTEXT:",
            f"- Academic Level: {context.get('purpose', 'Not specified').replace('_', ' ').title()}",
            f"- Grade/Level: {context.get('grade', 'Not specified')}",
            f"- Subjects: {', '.join(context.get('subjects', []))}",
            f"- Board/Curriculum: {context.get('board', 'Not specified')}",
            "",
            "INSTRUCTION:",
            "Provide clear, step-by-step explanations for academic questions. Focus on:",
            "- Breaking down complex concepts into simpler parts",
            "- Using examples and analogies where helpful",
            "- Providing formulas, definitions, and key principles",
            "- Explaining problem-solving approaches",
            "- Connecting concepts to real-world applications",
            "- Suggesting additional resources when appropriate",
            "",
            "Ensure explanations are accurate, age-appropriate for the student's level, and encourage critical thinking.",
            "If the question is unclear, ask for clarification rather than making assumptions.",
            "IMPORTANT: Do NOT use any markdown formatting. Avoid asterisks (**), hashes (#), emojis, or any special characters for formatting. Respond in plain text only.",
            "",
            f"STUDENT QUESTION: {message}",
            "",
            "EXPLANATION:"
        ]

        return "\n".join(prompt_parts)

# Global AI Assistant instance
_ai_assistant = None

def get_ai_assistant() -> AIAssistant:
    """Get or create AI Assistant instance"""
    global _ai_assistant
    if _ai_assistant is None:
        _ai_assistant = AIAssistant()
    return _ai_assistant
