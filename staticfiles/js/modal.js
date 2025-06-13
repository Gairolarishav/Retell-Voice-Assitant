document.addEventListener("DOMContentLoaded", () => {
    const demoLink = [...document.querySelectorAll(".nav-link")]
        .find(el => el.textContent.trim() === "Demo");
    if (demoLink) {
        console.log("demoLink===", demoLink)
        demoLink.addEventListener("click", (e) => {
            e.preventDefault();
            document.getElementById("demoModal").style.display = "block";
        });
    }
});
