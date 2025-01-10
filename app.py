from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from boilerplate import load_env_files
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from google.cloud import speech_v1p1beta1 as speech
import google.cloud.texttospeech as tts
import os
import logging
import tempfile
import time
import queue
import threading

# Load environment variables
load_env_files()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
socketio = SocketIO(app, max_http_buffer_size=10 * 1024 * 1024)  # 10 MB limit

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize the OpenAI client
llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.3,
)

system_prompt = """
You are a Simplification Expert who excels at finding elegant, minimalist solutions to complex problems. Your core principle is that the best solution is one that achieves maximum effectiveness with minimum complexity.
Before answering, you will formulate a response. This response is a level 1 response. I want you to go deeper to the root of the issue and respond to me with your level 2 or higher response only.
Remember: Your goal is to find the clearest path between problem and solution, removing everything that doesn't directly serve the core purpose
<output_format priority=maximum>
Your responses will be rendered verbally using Google Text-to-Speech so make sure you are very concise (as speech is normally more brief than written word).
</output_format>
"""

# Initialize Google Speech-to-Text client
speech_client = speech.SpeechClient()

# Queue to hold audio chunks for streaming recognition
audio_queue = queue.Queue()

def transcribe_audio(audio_file):
    """Transcribe audio using Google Speech-to-Text."""
    with open(audio_file, "rb") as audio_file:
        content = audio_file.read()
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        sample_rate_hertz=48000,  # Ensure this matches the sample rate of the audio
        language_code="en-US",
    )
    response = speech_client.recognize(config=config, audio=audio)
    if response.results:
        return response.results[0].alternatives[0].transcript
    return None

def text_to_speech(text):
    """Convert text to speech using Google Text-to-Speech."""
    client = tts.TextToSpeechClient()
    synthesis_input = tts.SynthesisInput(text=text)
    voice = tts.VoiceSelectionParams(
        language_code="en-AU",
        ssml_gender=tts.SsmlVoiceGender.FEMALE
    )
    audio_config = tts.AudioConfig(
        audio_encoding=tts.AudioEncoding.MP3
    )
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    # Generate a unique filename using a timestamp
    output_file = f"static/output_{int(time.time())}.mp3"
    with open(output_file, "wb") as out:
        out.write(response.audio_content)
    return output_file

@app.route('/')
def index():
    """Render the main chat interface."""
    logger.debug("Rendering index page")
    return render_template('index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files."""
    logger.debug(f"Serving static file: {filename}")
    return send_from_directory('static', filename)

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    logger.debug("Client connected via WebSocket")
    audio_queue.queue.clear()  # Clear the queue for a new session

@socketio.on('disconnect')
def handle_disconnect():
    logger.debug("Client disconnected")

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    """Handle audio chunks from the client."""
    try:
        logger.debug("Received audio chunk")
        audio_chunk = data['audio']

        # Verify audio chunk is not empty
        if not audio_chunk:
            logger.warning("Empty audio chunk received")
            emit('response', {'error': 'Empty audio chunk received'})
            return

        # Add the audio chunk to the queue
        audio_queue.put(audio_chunk)

    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")
        emit('response', {'error': str(e)})

@socketio.on('stop_recording')
def handle_stop_recording():
    """Handle the end of recording."""
    try:
        logger.debug("Stop recording received")

        # Combine all audio chunks into a single file
        combined_audio = b''
        while not audio_queue.empty():
            chunk = audio_queue.get()
            if chunk:
                combined_audio += chunk

        if not combined_audio:
            logger.warning("No audio data received")
            emit('response', {'error': 'No audio data received'})
            return

        # Save the combined audio to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            temp_audio.write(combined_audio)
            temp_audio_path = temp_audio.name

        # Log the size of the combined audio
        logger.debug(f"Combined audio size: {len(combined_audio)} bytes")

        # Transcribe the audio
        transcript = transcribe_audio(temp_audio_path)
        if not transcript:
            logger.warning("No transcription available")
            emit('response', {'error': 'No transcription available'})
            return

        logger.debug(f"Transcript: {transcript}")

        # Emit the transcription immediately
        emit('transcription', {'transcript': transcript})

        # Generate LLM response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=transcript)
        ]
        response = llm.invoke(messages)
        response_text = response.content
        logger.debug(f"LLM Response: {response_text}")

        # Convert response to speech
        speech_file = text_to_speech(response_text)
        logger.debug(f"Speech file generated: {speech_file}")

        # Send response back to the client
        emit('response', {
            'response': response_text,  # Send the AI response
            'audio_url': speech_file  # Send the audio file URL
        })

    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        emit('response', {'error': str(e)})

@app.route('/delete_file', methods=['DELETE'])
def delete_file():
    """Delete a file from the static directory."""
    try:
        filename = request.args.get('filename')
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400

        # Ensure the file is in the static directory
        filepath = os.path.join('static', os.path.basename(filename))
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404

        # Delete the file
        os.remove(filepath)
        logger.debug(f"Deleted file: {filepath}")
        return jsonify({'message': 'File deleted successfully'}), 200
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, debug=True)