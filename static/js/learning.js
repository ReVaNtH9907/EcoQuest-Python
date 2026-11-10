/**
 * EcoQuest — Learning Academy Client Controller (learning.js)
 * Manages client-side category filtering, quiz interactions, score calculation,
 * feedback rendering, and dynamic XP updates.
 */

document.addEventListener("DOMContentLoaded", () => {
    initCategoryFiltering();
    initQuizInteractivity();
});

/**
 * Filter lesson cards dynamically by category slug.
 */
function initCategoryFiltering() {
    const filterTabs = document.querySelectorAll(".category-tab[data-category]");
    const lessonCards = document.querySelectorAll(".lesson-card[data-category]");

    if (!filterTabs.length || !lessonCards.length) return;

    filterTabs.forEach((tab) => {
        tab.addEventListener("click", (e) => {
            e.preventDefault();
            const targetCat = tab.getAttribute("data-category");

            // Update active tab styling
            filterTabs.forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");

            // Filter cards
            let visibleCount = 0;
            lessonCards.forEach((card) => {
                const cardCat = card.getAttribute("data-category");
                if (targetCat === "all" || cardCat === targetCat) {
                    card.style.display = "flex";
                    visibleCount++;
                } else {
                    card.style.display = "none";
                }
            });

            // Update URL without page reload
            const url = new URL(window.location.href);
            if (targetCat === "all") {
                url.searchParams.delete("category");
            } else {
                url.searchParams.set("category", targetCat);
            }
            window.history.pushState({}, "", url);
        });
    });
}

/**
 * Interactive Quiz Controller: selection states, async submit, feedback display.
 */
function initQuizInteractivity() {
    const quizForm = document.getElementById("lesson-quiz-form");
    if (!quizForm) return;

    const optionLabels = quizForm.querySelectorAll(".quiz-option-label");
    const submitBtn = document.getElementById("submit-quiz-btn");
    const resultsContainer = document.getElementById("quiz-results-container");
    const lessonSlug = quizForm.getAttribute("data-lesson-slug");

    // Option selection visual feedback
    optionLabels.forEach((label) => {
        const radio = label.querySelector('input[type="radio"]');
        if (!radio) return;

        radio.addEventListener("change", () => {
            const questionCard = label.closest(".quiz-question-card");
            if (questionCard) {
                questionCard.querySelectorAll(".quiz-option-label").forEach((l) => {
                    l.classList.remove("selected");
                });
                label.classList.add("selected");
            }
        });
    });

    // Form submission handler
    quizForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        // Collect answers
        const questionCards = quizForm.querySelectorAll(".quiz-question-card");
        const answers = {};
        let unansweredCount = 0;

        questionCards.forEach((card) => {
            const qId = card.getAttribute("data-question-id");
            const checkedRadio = card.querySelector(`input[name="question_${qId}"]:checked`);
            if (checkedRadio) {
                answers[qId] = parseInt(checkedRadio.value, 10);
                card.style.borderColor = "var(--color-border)";
            } else {
                unansweredCount++;
                card.style.borderColor = "var(--color-error)";
            }
        });

        if (unansweredCount > 0) {
            alert(`Please answer all questions before submitting. (${unansweredCount} remaining)`);
            return;
        }

        // Disable submit button during request
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = "Evaluating Answers...";
        }

        try {
            // Retrieve CSRF token if present
            const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute("content") : "";

            const response = await fetch(`/learning/${lessonSlug}/quiz`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({ answers }),
            });

            if (response.status === 401) {
                const data = await response.json();
                const proceed = confirm("You must be logged in to submit quizzes and earn XP. Would you like to log in now?");
                if (proceed && data.login_url) {
                    window.location.href = data.login_url;
                } else if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = "Submit Quiz for Verification";
                }
                return;
            }

            const data = await response.json();
            if (!data.success && data.error) {
                alert(`Error: ${data.error}`);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = "Submit Quiz for Verification";
                }
                return;
            }

            // Render feedback and results
            renderQuizResults(data, quizForm, resultsContainer, submitBtn);

        } catch (err) {
            console.error("Quiz submission error:", err);
            // Fallback: submit standard form
            quizForm.submit();
        }
    });
}

/**
 * Display per-question explanations, score, and passing banner.
 */
function renderQuizResults(data, quizForm, resultsContainer, submitBtn) {
    // 1. Render Results Card Banner
    const isPassed = data.passed;
    const score = data.score;
    const correctCount = data.correct_answers;
    const totalCount = data.total_questions;
    const xpAwarded = data.xp_awarded;
    const alreadyEarned = data.already_earned;

    let bannerHtml = `
        <div class="quiz-results-card ${isPassed ? 'passed' : 'failed'}">
            <div class="results-icon">${isPassed ? '🎉' : '📚'}</div>
            <div class="results-title">${isPassed ? 'Quiz Passed! Congratulations!' : 'Quiz Incomplete — Needs 70%'}</div>
            <div class="results-score-display">${score}% Score</div>
            <p style="margin: 0; color: var(--color-text-secondary);">
                You answered <strong>${correctCount} of ${totalCount}</strong> questions correctly.
            </p>
    `;

    if (xpAwarded) {
        bannerHtml += `
            <div>
                <span class="results-xp-awarded">
                    ⭐ +${data.xp_amount} XP Added to Your Profile!
                </span>
            </div>
        `;
    } else if (alreadyEarned && isPassed) {
        bannerHtml += `
            <div style="margin-top: 0.5rem; font-size: 0.875rem; color: #047857; font-weight: 600;">
                ✓ 50 XP already claimed for this lesson.
            </div>
        `;
    } else if (!isPassed) {
        bannerHtml += `
            <div style="margin-top: 0.5rem; font-size: 0.875rem; color: #B45309; font-weight: 600;">
                Review the explanations below and retake the quiz to earn your 50 XP!
            </div>
        `;
    }

    bannerHtml += `
            <div class="quiz-action-bar">
                <button type="button" class="btn btn-secondary" onclick="resetQuiz()">
                    🔄 Retake Quiz
                </button>
                <a href="/learning/" class="btn btn-primary">
                    ← Explore More Lessons
                </a>
            </div>
        </div>
    `;

    if (resultsContainer) {
        resultsContainer.innerHTML = bannerHtml;
        resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // 2. Decorate each question card with feedback and explanations
    if (data.feedback && Array.isArray(data.feedback)) {
        data.feedback.forEach((item) => {
            const card = quizForm.querySelector(`.quiz-question-card[data-question-id="${item.question_id}"]`);
            if (!card) return;

            // Highlight options
            const options = card.querySelectorAll(".quiz-option-label");
            options.forEach((optLabel) => {
                const radio = optLabel.querySelector('input[type="radio"]');
                const optId = parseInt(radio.value, 10);

                if (optId === item.correct_option_id) {
                    optLabel.classList.add("is-correct");
                }
                if (optId === item.chosen_option_id && !item.is_correct) {
                    optLabel.classList.add("is-wrong");
                }
                // Disable radio
                radio.disabled = true;
            });

            // Reveal explanation
            let explanationBox = card.querySelector(".quiz-explanation-box");
            if (!explanationBox) {
                explanationBox = document.createElement("div");
                explanationBox.className = `quiz-explanation-box ${item.is_correct ? 'success' : 'warning'}`;
                card.appendChild(explanationBox);
            }
            explanationBox.innerHTML = `
                <strong>${item.is_correct ? '✓ Correct!' : '✗ Incorrect.'}</strong>
                <span>${item.explanation}</span>
            `;
        });
    }

    // Hide or update the submit button
    if (submitBtn) {
        submitBtn.style.display = "none";
    }
}

/**
 * Reset quiz form for retrying.
 */
window.resetQuiz = function() {
    const quizForm = document.getElementById("lesson-quiz-form");
    const resultsContainer = document.getElementById("quiz-results-container");
    const submitBtn = document.getElementById("submit-quiz-btn");

    if (!quizForm) return;

    if (resultsContainer) {
        resultsContainer.innerHTML = "";
    }

    const questionCards = quizForm.querySelectorAll(".quiz-question-card");
    questionCards.forEach((card) => {
        card.style.borderColor = "var(--color-border)";
        const options = card.querySelectorAll(".quiz-option-label");
        options.forEach((opt) => {
            opt.classList.remove("selected", "is-correct", "is-wrong");
            const radio = opt.querySelector('input[type="radio"]');
            if (radio) {
                radio.checked = false;
                radio.disabled = false;
            }
        });
        const explanationBox = card.querySelector(".quiz-explanation-box");
        if (explanationBox) {
            explanationBox.remove();
        }
    });

    if (submitBtn) {
        submitBtn.style.display = "inline-flex";
        submitBtn.disabled = false;
        submitBtn.innerHTML = "Submit Quiz for Verification";
    }

    quizForm.scrollIntoView({ behavior: "smooth", block: "start" });
};
