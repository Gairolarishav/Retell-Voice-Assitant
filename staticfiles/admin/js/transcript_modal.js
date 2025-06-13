function openTranscriptModal(leadId) {
    const panel = document.getElementById("transcriptPanel");

    fetch(`/retells/get-transcript/${leadId}/`)
        .then(response => response.json())
        .then(data => {
            const content = data.transcript || "No transcript found.";
            document.getElementById("transcriptContent").textContent = content;

            panel.style.display = "block";

            // Delay to allow CSS to animate
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
