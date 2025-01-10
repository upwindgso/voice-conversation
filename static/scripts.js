console.log("scripts.js loaded");

let mediaRecorder;
let audioChunks = [];
const socket = io();  // Initialize WebSocket connection
let audioContext;
let isRecording = false;
const CHUNK_SIZE = 5000; // Send chunks every 5 seconds
let listenersAttached = false; // Flag to track if listeners are already attached

// Function to preserve newlines and render markdown
function formatResponse(text) {
    // Replace newlines with <br> tags
    text = text.replace(/\n/g, '<br>');
    return text;
}

// Display user input in real-time
function displayUserInput(transcript) {
    const conversation = document.getElementById('conversation');
    const userMessage = document.createElement('div');
    userMessage.className = 'user-message';
    userMessage.textContent = transcript;
    conversation.appendChild(userMessage);
    conversation.scrollTop = conversation.scrollHeight; // Scroll to the bottom
}

// Display AI response with formatting
function displayAIResponse(response) {
    const conversation = document.getElementById('conversation');
    const aiMessage = document.createElement('div');
    aiMessage.className = 'ai-message';
    aiMessage.textContent = response;
    conversation.appendChild(aiMessage);
    conversation.scrollTop = conversation.scrollHeight; // Scroll to the bottom
}

// Function to start recording
function startRecording() {
    console.log("startRecording called");
    if (!isRecording) {
        console.log("Starting recording...");
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                console.log("Audio stream accessed");

                // Set up audio context
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                console.log("AudioContext created:", audioContext.state);

                // Ensure the AudioContext is running
                if (audioContext.state === 'suspended') {
                    audioContext.resume().then(() => {
                        console.log("AudioContext resumed");
                    });
                }

                // Set up media recorder
                mediaRecorder = new MediaRecorder(stream, {
                    mimeType: 'audio/webm; codecs=opus',
                    audioBitsPerSecond: 64000 // Lower bitrate for smaller file size
                });

                // Start recording with a timeslice of 5 seconds
                mediaRecorder.start(CHUNK_SIZE);
                isRecording = true;

                // Change button color to soft/pastel red
                const recordButton = document.getElementById('recordButton');
                recordButton.style.backgroundColor = '#ff7f7f'; // Soft red
                recordButton.textContent = 'Stop';

                audioChunks = [];
                mediaRecorder.ondataavailable = function(e) {
                    console.log("Audio chunk available");
                    const audioChunk = e.data;

                    // Send the audio chunk to the server
                    socket.emit('audio_chunk', { audio: audioChunk });
                };

                mediaRecorder.onstop = function() {
                    console.log("Recording stopped");

                    // Reset button color and text
                    const recordButton = document.getElementById('recordButton');
                    recordButton.style.backgroundColor = '#555555'; // Normal color
                    recordButton.textContent = 'Record';
                    isRecording = false;

                    // Notify the server that recording has stopped
                    socket.emit('stop_recording');

                    // Disconnect the microphone
                    if (audioContext) {
                        audioContext.close();
                    }
                };
            })
            .catch(error => {
                console.error("Error accessing microphone:", error);
            });
    } else {
        console.log("Recording is already in progress");
    }
}

// Function to stop recording
function stopRecording() {
    if (isRecording) {
        mediaRecorder.stop();
    }
}

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOMContentLoaded event fired");

    // Ensure listeners are only attached once
    if (!listenersAttached) {
        console.log("Attaching event listeners...");

        // Event listener for the record button
        const recordButton = document.getElementById('recordButton');
        recordButton.addEventListener('click', function() {
            if (!isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        });

        // Event listener for the spacebar
        document.addEventListener('keydown', function(event) {
            if (event.code === 'Space') {
                event.preventDefault();  // Prevent default spacebar behavior (e.g., scrolling)
                event.stopPropagation(); // Stop event propagation
                if (!isRecording) {
                    startRecording();
                } else {
                    stopRecording();
                }
            }
        });

        listenersAttached = true; // Mark listeners as attached
    } else {
        console.log("Event listeners already attached");
    }
});

// Listen for transcriptions from the server
socket.on('transcription', (data) => {
    console.log("Transcription received:", data);
    if (data.error) {
        console.error("Error:", data.error);
    } else {
        // Display the transcription immediately
        displayUserInput(data.transcript);
    }
});

// Listen for responses from the server
socket.on('response', (data) => {
    console.log("Response received:", data);
    if (data.error) {
        console.error("Error:", data.error);
    } else {
        // Display the AI response
        displayAIResponse(data.response);

        // Play the audio response
        const audio = new Audio(data.audio_url);
        audio.play();

        // Delete the audio file after playback
        audio.onended = function() {
            console.log("Audio playback finished. Deleting file:", data.audio_url);
            fetch(`/delete_file?filename=${encodeURIComponent(data.audio_url)}`, {
                method: 'DELETE',
            })
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
    }
});