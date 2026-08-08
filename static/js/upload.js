document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const uploadForm = document.getElementById('uploadForm');
  const fileDetails = document.getElementById('fileDetails');
  const fileNameDisplay = document.getElementById('fileNameDisplay');
  const progressBarContainer = document.getElementById('progressBarContainer');
  const progressBarFill = document.getElementById('progressBarFill');
  const uploadStatus = document.getElementById('uploadStatus');

  if (!dropZone || !fileInput || !uploadForm) return;

  // Open file dialog on zone click
  dropZone.addEventListener('click', () => fileInput.click());

  // Highlight drop zone on drag over
  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('dragover');
    }, false);
  });

  // Handle dropped files
  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
      fileInput.files = files;
      handleSelectedFile(files[0]);
    }
  });

  // Handle file select change
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      handleSelectedFile(fileInput.files[0]);
    }
  });

  function handleSelectedFile(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      alert('Please select a valid .csv file format.');
      fileInput.value = '';
      if (fileDetails) fileDetails.style.display = 'none';
      return;
    }
    if (fileNameDisplay) {
      fileNameDisplay.textContent = `Selected File: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    }
    if (fileDetails) fileDetails.style.display = 'block';
  }

  // Handle Form Submission with progress bar
  uploadForm.addEventListener('submit', (e) => {
    if (!fileInput.files || fileInput.files.length === 0) {
      e.preventDefault();
      alert('Please select a CSV dataset to upload.');
      return;
    }
    if (progressBarContainer) progressBarContainer.style.display = 'block';
    if (progressBarFill) progressBarFill.style.width = '70%';
    if (uploadStatus) uploadStatus.textContent = 'Processing dataset with BloomWatch Machine Learning Engine...';
  });
});
