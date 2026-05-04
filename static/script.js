// --- GLOBAL VARIABLES ---
let currentAttachments = [];
let currentThreadId = null;
let pendingImages = []; 
let uploadedFileNames = []; 

// Voice & Mic Variables
let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let currentAudio = null; 

document.addEventListener('DOMContentLoaded', function() {
    loadThreads();
    document.getElementById('fileUpload').addEventListener('change', handleFileUpload);
    
    // Detect clicks on any image inside the chat container to expand it
    document.getElementById('chatContainer').addEventListener('click', function(e) {
        if (e.target.tagName === 'IMG') {
            openImageModal(e.target.src);
        }
    });

    // Mic recording listener
    const micBtn = document.querySelector('.mic-btn');
    if (micBtn) {
        micBtn.addEventListener('click', toggleMicRecording);
    }
});

function filterThreads() {
    const input = document.getElementById('searchInput').value.toLowerCase();
    const threads = document.querySelectorAll('.thread-item');
    threads.forEach(thread => {
        const text = thread.textContent.toLowerCase();
        thread.style.display = text.includes(input) ? '' : 'none';
    });
}

async function loadThreads() {
    try {
        const response = await fetch('/api/threads');
        const data = await response.json();
        currentThreadId = data.current_thread;
        
        const threadsList = document.getElementById('threadsList');
        threadsList.innerHTML = '';
        
        data.threads.reverse().forEach(thread => {
            const threadItem = document.createElement('div');
            threadItem.className = 'thread-item';
            if (thread.id === currentThreadId) threadItem.classList.add('active');
            threadItem.textContent = thread.title;
            threadItem.onclick = () => switchThread(thread.id);
            threadsList.appendChild(threadItem);
        });
    } catch (error) { console.error('Error loading threads:', error); }
}

async function newChat() {
    try {
        const response = await fetch('/api/new-chat', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            currentThreadId = data.thread_id;
            document.getElementById('chatContainer').innerHTML = '';
            document.getElementById('filePreview').innerHTML = '';
            
            // Bring back the welcome screen
            const chatContainer = document.getElementById('chatContainer');
            if(document.getElementById('welcomeScreen')) {
                document.getElementById('welcomeScreen').style.display = 'flex';
            }
            
            pendingImages = [];
            uploadedFileNames = [];
            loadThreads();
        }
    } catch (error) { console.error('Error creating chat:', error); }
}

async function switchThread(threadId) {
    try {
        const response = await fetch(`/api/switch-thread/${threadId}`, { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            currentThreadId = threadId;
            const chatContainer = document.getElementById('chatContainer');
            chatContainer.innerHTML = '';
            
            data.messages.forEach(msg => {
                let finalContent = msg.content;
                // Render uploaded images beautifully using the markdown trick
                if (msg.attachments && msg.attachments.length > 0) {
                    msg.attachments.forEach(att => {
                        if (att.url) {
                            finalContent += `\n\n![Uploaded Image](${att.url})`;
                        }
                    });
                }
                addMessageToDOM(finalContent, msg.role, [], null, msg.attachments);
            });
            
            loadThreads();
        }
    } catch (error) { console.error('Error switching thread:', error); }
}

async function handleFileUpload(event) {
    const files = event.target.files;
    if (files.length === 0) return;
    
    const sendBtn = document.getElementById('sendBtn');
    const filePreview = document.getElementById('filePreview');
    
    sendBtn.disabled = true;
    filePreview.innerHTML = `
        <div class="status-indicator" style="margin-bottom: 5px;">
            <div class="spinner"></div>
            <span>Uploading & Processing RAG Knowledge Base...</span>
        </div>
    `;
    
    const formData = new FormData();
    for (let file of files) {
        formData.append('files', file);
    }
    
    try {
        const response = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await response.json();
        
        if (data.success) {
            for (let file of files) {
                currentAttachments.push({
                    name: file.name,
                    type: file.type,
                    url: file.type.startsWith('image/') ? URL.createObjectURL(file) : null
                });
            }
            renderAttachmentPreview();
        } else {
            filePreview.innerHTML = `<span style="color: red;">❌ Upload failed: ${data.error}</span>`;
        }
    } catch (error) {
        filePreview.innerHTML = `<span style="color: red;">❌ Upload failed to connect.</span>`;
    } finally {
        sendBtn.disabled = false;
        event.target.value = ''; 
    }
}

function renderAttachmentPreview() {
    const preview = document.getElementById('filePreview');
    preview.innerHTML = '';
    
    currentAttachments.forEach(att => {
        let icon = '📄';
        if (att.type.startsWith('video/')) icon = '🎥';
        else if (att.type.startsWith('image/')) icon = '🖼️';
        
        const badge = document.createElement('span');
        badge.className = 'attachment-badge preview-badge';
        badge.innerHTML = `${icon} ${att.name}`;
        preview.appendChild(badge);
    });
}

function parseAIResponse(text) {
    let processedText = text.replace(/\[DOWNLOAD_FILE:(.*?)\]/g, (match, path) => {
        const cleanPath = path.startsWith('/') ? path : '/' + path;
        return `<a href="${cleanPath}" class="download-btn" target="_blank"><i class="fas fa-download"></i> Download Generated File</a>`;
    });
    return marked.parse(processedText);
}

function addMessageToDOM(content, role, tools = [], agent = null, attachments = []) {
    const welcomeScreen = document.getElementById('welcomeScreen');
    if (welcomeScreen) welcomeScreen.style.display = 'none';

    const chatContainer = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const roleDiv = document.createElement('div');
    roleDiv.className = 'message-role';
    
    // Add the TTS play button to historical AI messages
    if (role === 'user') {
        roleDiv.textContent = 'You';
    } else {
        const safeContent = content.replace(/`/g, "'").replace(/"/g, '&quot;');
        roleDiv.innerHTML = `NextGen AI <button class="play-tts-btn" onclick="playAIVoice(this, \`${safeContent}\`)"><i class="fas fa-volume-up"></i></button>`;
    }
    
    messageDiv.appendChild(roleDiv);
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (attachments && attachments.length > 0 && role === 'user') {
        const attachmentContainer = document.createElement('div');
        attachmentContainer.className = 'chat-attachments-container';
        
        attachments.forEach(att => {
            if (!att.url) { 
                let icon = '📄';
                if (att.type && att.type.startsWith('video/')) icon = '🎥';
                
                const fileBox = document.createElement('div');
                fileBox.className = 'chat-file-box';
                fileBox.innerHTML = `<span class="file-icon">${icon}</span> <span class="file-name">${att.name}</span>`;
                attachmentContainer.appendChild(fileBox);
            }
        });
        contentDiv.appendChild(attachmentContainer);
    }
    
    const textSpan = document.createElement('div');
    textSpan.innerHTML = role === 'user' ? parseAIResponse(content) : parseAIResponse(content);
    contentDiv.appendChild(textSpan);
    
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

async function sendMessage(event) {
    event.preventDefault();
    const input = document.getElementById('messageInput');
    const rawMessage = input.value.trim();
    
    if (!rawMessage && currentAttachments.length === 0) return;
    
    const uiMessageText = rawMessage || "Please analyze this image.";
    addMessageToDOM(uiMessageText, 'user', [], null, [...currentAttachments]);

    let backendMessage = rawMessage;
    if (currentAttachments.length > 0) {
        const fileNames = currentAttachments.map(a => a.name).join(', ');
        backendMessage += `\n\n[SYSTEM CONTEXT: The user just uploaded the following files: ${fileNames}. 
        RULE 1 (Documents & Videos): PDFs, DOCX, PPTX, TXT, and MP4 files have been processed into the RAG database. Answer questions about them using your standard RAG retrieval.
        RULE 2 (Images): If the user uploaded an image (png, jpg, jpeg) and asks you to explain, analyze, or look at it, YOU MUST immediately execute the 'analyze_image_tool' and pass the exact filename. Do not ask for clarification, just use the tool!]`;
    }
    
    input.value = '';
    input.style.height = 'auto';
    document.getElementById('filePreview').innerHTML = '';
    currentAttachments = [];
    uploadedFileNames = [];
    
    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;
    
    const welcomeScreen = document.getElementById('welcomeScreen');
    if (welcomeScreen) welcomeScreen.style.display = 'none';

    const chatContainer = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message assistant`;
    
    const roleDiv = document.createElement('div');
    roleDiv.className = 'message-role';
    roleDiv.textContent = 'NextGen AI'; // Will update with TTS button when done
    messageDiv.appendChild(roleDiv);
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const statusDiv = document.createElement('div');
    statusDiv.className = 'status-indicator';
    statusDiv.innerHTML = '<div class="spinner"></div><span>Thinking...</span>';
    contentDiv.appendChild(statusDiv);
    
    const textContainer = document.createElement('div');
    textContainer.innerHTML = '<span class="typing-cursor">▌</span>';
    contentDiv.appendChild(textContainer);
    
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    let fullResponseText = "";
    let accumulatedTools = [];
    const selectedAgent = document.getElementById('agentSelect').value;
    const selectedTool = document.getElementById('toolSelect').value;
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: backendMessage,
                forced_agent: selectedAgent === 'auto' ? null : selectedAgent,
                forced_tool: selectedTool === 'none' ? null : selectedTool
            }) 
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); 

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.substring(6);
                    try {
                        const data = JSON.parse(dataStr);
                        
                        if (data.type === 'chunk') {
                            statusDiv.style.display = 'none'; 
                            fullResponseText += data.text;
                            textContainer.innerHTML = parseAIResponse(fullResponseText) + '<span class="typing-cursor">▌</span>';
                            chatContainer.scrollTop = chatContainer.scrollHeight;
                        } 
                        else if (data.type === 'tool') {
                            accumulatedTools.push(data.tool);
                            statusDiv.style.display = 'flex';
                            let toolName = data.tool.replace(/_/g, ' ');
                            statusDiv.innerHTML = `<div class="spinner"></div><span>Using ${toolName}...</span>`;
                            chatContainer.scrollTop = chatContainer.scrollHeight;
                        }
                        else if (data.type === 'done') {
                            statusDiv.remove(); 
                            textContainer.innerHTML = parseAIResponse(fullResponseText); 
                            
                            // Inject TTS Speaker Button now that text is complete
                            const safeContent = fullResponseText.replace(/`/g, "'").replace(/"/g, '&quot;');
                            roleDiv.innerHTML = `NextGen AI <button class="play-tts-btn" onclick="playAIVoice(this, \`${safeContent}\`)"><i class="fas fa-volume-up"></i></button>`;
                            
                            // Auto-play TTS Voice
                            const ttsBtn = messageDiv.querySelector('.play-tts-btn');
                            if (ttsBtn) playAIVoice(ttsBtn, fullResponseText);

                            if (data.images && data.images.length > 0) {
                                const imgGallery = document.createElement('div');
                                imgGallery.className = 'agent-image-gallery';
                                data.images.forEach(url => {
                                    const img = document.createElement('img');
                                    img.src = url;
                                    imgGallery.appendChild(img);
                                });
                                contentDiv.appendChild(imgGallery);
                            }
                            
                            if (accumulatedTools.length > 0 || (data.agent && data.agent !== "Supervisor" && data.agent !== "chatmodal")) {
                                const badgesDiv = document.createElement('div');
                                badgesDiv.className = 'badges-container';
                                
                                if (data.agent && data.agent !== "Supervisor" && data.agent !== "chatmodal") {
                                    const agentBadge = document.createElement('span');
                                    agentBadge.className = 'agent-badge';
                                    agentBadge.textContent = `🧠 ${data.agent.replace('_', ' ').toUpperCase()}`;
                                    badgesDiv.appendChild(agentBadge);
                                }
                                
                                accumulatedTools.forEach(tool => {
                                    const badge = document.createElement('span');
                                    badge.className = 'tool-badge';
                                    badge.textContent = `🔧 ${tool}`;
                                    badgesDiv.appendChild(badge);
                                });
                                messageDiv.appendChild(badgesDiv);
                            }

                            chatContainer.scrollTop = chatContainer.scrollHeight;

                            if (data.pending_email) {
                                setTimeout(() => {
                                    const emailText = `📧 DRAFT READY FOR APPROVAL\n\nTo: ${data.pending_email.to_email}\nSubject: ${data.pending_email.subject}\n\n${data.pending_email.body}\n\nDo you want to send this email right now?`;
                                    const isApproved = confirm(emailText);
                                    const input = document.getElementById('messageInput');
                                    
                                    if (isApproved) {
                                        input.value = "Yes, it looks perfect. Send it!";
                                    } else {
                                        const changes = prompt("Email halted. What changes would you like to make? (Leave blank to just cancel entirely)", "Make it more formal");
                                        if (changes) {
                                            input.value = `Update the email draft: ${changes}`;
                                        } else {
                                            input.value = "Cancel the email, I changed my mind.";
                                        }
                                    }
                                }, 500);
                            }
                        }
                        else if (data.type === 'error') {
                            statusDiv.remove(); 
                            textContainer.innerHTML += `<br>❌ Error: ${data.text}`;
                        }
                    } catch (err) {
                        console.error("Parse Error:", err, "Data:", dataStr);
                    }
                }
            }
        }
        loadThreads(); 
    } catch (error) {
        statusDiv.remove();
        textContainer.innerHTML = '❌ Error: Failed to connect to server.';
    } finally {
        sendBtn.disabled = false;
        input.focus();
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage(event);
    }
}

// --- THEME TOGGLE LOGIC ---
function toggleTheme() {
    document.body.classList.toggle('light-mode');
    const themeBtn = document.getElementById('themeToggleBtn');
    
    if (document.body.classList.contains('light-mode')) {
        themeBtn.classList.remove('fa-sun');
        themeBtn.classList.add('fa-moon');
    } else {
        themeBtn.classList.remove('fa-moon');
        themeBtn.classList.add('fa-sun');
    }
}

// --- IMAGE ENLARGE LOGIC ---
function openImageModal(imgSrc) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('enlargedImg');
    
    if (!imgSrc.includes('spinner')) {
        modal.style.display = 'flex';
        modalImg.src = imgSrc;
    }
}

function closeImageModal() {
    document.getElementById('imageModal').style.display = 'none';
}

// --- BROWSER MIC RECORDING LOGIC ---
async function toggleMicRecording() {
    const micBtn = document.querySelector('.mic-btn');
    const inputField = document.getElementById('messageInput');
    
    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
            
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                inputField.placeholder = "Transcribing with Groq Whisper...";
                
                const formData = new FormData();
                formData.append('audio', audioBlob, 'recording.webm');
                
                try {
                    const res = await fetch('/api/transcribe', { method: 'POST', body: formData });
                    const data = await res.json();
                    if (data.success && data.text.trim()) {
                        inputField.value = data.text;
                    }
                } catch (err) {
                    console.error("Transcription error", err);
                }
                inputField.placeholder = "Ask anything or upload files...";
            };
            
            mediaRecorder.start();
            isRecording = true;
            micBtn.classList.add('recording');
            inputField.placeholder = "Listening... Click mic again to stop.";
            
        } catch (err) {
            alert("Microphone access denied or not available. Ensure site has permission.");
            console.error(err);
        }
    } else {
        mediaRecorder.stop();
        isRecording = false;
        micBtn.classList.remove('recording');
    }
}

// --- TEXT TO SPEECH LOGIC ---
async function playAIVoice(btnElement, text) {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
        document.querySelectorAll('.play-tts-btn').forEach(btn => btn.classList.remove('playing'));
    }
    
    btnElement.classList.add('playing');
    
    try {
        const res = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });
        const data = await res.json();
        
        if (data.success) {
            currentAudio = new Audio(data.audio_url);
            currentAudio.play();
            currentAudio.onended = () => {
                btnElement.classList.remove('playing');
            };
        }
    } catch (err) {
        console.error("TTS Error", err);
        btnElement.classList.remove('playing');
    }
}