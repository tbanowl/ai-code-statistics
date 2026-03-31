import { createApp } from "vue";
import App from "./App.vue";
import "./assets/styles/main.css";
import "flatpickr/dist/l10n/zh";
import "flatpickr/dist/flatpickr.min.css";

const app = createApp(App);
app.mount("#app");
