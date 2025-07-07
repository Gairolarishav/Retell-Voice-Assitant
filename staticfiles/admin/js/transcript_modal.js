// function openTranscriptModal(leadId) {
//   const panel = document.getElementById("transcriptPanel");
//   const contentContainer = document.getElementById("transcriptContent");

//   fetch(`/retells/get-transcript/${leadId}/`)
//     .then(response => response.json())
//     .then(data => {
//       const raw = data.transcript || "No transcript found.";
//       contentContainer.innerHTML = ""; // Clear previous

//       const lines = raw.split('\n');

//       lines.forEach(line => {
//         let sender = 'agent'; // default
//         if (/^user[:\-]/i.test(line)) sender = 'user';
//         const messageText = line.replace(/^(user|agent)[:\-]\s*/i, '').trim();

//         const msgDiv = document.createElement("div");
//         msgDiv.className = `chat-message ${sender}`;
//         msgDiv.textContent = messageText;
//         contentContainer.appendChild(msgDiv);
//       });

//       // Slide-in animation
//       panel.style.display = "flex";
//       setTimeout(() => {
//         panel.classList.add("show");
//       }, 10);
//     });
// }


// function closeTranscriptPanel() {
//     const panel = document.getElementById("transcriptPanel");
//     panel.classList.remove("show");

//     setTimeout(() => {
//         panel.style.display = "none";
//     }, 300);
// }


let currentUserId = '';

function openTranscriptModal(userId) {
  currentUserId = userId;
  console.log('currentUserId==', currentUserId)
  loadAvailableSessions(userId);     // Populate dropdown
  fetchTranscript(userId);           // Show latest by default

  const panel = document.getElementById("transcriptPanel");
  panel.style.display = "flex";
  setTimeout(() => panel.classList.add("show"), 10);
}

function loadAvailableSessions(userId) {
  const dropdown = document.getElementById("transcriptDateDropdown");
  dropdown.innerHTML = '<option value="">Latest</option>';

  fetch(`/AI-Assistant/available-sessions/?user_id=${userId}`)
    .then(res => res.json())
    .then(data => {
      console.log("data===", data)
      const sessions = data.sessions || [];
      sessions.forEach(session => {
        const option = document.createElement("option");
        option.value = session.id;
        option.textContent = session.label;
        dropdown.appendChild(option);
      });
    });
}

function filterTranscriptByDate() {
  const selectedSessionId = document.getElementById("transcriptDateDropdown").value;
  fetchTranscript(currentUserId, selectedSessionId);
}

function fetchTranscript(userId, sessionId = "") {
  const contentContainer = document.getElementById("transcriptContent");
  contentContainer.innerHTML = "Loading...";

  const url = `/conversational_ai/transcript/?user_id=${userId}${sessionId ? `&session_id=${sessionId}` : ''}`;

  fetch(url)
    .then(res => res.json())
    .then(data => displayTranscript(data.transcript || []))
    .catch(err => {
      contentContainer.innerHTML = "Error loading transcript.";
      console.error("Transcript error:", err);
    });
}

function displayTranscript(transcript) {
  const contentContainer = document.getElementById("transcriptContent");
  contentContainer.innerHTML = "";

  if (transcript.length === 0) {
    contentContainer.innerHTML = "<p>No messages for this session.</p>";
    return;
  }

  transcript.forEach(entry => {
    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-message ${entry.source}`;
    msgDiv.textContent = entry.text;
    contentContainer.appendChild(msgDiv);
  });
}

function closeTranscriptPanel() {
  const panel = document.getElementById("transcriptPanel");
  panel.classList.remove("show");
  setTimeout(() => (panel.style.display = "none"), 300);
}
