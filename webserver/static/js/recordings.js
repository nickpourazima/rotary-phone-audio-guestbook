// In your recordings.js file
function loadRecordings() {
  console.log("Starting to load recordings...");

  // Add a timestamp parameter to prevent caching
  fetch("/api/recordings?t=" + new Date().getTime())
    .then((response) => {
      console.log("API response status:", response.status);
      if (!response.ok) {
        throw new Error(`API returned status ${response.status}`);
      }
      return response.json();
    })
    .then((files) => {
      console.log("Files returned by API:", files);

      const recordingList = document.getElementById("recording-list");
      if (!recordingList) {
        console.error("recording-list element not found in DOM");
        return;
      }

      recordingList.innerHTML = "";

      if (!files || files.length === 0) {
        console.log("No files returned by API");
        // Display empty state message
        const emptyRow = document.createElement("tr");
        emptyRow.innerHTML = `
          <td colspan="5" class="py-8 text-center">
            <div class="flex flex-col items-center">
              <i class="fas fa-microphone-slash text-4xl text-gray-300 dark:text-gray-600 mb-3"></i>
              <p class="text-gray-500 dark:text-gray-400">No recordings yet.</p>
              <p class="text-sm text-gray-400 dark:text-gray-500 mt-1">Recordings will appear here when created.</p>
            </div>
          </td>
        `;
        recordingList.appendChild(emptyRow);

        // Hide the action buttons when there are no recordings
        document.getElementById('download-selected')?.classList.add("hidden");
        document.getElementById('delete-selected')?.classList.add("hidden");
      } else {
        // Show the action buttons when there are recordings
        document.getElementById('download-selected')?.classList.remove("hidden");
        document.getElementById('delete-selected')?.classList.remove("hidden");

        // Add recording items
        files.forEach((filename, index) => {
          console.log(`Creating item ${index + 1}/${files.length}: ${filename}`);
          try {
            const item = createRecordingItem(filename);
            recordingList.appendChild(item);
          } catch (err) {
            console.error(`Error creating item for ${filename}:`, err);
          }
        });
      }

      try {
        console.log("Setting up event listeners");
        setupEventListeners();
      } catch (err) {
        console.error("Error in setupEventListeners:", err);
      }

      try {
        // Initialize Plyr for all audio elements
        console.log("Initializing audio players");
        const audioElements = document.querySelectorAll('audio');
        console.log(`Found ${audioElements.length} audio elements`);

        const players = Array.from(audioElements).map(p => {
          // Ensure audio elements are set up for proper loading
          p.preload = "metadata";

          // Create and configure the Plyr instance with simplified controls
          // Remove the settings control from the options
          return new Plyr(p, {
            controls: ['play', 'progress', 'current-time', 'duration', 'mute', 'volume'],
            displayDuration: true,
            hideControls: false,
            invertTime: false,
            toggleInvert: false,
            seekTime: 5,
            tooltips: { controls: false, seek: false },
            fullscreen: { enabled: false },
            keyboard: { focused: true, global: false }
          });
        });

        improveAudioDurationDetection();
        console.log(`Initialized ${players.length} Plyr players`);
      } catch (err) {
        console.error("Error initializing audio players:", err);
      }
    })
    .catch((error) => {
      console.error("Error loading recordings:", error);

      // Show error in UI if toast function exists
      if (typeof showToast === 'function') {
        showToast("Failed to load recordings: " + error.message, "error");
      } else {
        console.error("showToast function not available");

        // Fallback error display if toast isn't available
        const recordingList = document.getElementById("recording-list");
        if (recordingList) {
          recordingList.innerHTML = `
            <tr>
              <td colspan="5" class="p-4 text-center text-red-600">
                <div class="flex flex-col items-center">
                  <i class="fas fa-exclamation-circle text-4xl mb-3"></i>
                  <p class="font-semibold">Error loading recordings</p>
                  <p class="text-sm mt-1">${error.message}</p>
                  <button onclick="loadRecordings()" class="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
                    Retry
                  </button>
                </div>
              </td>
            </tr>
          `;
        }
      }
    });
}

function improveAudioDurationDetection() {
  document.querySelectorAll('audio').forEach(audio => {
    // For WAV files specifically
    if (audio.src.toLowerCase().endsWith('.wav')) {
      // Try to force metadata loading
      audio.addEventListener('loadedmetadata', () => {
        // If duration is infinity or unusually small, try to fix it
        if (!isFinite(audio.duration) || audio.duration < 0.1) {
          console.log('Attempting to fix infinite duration for WAV file...');

          // Force a tiny play/pause to get Chrome to recalculate
          const playPromise = audio.play();
          if (playPromise !== undefined) {
            playPromise.then(() => {
              setTimeout(() => {
                audio.pause();
                console.log(`New duration after fix: ${audio.duration}`);
              }, 10);
            }).catch(err => {
              console.warn('Play attempt to fix duration failed:', err);
            });
          }
        }
      });

      // Add error handling
      audio.addEventListener('error', (e) => {
        console.error('Audio error:', e);
      });
    }
  });
}

function createRecordingItem(filename) {
  const row = document.createElement("tr");
  row.className =
    "recording-item border-b border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors duration-200";

  const dateTime = parseDateTime(filename);
  const formattedDate = moment(dateTime).format("MMMM D, YYYY [at] h:mm A");

  // Generate a random pastel color for the recording icon
  const hue = Math.floor(Math.random() * 360);
  const iconColor = `hsl(${hue}, 70%, 80%)`;

  row.innerHTML = `
      <td class="p-2 text-center"><input type="checkbox" class="recording-checkbox w-4 h-4" data-id="${filename}"></td>
      <td class="p-2">
        <div class="flex items-center">
          <div class="w-8 h-8 rounded-full flex items-center justify-center mr-3" style="background-color: ${iconColor}">
            <i class="fas fa-microphone text-white"></i>
          </div>
          <span contenteditable="true" class="recording-name font-semibold hover:bg-gray-200 dark:hover:bg-gray-700 p-1 rounded">${filename}</span>
        </div>
      </td>
      <td class="p-2">
        <audio class="audio-player" src="/recordings/${filename}"></audio>
      </td>
      <td class="p-2 recording-date text-sm text-gray-600 dark:text-gray-400">${formattedDate}</td>
      <td class="p-2">
        <button class="delete-button bg-red-500 hover:bg-red-600 text-white rounded-md px-3 py-2 flex items-center transition-colors duration-200 shadow-sm">
          <i class="fas fa-times mr-1"></i><span class="hidden sm:inline">Delete</span>
        </button>
      </td>
    `;

  row.dataset.filename = filename;
  return row;
}

function parseDateTime(filename) {
  const regex = /(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})/;
  const match = filename.match(regex);
  return match ? match[1] : null;
}

function setupEventListeners() {
  const selectAllCheckbox = document.getElementById("select-all");
  const downloadSelectedButton = document.getElementById("download-selected");
  const deleteSelectedButton = document.getElementById("delete-selected");
  const recordingItems = document.querySelectorAll(".recording-item");

  selectAllCheckbox.addEventListener("change", function () {
    const isChecked = this.checked;
    recordingItems.forEach((item) => {
      item.querySelector(".recording-checkbox").checked = isChecked;
      item.classList.toggle("selected", isChecked);
    });
  });

  downloadSelectedButton.addEventListener("click", function () {
    const selectedFiles = Array.from(
      document.querySelectorAll(".recording-checkbox:checked"),
    ).map((checkbox) => checkbox.closest(".recording-item").dataset.filename);

    if (selectedFiles.length === 0) {
      alert("Please select at least one recording to download.");
      return;
    }

    // Create a form to submit the selected files
    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/download-selected";

    selectedFiles.forEach((filename) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "files[]";
      input.value = filename;
      form.appendChild(input);
    });

    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
  });

  deleteSelectedButton.addEventListener("click", function() {
    const selectedItems = document.querySelectorAll('.recording-checkbox:checked');
    if (selectedItems.length === 0) {
      alert('Please select at least one recording to delete.');
      return;
    }

    if (confirm(`Are you sure you want to delete ${selectedItems.length} selected recording(s)?`)) {
      const idsToDelete = Array.from(selectedItems).map(checkbox => checkbox.dataset.id);

      fetch('/delete-recordings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ids: idsToDelete })
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          // Remove deleted items from the DOM
          selectedItems.forEach(checkbox => {
            checkbox.closest('tr').remove();
          });

          // Show success message
          if (typeof showToast === 'function') {
            showToast(`Deleted ${selectedItems.length} recording(s)`, 'success');
          }

          // Check if all recordings were deleted
          if (document.querySelectorAll('.recording-item').length === 0) {
            loadRecordings(); // Reload to show empty state
          }
        } else {
          throw new Error(data.message || 'Failed to delete recordings');
        }
      })
      .catch(error => {
        console.error('Error:', error);
        if (typeof showToast === 'function') {
          showToast('Error deleting recordings: ' + error.message, 'error');
        } else {
          alert('Error deleting recordings: ' + error.message);
        }
      });
    }
  });

  recordingItems.forEach((item) => {
    item.addEventListener("click", function (e) {
      if (e.target.type === "checkbox") return; // Don't toggle selection when clicking the checkbox
      if (e.target.closest('.plyr')) return; // Don't toggle selection when clicking the player
      if (e.target.closest('.delete-button')) return; // Don't toggle selection when clicking delete
      if (e.target.classList.contains('recording-name')) return; // Don't toggle when clicking the name

      const checkbox = this.querySelector(".recording-checkbox");
      checkbox.checked = !checkbox.checked;
      this.classList.toggle("selected", checkbox.checked);
      updateSelectAllCheckbox();
    });

    const checkbox = item.querySelector(".recording-checkbox");
    checkbox.addEventListener("change", function () {
      item.classList.toggle("selected", this.checked);
      updateSelectAllCheckbox();
    });
  });

  // Detect mobile devices to activate swipe only on mobile
  if (isMobileDevice()) {
    recordingItems.forEach((item) => {
      const hammer = new Hammer(item);
      hammer.on("swipeleft", function () {
        // Animate swipe left
        item.style.transition = "transform 0.3s ease-out";
        item.style.transform = "translateX(-100%)";
        setTimeout(() => {
          if (
            confirm(`Are you sure you want to delete ${item.dataset.filename}?`)
          ) {
            fetch(`/delete/${item.dataset.filename}`, { method: "POST" }).then(
              () => loadRecordings(),
            );
          } else {
            // Reset position if canceled
            item.style.transform = "translateX(0)";
          }
        }, 300); // Wait for animation to finish
      });
    });
  }

  // Handle click-to-delete for desktop users
  document.querySelectorAll(".delete-button").forEach((button) => {
    button.addEventListener("click", function (e) {
      e.stopPropagation(); // Prevent row click event
      const item = button.closest(".recording-item");
      if (
        confirm(`Are you sure you want to delete ${item.dataset.filename}?`)
      ) {
        fetch(`/delete/${item.dataset.filename}`, { method: "POST" }).then(() =>
          loadRecordings(),
        );
      }
    });
  });

  // Handle renaming the recording when the title is edited
  document.querySelectorAll(".recording-name").forEach((span) => {
    span.addEventListener("blur", function () {
      const newFilename = span.innerText.trim();
      const oldFilename = span.closest(".recording-item").dataset.filename;
      if (newFilename !== oldFilename) {
        // Send a request to rename the file
        fetch(`/rename/${oldFilename}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ newFilename }),
        })
          .then(() => {
            loadRecordings();
          })
          .catch((err) => {
            console.error("Rename error:", err);
            alert("Failed to rename the file.");
          });
      }
    });
  });
}

function updateSelectAllCheckbox() {
  const selectAllCheckbox = document.getElementById("select-all");
  const allCheckboxes = document.querySelectorAll(".recording-checkbox");
  const allChecked = Array.from(allCheckboxes).every(
    (checkbox) => checkbox.checked,
  );
  selectAllCheckbox.checked = allChecked;
}

function isMobileDevice() {
  return /Mobi|Android/i.test(navigator.userAgent);
}

// Initialize recordings on page load
document.addEventListener("DOMContentLoaded", function () {
  loadRecordings();
});