import "@awesome.me/webawesome/dist/styles/webawesome.css";
import "@awesome.me/webawesome/dist/components/badge/badge.js";
import "@awesome.me/webawesome/dist/components/button/button.js";
import "@awesome.me/webawesome/dist/components/card/card.js";
import "@awesome.me/webawesome/dist/components/details/details.js";
import "@awesome.me/webawesome/dist/components/dialog/dialog.js";
import "@awesome.me/webawesome/dist/components/divider/divider.js";
import "@awesome.me/webawesome/dist/components/input/input.js";
import "@awesome.me/webawesome/dist/components/option/option.js";
import "@awesome.me/webawesome/dist/components/progress-bar/progress-bar.js";
import "@awesome.me/webawesome/dist/components/radio/radio.js";
import "@awesome.me/webawesome/dist/components/radio-group/radio-group.js";
import "@awesome.me/webawesome/dist/components/select/select.js";
import "@awesome.me/webawesome/dist/components/switch/switch.js";
import "@awesome.me/webawesome/dist/components/textarea/textarea.js";
import "@awesome.me/webawesome/dist/components/tooltip/tooltip.js";
import "./sentinel.css";
import "./sentinel-chart.js";
import "./sentinel-header.js";
import "./sentinel-planner-status.js";
import "./sentinel-portfolio-pnl.js";
import "./sentinel-portfolio-status.js";
import "./sentinel-portfolio-value.js";
import "./sentinel-securities.js";
import "./sentinel-inactive-securities.js";
import "./sentinel-risk-return.js";
import "./sentinel-security-allocation.js";
import "./sentinel-status-bar.js";
import "./sentinel-app.js";

const darkScheme = window.matchMedia("(prefers-color-scheme: dark)");
function applyColorScheme() {
  document.documentElement.classList.toggle("wa-dark", darkScheme.matches);
}
darkScheme.addEventListener("change", applyColorScheme);
applyColorScheme();
