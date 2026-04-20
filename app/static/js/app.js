// Finess-for-Laure - client-side helpers
document.addEventListener("DOMContentLoaded", function () {
    // Highlight active nav link
    const currentPath = window.location.pathname;
    document.querySelectorAll(".navbar-nav .nav-link").forEach(function (link) {
        if (link.getAttribute("href") === currentPath) {
            link.classList.add("active");
        }
    });
});
