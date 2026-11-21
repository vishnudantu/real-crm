import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/manrope/wght.css";
import { applyBrandingBootstrap } from "./tenant/branding";

// Apply the default synchronously; TenantProvider updates this for the configured tenant.
applyBrandingBootstrap();
import "./index.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
