/* ============================================================
   EcoQuest — Authentication & User Profile Client Logic
   ============================================================
   Zero external dependencies.
   ============================================================ */

document.addEventListener("DOMContentLoaded", function () {

    /* ---------------------------------------------------------
       1. Password Visibility Toggle
       --------------------------------------------------------- */
    document.querySelectorAll(".password-toggle-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const targetId = btn.getAttribute("data-target");
            const input = document.getElementById(targetId);
            if (!input) return;

            const isPassword = input.type === "password";
            input.type = isPassword ? "text" : "password";

            // Toggle icon
            const svg = btn.querySelector("svg");
            if (svg) {
                if (isPassword) {
                    // Show eye-off icon
                    svg.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24M1 1l22 22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';
                    btn.setAttribute("aria-label", "Hide password");
                } else {
                    // Show eye icon
                    svg.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';
                    btn.setAttribute("aria-label", "Show password");
                }
            }
        });
    });

    /* ---------------------------------------------------------
       2. Avatar Image Preview & Validation
       --------------------------------------------------------- */
    const avatarInput = document.getElementById("profile_picture");
    const avatarPreview = document.getElementById("avatar-preview-img");

    if (avatarInput && avatarPreview) {
        avatarInput.addEventListener("change", function () {
            const file = this.files[0];
            if (!file) return;

            // Size check: max 5 MB
            if (file.size > 5 * 1024 * 1024) {
                alert("File size exceeds 5 MB. Please choose a smaller image.");
                this.value = "";
                return;
            }

            // Extension check
            const allowed = ["image/png", "image/jpeg", "image/jpg", "image/webp"];
            if (!allowed.includes(file.type)) {
                alert("Invalid image type. Please choose a PNG, JPG, or WebP image.");
                this.value = "";
                return;
            }

            const reader = new FileReader();
            reader.onload = function (e) {
                avatarPreview.src = e.target.result;
            };
            reader.readAsDataURL(file);
        });
    }

    /* ---------------------------------------------------------
       3. OTP Form Auto-Focus & Digit Formatting
       --------------------------------------------------------- */
    const otpInput = document.getElementById("otp_code");
    if (otpInput) {
        otpInput.focus();
        otpInput.addEventListener("input", function () {
            // Keep only numbers and max 6 digits
            this.value = this.value.replace(/[^0-9]/g, "").slice(0, 6);
        });
    }

    /* ---------------------------------------------------------
       4. Form Submit Loading Feedback
       --------------------------------------------------------- */
    document.querySelectorAll("form.auth-form").forEach(function (form) {
        form.addEventListener("submit", function () {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                const originalText = submitBtn.textContent;
                submitBtn.setAttribute("data-original-text", originalText);
                submitBtn.textContent = "Processing...";
                submitBtn.style.opacity = "0.75";
            }
        });
    });

});
