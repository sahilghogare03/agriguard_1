// static/js/script.js

const fileInput = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const previewCard = document.getElementById("preview-card");
const imagePreview = document.getElementById("image-preview");
const fileName = document.getElementById("file-name");
const predictBtn = document.getElementById("predict-btn");
const clearBtn = document.getElementById("clear-image");

const errorBanner = document.getElementById("error-banner");
const errorMessage = document.getElementById("error-message");

const loadingState = document.getElementById("loading-state");
const resultsSection = document.getElementById("results-section");

let selectedFile = null;


function checkAuthSession() {
    fetch('/api/auth/user')
        .then(res => res.json())
        .then(data => {
            const authBox = document.getElementById('auth-buttons');
            if (authBox && data.logged_in && data.user) {
                const isAdmin = data.user.email && data.user.email.toLowerCase() === 'admin123@gmail.com';
                const adminBtn = isAdmin ? `<a href="/admin" class="bg-amber-100 text-amber-900 border border-amber-300 px-2.5 py-1 rounded-full text-xs font-bold hover:bg-amber-600 hover:text-white transition-colors flex items-center gap-1"><span class="material-symbols-outlined text-xs">admin_panel_settings</span> Admin Panel</a>` : '';

                authBox.innerHTML = `
                    <div class="flex items-center gap-2 bg-surface-container px-3 py-1.5 rounded-full text-xs font-bold border border-outline-variant">
                        <span class="material-symbols-outlined text-secondary text-sm">account_circle</span>
                        <span class="text-primary">${data.user.name || data.user.email}</span>
                        ${adminBtn}
                        <a href="/logout" class="text-error hover:underline ml-1 font-semibold">Logout</a>
                    </div>
                `;
            }
        })
        .catch(() => { });
}
document.addEventListener('DOMContentLoaded', checkAuthSession);

function hideError() {
    if (errorBanner) {
        errorBanner.classList.add("hidden");
    }
}

function showError(msg) {
    if (errorMessage) {
        errorMessage.innerText = msg;
    }
    if (errorBanner) {
        errorBanner.classList.remove("hidden");
    }
}


// -------------------------
// Image Preview
// -------------------------

fileInput.addEventListener("change", function () {

    selectedFile = this.files[0];

    if (!selectedFile)
        return;

    hideError();

    const reader = new FileReader();

    reader.onload = function (e) {

        imagePreview.src = e.target.result;

        fileName.innerHTML = selectedFile.name;

        dropZone.classList.add("hidden");

        previewCard.classList.remove("hidden");

        resultsSection.classList.add("hidden");

    };

    reader.readAsDataURL(selectedFile);

});


// -------------------------
// Clear Image
// -------------------------

clearBtn.addEventListener("click", function () {

    fileInput.value = "";

    selectedFile = null;

    imagePreview.src = "";

    hideError();

    previewCard.classList.add("hidden");

    resultsSection.classList.add("hidden");

    dropZone.classList.remove("hidden");

});


// -------------------------
// Drag & Drop
// -------------------------

dropZone.addEventListener("dragover", function (e) {

    e.preventDefault();

});

dropZone.addEventListener("drop", function (e) {

    e.preventDefault();

    const files = e.dataTransfer.files;

    if (files.length) {

        fileInput.files = files;

        fileInput.dispatchEvent(new Event("change"));

    }

});


// -------------------------
// Prediction
// -------------------------

predictBtn.addEventListener("click", function () {

    if (!selectedFile) {

        alert("Please select an image.");

        return;

    }

    hideError();

    loadingState.classList.remove("hidden");

    resultsSection.classList.add("hidden");

    const formData = new FormData();

    formData.append("image", selectedFile);

    fetch("/predict", {

        method: "POST",

        body: formData

    })

        .then(response => response.json())

        .then(data => {

            loadingState.classList.add("hidden");

            if (data.error) {

                showError(data.error);

                alert(data.error);

                return;

            }

            hideError();

            // Disease Name

            document.getElementById("disease-name").innerHTML =
                data.disease;

            // Confidence

            document.getElementById("confidence").innerHTML =
                data.confidence + "%";

            // Description

            document.getElementById("description").innerHTML =
                data.description;

            // Treatment

            document.getElementById("treatment").innerHTML =
                data.treatment;

            // Prevention

            document.getElementById("prevention").innerHTML =
                data.prevention;

            // Health Status

            if (data.disease.toLowerCase().includes("healthy")) {

                document.getElementById("health-status").innerHTML =
                    "Healthy";

            }
            else {

                document.getElementById("health-status").innerHTML =
                    "Diseased";

            }

            // Progress Bar

            document.getElementById("confidence-bar").style.width =
                data.confidence + "%";

            latestScanData = data;
            resultsSection.classList.remove("hidden");

            resultsSection.scrollIntoView({

                behavior: "smooth"

            });

        })

        .catch(error => {

            loadingState.classList.add("hidden");

            showError("An error occurred while processing the image. Please try again.");

            console.error(error);

        });

});

// -------------------------
// PDF Diagnostic Report Generator
// -------------------------
let latestScanData = null;

function downloadPDFReport(customData) {
    const reportData = customData || latestScanData;
    if (!reportData) {
        alert("No diagnostic scan data available for report generation.");
        return;
    }

    const diseaseName = (reportData.disease || 'Unknown').replace(/_/g, ' ');
    const healthStatus = reportData.health_status || (diseaseName.toLowerCase().includes('healthy') ? 'Healthy' : 'Diseased');
    const isHealthy = healthStatus === 'Healthy';
    const statusColor = isHealthy ? '#1f6d1a' : '#ba1a1a';
    const statusBg = isHealthy ? '#e8f5e9' : '#ffebee';
    const confidence = reportData.confidence || 0;
    const dateStr = reportData.created_at ? new Date(reportData.created_at).toLocaleString() : new Date().toLocaleString();
    const imgSrc = reportData.image ? (reportData.image.startsWith('http') ? reportData.image : '/' + reportData.image) : '';

    const container = document.createElement('div');
    container.style.width = '700px';
    container.style.padding = '20px 25px';
    container.style.boxSizing = 'border-box';
    container.style.fontFamily = "Helvetica, Arial, sans-serif";
    container.style.color = '#191c1d';
    container.style.backgroundColor = '#ffffff';

    container.innerHTML = `
        <div style="border-bottom: 2px solid #012d1d; padding-bottom: 10px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: flex-end;">
            <div>
                <h1 style="color: #012d1d; margin: 0; font-size: 20px; font-weight: bold;">🌱 AgriGuard AI Diagnostic Report</h1>
                <p style="color: #414844; margin: 3px 0 0 0; font-size: 11px;">Official Crop Pathology & Botanical AI Analysis</p>
            </div>
            <div style="text-align: right;">
                <p style="margin: 0; font-size: 11px; font-weight: bold; color: #012d1d;">REPORT ID: #AG-${Math.floor(100000 + Math.random() * 900000)}</p>
                <p style="margin: 2px 0 0 0; font-size: 10px; color: #717973;">Date: ${dateStr}</p>
            </div>
        </div>

        <div style="display: flex; gap: 16px; margin-bottom: 14px; align-items: stretch;">
            ${imgSrc ? `
            <div style="width: 140px; height: 120px; flex-shrink: 0; border: 1px solid #c1c8c2; border-radius: 8px; overflow: hidden; background: #000;">
                <img src="${imgSrc}" style="width: 100%; height: 100%; object-fit: cover;" />
            </div>` : ''}
            
            <div style="flex-grow: 1; background: #f8f9fa; border: 1px solid #c1c8c2; border-radius: 8px; padding: 12px 16px; border-left: 5px solid ${statusColor}; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 10px; color: #717973; text-transform: uppercase; font-weight: bold;">Detected Crop Condition</span>
                        <span style="background-color: ${statusBg}; color: ${statusColor}; padding: 3px 10px; border-radius: 10px; font-weight: bold; font-size: 11px; text-transform: uppercase;">
                            ${healthStatus.toUpperCase()}
                        </span>
                    </div>
                    <h2 style="margin: 0; color: #012d1d; font-size: 18px; font-weight: bold;">${diseaseName}</h2>
                </div>

                <div style="margin-top: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span style="font-size: 10px; color: #717973; font-weight: bold;">AI Prediction Confidence</span>
                        <span style="font-size: 12px; font-weight: bold; color: #012d1d;">${confidence}%</span>
                    </div>
                    <div style="width: 100%; background: #e7e8e9; height: 7px; border-radius: 4px; overflow: hidden;">
                        <div style="width: ${confidence}%; background: ${statusColor}; height: 100%;"></div>
                    </div>
                </div>
            </div>
        </div>

        <div style="margin-bottom: 12px; background: #ffffff; border: 1px solid #e7e8e9; border-radius: 6px; padding: 10px 14px;">
            <h3 style="color: #012d1d; font-size: 11px; font-weight: bold; margin: 0 0 4px 0; text-transform: uppercase;">
                📋 Diagnostic Description & Symptoms
            </h3>
            <p style="margin: 0; font-size: 11px; color: #414844; line-height: 1.5;">${reportData.description || 'No detailed description available.'}</p>
        </div>

        <div style="margin-bottom: 12px; background: #e8f5e9; border: 1px solid #c8e6c9; border-radius: 6px; padding: 10px 14px; border-left: 4px solid #1f6d1a;">
            <h3 style="color: #1f6d1a; font-size: 11px; font-weight: bold; margin: 0 0 4px 0; text-transform: uppercase;">
                🧪 Recommended Immediate Treatment Protocol
            </h3>
            <p style="margin: 0; font-size: 11px; color: #1b5e20; line-height: 1.5; font-weight: 500;">${reportData.treatment || 'No chemical or organic treatment required.'}</p>
        </div>

        <div style="margin-bottom: 16px; background: #ffffff; border: 1px solid #e7e8e9; border-radius: 6px; padding: 10px 14px;">
            <h3 style="color: #012d1d; font-size: 11px; font-weight: bold; margin: 0 0 4px 0; text-transform: uppercase;">
                🛡️ Long-Term Prevention & Management Guidelines
            </h3>
            <p style="margin: 0; font-size: 11px; color: #414844; line-height: 1.5;">${reportData.prevention || 'Maintain standard agricultural sanitation and crop rotation.'}</p>
        </div>

        <div style="border-top: 1px solid #c1c8c2; padding-top: 10px; display: flex; justify-content: space-between; align-items: center; font-size: 9px; color: #717973;">
            <div>
                <p style="margin: 0; font-weight: bold; color: #012d1d;">AgriGuard AI Pathology Neural Engine v4.2</p>
                <p style="margin: 1px 0 0 0;">Validated against PlantVillage Deep Learning Dataset</p>
            </div>
            <div style="text-align: right;">
                <p style="margin: 0; font-weight: bold; color: #1f6d1a;">✓ Verified Electronic Diagnostic Certificate</p>
            </div>
        </div>
    `;

    const opt = {
        margin: [6, 6, 6, 6],
        filename: `AgriGuard_Report_${diseaseName.replace(/\s+/g, '_')}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, logging: false },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    if (window.html2pdf) {
        html2pdf().set(opt).from(container).save();
    } else {
        alert("PDF generator library loading. Please click again.");
    }
}