# AI-Powered Voice Chat Application

This project is an AI-powered voice chat application built with **Flask**, **Socket.IO**, and **Google Speech-to-Text** and **Text-to-Speech APIs**. It allows users to interact with an AI assistant using voice commands. The AI responds verbally, and the conversation is displayed in a chat interface.

As a 

## Features

- **Voice Input:** Speak to the AI assistant, and your speech is transcribed using Google Speech-to-Text.
- **AI Response:** The AI (powered by OpenAI's GPT-4) generates a response, which is converted to speech using Google Text-to-Speech.
- **Real-Time Chat Interface:** The conversation is displayed in a chat interface with user and AI messages.
- **Recording Indicator:** The record button changes color to indicate when recording is active.
- **5-Minute Recording Limit:** Recording automatically stops after 5 minutes to prevent excessively long recordings.

## Technologies Used

- **Backend:**
  - Flask (Python web framework)
  - Flask-SocketIO (WebSocket communication)
  - Google Cloud Speech-to-Text (Audio transcription)
  - Google Cloud Text-to-Speech (AI response synthesis)
  - OpenAI GPT-4 (AI model for generating responses)

- **Frontend:**
  - HTML, CSS, JavaScript
  - Socket.IO (Real-time communication)
  - MediaRecorder API (Audio recording)

## Setup Instructions

### Prerequisites

1. **Python 3.10.16**: Ensure Python is installed on your system.
2. **Google Cloud Account**: Set up a Google Cloud project and enable the Speech-to-Text and Text-to-Speech APIs.
3. **OpenAI API Key**: Obtain an API key from OpenAI for GPT-4.

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/upwindgso/voice-conversation.git
   cd voice-conversation
   ```

2. **Set Up a Virtual Environment:**
   ```bash
   conda env create voice-conversation python=3.10.16
   conda activate voice-conversation
   ```

3. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables:**
   Create a `.env` file in the root directory and add the following variables:
   ```plaintext
   FLASK_SECRET_KEY=your_secret_key
   OPENAI_API_KEY=your_openai_api_key
   ```

   You'll also need to set up google api auths through google cli => enable:
   - Google Cloud Speech-to-Text API
   - Google Cloud Text-to-Speech API


5. **Run the Application:**
   ```bash
   python app.py
   ```

6. **Access the Application:**
   Open your browser and navigate to `http://127.0.0.1:5000`.

## Usage

1. **Start Recording:**
   - Click the "Record" button or press the **Spacebar** to start recording.
   - The button will turn soft/pastel red to indicate that recording is active.

2. **Speak to the AI:**
   - Speak into your microphone. Your speech will be transcribed and sent to the AI.

3. **AI Response:**
   - The AI will generate a response, which will be displayed in the chat interface and played as audio.

4. **Stop Recording:**
   - Click the "Stop" button or press the **Spacebar** again to stop recording.
   - The button will revert to its normal color.

5. **5-Minute Limit:**
   - Recording will automatically stop after 5 minutes.

## Project Structure

```
project/
│
├── app.py                  # Flask application and WebSocket handlers
├── boilerplate.py          # Utility functions (e.g., loading environment variables)
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables
│
├── static/
│   └── scripts.js          # Frontend JavaScript for handling audio and UI
│
├── templates/
│   └── index.html          # HTML template for the chat interface
│
└── README.md               # Project documentation
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
