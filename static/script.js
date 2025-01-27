const socket = io();

let mediaRecorder;

let chunksize = 2000;
let ai_is_thinking = false;

// Initialize MediaRecorder
navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm; codecs=opus' // Set MIME type
        });
        mediaRecorder.ondataavailable = event => {
            const reader = new FileReader();
            reader.onload = () => {
                socket.emit('audio_chunk', reader.result); // Send as ArrayBuffer
            };
            reader.readAsArrayBuffer(event.data);
        };
        mediaRecorder.onstop = () => {
            socket.emit('stop_recording'); // Notify server
        };
    })
    .catch(error => {
        console.error('Microphone access denied:', error);
    });

// Record button functionality
const recordButton = document.getElementById('record-button');
recordButton.addEventListener('click', () => {
    if (mediaRecorder.state === 'inactive') {
        mediaRecorder.start(chunksize);
        recordButton.classList.add('active');
        recordButton.innerText = 'Press space to STOP';
        socket.emit('start_recording'); // Notify server
        displayResponse('', isAIMessage = false, speech_final=false, is_final=false); //placeholder to show that recording has begun
    } else {
        setTimeout(() => {
            mediaRecorder.stop();
            recordButton.classList.remove('active');
            recordButton.innerText = 'Press space to RECORD';
            showThinkingBubble()
        }, 1000);  // 1000 milliseconds = 1 second
    }
});

// Spacebar functionality
document.addEventListener('keydown', event => {
    if (event.code === 'Space' && mediaRecorder) {
        if (mediaRecorder.state === 'inactive') {
            mediaRecorder.start(chunksize);
            recordButton.classList.add('active');
            recordButton.innerText = 'Press space to STOP';
            socket.emit('start_recording'); // Notify server
            displayResponse('', isAIMessage = false, speech_final=false, is_final=false); //placeholder to show that recording has begun
        } else {
            setTimeout(() => {
                mediaRecorder.stop();
                recordButton.classList.remove('active');
                recordButton.innerText = 'Press space to RECORD';
                showThinkingBubble()
            }, 1000);  // 1000 milliseconds = 1 second
        }
    }
});

// Function to preserve newlines and render markdown
function formatResponse(text) {
    text = text.replace(/\n/g, '<br>');
    return text;
}

function removeProvisionalResponses(){
    document.querySelectorAll('.ai-message-provisional').forEach(element => {
        element.remove();
    });

    document.querySelectorAll('.user-message-provisional').forEach(element => {
        element.remove();
    });
}

// Append to transcript
function displayResponse(response, isAIMessage = false, speech_final, is_final) {
    
    removeThinkingBubble();
    removeProvisionalResponses()
    //console.log(isAIMessage + ": " + is_final + " / " + speech_final + " = " + response)

    const conversation = document.getElementById('conversation');
    const Response = document.createElement('div');

    if (isAIMessage){
        ai_is_thinking =false

        if(speech_final){
            //final response
            Response.className = 'ai-message';
        } else{
            //interim response
            Response.className = 'ai-message-provisional';
        }
    } else {
        if(speech_final){
            Response.className = 'user-message';
        } else{
            Response.className = 'user-message-provisional';
        }
        
    }
    
    
    Response.innerHTML = formatResponse(response);
    
    conversation.appendChild(Response);

    if(ai_is_thinking){
        showThinkingBubble()
    }

    conversation.scrollTop = conversation.scrollHeight; // Scroll to the bottom

}

function showThinkingBubble() {
    ai_is_thinking = true

    const conversation = document.getElementById('conversation');
    const thinkingBubble = document.createElement('div');
    thinkingBubble.id = 'thinking-bubble';
    thinkingBubble.className = 'ai-thinking';
        
    thinkingBubble.innerHTML = '...';
    conversation.appendChild(thinkingBubble);
    conversation.scrollTop = conversation.scrollHeight; // Scroll to the bottom
}

function removeThinkingBubble() {
    document.querySelectorAll('.ai-thinking').forEach(element => {
        element.remove();
    });
}

// SocketIO events
socket.on('human_response', data => {
    //const transcriptionElement = document.getElementById('transcript');
    //transcriptionElement.innerText = data.text;
    displayResponse(data.text, isAIMessage = false, speech_final=data.speech_final, is_final=data.is_final);
    
});


socket.on('ai_response', data => {
    displayResponse(data.text, isAIMessage = true,speech_final=true, is_final=true);
    const audio = new Audio(data.audio_url);

    audio.play();

    audio.onended = function() {
        fetch(`/delete_file?filename=${encodeURIComponent(data.audio_url.split('/').pop())}`, { method: 'DELETE' })
            .then(response => {
                if (response.ok) {
                    console.log("File deleted successfully");
                } else {
                    console.error("Failed to delete file");
                }
            })
            .catch(error => {
                console.error("Error deleting file:", error);
            });
    };
});




