import os
import json
import wx
import wx.lib.scrolledpanel as scrolled
import wx.lib.newevent
import threading
import shutil
import requests
import sys
import traceback
import wx

# Override IsDisplayAvailable to always return True
wx.PyApp.IsDisplayAvailable = lambda _: True

# A további kód változatlan marad
# Custom event for updating UI from threads
ResponseEvent, EVT_RESPONSE = wx.lib.newevent.NewEvent()

# Add detailed startup logging
def log_message(message, is_error=False):
    print(message)
    log_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    log_file = os.path.join(log_dir, "app_log.txt")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")
    if is_error:
        error_log = os.path.join(log_dir, "error_log.txt")
        with open(error_log, 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")

# Ensure application paths are set up correctly
def get_app_path():
    if getattr(sys, 'frozen', False):
        # Running as a compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as a script
        return os.path.dirname(os.path.abspath(__file__))

APP_PATH = get_app_path()
log_message(f"Application path determined as: {APP_PATH}")

# Ensure the Documents directory exists
documents_dir = os.path.join(APP_PATH, "Documents")
log_message(f"Ensuring Documents directory exists at: {documents_dir}")
os.makedirs(documents_dir, exist_ok=True)

# Try to load dotenv if available
try:
    import dotenv
    # Look for .env in the application directory
    env_path = os.path.join(APP_PATH, ".env")
    log_message(f"Checking for .env file at: {env_path}")
    if os.path.exists(env_path):
        dotenv.load_dotenv(env_path)
        log_message(".env file loaded")
    else:
        log_message("No .env file found")
except ImportError:
    log_message("dotenv module not available, skipping environment loading", True)

# Wrap document parsing imports in try-except blocks to handle missing dependencies
try:
    from docx import Document
    HAS_DOCX = True
    log_message("Successfully imported python-docx")
except ImportError:
    log_message("Warning: python-docx not installed. DOCX support will be limited.", True)
    HAS_DOCX = False

try:
    from pypdf import PdfReader
    HAS_PDF = True
    log_message("Successfully imported pypdf")
except ImportError:
    log_message("Warning: pypdf not installed. PDF support will be limited.", True)
    HAS_PDF = False

# Load configuration
def load_config():
    try:
        config_path = os.path.join(APP_PATH, "config.json")
        log_message(f"Loading config from: {config_path}")
        
        if os.path.exists(config_path):
            with open(config_path, "r", encoding='utf-8') as f:
                config = json.load(f)
                log_message("Config loaded successfully")
                return config
        else:
            log_message(f"Config file not found at {config_path}, creating default", True)
            return create_default_config(config_path)
    except Exception as e:
        log_message(f"Error loading config: {str(e)}", True)
        log_message(traceback.format_exc(), True)
        return create_default_config()

def create_default_config(config_path=None):
    # Create default config if not found
    default_config = {
        "models": {
            "openai": {
                "name": "OpenAI GPT-4",
                "api_key_env": "OPENAI_API_KEY",
                "model_name": "gpt-4o-mini"
            },
            "anthropic": {
                "name": "Anthropic Claude",
                "api_key_env": "ANTHROPIC_API_KEY",
                "model_name": "claude-3-opus-20240229"
            },
            "gemini": {
                "name": "Google Gemini",
                "api_key_env": "GOOGLE_API_KEY",
                "model_name": "gemini-pro"
            }
        },
        "default_model": "openai",
        "system_prompt": "You are a helpful AI research assistant. Your goal is to help researchers write new papers or expand work-in-progress papers based on the provided documents and instructions."
    }
    
    if config_path:
        try:
            with open(config_path, "w", encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            log_message(f"Default config saved to {config_path}")
        except Exception as e:
            log_message(f"Error saving default config: {str(e)}", True)
    
    return default_config

# Document handling functions
def read_pdf(file_path):
    if not HAS_PDF:
        return f"PDF support not available. Please install pypdf package."
    
    try:
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        log_message(f"Error reading PDF {file_path}: {str(e)}", True)
        return f"Error reading PDF: {str(e)}"

def read_docx(file_path):
    if not HAS_DOCX:
        return f"DOCX support not available. Please install python-docx package."
    
    try:
        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        log_message(f"Error reading DOCX {file_path}: {str(e)}", True)
        return f"Error reading DOCX: {str(e)}"

def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            return file.read()
    except Exception as e:
        log_message(f"Error reading text file {file_path}: {str(e)}", True)
        return f"Error reading text file: {str(e)}"

def read_file(file_path):
    try:
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension == '.pdf':
            return read_pdf(file_path)
        elif file_extension == '.docx':
            return read_docx(file_path)
        elif file_extension in ['.txt', '.md', '.markdown']:
            return read_text_file(file_path)
        else:
            message = f"Unsupported file format: {file_extension}"
            log_message(message, True)
            return message
    except Exception as e:
        log_message(f"Error in read_file for {file_path}: {str(e)}", True)
        return f"Error reading file: {str(e)}"

# Simple API clients for different LLM providers
class OpenAIClient:
    def __init__(self, model_name):
        self.model_name = model_name
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found in environment variables")
    
    def generate_response(self, prompt):
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            }
            
            log_message(f"Sending request to OpenAI API with model {self.model_name}")
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                log_message("Received successful response from OpenAI API")
                return response.json()["choices"][0]["message"]["content"]
            else:
                error_msg = f"OpenAI API Error: {response.status_code} - {response.text}"
                log_message(error_msg, True)
                return error_msg
        except Exception as e:
            error_msg = f"OpenAI API Exception: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            return error_msg

class AnthropicClient:
    def __init__(self, model_name):
        self.model_name = model_name
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key not found in environment variables")
    
    def generate_response(self, prompt):
        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            data = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000
            }
            
            log_message(f"Sending request to Anthropic API with model {self.model_name}")
            
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                log_message("Received successful response from Anthropic API")
                return response.json()["content"][0]["text"]
            else:
                error_msg = f"Anthropic API Error: {response.status_code} - {response.text}"
                log_message(error_msg, True)
                return error_msg
        except Exception as e:
            error_msg = f"Anthropic API Exception: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            return error_msg

class GoogleClient:
    def __init__(self, model_name):
        self.model_name = model_name
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key not found in environment variables")
    
    def generate_response(self, prompt):
        try:
            # This is a simplified version - actual implementation depends on the Gemini API
            log_message(f"Google API integration not fully implemented, using model: {self.model_name}")
            return f"This would be a response from the Google Gemini API using the {self.model_name} model."
        except Exception as e:
            error_msg = f"Google API Exception: {str(e)}"
            log_message(error_msg, True)
            return error_msg

# Main application class
class ResearchAssistantApp(wx.Frame):
    def __init__(self):
        super(ResearchAssistantApp, self).__init__(None, title="Research Assistant", size=(1200, 800))
        
        log_message("Initializing Research Assistant App (wxPython version)")
        
        # Load configuration
        self.config = load_config()
        
        # Initialize data storage
        self.documents = {}  # Store loaded documents
        self.selected_docs = []  # Track selected documents
        self.conversation_history = []  # Store conversation history
        self.doc_checkboxes = []  # Track document checkboxes
        
        # Set up the UI
        self.setup_ui()
        
        # Update document list
        self.update_document_list()
        
        # Set up event handler for response updates
        self.Bind(EVT_RESPONSE, self.on_response_event)
        
        # Create status bar
        self.CreateStatusBar()
        self.SetStatusText("Ready")
        
        log_message("App initialization complete")
        
        # Center the window
        self.Centre()
        self.Show()
    
    def setup_ui(self):
        try:
            log_message("Setting up wxPython UI components")
            
            # Main panel
            panel = wx.Panel(self)
            
            # Main sizer
            main_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # Left panel (Documents) - 1/3 of width
            left_panel = wx.Panel(panel)
            left_sizer = wx.BoxSizer(wx.VERTICAL)
            
            # Document section title
            doc_title = wx.StaticText(left_panel, label="Documents")
            font = doc_title.GetFont()
            font.SetPointSize(14)
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            doc_title.SetFont(font)
            left_sizer.Add(doc_title, 0, wx.ALL, 10)
            
            # Upload button
            upload_btn = wx.Button(left_panel, label="Upload Document")
            upload_btn.Bind(wx.EVT_BUTTON, self.on_upload_document)
            left_sizer.Add(upload_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            
            # Document list in a scrolled panel
            self.doc_panel = scrolled.ScrolledPanel(left_panel, style=wx.SUNKEN_BORDER)
            self.doc_panel.SetAutoLayout(True)
            self.doc_panel.SetupScrolling()
            
            self.doc_sizer = wx.BoxSizer(wx.VERTICAL)
            self.doc_panel.SetSizer(self.doc_sizer)
            left_sizer.Add(self.doc_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            
            left_panel.SetSizer(left_sizer)
            main_sizer.Add(left_panel, 1, wx.EXPAND | wx.ALL, 10)
            
            # Right panel (Chat) - 2/3 of width
            right_panel = wx.Panel(panel)
            right_sizer = wx.BoxSizer(wx.VERTICAL)
            
            # Chat section title
            chat_title = wx.StaticText(right_panel, label="Research Assistant Chat")
            chat_title.SetFont(font)  # Reuse font from above
            right_sizer.Add(chat_title, 0, wx.ALL, 10)
            
            # Model selection
            model_panel = wx.Panel(right_panel)
            model_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            model_label = wx.StaticText(model_panel, label="Model:")
            model_sizer.Add(model_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            
            # Get list of model names for the dropdown
            model_names = [model_info["name"] for model_key, model_info in self.config["models"].items()]
            
            # Set default model
            default_model_key = self.config.get("default_model", "openai")
            default_model_name = ""
            if default_model_key in self.config["models"]:
                default_model_name = self.config["models"][default_model_key]["name"]
            elif model_names:
                default_model_name = model_names[0]
            
            self.model_choice = wx.Choice(model_panel, choices=model_names)
            if default_model_name in model_names:
                self.model_choice.SetStringSelection(default_model_name)
            model_sizer.Add(self.model_choice, 1, wx.EXPAND)
            
            model_panel.SetSizer(model_sizer)
            right_sizer.Add(model_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            
            # Chat display
            self.chat_display = wx.TextCtrl(right_panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.BORDER_SUNKEN)
            right_sizer.Add(self.chat_display, 2, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
            
            # User input label
            input_label = wx.StaticText(right_panel, label="Your message:")
            right_sizer.Add(input_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
            
            # User input area
            self.user_input = wx.TextCtrl(right_panel, style=wx.TE_MULTILINE | wx.BORDER_SUNKEN)
            right_sizer.Add(self.user_input, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
            
            # Send button
            send_btn = wx.Button(right_panel, label="Send")
            send_btn.Bind(wx.EVT_BUTTON, self.on_send_message)
            right_sizer.Add(send_btn, 0, wx.EXPAND | wx.ALL, 10)
            
            right_panel.SetSizer(right_sizer)
            main_sizer.Add(right_panel, 2, wx.EXPAND | wx.ALL, 10)
            
            panel.SetSizer(main_sizer)
            
            log_message("wxPython UI setup complete")
        except Exception as e:
            log_message(f"Error setting up UI: {str(e)}", True)
            log_message(traceback.format_exc(), True)
            wx.MessageBox(f"Error setting up UI: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
    
    def update_document_list(self):
        try:
            log_message("Updating document list")
            
            # Clear existing checkboxes
            self.doc_sizer.Clear(delete_windows=True)
            self.doc_checkboxes = []
            
            # Get documents from the Documents folder
            doc_path = os.path.join(APP_PATH, "Documents")
            doc_files = []
            
            if os.path.exists(doc_path):
                doc_files = [f for f in os.listdir(doc_path) 
                            if os.path.isfile(os.path.join(doc_path, f)) 
                            and f.lower().endswith(('.pdf', '.docx', '.txt', '.md'))]
            
            log_message(f"Found {len(doc_files)} documents")
            
            # Add checkboxes for each document
            for doc in doc_files:
                checkbox = wx.CheckBox(self.doc_panel, label=doc)
                checkbox.Bind(wx.EVT_CHECKBOX, self.on_document_selection)
                self.doc_sizer.Add(checkbox, 0, wx.EXPAND | wx.ALL, 5)
                self.doc_checkboxes.append(checkbox)
            
            # Update panel layout
            self.doc_panel.Layout()
            self.doc_panel.SetupScrolling()
            
            log_message("Document list updated successfully")
        except Exception as e:
            log_message(f"Error updating document list: {str(e)}", True)
            log_message(traceback.format_exc(), True)
            wx.MessageBox(f"Error updating document list: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
    
    def on_upload_document(self, event):
        try:
            with wx.FileDialog(self, "Select Document", wildcard="Document Files (*.pdf;*.docx;*.txt;*.md)|*.pdf;*.docx;*.txt;*.md",
                              style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
                
                if file_dialog.ShowModal() == wx.ID_CANCEL:
                    return
                
                file_path = file_dialog.GetPath()
                log_message(f"Selected file to upload: {file_path}")
                file_name = os.path.basename(file_path)
                
                # Define the destination in the Documents folder
                doc_path = os.path.join(APP_PATH, "Documents")
                destination = os.path.join(doc_path, file_name)
                
                # Check if file already exists
                if not os.path.exists(destination):
                    # Copy file to Documents folder
                    shutil.copy(file_path, destination)
                    log_message(f"Document uploaded successfully: {file_name}")
                    self.SetStatusText(f"Document uploaded: {file_name}")
                else:
                    log_message(f"Document {file_name} already exists in the Documents folder")
                    self.SetStatusText(f"Document {file_name} already exists")
                
                # Update the document list
                self.update_document_list()
        except Exception as e:
            error_msg = f"Error uploading document: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            self.SetStatusText(error_msg)
            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_ERROR)
    
    def on_document_selection(self, event):
        try:
            self.selected_docs = []
            for i, checkbox in enumerate(self.doc_checkboxes):
                if checkbox.IsChecked():
                    self.selected_docs.append(checkbox.GetLabel())
            
            log_message(f"Selected documents updated: {', '.join(self.selected_docs) if self.selected_docs else 'None'}")
            self.SetStatusText(f"Selected documents: {len(self.selected_docs)}")
        except Exception as e:
            log_message(f"Error updating selected documents: {str(e)}", True)
    
    def load_selected_documents(self):
        try:
            log_message(f"Loading content for {len(self.selected_docs)} selected documents")
            doc_path = os.path.join(APP_PATH, "Documents")
            
            # Load document content if not already loaded
            for doc_name in self.selected_docs:
                if doc_name not in self.documents:
                    file_path = os.path.join(doc_path, doc_name)
                    log_message(f"Loading document: {file_path}")
                    self.documents[doc_name] = read_file(file_path)
            
            # Prepare document context for the prompt
            doc_context = ""
            for doc_name in self.selected_docs:
                doc_context += f"\n--- Document: {doc_name} ---\n"
                doc_context += self.documents[doc_name]
                doc_context += "\n"
            
            return doc_context
        except Exception as e:
            error_msg = f"Error loading documents: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            return f"Error loading documents: {str(e)}"
    
    def get_model_key_by_name(self, model_name):
        for key, model_config in self.config["models"].items():
            if model_config.get("name") == model_name:
                return key
        return None
    
    def get_llm_client(self):
        try:
            model_name = self.model_choice.GetStringSelection()
            log_message(f"Getting LLM client for model: {model_name}")
            
            # Find the model key
            model_key = self.get_model_key_by_name(model_name)
            
            if not model_key or model_key not in self.config["models"]:
                error_msg = f"Model {model_name} not found in configuration"
                log_message(error_msg, True)
                self.SetStatusText(error_msg)
                return None
            
            model_config = self.config["models"][model_key]
            model_id = model_config.get("model_name", "")
            
            if model_key == "openai":
                return OpenAIClient(model_id)
            elif model_key == "anthropic":
                return AnthropicClient(model_id)
            elif model_key == "gemini" or model_key == "google":
                return GoogleClient(model_id)
            else:
                error_msg = f"Provider {model_key} not implemented yet"
                log_message(error_msg, True)
                self.SetStatusText(error_msg)
                return None
        except Exception as e:
            error_msg = f"Error initializing LLM client: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            self.SetStatusText(error_msg)
            return None
    
    def append_to_chat(self, message, sender):
        try:
            # Determine insert position (end of text)
            end_pos = self.chat_display.GetLastPosition()
            
            # Insert sender with formatting
            self.chat_display.SetInsertionPoint(end_pos)
            self.chat_display.WriteText(f"{sender}: ")
            
            # Style the sender text
            last_pos = self.chat_display.GetLastPosition()
            self.chat_display.SetStyle(end_pos, last_pos, 
                                      wx.TextAttr(wx.BLACK, font=wx.Font(wx.FontInfo(10).Bold())))
            
            # Add message
            self.chat_display.WriteText(f"{message}\n\n")
            
            # Scroll to end
            self.chat_display.ShowPosition(self.chat_display.GetLastPosition())
        except Exception as e:
            log_message(f"Error appending to chat: {str(e)}", True)
    
    def on_send_message(self, event):
        try:
            user_message = self.user_input.GetValue().strip()
            
            if not user_message:
                return
            
            log_message(f"Sending user message: {user_message[:50]}...")
            
            # Clear input
            self.user_input.Clear()
            
            # Add to chat display
            self.append_to_chat(user_message, "You")
            
            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            
            # Disable input during processing
            self.user_input.Disable()
            self.SetStatusText("Processing...")
            
            # Use threading to keep UI responsive
            threading.Thread(target=self.process_message, args=(user_message,), daemon=True).start()
        except Exception as e:
            error_msg = f"Error sending message: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            self.SetStatusText(error_msg)
            self.user_input.Enable()
    
    def process_message(self, user_message):
        try:
            # Load selected documents
            doc_context = self.load_selected_documents()
            
            # Create conversation history text
            history_text = ""
            for msg in self.conversation_history[:-1]:  # Skip the last user message as we'll add it separately
                sender = "User" if msg["role"] == "user" else "Assistant"
                history_text += f"{sender}: {msg['content']}\n\n"
            
            # Get system prompt from config
            system_prompt = self.config.get("system_prompt", "You are a helpful AI research assistant.")
            
            # Create the full prompt
            prompt = f"""
{system_prompt}

Document Context:
{doc_context}

Conversation History:
{history_text}

Current Question:
{user_message}
"""
            
            # Get LLM client
            client = self.get_llm_client()
            
            if client:
                response = client.generate_response(prompt)
            else:
                response = "Could not initialize LLM client. Please check your API keys and configuration."
            
            # Add to conversation history
            self.conversation_history.append({"role": "assistant", "content": response})
            
            # Update UI in the main thread
            wx.PostEvent(self, ResponseEvent(response=response))
        except Exception as e:
            error_message = f"Error processing message: {str(e)}"
            log_message(error_message, True)
            log_message(traceback.format_exc(), True)
            wx.PostEvent(self, ResponseEvent(response=error_message))
    
    def on_response_event(self, event):
        try:
            # Add response to chat
            self.append_to_chat(event.response, "Assistant")
            
            # Enable input
            self.user_input.Enable()
            self.SetStatusText("Ready")
        except Exception as e:
            log_message(f"Error updating UI with response: {str(e)}", True)
            self.SetStatusText(f"Error: {str(e)}")
            self.user_input.Enable()

# Set up basic error logging
def setup_error_logging():
    try:
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        log_path = os.path.join(base_dir, "error_log.txt")
        
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"Application starting at {os.path.abspath(sys.argv[0])}\n")
        
        log_message(f"Application starting. Errors will be logged to {log_path}")
        return log_path
    except Exception as e:
        print(f"Error setting up logging: {str(e)}")
        return None

# Main entry point
if __name__ == "__main__":
    try:
        # Set up logging
        log_file = setup_error_logging()
        
        # Initialize wx app
        app = wx.App()
        
        # Create main window
        frame = ResearchAssistantApp()
        
        # Start the main loop
        app.MainLoop()
    except Exception as e:
        error_message = f"Critical error: {str(e)}"
        print(error_message)
        log_message(error_message, True)
        log_message(traceback.format_exc(), True)
        
        # Show error in dialog
        try:
            wx.MessageBox(f"Application error: {str(e)}\nCheck error_log.txt for details.", "Error", 
                         wx.OK | wx.ICON_ERROR)
        except:
            pass