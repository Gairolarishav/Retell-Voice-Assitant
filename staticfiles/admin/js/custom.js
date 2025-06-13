document.addEventListener("DOMContentLoaded", function () {
    const demoLink = [...document.querySelectorAll(".nav-link")].find(link => link.textContent.trim() === "Demo");

    if (demoLink) {
        demoLink.addEventListener("click", function (e) {
            e.preventDefault();
            const modal = document.getElementById("demoModal");
            if (modal) {
                modal.style.display = "block";
            }
        });
    }

    const closeBtn = document.getElementById("closeModal");
    if (closeBtn) {
        closeBtn.addEventListener("click", function () {
            const modal = document.getElementById("demoModal");
            if (modal) {
                modal.style.display = "none";
            }
        });
    }
});
