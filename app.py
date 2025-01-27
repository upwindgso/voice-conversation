from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
from google.cloud import texttospeech

from datetime import datetime, timedelta
import re
import json
import os

import traceback
from threading import Lock, Thread
from queue import Queue, Empty
import subprocess
import threading
import queue
import io

import time


import azure.cognitiveservices.speech as speechsdk
import av
import wave
from pydub import AudioSegment


# Set up logging
"""
Level   Numeric value   What it means / When to use it
logging.DEBUG       10  Detailed information, typically only of interest to a developer trying to diagnose a problem.
logging.INFO        20  Confirmation that things are working as expected.
logging.WARNING     30  An indication that something unexpected happened, or that a problem might occur in the near future (e.g. ‘disk space low’). The software is still working as expected.
logging.ERROR       40  Due to a more serious problem, the software has not been able to perform some function.
logging.CRITICAL    50  A serious error, indicating that the program itself may be unable to continue running."""
import logging

loggers_to_silence = ["urllib3", "openai","httpcore","werkzeug","httpx","websockets"]
for logger_name in loggers_to_silence:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.WARNING)  # Ignore DEBUG/INFO
    logger.propagate = False  # Optional
logging.basicConfig(level=logging.NOTSET)
logger = logging.getLogger(__name__)

# Load environment variables
from boilerplate import load_env_files, Track
load_env_files()
track = Track(logger)
# call track with a track.level (lowercase loggin level). 
# you can pass an optional message to it like an error message
# it will always display the functon name first

# Initialize Flask and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
#socketio = SocketIO(app, cors_allowed_origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", binary=True)

# Initialize Google Cloud and OpenAI clients
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
You are my coworker who sits next to me in the same cubicle. We have worked in the same area for a long time and have a easy rapport. You are a female Australian.
<instructions priority=absolute>
Your responses will be rendered verbally using Google Text-to-Speech so make sure you are very concise (as speech is normally more brief than written word).
</instructions>
"""

from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions, DeepgramClientOptions
config = DeepgramClientOptions(verbose=logging.WARNING)
deepgram = DeepgramClient(
    api_key = os.getenv('DEEPGRAM_API_KEY'),
    config= config
    )

#tts_client = texttospeech.TextToSpeechClient()
import azure.cognitiveservices.speech as speechsdk
speech_config = speechsdk.SpeechConfig(subscription=os.getenv('AZURE_KEY'), region=os.getenv('AZURE_REGION'))
# Note: the voice setting will not overwrite the voice element in input SSML.
speech_config.speech_synthesis_voice_name = "en-AU-FreyaNeural" #"en-GB-AdaMultilingualNeural"

# use the default speaker as audio output.
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)


thread_lock = Lock()


# Audio buffer queue (thread-safe)
audio_buffer = Queue()






# Text-to-speech function
def text_to_speech(text):
    track(track.debug, text)

    result = speech_synthesizer.speak_text_async(text).get() #async = just generate the file....syncronous actually plays the text
    
    # Check result
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        track(track.debug, result.audio_duration)
        track(track.debug, result.properties)
        return result.audio_data
    
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        track(track.error,"Speech synthesis canceled: {}".format(cancellation_details.reason))
        
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            track(track.error,"Error details: {}".format(cancellation_details.error_details))

    """synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-AU", name="en-AU-Wavenet-C"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    return response.audio_content"""

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


def send_to_ai(complete_transcript):

    track(track.debug,complete_transcript)
    ai_response = generate_response(complete_transcript) 
    
    audio_content = text_to_speech(ai_response)

    with open(f"static/output_{int(time.time())}.mp3", "wb") as f:
        f.write(audio_content)
    
    socketio.emit('ai_response', {'audio_url': f"static/output_{int(time.time())}.mp3", 'text': ai_response})



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



# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
        'favicon.ico', mimetype='image/vnd.microsoft.icon')

class ClientState:
    def __init__(self):
        self.dg_connection = None
        self.processing = False
        self.current_transcript = ""
        self.complete_transcript = ""
        self.speech_final = False
        self.from_finalize = False
        

clients = {}

def keep_dg_connection_alive(sid):
    "a periodic heartbeat to keep the connection alive to speed up first response latency"

    client = clients[sid]

    if client.dg_connection:
        client.dg_connection.keep_alive()
        track(track.debug, sid)
    else:
        client.processing = False
        init_dg_connection_client(sid)
        track(track.info, sid + " => reopening connection")
        return #because we dont want to create duplicate keep alive threads
    

    threading.Timer(7.0, function=keep_dg_connection_alive, args=(sid,)).start() #one shot timer

def init_dg_connection_client(sid, start_keep_alive = True):
    track(track.info, sid)
    
    client = clients[sid]

    if not client.processing:
        track(track.info,'create processing client')

        # Initialize Deepgram connection
        client.dg_connection = deepgram.listen.websocket.v('1')
        
        client.processing = True
        threading.Thread(target=process_transcription, args=(sid,)).start() #one shot run
        
        if start_keep_alive:
            threading.Timer(7.0, function=keep_dg_connection_alive, args=(sid,)).start() #one shot timer

def close_dg_connection(sid):
    track(track.info)

    client = clients[sid]

    if client.dg_connection:
    
        client.dg_connection.finish()
        client.processing = False
        client.dg_connection = None



@socketio.on('connect') #fires automatically on tab open
def handle_connect():
    track(track.info)

    sid = request.sid  # <-- This is the correct way
    clients[sid] = ClientState()

    track(track.info,f'sid: {sid}')

    init_dg_connection_client(sid)

@socketio.on('disconnect') #fiore automaticaly on close tab / where as stop_recording is manual
def handle_disconnect():
    track(track.info)

    sid = request.sid  # <-- Get ID from request here too

    track(track.info,f'sid: {sid}')
    if sid in clients:

        close_dg_connection(sid)
        
        del clients[sid]

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    try:
        sid = request.sid
        if sid not in clients:
            return
        client = clients[sid]
        #client.audio_queue.put(data)
        if data is not None:  # End of stream
            client.dg_connection.send(data)
            track(track.info)
        else:
            track(track.info,"empty chunk")
        
    except Exception as e:
        track(track.error, message=e)
        traceback.print_exc()

@socketio.on('start_recording')
def handle_start_recording():
    track(track.info)

    sid = request.sid
    if sid in clients:
        client = clients[sid]

        if not client.dg_connection:
            #start a new connection...
            init_dg_connection_client(sid, start_keep_alive=False) #we're starting it early so we dont want to also start a dupe keepalive thread
            

@socketio.on('stop_recording')
def handle_stop_recording():
    """tell it we've stopped recording gracefully
        either get a finalised response for wait a moment and force it to finalise what ever its got
            the finalised response will push itself through to the client as normal
        now once its finalised, we can push it to the llm
    """
    
    sid = request.sid
    if sid in clients:
        client = clients[sid]
       
    track(track.info, sid)

    stopped = datetime.now()

    while not client.speech_final:
        if datetime.now() > stopped + timedelta(seconds=1.2):
            client.dg_connection.finalize()
            track(track.info, "finalize")

            finalize_request = datetime.now()

            while not client.from_finalize:
                if datetime.now() > finalize_request + timedelta(seconds=2.7):
                    track(track.info, "failed to finalize")
                    socketio.emit('human_response', {'text': client.complete_transcript, "speech_final" : True, "is_final": True}, to=sid)
                    break

            break


    #ok, we've got a final response in complete_transcript, we can send to llm and proceed

    send_to_ai(client.complete_transcript)

    client.current_transcript = ''
    client.complete_transcript = ''
    client.speech_final = False
    client.from_finalize = False

    #and close the service and open a new one
    close_dg_connection(sid)



        



def process_transcription(sid):
    global final_transcript
    global complete_transcript
    

    client = clients.get(sid)
    if not client:
        return
    
    try:
        track(track.info)
               

        # Transcription callback
        def process_transcription_on_transcript(self, result,**kwargs):

            #track(track.info)
            #if 'channel' in result:
            transcript = result.channel.alternatives[0].transcript
            
            if transcript.strip():
                track(track.debug,f"is_final: {result.is_final} speech_final: {result.speech_final} from_finalize: {result.from_finalize}  transcript: {transcript}")
                #need to concatentate fragments https://developers.deepgram.com/docs/understand-endpointing-interim-results#getting-final-transcripts
                
                human_response = ''

                """ current_transcription = one human_response bubble
                    complete_trancript = all bubbles combined together (they get reset every speech_final)
                    
                    - If is_final/were confident in the transcription then lock it into the current transcript
                        - else, attatch the current WIP translation only the end of what we're confident in
                    - do we need to creat a new bubble / speech final? The flush current_transcript

                    Assumption: from_finalise=True means is_final must always also be true. if not then we'll need to handle
                """
                if result.from_finalize:
                    pass
                
                if result.is_final:
                    client.current_transcript += ' ' + transcript
                    client.complete_transcript += client.current_transcript
                    human_response = client.current_transcript
                else:
                    human_response = client.current_transcript + transcript
                
                if result.from_finalize or result.speech_final:
                    human_response = client.current_transcript
                    client.complete_transcript += '\n'
                    client.current_transcript = ''

                socketio.emit('human_response', {'text': human_response, "speech_final" : result.from_finalize or result.speech_final, "is_final": result.is_final}, to=sid)

                if result.speech_final:
                    #just in case it was running out of order
                    time.sleep(0.1)
                    client.speech_final = True

                if result.from_finalize:
                    client.from_finalize = True

        client.dg_connection.on(LiveTranscriptionEvents.Transcript, process_transcription_on_transcript)

        def process_transcription_on_error(self, error,**kwargs):
            track(track.error,error)

        client.dg_connection.on(LiveTranscriptionEvents.Error, process_transcription_on_error)

        def process_transcription_on_metadata(self, metadata,**kwargs):
            pass
            #track(track.debug,metadata)
            
        client.dg_connection.on(LiveTranscriptionEvents.Metadata, process_transcription_on_metadata)

        def process_transcription_on_unhandled(self, event,**kwargs):
            track(track.error,event)
            
        client.dg_connection.on(LiveTranscriptionEvents.Unhandled, process_transcription_on_unhandled)

        options = LiveOptions(
            model='nova-2',
            language='en-AU',
            #encoding='audio/webm',  # ❌ WRONG PARAMETER
            interim_results=True,
            endpointing=500,
            smart_format=True,
            filler_words=False
        )

        client.dg_connection.start(
            options,
            content_type='audio/webm'  # ✅ CORRECT MIME TYPE HANDLING
            )

    except Exception as e:
        track(track.error, message=e)
        traceback.print_exc()
            
        

if __name__ == '__main__':
    if not os.path.exists('temp_audio'):
        os.makedirs('temp_audio')
    socketio.run(app, debug=True)