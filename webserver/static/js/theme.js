function setTheme(theme) {
  const themeIcon = document.getElementById("theme-icon");
  const homeIcon = document.getElementById("home-icon");
  const settingsIcon = document.getElementById("settings-icon");

  if (theme === "dark") {
    document.documentElement.classList.add("dark");
    themeIcon.src = "/static/img/moon.png";
    homeIcon.src = "/static/img/home_dark.png";
    settingsIcon.src = "/static/img/gear_dark.png";
  } else {
    document.documentElement.classList.remove("dark");
    themeIcon.src = "/static/img/sun.png";
    homeIcon.src = "/static/img/home_light.png";
    settingsIcon.src = "/static/img/gear_light.png";
  }

  localStorage.setItem("theme", theme);
}

document.addEventListener("DOMContentLoaded", () => {
  const toggleSwitch = document.querySelector(
    '.theme-switch input[type="checkbox"]',
  );
  const currentTheme = localStorage.getItem("theme");

  if (currentTheme) {
    setTheme(currentTheme);
    toggleSwitch.checked = currentTheme === "dark";
  }

  toggleSwitch.addEventListener("change", function (e) {
    setTheme(e.target.checked ? "dark" : "light");
  });
});
