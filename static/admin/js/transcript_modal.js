function openTranscriptModal(leadId) {
  const panel = document.getElementById("transcriptPanel");
  const contentContainer = document.getElementById("transcriptContent");

  fetch(`/retells/get-transcript/${leadId}/`)
    .then(response => response.json())
    .then(data => {
      const raw = data.transcript || "No transcript found.";
      contentContainer.innerHTML = ""; // Clear previous

      const lines = raw.split('\n');

      lines.forEach(line => {
        let sender = 'agent'; // default
        if (/^user[:\-]/i.test(line)) sender = 'user';
        const messageText = line.replace(/^(user|agent)[:\-]\s*/i, '').trim();

        const msgDiv = document.createElement("div");
        msgDiv.className = `chat-message ${sender}`;
        msgDiv.textContent = messageText;
        contentContainer.appendChild(msgDiv);
      });

      // Slide-in animation
      panel.style.display = "flex";
      setTimeout(() => {
        panel.classList.add("show");
      }, 10);
    });
}


function closeTranscriptPanel() {
    const panel = document.getElementById("transcriptPanel");
    panel.classList.remove("show");

    setTimeout(() => {
        panel.style.display = "none";
    }, 300);
}
