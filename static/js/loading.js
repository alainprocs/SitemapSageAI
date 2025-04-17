const messages = [
    { text: 'Parsing your sitemap... 🌐', emoji: '🌐', progress: 15 },
    { text: 'Mapping your website structure... 🗺️', emoji: '🗺️', progress: 30 },
    { text: 'Clustering similar topics... 🧩', emoji: '🧩', progress: 50 },
    { text: 'Analyzing SEO signals... 📊', emoji: '📊', progress: 65 },
    { text: 'Generating article ideas... 💡', emoji: '💡', progress: 80 },
    { text: 'Almost done! Preparing results... 🚀', emoji: '🚀', progress: 95 }
];

let msgIdx = 0;
let progress = 0;
let targetProgress = 15; // First milestone
const progressMax = 98; // Don't fill to 100% until redirect
const animationSpeed = 0.3; // Slower animation speed

function cycleMessage() {
    msgIdx = (msgIdx + 1) % messages.length;
    const message = messages[msgIdx];
    document.getElementById('loading-message').textContent = message.text;
    document.getElementById('loading-emoji').textContent = message.emoji;
    // Set the next target progress milestone based on the message
    targetProgress = message.progress;
}

function advanceProgress() {
    // Gradually move toward target progress (smoother animation)
    if (progress < targetProgress && progress < progressMax) {
        // Advance by small random increments for smoother animation
        progress += Math.random() * animationSpeed + 0.1;
        
        // Don't exceed current target
        if (progress > targetProgress) {
            progress = targetProgress;
        }
        
        // Update the progress bar
        document.getElementById('progress-bar-inner').style.width = progress + '%';
    }
}

// More frequent but smaller updates for smoother animation
setInterval(advanceProgress, 100);

// Cycle messages less frequently
setInterval(cycleMessage, 4000);

// Optionally, you can expose a function to set progress to 100% before redirecting
window.finishLoading = function() {
    progress = 100;
    document.getElementById('progress-bar-inner').style.width = '100%';
};

// Poll the backend for job status
function getJobId() {
    const params = new URLSearchParams(window.location.search);
    return params.get('job_id');
}

function pollStatus() {
    const jobId = getJobId();
    if (!jobId) return;
    fetch(`/analyze_status?job_id=${jobId}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === 'done') {
                window.finishLoading();
                setTimeout(() => {
                    window.location.href = `/results?job_id=${jobId}`;
                }, 600);
            } else if (data.status === 'error') {
                window.finishLoading();
                setTimeout(() => {
                    window.location.href = `/results?job_id=${jobId}`;
                }, 600);
            } else {
                setTimeout(pollStatus, 2000);
            }
        })
        .catch(() => setTimeout(pollStatus, 2000));
}

pollStatus();
