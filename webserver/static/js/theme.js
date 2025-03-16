/**
 * Enhanced Theme Switcher for Rotary Phone Audio Guestbook
 * Handles light/dark mode toggle with robust error handling
 */

// Create a self-executing function to avoid global scope pollution
(function () {
  // Constants for theme values and image paths
  const THEME = {
    LIGHT: "light",
    DARK: "dark"
  };

  const IMAGES = {
    SUN: "/static/img/sun.png",
    MOON: "/static/img/moon.png",
    HOME_LIGHT: "/static/img/home_light.png",
    HOME_DARK: "/static/img/home_dark.png",
    GEAR_LIGHT: "/static/img/gear_light.png",
    GEAR_DARK: "/static/img/gear_dark.png"
  };

  // DOM element references
  let elements = {
    themeIcon: null,
    homeIcon: null,
    settingsIcon: null,
    toggleSwitch: null
  };

  // Update references to DOM elements
  function updateDomReferences() {
    elements.themeIcon = document.getElementById("theme-icon");
    elements.homeIcon = document.getElementById("home-icon");
    elements.settingsIcon = document.getElementById("settings-icon");
    elements.toggleSwitch = document.querySelector('.theme-switch input[type="checkbox"]');

    // Log what was found for debugging
    console.log("DOM elements found:", {
      themeIcon: !!elements.themeIcon,
      homeIcon: !!elements.homeIcon,
      settingsIcon: !!elements.settingsIcon,
      toggleSwitch: !!elements.toggleSwitch
    });
  }

  // Apply the given theme to the UI
  function setTheme(theme) {
    console.log(`Setting theme to: ${theme}`);

    // Update DOM references to ensure we have the latest elements
    updateDomReferences();

    try {
      // Apply correct class to document element
      if (theme === THEME.DARK) {
        document.documentElement.classList.add("dark");

        // Update icons if they exist
        if (elements.themeIcon) elements.themeIcon.src = IMAGES.MOON;
        if (elements.homeIcon) elements.homeIcon.src = IMAGES.HOME_DARK;
        if (elements.settingsIcon) elements.settingsIcon.src = IMAGES.GEAR_DARK;
      } else {
        document.documentElement.classList.remove("dark");

        // Update icons if they exist
        if (elements.themeIcon) elements.themeIcon.src = IMAGES.SUN;
        if (elements.homeIcon) elements.homeIcon.src = IMAGES.HOME_LIGHT;
        if (elements.settingsIcon) elements.settingsIcon.src = IMAGES.GEAR_LIGHT;
      }

      // Update toggle switch state if it exists
      if (elements.toggleSwitch) {
        elements.toggleSwitch.checked = theme === THEME.DARK;
      }

      // Store theme preference
      localStorage.setItem("theme", theme);

      console.log(`Theme set successfully to: ${theme}`);
    } catch (error) {
      console.error("Error setting theme:", error);
    }
  }

  // Get the current theme preference
  function getCurrentTheme() {
    // First check localStorage
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) {
      return savedTheme;
    }

    // Then check system preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return THEME.DARK;
    }

    // Default to light theme
    return THEME.LIGHT;
  }

  // Toggle between light and dark themes
  function toggleTheme() {
    const currentTheme = getCurrentTheme();
    setTheme(currentTheme === THEME.DARK ? THEME.LIGHT : THEME.DARK);
  }

  // Set up event listeners for the toggle switch
  function setupEventListeners() {
    // Update DOM references
    updateDomReferences();

    if (elements.toggleSwitch) {
      console.log("Setting up toggle switch event listener");

      // Remove any existing listeners by cloning and replacing the element
      const newToggle = elements.toggleSwitch.cloneNode(true);
      elements.toggleSwitch.parentNode.replaceChild(newToggle, elements.toggleSwitch);
      elements.toggleSwitch = newToggle;

      // Add the new event listener
      elements.toggleSwitch.addEventListener("change", function (e) {
        setTheme(e.target.checked ? THEME.DARK : THEME.LIGHT);
      });
    } else {
      console.warn("Toggle switch not found in DOM");
    }

    // Set up event delegation as a backup
    document.addEventListener("change", function (e) {
      if (e.target.matches('.theme-switch input[type="checkbox"]')) {
        console.log("Theme toggle changed via delegation");
        setTheme(e.target.checked ? THEME.DARK : THEME.LIGHT);
      }
    });
  }

  // Initialize theme
  function initializeTheme() {
    try {
      console.log("Initializing theme");

      // Get current theme preference
      const currentTheme = getCurrentTheme();

      // Set up event listeners
      setupEventListeners();

      // Apply the theme
      setTheme(currentTheme);

      // Set up mutation observer to handle dynamic DOM changes
      setupMutationObserver();

      console.log("Theme initialized successfully");
    } catch (error) {
      console.error("Error initializing theme:", error);
    }
  }

  // Set up mutation observer to watch for DOM changes
  function setupMutationObserver() {
    // Create mutation observer to watch for changes to the DOM
    const observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        if (mutation.addedNodes.length) {
          // Check if any relevant elements were added
          const toggleAdded = Array.from(mutation.addedNodes).some(
            node => node.nodeType === 1 &&
              (node.matches('.theme-switch') ||
                node.querySelector('.theme-switch'))
          );

          if (toggleAdded) {
            console.log("Theme toggle added to DOM, updating event listeners");
            setupEventListeners();

            // Make sure the toggle reflects the current theme
            updateDomReferences();
            if (elements.toggleSwitch) {
              elements.toggleSwitch.checked = getCurrentTheme() === THEME.DARK;
            }
          }
        }
      });
    });

    // Start observing the document
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    console.log("Mutation observer set up");
  }

  // Initialize when the DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeTheme);
  } else {
    // DOM already loaded, initialize immediately
    initializeTheme();
  }

  // Initialize again after window load to catch any late DOM changes
  window.addEventListener('load', function () {
    // Short delay to ensure all other scripts have run
    setTimeout(function () {
      console.log("Window loaded, reinitializing theme");
      setupEventListeners();

      // Ensure toggle state matches current theme
      const currentTheme = getCurrentTheme();
      updateDomReferences();
      if (elements.toggleSwitch) {
        elements.toggleSwitch.checked = currentTheme === THEME.DARK;
      }
    }, 100);
  });

  // Expose API for other scripts
  window.themeManager = {
    setTheme: setTheme,
    getCurrentTheme: getCurrentTheme,
    toggleTheme: toggleTheme
  };

  console.log("Theme script loaded");
})();