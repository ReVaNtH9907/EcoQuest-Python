/**
 * EcoQuest — Camera-Based Mission Proof Capture Controller (camera_capture.js)
 *
 * Implements:
 * - Direct browser MediaDevices camera access (getUserMedia).
 * - Live camera preview viewfinder and camera toggle (front / rear).
 * - Canvas frame snapshotting for Before and After photo evidence.
 * - Video recording with MediaRecorder and 20-second duration limiter.
 * - Media preview and retake workflows.
 * - Browser Geolocation API integration (lat, lng, accuracy, timestamp).
 * - Form validation and async submission.
 * - Strictly NO file inputs, NO gallery pickers, NO drag-and-drop.
 */

document.addEventListener("DOMContentLoaded", () => {
    initCameraSystem();
    initGeolocation();
    initSubmissionForm();
});

// State storage for captured media
const mediaState = {
    beforePhotoData: null,
    afterPhotoData: null,
    videoData: null,
    activeStream: null,
    currentFacingMode: "environment", // Default to rear camera on mobile
    mediaRecorder: null,
    recordedChunks: [],
    recordTimerInterval: null,
    recordSecondsRemaining: 20,
    gpsData: {
        latitude: null,
        longitude: null,
        accuracy: null,
        timestamp: null,
        status: "pending",
    },
};

/**
 * Initialize camera viewport and media controls.
 */
async function initCameraSystem() {
    const videoElem = document.getElementById("camera-viewfinder");
    const startCamBtn = document.getElementById("start-camera-btn");
    const switchCamBtn = document.getElementById("switch-camera-btn");
    const captureBeforeBtn = document.getElementById("capture-before-btn");
    const captureAfterBtn = document.getElementById("capture-after-btn");
    const retakeBeforeBtn = document.getElementById("retake-before-btn");
    const retakeAfterBtn = document.getElementById("retake-after-btn");

    // Video recording elements
    const startRecordBtn = document.getElementById("start-record-btn");
    const stopRecordBtn = document.getElementById("stop-record-btn");
    const retakeVideoBtn = document.getElementById("retake-video-btn");

    if (!videoElem) return;

    // Check MediaDevices support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showCameraError("Your browser or device does not support direct MediaDevices camera access.");
        return;
    }

    // Auto-start camera
    startCamera();

    if (startCamBtn) {
        startCamBtn.addEventListener("click", () => startCamera());
    }

    if (switchCamBtn) {
        switchCamBtn.addEventListener("click", () => {
            mediaState.currentFacingMode =
                mediaState.currentFacingMode === "environment" ? "user" : "environment";
            startCamera();
        });
    }

    // Photo capture buttons
    if (captureBeforeBtn) {
        captureBeforeBtn.addEventListener("click", () => captureSnapshot("before"));
    }
    if (captureAfterBtn) {
        captureAfterBtn.addEventListener("click", () => captureSnapshot("after"));
    }
    if (retakeBeforeBtn) {
        retakeBeforeBtn.addEventListener("click", () => retakeSnapshot("before"));
    }
    if (retakeAfterBtn) {
        retakeAfterBtn.addEventListener("click", () => retakeSnapshot("after"));
    }

    // Video recording handlers
    if (startRecordBtn) {
        startRecordBtn.addEventListener("click", () => startVideoRecording());
    }
    if (stopRecordBtn) {
        stopRecordBtn.addEventListener("click", () => stopVideoRecording());
    }
    if (retakeVideoBtn) {
        retakeVideoBtn.addEventListener("click", () => retakeVideoEvidence());
    }
}

/**
 * Request camera access and attach stream to viewfinder.
 */
async function startCamera() {
    const videoElem = document.getElementById("camera-viewfinder");
    const cameraStatus = document.getElementById("camera-status-msg");
    const switchCamBtn = document.getElementById("switch-camera-btn");

    // Stop any existing stream
    stopActiveStream();

    try {
        if (cameraStatus) {
            cameraStatus.textContent = "Connecting to device camera...";
            cameraStatus.style.display = "block";
        }

        const constraints = {
            video: {
                facingMode: mediaState.currentFacingMode,
                width: { ideal: 1280 },
                height: { ideal: 720 },
            },
            audio: true, // Needed if user records video
        };

        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia(constraints);
        } catch (audioErr) {
            // If microphone permission is blocked, fallback to video-only
            console.warn("Microphone access unavailable, attempting video-only stream:", audioErr);
            stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: mediaState.currentFacingMode,
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                },
            });
        }

        mediaState.activeStream = stream;
        videoElem.srcObject = stream;
        await videoElem.play();

        if (cameraStatus) cameraStatus.style.display = "none";
        if (switchCamBtn) switchCamBtn.style.display = "inline-flex";

    } catch (err) {
        console.error("Camera access error:", err);
        showCameraError(
            err.name === "NotAllowedError"
                ? "Camera permission was denied. Please allow camera access in your browser settings to capture live mission proof."
                : `Camera unavailable (${err.message || err.name}).`
        );
    }
}

function stopActiveStream() {
    if (mediaState.activeStream) {
        mediaState.activeStream.getTracks().forEach((track) => track.stop());
        mediaState.activeStream = null;
    }
}

function showCameraError(msg) {
    const cameraStatus = document.getElementById("camera-status-msg");
    const videoContainer = document.getElementById("camera-viewport-card");
    if (cameraStatus) {
        cameraStatus.textContent = msg;
        cameraStatus.className = "camera-error-banner";
        cameraStatus.style.display = "block";
    }
    if (videoContainer) {
        videoContainer.classList.add("camera-disabled");
    }
}

/**
 * Capture frame from live video using an in-memory Canvas element.
 */
function captureSnapshot(type) {
    const videoElem = document.getElementById("camera-viewfinder");
    if (!videoElem || !videoElem.videoWidth || !videoElem.videoHeight) {
        alert("Camera stream is not ready yet. Please wait for the preview to initialize.");
        return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = videoElem.videoWidth;
    canvas.height = videoElem.videoHeight;
    const ctx = canvas.getContext("2d");

    // Draw video frame to canvas
    ctx.drawImage(videoElem, 0, 0, canvas.width, canvas.height);

    // Convert to JPEG DataURL with optimal compression
    const dataUrl = canvas.toDataURL("image/jpeg", 0.88);

    if (type === "before") {
        mediaState.beforePhotoData = dataUrl;
        document.getElementById("preview-before-img").src = dataUrl;
        document.getElementById("slot-before-empty").style.display = "none";
        document.getElementById("slot-before-filled").style.display = "block";
        document.getElementById("badge-before-status").textContent = "✓ Captured";
        document.getElementById("badge-before-status").className = "badge badge-success";
    } else if (type === "after") {
        mediaState.afterPhotoData = dataUrl;
        document.getElementById("preview-after-img").src = dataUrl;
        document.getElementById("slot-after-empty").style.display = "none";
        document.getElementById("slot-after-filled").style.display = "block";
        document.getElementById("badge-after-status").textContent = "✓ Captured";
        document.getElementById("badge-after-status").className = "badge badge-success";
    }

    // Record client timestamp
    mediaState.gpsData.timestamp = new Date().toISOString();
    updateSubmitButtonState();
}

/**
 * Retake snapshot.
 */
function retakeSnapshot(type) {
    if (type === "before") {
        mediaState.beforePhotoData = null;
        document.getElementById("preview-before-img").src = "";
        document.getElementById("slot-before-empty").style.display = "flex";
        document.getElementById("slot-before-filled").style.display = "none";
        document.getElementById("badge-before-status").textContent = "Required";
        document.getElementById("badge-before-status").className = "badge badge-warning";
    } else if (type === "after") {
        mediaState.afterPhotoData = null;
        document.getElementById("preview-after-img").src = "";
        document.getElementById("slot-after-empty").style.display = "flex";
        document.getElementById("slot-after-filled").style.display = "none";
        document.getElementById("badge-after-status").textContent = "Required";
        document.getElementById("badge-after-status").className = "badge badge-warning";
    }
    updateSubmitButtonState();
}

/**
 * Video Recording with MediaRecorder API.
 */
function startVideoRecording() {
    if (!mediaState.activeStream) {
        alert("Camera stream must be active to record video.");
        return;
    }

    if (!window.MediaRecorder) {
        alert("MediaRecorder is not supported in this browser.");
        return;
    }

    mediaState.recordedChunks = [];
    const mimeTypes = ["video/webm;codecs=vp8,opus", "video/webm", "video/mp4"];
    let chosenMime = "";
    for (const mime of mimeTypes) {
        if (MediaRecorder.isTypeSupported(mime)) {
            chosenMime = mime;
            break;
        }
    }

    try {
        const options = chosenMime ? { mimeType: chosenMime } : {};
        mediaState.mediaRecorder = new MediaRecorder(mediaState.activeStream, options);
    } catch (e) {
        console.warn("MediaRecorder creation fallback:", e);
        mediaState.mediaRecorder = new MediaRecorder(mediaState.activeStream);
    }

    mediaState.mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
            mediaState.recordedChunks.push(event.data);
        }
    };

    mediaState.mediaRecorder.onstop = () => {
        const blob = new Blob(mediaState.recordedChunks, {
            type: mediaState.mediaRecorder.mimeType || "video/webm",
        });

        // Convert blob to DataURL for submission
        const reader = new FileReader();
        reader.onloadend = () => {
            mediaState.videoData = reader.result;
            const videoPreview = document.getElementById("preview-video-player");
            videoPreview.src = URL.createObjectURL(blob);
            document.getElementById("slot-video-empty").style.display = "none";
            document.getElementById("slot-video-filled").style.display = "block";
            document.getElementById("badge-video-status").textContent = "✓ Recorded";
            document.getElementById("badge-video-status").className = "badge badge-success";
        };
        reader.readAsDataURL(blob);
    };

    mediaState.mediaRecorder.start();

    // UI state
    document.getElementById("start-record-btn").style.display = "none";
    document.getElementById("stop-record-btn").style.display = "inline-flex";
    document.getElementById("recording-indicator").style.display = "flex";

    // 20-second countdown timer
    mediaState.recordSecondsRemaining = 20;
    const timerElem = document.getElementById("recording-timer");
    if (timerElem) timerElem.textContent = `0:${mediaState.recordSecondsRemaining.toString().padStart(2, "0")}`;

    mediaState.recordTimerInterval = setInterval(() => {
        mediaState.recordSecondsRemaining--;
        if (timerElem) {
            timerElem.textContent = `0:${mediaState.recordSecondsRemaining.toString().padStart(2, "0")}`;
        }
        if (mediaState.recordSecondsRemaining <= 0) {
            stopVideoRecording();
        }
    }, 1000);
}

function stopVideoRecording() {
    if (mediaState.mediaRecorder && mediaState.mediaRecorder.state !== "inactive") {
        mediaState.mediaRecorder.stop();
    }
    clearInterval(mediaState.recordTimerInterval);

    document.getElementById("start-record-btn").style.display = "inline-flex";
    document.getElementById("stop-record-btn").style.display = "none";
    document.getElementById("recording-indicator").style.display = "none";
}

function retakeVideoEvidence() {
    mediaState.videoData = null;
    const videoPreview = document.getElementById("preview-video-player");
    if (videoPreview) videoPreview.src = "";
    document.getElementById("slot-video-empty").style.display = "flex";
    document.getElementById("slot-video-filled").style.display = "none";
    document.getElementById("badge-video-status").textContent = "Optional";
    document.getElementById("badge-video-status").className = "badge badge-neutral";
}

/**
 * Geolocation API Integration.
 */
function initGeolocation() {
    const statusText = document.getElementById("gps-status-text");
    const coordsText = document.getElementById("gps-coords-display");
    const gpsCard = document.getElementById("gps-status-card");

    if (!navigator.geolocation) {
        mediaState.gpsData.status = "unsupported";
        if (statusText) statusText.textContent = "GPS Unavailable on this device.";
        if (coordsText) coordsText.textContent = "Location coordinates marked unavailable.";
        if (gpsCard) gpsCard.classList.add("gps-warning");
        return;
    }

    if (statusText) statusText.textContent = "Requesting device GPS coordinates...";

    navigator.geolocation.getCurrentPosition(
        (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            const accuracy = position.coords.accuracy;

            mediaState.gpsData.latitude = lat;
            mediaState.gpsData.longitude = lng;
            mediaState.gpsData.accuracy = accuracy;
            mediaState.gpsData.timestamp = new Date(position.timestamp).toISOString();
            mediaState.gpsData.status = "acquired";

            if (statusText) {
                statusText.textContent = "GPS Coordinates Verified";
                statusText.style.color = "var(--color-primary-dark)";
            }
            if (coordsText) {
                coordsText.innerHTML = `
                    <strong>${lat.toFixed(5)}° N, ${lng.toFixed(5)}° E</strong> 
                    <span style="color: var(--color-text-secondary);">(Accuracy: ±${Math.round(accuracy)}m)</span>
                `;
            }
            if (gpsCard) {
                gpsCard.classList.add("gps-success");
            }
        },
        (error) => {
            mediaState.gpsData.status = "denied";
            let message = "Location unavailable.";
            if (error.code === error.PERMISSION_DENIED) {
                message = "Location permission was not granted. Evidence will proceed without GPS tags.";
            } else if (error.code === error.TIMEOUT) {
                message = "GPS request timed out. Location marked unavailable.";
            }

            if (statusText) {
                statusText.textContent = "Location Info Optional";
                statusText.style.color = "#92400E";
            }
            if (coordsText) coordsText.textContent = message;
            if (gpsCard) gpsCard.classList.add("gps-warning");
        },
        { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 }
    );
}

/**
 * Form Validation & Asynchronous Submit Controller.
 */
function initSubmissionForm() {
    const form = document.getElementById("mission-evidence-form");
    const descInput = document.getElementById("evidence-description");

    if (!form) return;

    if (descInput) {
        descInput.addEventListener("input", updateSubmitButtonState);
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        // Strict Validation Checks
        if (!mediaState.beforePhotoData) {
            alert("Please capture a live Before-Photo evidence before submitting.");
            return;
        }

        if (!mediaState.afterPhotoData) {
            alert("Please capture a live After-Photo evidence before submitting.");
            return;
        }

        const description = (descInput ? descInput.value : "").trim();
        if (description.length < 5) {
            alert("Please provide a brief description (at least 5 characters) of the fieldwork completed.");
            if (descInput) descInput.focus();
            return;
        }

        const submitBtn = document.getElementById("submit-evidence-btn");
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = `
                <span class="spinner-inline"></span> Submitting Camera Proof...
            `;
        }

        const missionSlug = form.getAttribute("data-mission-slug");
        const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute("content") : "";

        const payload = {
            before_photo: mediaState.beforePhotoData,
            after_photo: mediaState.afterPhotoData,
            video_data: mediaState.videoData,
            description: description,
            latitude: mediaState.gpsData.latitude,
            longitude: mediaState.gpsData.longitude,
            location_accuracy: mediaState.gpsData.accuracy,
            capture_timestamp: mediaState.gpsData.timestamp || new Date().toISOString(),
        };

        try {
            const response = await fetch(`/missions/${missionSlug}/submit`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify(payload),
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Stop camera stream
                stopActiveStream();
                // Redirect to receipt confirmation page
                window.location.href = data.redirect_url || `/missions/submissions/${data.submission_id}/confirmation`;
            } else {
                alert(`Submission error: ${data.message || data.error || 'Failed to submit evidence'}`);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = "🚀 Submit Mission Proof for Verification";
                }
            }
        } catch (networkErr) {
            console.error("Submission network error:", networkErr);
            alert("A network error occurred while uploading evidence. Please check your connection and try again.");
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = "🚀 Submit Mission Proof for Verification";
            }
        }
    });
}

function updateSubmitButtonState() {
    const submitBtn = document.getElementById("submit-evidence-btn");
    const descInput = document.getElementById("evidence-description");
    if (!submitBtn) return;

    const hasBefore = !!mediaState.beforePhotoData;
    const hasAfter = !!mediaState.afterPhotoData;
    const hasDesc = descInput && descInput.value.trim().length >= 5;

    if (hasBefore && hasAfter && hasDesc) {
        submitBtn.classList.remove("btn-disabled");
    }
}

// Cleanup camera stream when user navigates away
window.addEventListener("beforeunload", () => {
    stopActiveStream();
});
