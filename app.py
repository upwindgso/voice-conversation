from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import texttospeech

from datetime import datetime, timedelta
import re
import os
from threading import Lock, Thread
from queue import Queue
import atexit
import time
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
from boilerplate import load_env_files
load_env_files()

# Initialize Flask and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Google Cloud and OpenAI clients
speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
#from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# Initialize the OpenAI client
llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.3,
)

#use this to store an array of messages...manually append to it
message_history = []

#memory = ConversationBufferMemory()

system_prompt = """
You are my coworker who sits next to me in the same cubicle. We have worked in the same area for a long time and have a easy rapport. You are a female Australian and have a very ocker way of speaking.
<output_format priority=maximum>
Your responses will be rendered verbally using Google Text-to-Speech so make sure you are very concise (as speech is normally more brief than written word).
</output_format>
"""

# Audio processing queue
audio_queue = Queue()
thread_lock = Lock()

# Transcription function
def transcribe_stream(stream):
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        sample_rate_hertz=48000,
        language_code="en-AU",
        enable_automatic_punctuation=True,
        
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config, 
        interim_results=True, 
        single_utterance=False,
    )
    requests = (speech.StreamingRecognizeRequest(audio_content=chunk) for chunk in stream)
    responses = speech_client.streaming_recognize(streaming_config, requests)
    return responses

# Text-to-speech function
def text_to_speech(text):
    logger.debug(f'text_to_speech:{text_to_speech}')

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-AU", name="en-AU-Wavenet-C"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    return response.audio_content

# OpenAI GPT-4 function
def generate_response(humanmessage):
    
    global message_history

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        MessagesPlaceholder(variable_name="messages"),
    ])

    """
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ]"""

    message_history.append(HumanMessage(content=humanmessage))

    chain = prompt | llm
    
    response = chain.invoke({"messages" : message_history})

    message_history.append(AIMessage(content=response.content))

    logger.debug(f'message_history: {message_history}')

    
    return response.content

# Define global variable at the top of your script
global_transcription = ""


last_transcript = datetime.now() + timedelta(days=10)

def process_audio():
    global global_transcription  # Declare the global variable
    global last_transcript

    while True:
        chunk = audio_queue.get()
        responses = transcribe_stream([chunk])

        for response in responses:
           
            for result in response.results:
                if result.is_final:
                    transcription = result.alternatives[0].transcript
                    global_transcription += transcription + "\n"  # Append to global variable
                    socketio.emit('transcription', {'text': transcription})
                    last_transcript = datetime.now()
                    #logger.debug(f'global_transcription:{global_transcription}')

def send_to_ai(global_transcription):


    ai_response = generate_response(global_transcription) 
    
    audio_content = text_to_speech(ai_response)
    with open(f"static/output_{int(time.time())}.mp3", "wb") as f:
        f.write(audio_content)
    socketio.emit('ai_response', {'audio_url': f"static/output_{int(time.time())}.mp3", 'text': ai_response})


#because the transcription will split the text into multiple responses...and we dont know if any
#individual response is the last one, we have to do this janky crap to infer there is nothing
#more coming down the pipe => invoke the llm from there
def check_transcription_end():
    global last_transcript, global_transcription
    while True:

        if datetime.now() < last_transcript:
            pass
            #logger.debug("No transcription in progress")
        else:
            #logger.debug(f"Last transcription: {last_transcript}")
            if datetime.now() - last_transcript > timedelta(milliseconds=4000):
                logger.debug(f"Speech has ended. Final transcription: {global_transcription}")

                send_to_ai(global_transcription)
                global_transcription = ""

                last_transcript = datetime.now() + timedelta(days=10)
        time.sleep(1)
       
Thread(target=check_transcription_end, daemon=True).start()

@app.route('/delete_file', methods=['DELETE'])
def delete_file():
    try:
        filename = request.args.get('filename')
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400

        # Validate filename pattern (output_<numbers>.mp3)
        if not re.match(r'^output_\d+\.mp3$', filename):
            return jsonify({'error': 'Invalid filename format'}), 400

        # Ensure we only look in static directory and prevent directory traversal
        filepath = os.path.join('static', filename)
        if os.path.dirname(os.path.abspath(filepath)) != os.path.abspath('static'):
            return jsonify({'error': 'Invalid file path'}), 400

        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404

        os.remove(filepath)
        logger.debug(f"Deleted file: {filepath}")
        return jsonify({'message': 'File deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return jsonify({'error': str(e)}), 500

# Start background thread
Thread(target=process_audio, daemon=True).start()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

# SocketIO events
@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    logger.debug('audio_chunk')
    #with thread_lock:
    audio_queue.put(data['chunk'])

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
        'favicon.ico', mimetype='image/vnd.microsoft.icon')


if __name__ == '__main__':
    if not os.path.exists('temp_audio'):
        os.makedirs('temp_audio')
    socketio.run(app, debug=True)