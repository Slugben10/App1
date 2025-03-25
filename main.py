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

# Custom event for updating UI from threads
ResponseEvent, EVT_RESPONSE = wx.lib.newevent.NewEvent()
StreamEvent, EVT_STREAM = wx.lib.newevent.NewEvent()  # New event for streaming updates

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
        if sys.platform == 'darwin' and hasattr(sys, '_MEIPASS'):
            # Handle macOS .app bundle
            return os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
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

# Ensure the Prompts directory exists (new for prompt library)
prompts_dir = os.path.join(APP_PATH, "Prompts")
log_message(f"Ensuring Prompts directory exists at: {prompts_dir}")
os.makedirs(prompts_dir, exist_ok=True)

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
        # Try alternative locations for macOS app bundle
        if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
            alt_paths = [
                os.path.join(os.path.dirname(sys.executable), ".env"),
                os.path.join(os.path.dirname(os.path.dirname(sys.executable)), ".env"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(sys.executable))), ".env")
            ]
            for alt_path in alt_paths:
                log_message(f"Checking alternative .env path: {alt_path}")
                if os.path.exists(alt_path):
                    dotenv.load_dotenv(alt_path)
                    log_message(f".env file loaded from alternative path: {alt_path}")
                    break
            else:
                log_message("No .env file found in any location")
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
            # Try alternative locations for macOS app bundle
            if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
                alt_paths = [
                    os.path.join(os.path.dirname(sys.executable), "config.json"),
                    os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "config.json"),
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(sys.executable))), "config.json")
                ]
                for alt_path in alt_paths:
                    log_message(f"Checking alternative config path: {alt_path}")
                    if os.path.exists(alt_path):
                        with open(alt_path, "r", encoding='utf-8') as f:
                            config = json.load(f)
                            log_message(f"Config loaded successfully from alternative path: {alt_path}")
                            return config
            
            log_message(f"Config file not found at {config_path} or alternative locations, creating default", True)
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
                "model_name": "claude-3-7-sonnet-20250219"
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
    
    def generate_response(self, prompt, on_chunk=None):
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "stream": False
            }
            
            log_message(f"Sending request to OpenAI API with model {self.model_name}")
            
            # Regular response (disable streaming for now to fix crashes)
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
    
    def generate_response(self, prompt, on_chunk=None):
        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            data = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "stream": False
            }
            
            log_message(f"Sending request to Anthropic API with model {self.model_name}")
            
            # Regular response (disable streaming for now to fix crashes)
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
    
    def generate_response(self, prompt, on_chunk=None):
        try:
            # This is a simplified version - actual implementation depends on the Gemini API
            log_message(f"Google API integration not fully implemented, using model: {self.model_name}")
            return f"This would be a response from the Google Gemini API using the {self.model_name} model."
        except Exception as e:
            error_msg = f"Google API Exception: {str(e)}"
            log_message(error_msg, True)
            return error_msg

# Dialog for editing a message
class MessageEditDialog(wx.Dialog):
    def __init__(self, parent, message):
        super(MessageEditDialog, self).__init__(parent, title="Edit Message", size=(500, 300))
        
        self.message = message
        
        # Create a panel
        panel = wx.Panel(self)
        
        # Create a sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add a text control for editing the message
        self.text_ctrl = wx.TextCtrl(panel, value=message, style=wx.TE_MULTILINE)
        sizer.Add(self.text_ctrl, 1, wx.ALL|wx.EXPAND, 10)
        
        # Add OK and Cancel buttons
        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        button_sizer.AddButton(ok_button)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        sizer.Add(button_sizer, 0, wx.ALIGN_CENTER|wx.ALL, 10)
        
        panel.SetSizer(sizer)
        
        # Center the dialog
        self.Centre()
    
    def GetMessage(self):
        return self.text_ctrl.GetValue()

# Dialog for managing document priorities
class DocumentPriorityDialog(wx.Dialog):
    def __init__(self, parent, documents, doc_priorities):
        super(DocumentPriorityDialog, self).__init__(parent, title="Document Priorities", size=(500, 400))
        
        self.documents = documents
        self.doc_priorities = doc_priorities.copy()
        
        # Create a panel and main sizer
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add instructions
        instructions = wx.StaticText(panel, label="Set priority for each document:")
        main_sizer.Add(instructions, 0, wx.ALL, 10)
        
        # Create a scrolled panel for the documents
        self.scroll_panel = scrolled.ScrolledPanel(panel)
        self.scroll_panel.SetAutoLayout(True)
        self.scroll_panel.SetupScrolling()
        
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Priority choices
        self.priority_levels = ["Low", "Medium", "High"]
        self.priority_controls = {}
        
        # Add controls for each document
        for doc in self.documents:
            doc_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # Document name
            doc_label = wx.StaticText(self.scroll_panel, label=doc)
            doc_sizer.Add(doc_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            
            # Priority dropdown
            priority_choice = wx.Choice(self.scroll_panel, choices=self.priority_levels)
            current_priority = self.doc_priorities.get(doc, "Medium")
            priority_choice.SetStringSelection(current_priority)
            doc_sizer.Add(priority_choice, 0)
            
            # Store the control reference
            self.priority_controls[doc] = priority_choice
            
            scroll_sizer.Add(doc_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        self.scroll_panel.SetSizer(scroll_sizer)
        main_sizer.Add(self.scroll_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        # Add OK and Cancel buttons
        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        button_sizer.AddButton(ok_button)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(main_sizer)
        self.Centre()
    
    def get_priorities(self):
        priorities = {}
        for doc, control in self.priority_controls.items():
            priorities[doc] = control.GetStringSelection()
        return priorities

# Dialog for saving/loading prompts
class PromptLibraryDialog(wx.Dialog):
    def __init__(self, parent, mode="load", current_prompt=""):
        title = "Load Prompt" if mode == "load" else "Save Prompt"
        super(PromptLibraryDialog, self).__init__(parent, title=title, size=(500, 400))
        
        self.mode = mode
        self.current_prompt = current_prompt
        self.prompts_dir = os.path.join(APP_PATH, "Prompts")
        self.selected_prompt = None
        
        # Create a panel and main sizer
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add appropriate controls based on mode
        if mode == "load":
            # Prompt list for loading
            list_label = wx.StaticText(panel, label="Select a prompt to load:")
            main_sizer.Add(list_label, 0, wx.ALL, 10)
            
            self.prompt_list = wx.ListBox(panel, style=wx.LB_SINGLE)
            self.load_saved_prompts()
            main_sizer.Add(self.prompt_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
            
            # Delete button for removing prompts
            delete_btn = wx.Button(panel, label="Delete Selected Prompt")
            delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_prompt)
            main_sizer.Add(delete_btn, 0, wx.ALL, 10)
            
        else:  # Save mode
            # Prompt name field
            name_label = wx.StaticText(panel, label="Prompt Name:")
            main_sizer.Add(name_label, 0, wx.ALL, 10)
            
            self.name_field = wx.TextCtrl(panel)
            main_sizer.Add(self.name_field, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            
            # Preview of prompt to save
            preview_label = wx.StaticText(panel, label="Prompt Preview:")
            main_sizer.Add(preview_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
            
            preview_text = wx.TextCtrl(panel, value=current_prompt[:200] + ("..." if len(current_prompt) > 200 else ""), 
                                     style=wx.TE_MULTILINE | wx.TE_READONLY)
            preview_text.SetMinSize((400, 100))
            main_sizer.Add(preview_text, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # Add OK and Cancel buttons
        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        button_sizer.AddButton(ok_button)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(main_sizer)
        self.Centre()
    
    def load_saved_prompts(self):
        # Clear the list
        self.prompt_list.Clear()
        
        # Get all JSON files from the Prompts directory
        if os.path.exists(self.prompts_dir):
            prompt_files = [f for f in os.listdir(self.prompts_dir) 
                           if os.path.isfile(os.path.join(self.prompts_dir, f)) 
                           and f.lower().endswith('.json')]
            
            # Add each file to the list (without .json extension)
            for prompt_file in prompt_files:
                prompt_name = os.path.splitext(prompt_file)[0]
                self.prompt_list.Append(prompt_name)
    
    def on_delete_prompt(self, event):
        selected_idx = self.prompt_list.GetSelection()
        if selected_idx != wx.NOT_FOUND:
            prompt_name = self.prompt_list.GetString(selected_idx)
            
            # Confirm deletion
            dialog = wx.MessageDialog(self, 
                                     f"Are you sure you want to delete the prompt '{prompt_name}'?",
                                     "Confirm Deletion", 
                                     wx.YES_NO | wx.ICON_QUESTION)
            
            if dialog.ShowModal() == wx.ID_YES:
                # Delete the prompt file
                file_path = os.path.join(self.prompts_dir, f"{prompt_name}.json")
                try:
                    os.remove(file_path)
                    # Update the list
                    self.prompt_list.Delete(selected_idx)
                    log_message(f"Deleted prompt: {prompt_name}")
                except Exception as e:
                    log_message(f"Error deleting prompt: {str(e)}", True)
                    wx.MessageBox(f"Error deleting prompt: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
            
            dialog.Destroy()
    
    def get_prompt_content(self):
        if self.mode == "load":
            selected_idx = self.prompt_list.GetSelection()
            if selected_idx != wx.NOT_FOUND:
                prompt_name = self.prompt_list.GetString(selected_idx)
                self.selected_prompt = prompt_name
                
                file_path = os.path.join(self.prompts_dir, f"{prompt_name}.json")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        prompt_data = json.load(f)
                        return prompt_data.get("content", "")
                except Exception as e:
                    log_message(f"Error loading prompt: {str(e)}", True)
                    return ""
            return ""
        else:
            return self.current_prompt
    
    def get_prompt_name(self):
        if self.mode == "load":
            return self.selected_prompt
        else:
            return self.name_field.GetValue()

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
        self.message_positions = []  # Store positions of messages in the chat display
        self.doc_priorities = {}  # Store document priorities (new)
        self.current_streaming_response = ""  # Store current streaming response (new)
    
    # Set up the UI
        self.setup_ui()
    
    # Update document list
        self.update_document_list()
    
    # Set up event handlers
        self.Bind(EVT_RESPONSE, self.on_response_event)
        self.Bind(EVT_STREAM, self.on_stream_event)  # New event handler for streaming
    
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
            
            # Set document priorities button (new)
            priority_btn = wx.Button(left_panel, label="Set Document Priorities")
            priority_btn.Bind(wx.EVT_BUTTON, self.on_set_priorities)
            left_sizer.Add(priority_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            
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
            
            # Chat management buttons
            chat_management_panel = wx.Panel(right_panel)
            chat_management_sizer = wx.BoxSizer(wx.HORIZONTAL)

            clear_all_btn = wx.Button(chat_management_panel, label="Clear All Chat")
            clear_all_btn.Bind(wx.EVT_BUTTON, self.on_clear_all_chat)
            chat_management_sizer.Add(clear_all_btn, 1, wx.RIGHT, 5)

            clear_last_btn = wx.Button(chat_management_panel, label="Clear Last Exchange")
            clear_last_btn.Bind(wx.EVT_BUTTON, self.on_clear_last_exchange)
            chat_management_sizer.Add(clear_last_btn, 1, wx.RIGHT, 5)

            edit_msg_btn = wx.Button(chat_management_panel, label="Edit Message")
            edit_msg_btn.Bind(wx.EVT_BUTTON, self.on_edit_message)
            chat_management_sizer.Add(edit_msg_btn, 1)

            chat_management_panel.SetSizer(chat_management_sizer)
            right_sizer.Add(chat_management_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            
            # Prompt library buttons (new)
            prompt_panel = wx.Panel(right_panel)
            prompt_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            save_prompt_btn = wx.Button(prompt_panel, label="Save Prompt")
            save_prompt_btn.Bind(wx.EVT_BUTTON, self.on_save_prompt)
            prompt_sizer.Add(save_prompt_btn, 1, wx.RIGHT, 5)
            
            load_prompt_btn = wx.Button(prompt_panel, label="Load Prompt")
            load_prompt_btn.Bind(wx.EVT_BUTTON, self.on_load_prompt)
            prompt_sizer.Add(load_prompt_btn, 1)
            
            prompt_panel.SetSizer(prompt_sizer)
            right_sizer.Add(prompt_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            
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
                
                # Add priority indicator if priority is set
                doc_sizer = wx.BoxSizer(wx.HORIZONTAL)
                doc_sizer.Add(checkbox, 1, wx.EXPAND)
                
                if doc in self.doc_priorities:
                    priority = self.doc_priorities[doc]
                    priority_label = wx.StaticText(self.doc_panel, label=f"[{priority}]")
                    
                    # Set color based on priority
                    if priority == "High":
                        priority_label.SetForegroundColour(wx.Colour(255, 0, 0))  # Red
                    elif priority == "Medium":
                        priority_label.SetForegroundColour(wx.Colour(0, 0, 255))  # Blue
                    
                    doc_sizer.Add(priority_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
                
                self.doc_sizer.Add(doc_sizer, 0, wx.EXPAND | wx.ALL, 5)
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
    
    def on_set_priorities(self, event):
        try:
            # Get all document names
            doc_path = os.path.join(APP_PATH, "Documents")
            doc_files = []
            
            if os.path.exists(doc_path):
                doc_files = [f for f in os.listdir(doc_path) 
                            if os.path.isfile(os.path.join(doc_path, f)) 
                            and f.lower().endswith(('.pdf', '.docx', '.txt', '.md'))]
            
            if not doc_files:
                wx.MessageBox("No documents available to prioritize.", "Info", wx.OK | wx.ICON_INFORMATION)
                return
            
            # Show the priority dialog
            dialog = DocumentPriorityDialog(self, doc_files, self.doc_priorities)
            if dialog.ShowModal() == wx.ID_OK:
                # Update priorities
                self.doc_priorities = dialog.get_priorities()
                log_message(f"Updated document priorities: {self.doc_priorities}")
                
                # Update document list to show priorities
                self.update_document_list()
            
            dialog.Destroy()
        except Exception as e:
            error_msg = f"Error setting document priorities: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            self.SetStatusText(error_msg)
            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_ERROR)
    
    def on_save_prompt(self, event):
        try:
            # Get current message from input
            current_prompt = self.user_input.GetValue().strip()
            
            if not current_prompt:
                wx.MessageBox("Please enter a prompt to save first.", "Error", wx.OK | wx.ICON_ERROR)
                return
            
            # Show save prompt dialog
            dialog = PromptLibraryDialog(self, mode="save", current_prompt=current_prompt)
            if dialog.ShowModal() == wx.ID_OK:
                prompt_name = dialog.get_prompt_name()
                
                if not prompt_name:
                    wx.MessageBox("Please enter a name for the prompt.", "Error", wx.OK | wx.ICON_ERROR)
                    return
                
                # Save prompt to file
                os.makedirs(prompts_dir, exist_ok=True)
                file_path = os.path.join(prompts_dir, f"{prompt_name}.json")
                
                prompt_data = {
                    "name": prompt_name,
                    "content": current_prompt,
                    "created_at": wx.DateTime.Now().Format("%Y-%m-%d %H:%M:%S")
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(prompt_data, f, indent=2)
                
                log_message(f"Saved prompt: {prompt_name}")
                self.SetStatusText(f"Prompt saved as: {prompt_name}")
            
            dialog.Destroy()
        except Exception as e:
            error_msg = f"Error saving prompt: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            self.SetStatusText(error_msg)
            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_ERROR)
    
    def on_load_prompt(self, event):
        try:
            # Show load prompt dialog
            dialog = PromptLibraryDialog(self, mode="load")
            if dialog.ShowModal() == wx.ID_OK:
                prompt_content = dialog.get_prompt_content()
                prompt_name = dialog.get_prompt_name()
                
                if prompt_content:
                    # Set loaded prompt in input field
                    self.user_input.SetValue(prompt_content)
                    log_message(f"Loaded prompt: {prompt_name}")
                    self.SetStatusText(f"Loaded prompt: {prompt_name}")
                else:
                    log_message("No prompt selected or error loading prompt")
            
            dialog.Destroy()
        except Exception as e:
            error_msg = f"Error loading prompt: {str(e)}"
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
            
            # Prepare document context for the prompt, giving priority to high priority documents
            doc_context = ""
            
            # Sort documents by priority (High -> Medium -> Low or not set)
            priority_order = {"High": 0, "Medium": 1, "Low": 2}
            sorted_docs = sorted(self.selected_docs, 
                                key=lambda d: priority_order.get(self.doc_priorities.get(d, "Medium"), 1))
            
            for doc_name in sorted_docs:
                priority = self.doc_priorities.get(doc_name, "Medium")
                doc_context += f"\n--- Document: {doc_name} [Priority: {priority}] ---\n"
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
            env_key = model_config.get("api_key_env", "")
            
            
            log_message(f"Available environment variables: {', '.join([k for k in os.environ.keys()])}")
            log_message(f"Checking for API key in environment variable: {env_key}")
            
            
            if env_key and not os.environ.get(env_key):
                error_msg = f"API key for {model_name} not found in environment variable {env_key}"
                log_message(error_msg, True)
                self.SetStatusText(error_msg)
                return None
            
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
            
            # Insert separator between Q&A if this is an assistant response (new)
            if sender == "Assistant" and end_pos > 0:
                self.chat_display.SetInsertionPoint(end_pos)
                self.chat_display.WriteText("------------------------\n")  # Horizontal separator
            
            # Insert sender with formatting
            end_pos = self.chat_display.GetLastPosition()
            self.chat_display.SetInsertionPoint(end_pos)
            
            # Format just the "You:" or "Assistant:" prefix in bold, not the entire message (new)
            prefix = f"{sender}: "
            self.chat_display.WriteText(prefix)
            
            # Style the sender text
            last_pos = self.chat_display.GetLastPosition()
            self.chat_display.SetStyle(end_pos, last_pos, 
                                    wx.TextAttr(wx.BLACK, font=wx.Font(wx.FontInfo(10).Bold())))
            
            # Add message with regular formatting
            self.chat_display.WriteText(f"{message}\n\n")
            
            # Scroll to end
            self.chat_display.ShowPosition(self.chat_display.GetLastPosition())
        except Exception as e:
            log_message(f"Error appending to chat: {str(e)}", True)
    
    def append_streaming_chunk(self, chunk):
        try:
            # Get current end position
            end_pos = self.chat_display.GetLastPosition()
            
            # Insert the chunk
            self.chat_display.SetInsertionPoint(end_pos)
            self.chat_display.WriteText(chunk)
            
            # Force UI update to show changes immediately (new)
            self.chat_display.ShowPosition(self.chat_display.GetLastPosition())
            wx.Yield()
        except Exception as e:
            log_message(f"Error appending streaming chunk: {str(e)}", True)
    
    def on_clear_all_chat(self, event):
        try:
            # Confirm with user
            dialog = wx.MessageDialog(self, 
                                    "Are you sure you want to clear the entire chat history?",
                                    "Confirm Clear All", 
                                    wx.YES_NO | wx.ICON_QUESTION)
            
            if dialog.ShowModal() == wx.ID_YES:
                # Clear conversation history
                self.conversation_history = []
                
                # Clear chat display
                self.chat_display.Clear()
                
                # Clear message positions
                self.message_positions = []
                
                log_message("Chat history cleared")
                self.SetStatusText("Chat history cleared")
            
            dialog.Destroy()
        except Exception as e:
            error_msg = f"Error clearing chat: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            self.SetStatusText(error_msg)

    def on_clear_last_exchange(self, event):
        try:
            if len(self.conversation_history) >= 2:
                # Remove last assistant and user messages (one exchange)
                self.conversation_history = self.conversation_history[:-2]
                
                # Redraw chat display
                self.chat_display.Clear()
                self.message_positions = []
                
                for msg in self.conversation_history:
                    sender = "You" if msg["role"] == "user" else "Assistant"
                    self.append_to_chat(msg["content"], sender)
                
                log_message("Last exchange cleared")
                self.SetStatusText("Last exchange cleared")
            else:
                self.SetStatusText("No complete exchanges to clear")
        except Exception as e:
            error_msg = f"Error clearing last exchange: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            self.SetStatusText(error_msg)

    def on_edit_message(self, event):
        try:
            # First, store the current position of each message to enable selection
            if not self.message_positions:
                # If we haven't tracked positions yet, we need to rebuild this list
                self.rebuild_message_positions()
            
            # Create a dialog to select which message to edit
            messages = []
            for i, msg in enumerate(self.conversation_history):
                role = "You" if msg["role"] == "user" else "Assistant"
                # Truncate message for display in selection dialog
                content = msg["content"]
                if len(content) > 50:
                    content = content[:47] + "..."
                messages.append(f"{i+1}. {role}: {content}")
            
            # Show message selection dialog
            dialog = wx.SingleChoiceDialog(
                self, "Select a message to edit:", "Edit Message", messages)
            
            if dialog.ShowModal() == wx.ID_OK:
                selected_index = dialog.GetSelection()
                dialog.Destroy()
                
                # Now show edit dialog for the selected message
                edit_dialog = MessageEditDialog(
                    self, self.conversation_history[selected_index]["content"])
                
                if edit_dialog.ShowModal() == wx.ID_OK:
                    # Update the message with edited content
                    edited_content = edit_dialog.GetMessage()
                    self.conversation_history[selected_index]["content"] = edited_content
                    
                    # Redraw chat display up to the edited message
                    self.chat_display.Clear()
                    self.message_positions = []
                    
                    # Display all messages up to and including the edited one
                    for i, msg in enumerate(self.conversation_history[:selected_index+1]):
                        sender = "You" if msg["role"] == "user" else "Assistant"
                        self.append_to_chat(msg["content"], sender)
                    
                    # Remove all messages after the edited one
                    self.conversation_history = self.conversation_history[:selected_index+1]
                    
                    # Disable input during processing
                    self.user_input.Disable()
                    self.SetStatusText("Processing edited message...")
                    
                    # Process the edited message - use the last message in the conversation history
                    # which is the edited message we just updated
                    threading.Thread(target=self.process_message, args=(self.conversation_history[-1]["content"],), daemon=True).start()
                
                edit_dialog.Destroy()
            else:
                dialog.Destroy()
        except Exception as e:
            error_msg = f"Error editing message: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            self.SetStatusText(error_msg)
    
    def rebuild_message_positions(self):
        try:
            self.message_positions = []
            current_position = 0
            
            # Get the text of the chat display
            text = self.chat_display.GetValue()
            lines = text.split('\n')
            
            # Rebuild positions based on message markers in text
            for i, line in enumerate(lines):
                # Check if this line starts a message (contains "You: " or "Assistant: ")
                if line.startswith("You: ") or line.startswith("Assistant: "):
                    # Calculate position in characters
                    position = sum(len(lines[j]) + 1 for j in range(i))
                    self.message_positions.append(position)
            
            log_message(f"Rebuilt message positions: {len(self.message_positions)} found")
        except Exception as e:
            log_message(f"Error rebuilding message positions: {str(e)}", True)
            log_message(traceback.format_exc(), True)

    def edit_conversation_history(self, event):
        try:
            # Create a dialog to edit conversation history
            dialog = ConversationHistoryDialog(self, self.conversation_history)
            if dialog.ShowModal() == wx.ID_OK:
                # Update conversation history
                self.conversation_history = dialog.get_updated_history()
                
                # Update chat display
                self.chat_display.Clear()
                for msg in self.conversation_history:
                    sender = "You" if msg["role"] == "user" else "Assistant"
                    self.append_to_chat(msg["content"], sender)
                
                log_message("Conversation history updated")
                self.SetStatusText("Conversation history updated")
            
            dialog.Destroy()
        except Exception as e:
            error_msg = f"Error editing conversation history: {str(e)}"
            log_message(error_msg, True)
            log_message(traceback.format_exc(), True)
            self.SetStatusText(error_msg)
    
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

    def on_stream_event(self, event):
        # Append the chunk to the chat display
        self.append_streaming_chunk(event.chunk)
        # Add to the current streaming response
        self.current_streaming_response += event.chunk

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
                # Get response (no streaming for now to fix the crash)
                response = client.generate_response(prompt)
                
                # Post event to add response to UI
                wx.PostEvent(self, ResponseEvent(response=response))
                
                # Add to conversation history
                self.conversation_history.append({"role": "assistant", "content": response})
            else:
                error_response = "Could not initialize LLM client. Please check your API keys and configuration."
                wx.PostEvent(self, ResponseEvent(response=error_response))
                self.conversation_history.append({"role": "assistant", "content": error_response})
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


# Dialog for editing conversation history
class ConversationHistoryDialog(wx.Dialog):
    def __init__(self, parent, conversation_history):
        super(ConversationHistoryDialog, self).__init__(
            parent, title="Edit Conversation History", size=(800, 600)
        )
        
        self.conversation_history = conversation_history.copy()
        
        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Instructions
        instructions = wx.StaticText(self, label="Edit or delete conversation messages:")
        main_sizer.Add(instructions, 0, wx.ALL, 10)
        
        # Create a scrolled panel for the messages
        self.panel = scrolled.ScrolledPanel(self)
        self.panel.SetAutoLayout(True)
        self.panel.SetupScrolling()
        
        self.panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.message_editors = []
        
        # Add each message to the panel
        for i, msg in enumerate(self.conversation_history):
            self.add_message_editor(i, msg)
        
        self.panel.SetSizer(self.panel_sizer)
        main_sizer.Add(self.panel, 1, wx.EXPAND | wx.ALL, 10)
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        ok_button = wx.Button(self, wx.ID_OK, "Save Changes")
        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        
        button_sizer.Add(ok_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        self.Centre()
    
    def add_message_editor(self, index, message):
        # Create a panel for this message
        msg_panel = wx.Panel(self.panel)
        msg_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Role selection
        role_sizer = wx.BoxSizer(wx.HORIZONTAL)
        role_label = wx.StaticText(msg_panel, label="Role:")
        role_choices = ["user", "assistant"]
        role_choice = wx.Choice(msg_panel, choices=["User", "Assistant"])
        role_choice.SetSelection(0 if message["role"] == "user" else 1)
        
        role_sizer.Add(role_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        role_sizer.Add(role_choice, 0)
        
        # Delete button
        delete_btn = wx.Button(msg_panel, label="Delete")
        delete_btn.index = index  # Store the index
        delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_message)
        
        role_sizer.Add(delete_btn, 0, wx.LEFT, 10)
        
        msg_sizer.Add(role_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Message content
        content_label = wx.StaticText(msg_panel, label="Content:")
        msg_sizer.Add(content_label, 0, wx.ALL, 5)
        
        content_text = wx.TextCtrl(msg_panel, value=message["content"], style=wx.TE_MULTILINE)
        msg_sizer.Add(content_text, 0, wx.EXPAND | wx.ALL, 5)
        
        msg_panel.SetSizer(msg_sizer)
        self.panel_sizer.Add(msg_panel, 0, wx.EXPAND | wx.ALL | wx.BOTTOM, 10)
        
        # Add separator line
        line = wx.StaticLine(self.panel, style=wx.LI_HORIZONTAL)
        self.panel_sizer.Add(line, 0, wx.EXPAND | wx.ALL, 5)
        
        # Store references to UI elements
        self.message_editors.append({
            "panel": msg_panel,
            "role": role_choice,
            "content": content_text,
            "index": index
        })
    
    def on_delete_message(self, event):
        # Get the index from the button that triggered the event
        index = event.GetEventObject().index
        
        # Find the corresponding editor
        editor = None
        for ed in self.message_editors:
            if ed["index"] == index:
                editor = ed
                break
        
        if editor:
            # Remove the panel and its separator line from the sizer
            self.panel_sizer.Remove(editor["panel"])
            editor["panel"].Destroy()
            
            # Get the index of the editor in the list
            list_index = self.message_editors.index(editor)
            
            # If not the last item, remove the separator line
            if list_index < len(self.message_editors) - 1:
                # The separator line is right after the panel
                next_item = self.panel_sizer.GetItem(list_index * 2 + 1).GetWindow()
                if next_item:
                    self.panel_sizer.Remove(next_item)
                    next_item.Destroy()
            
            # Remove from our list
            self.message_editors.remove(editor)
            
            # Update the UI
            self.panel.Layout()
            self.panel.SetupScrolling()
    
    def get_updated_history(self):
        # Create a new history from the current state of editors
        updated_history = []
        
        for editor in self.message_editors:
            role = "user" if editor["role"].GetSelection() == 0 else "assistant"
            content = editor["content"].GetValue()
            
            updated_history.append({
                "role": role,
                "content": content
            })
        
        return updated_history

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