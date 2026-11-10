/* ============================================================
   EcoQuest — Core JavaScript
   ============================================================
   Handles: mobile navigation, modals, toast notifications,
            and interactive component behaviours.
   No external dependencies.
   ============================================================ */

document.addEventListener("DOMContentLoaded", function () {

    /* ---------------------------------------------------------
       Mobile Navigation Toggle
       --------------------------------------------------------- */
    const navToggle = document.getElementById("navbar-toggle");
    const navMobile = document.getElementById("navbar-mobile");

    if (navToggle && navMobile) {
        navToggle.addEventListener("click", function () {
            const isOpen = navMobile.classList.toggle("is-open");
            navToggle.classList.toggle("is-active", isOpen);
            navToggle.setAttribute("aria-expanded", String(isOpen));
        });

        // Close mobile menu when clicking a link
        navMobile.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                navMobile.classList.remove("is-open");
                navToggle.classList.remove("is-active");
                navToggle.setAttribute("aria-expanded", "false");
            });
        });

        // Close mobile menu on outside click
        document.addEventListener("click", function (e) {
            if (!navToggle.contains(e.target) && !navMobile.contains(e.target)) {
                navMobile.classList.remove("is-open");
                navToggle.classList.remove("is-active");
                navToggle.setAttribute("aria-expanded", "false");
            }
        });
    }


    /* ---------------------------------------------------------
       Modal System
       --------------------------------------------------------- */
    window.EcoQuest = window.EcoQuest || {};

    /**
     * Open a modal by its overlay element ID.
     * @param {string} modalId - The id of the .modal-overlay element.
     */
    window.EcoQuest.openModal = function (modalId) {
        const overlay = document.getElementById(modalId);
        if (!overlay) return;
        overlay.classList.add("is-open");
        document.body.style.overflow = "hidden";

        // Focus the first focusable element
        const focusable = overlay.querySelector(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable) focusable.focus();
    };

    /**
     * Close a modal by its overlay element ID.
     * @param {string} modalId - The id of the .modal-overlay element.
     */
    window.EcoQuest.closeModal = function (modalId) {
        const overlay = document.getElementById(modalId);
        if (!overlay) return;
        overlay.classList.remove("is-open");
        document.body.style.overflow = "";
    };

    // Close on overlay background click
    document.querySelectorAll(".modal-overlay").forEach(function (overlay) {
        overlay.addEventListener("click", function (e) {
            if (e.target === overlay) {
                overlay.classList.remove("is-open");
                document.body.style.overflow = "";
            }
        });
    });

    // Close on Escape key
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            document.querySelectorAll(".modal-overlay.is-open").forEach(function (overlay) {
                overlay.classList.remove("is-open");
            });
            document.body.style.overflow = "";
        }
    });

    // Close buttons inside modals
    document.querySelectorAll("[data-modal-close]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const overlay = btn.closest(".modal-overlay");
            if (overlay) {
                overlay.classList.remove("is-open");
                document.body.style.overflow = "";
            }
        });
    });


    /* ---------------------------------------------------------
       Toast Notification System
       --------------------------------------------------------- */
    let toastContainer = document.getElementById("toast-container");

    if (!toastContainer) {
        toastContainer = document.createElement("div");
        toastContainer.id = "toast-container";
        toastContainer.className = "toast-container";
        toastContainer.setAttribute("aria-live", "polite");
        document.body.appendChild(toastContainer);
    }

    /**
     * Show a toast notification.
     * @param {Object} options
     * @param {string} options.title     - Bold title text.
     * @param {string} options.message   - Body message.
     * @param {string} [options.type]    - 'success' | 'warning' | 'error' | 'info'
     * @param {number} [options.duration] - Auto-dismiss milliseconds (0 = manual).
     */
    window.EcoQuest.showToast = function (options) {
        var type     = options.type || "info";
        var duration = options.duration !== undefined ? options.duration : 5000;

        var icons = {
            success: "✓",
            warning: "⚠",
            error:   "✕",
            info:    "ℹ"
        };

        var toast = document.createElement("div");
        toast.className = "toast toast-" + type;
        toast.setAttribute("role", "alert");
        toast.innerHTML =
            '<span class="toast-icon">' + (icons[type] || "ℹ") + '</span>' +
            '<div class="toast-content">' +
                '<div class="toast-title">' + (options.title || "") + '</div>' +
                '<p class="toast-message">' + (options.message || "") + '</p>' +
            '</div>' +
            '<button class="toast-dismiss" aria-label="Dismiss">&times;</button>';

        // Dismiss on click
        toast.querySelector(".toast-dismiss").addEventListener("click", function () {
            dismissToast(toast);
        });

        toastContainer.appendChild(toast);

        // Auto dismiss
        if (duration > 0) {
            setTimeout(function () { dismissToast(toast); }, duration);
        }

        return toast;
    };

    function dismissToast(toast) {
        if (!toast || !toast.parentNode) return;
        toast.classList.add("is-dismissing");
        toast.addEventListener("animationend", function () {
            toast.remove();
        });
    }


    /* ---------------------------------------------------------
       Auto-dismiss Flash Messages
       --------------------------------------------------------- */
    document.querySelectorAll(".flash").forEach(function (flash) {
        setTimeout(function () {
            flash.style.transition = "opacity 0.3s ease, transform 0.3s ease";
            flash.style.opacity = "0";
            flash.style.transform = "translateY(-8px)";
            setTimeout(function () { flash.remove(); }, 300);
        }, 6000);
    });


    console.log("EcoQuest design system loaded.");
});
