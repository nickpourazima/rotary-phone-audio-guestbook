function loadRecordings() {
  fetch("/api/recordings")
    .then((response) => response.json())
    .then((files) => {
      const recordingList = document.getElementById("recording-list");
      recordingList.innerHTML = "";

      if (files.length === 0) {
        // Display an empty state message
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

        // Hide the download button when there are no recordings
        document.getElementById("download-selected").classList.add("hidden");
      } else {
        // Show the download button when there are recordings
        document.getElementById("download-selected").classList.remove("hidden");

        // Add recording items
        files.forEach((filename) => {
          const item = createRecordingItem(filename);
          recordingList.appendChild(item);
        });
      }

      setupEventListeners();

      // Initialize Plyr for all audio elements
      const players = Array.from(document.querySelectorAll('audio')).map(p => {
        // Ensure audio elements are set up for proper loading
        p.preload = "metadata";

        // Create and configure the Plyr instance
        const player = new Plyr(p, {
          controls: ['play', 'progress', 'current-time', 'duration'],
          displayDuration: true,
          hideControls: false,
          invertTime: false,
          toggleInvert: false,
          seekTime: 5,
          tooltips: { controls: true, seek: true },
          // Plyr settings to improve seeking behavior
          fullscreen: { enabled: false },
          seekTime: 1,
          keyboard: { focused: true, global: false }
        });

        // Handle special events for better Chrome compatibility
        player.on('loadedmetadata', () => {
          console.log(`Player loaded metadata, duration: ${p.duration}`);
        });

        player.on('error', (error) => {
          console.error('Player error:', error);
        });

        return player;
      });

      improveAudioDurationDetection();

      console.log(`Initialized ${players.length} Plyr players`);
    })
    .catch((error) => {
      console.error("Error loading recordings:", error);
      showToast("Failed to load recordings.", "error");
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
      <td class="p-2 text-center"><input type="checkbox" class="recording-checkbox w-4 h-4"></td>
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