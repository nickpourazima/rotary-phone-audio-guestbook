function loadRecordings() {
  fetch("/api/recordings")
    .then((response) => response.json())
    .then((files) => {
      const recordingList = document.getElementById("recording-list");
      recordingList.innerHTML = "";
      files.forEach((filename) => {
        const item = createRecordingItem(filename);
        recordingList.appendChild(item);
      });
      setupEventListeners();

      // Ensure all elements are properly visible
      console.log("Recordings loaded: " + files.length);
      document.querySelectorAll(".delete-button").forEach(btn => {
        console.log("Delete button styled");
        btn.style.display = "flex";
        btn.style.visibility = "visible";
      });
    })
    .catch(error => {
      console.error("Error loading recordings:", error);
    });
}

function createRecordingItem(filename) {
  const row = document.createElement("tr");
  row.className =
    "recording-item border-b border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800";

  const dateTime = parseDateTime(filename);
  const formattedDate = moment(dateTime).format("MMMM D, YYYY [at] h:mm A");

  row.innerHTML = `
      <td class="p-2"><input type="checkbox" class="recording-checkbox"></td>
      <td class="p-2"><span contenteditable="true" class="recording-name font-semibold hover:bg-gray-200 dark:hover:bg-gray-700 p-1">${filename}</span></td>
      <td class="p-2">
        <audio controls class="w-48">
          <source src="/recordings/${filename}" type="audio/wav">
        </audio>
      </td>
      <td class="p-2 recording-date text-sm text-gray-600 dark:text-gray-400">${formattedDate}</td>
      <td class="p-2">
        <button class="delete-button bg-red-500 hover:bg-red-600 text-white rounded px-2 py-1 flex items-center">
          <span class="delete-icon">🗑️</span> Delete
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
    button.addEventListener("click", function () {
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

document.addEventListener("DOMContentLoaded", loadRecordings);
