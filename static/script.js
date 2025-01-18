const socket = io();

let mediaRecorder;
let audioChunks = [];

// Initialize MediaRecorder
navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
        console.log("media init")
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = event => {
            console.log("ondataavailable")
            audioChunks.push(event.data);
        };
        mediaRecorder.onstop = () => {
            
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm; codecs=opus' });
            console.log("onstop")
            socket.emit('audio_chunk', { chunk: audioBlob });
            console.log("audio_chunk emitted")
            audioChunks = [];
        };
    })
    .catch(error => {
        console.error('Microphone access denied:', error);
    });

// Record button functionality
const recordButton = document.getElementById('record-button');
recordButton.addEventListener('click', () => {
    if (mediaRecorder.state === 'inactive') {
        mediaRecorder.start();
        recordButton.classList.add('active');
        recordButton.innerText = 'Press space to STOP';
    } else {
        setTimeout(() => {
            mediaRecorder.stop();
            recordButton.classList.remove('active');
            recordButton.innerText = 'Press space to RECORD';
        }, 500);  // 1000 milliseconds = 1 second
    }
});

// Spacebar functionality
document.addEventListener('keydown', event => {
    if (event.code === 'Space' && mediaRecorder) {
        if (mediaRecorder.state === 'inactive') {
            mediaRecorder.start();
            recordButton.classList.add('active');
            recordButton.innerText = 'Press space to STOP';
        } else {
            setTimeout(() => {
                mediaRecorder.stop();
                recordButton.classList.remove('active');
                recordButton.innerText = 'Press space to RECORD';
            }, 500);  // 1000 milliseconds = 1 second
        }
    }
});

// Function to preserve newlines and render markdown
function formatResponse(text) {
    text = text.replace(/\n/g, '<br>');
    return text;
}


// Append to transcript
function displayResponse(response, isAIMessage = false) {
    hideThinkingBubble();
    console.log(response + ' - ' + isAIMessage)

    const conversation = document.getElementById('conversation');
    const Response = document.createElement('div');

    if (isAIMessage){
        Response.className = 'ai-message';
    } else {
        Response.className = 'user-message';
    }
    
    Response.innerHTML = formatResponse(response);
    conversation.appendChild(Response);

    if(isAIMessage == false){
        showThinkingBubble()
    };
    conversation.scrollTop = conversation.scrollHeight; // Scroll to the bottom
}

function showThinkingBubble() {

        const conversation = document.getElementById('conversation');
        const thinkingBubble = document.createElement('div');
        thinkingBubble.id = 'thinking-bubble';
        thinkingBubble.className = 'ai-thinking';
            
        thinkingBubble.innerHTML = '...';
        conversation.appendChild(thinkingBubble);
        conversation.scrollTop = conversation.scrollHeight; // Scroll to the bottom
    }

function hideThinkingBubble() {
    document.querySelectorAll('.ai-thinking').forEach(element => {
        element.style.display = 'none';
    });
}

// SocketIO events
socket.on('transcription', data => {
    //const transcriptionElement = document.getElementById('transcript');
    //transcriptionElement.innerText = data.text;
    displayResponse(data.text, isAIMessage = false);
    
});

socket.on('ai_response', data => {
    displayResponse(data.text, isAIMessage = true);
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




