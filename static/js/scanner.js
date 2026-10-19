// QR Code Camera Scanner
// Uses the device camera to detect QR codes

const video   = document.getElementById('cameraPreview');
const startBtn = document.getElementById('startCamera');
let stream = null;
let scanning = false;

if (startBtn) {
  startBtn.addEventListener('click', async () => {
    if (scanning) {
      stopCamera();
      return;
    }
    await startCamera();
  });
}

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment' }   // back camera on phone
    });
    video.srcObject = stream;
    video.style.display = 'block';
    startBtn.textContent = '⏹ Stop Camera';
    scanning = true;

    // Use BarcodeDetector if available (Chrome/Android)
    if ('BarcodeDetector' in window) {
      const detector = new BarcodeDetector({ formats: ['qr_code'] });
      scanLoop(detector);
    } else {
      // Fallback: show manual input hint
      const hint = document.querySelector('.hint');
      if (hint) hint.textContent = 'Camera opened. Auto-detection not supported on this browser — please copy the token manually.';
    }
  } catch (err) {
    alert('Could not access camera: ' + err.message);
  }
}

async function scanLoop(detector) {
  if (!scanning) return;

  try {
    const barcodes = await detector.detect(video);
    if (barcodes.length > 0) {
      const data = barcodes[0].rawValue;
      // Extract token from URL (last URL segment)
      const parts = data.split('/');
      const token = parts[parts.length - 1];

      stopCamera();
      // Redirect to scan URL
      window.location.href = `/student/scan/${token}`;
      return;
    }
  } catch (e) { /* no barcode in frame */ }

  // Keep scanning
  requestAnimationFrame(() => scanLoop(detector));
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }
  video.style.display = 'none';
  if (startBtn) startBtn.textContent = '📷 Open Camera';
  scanning = false;
}
