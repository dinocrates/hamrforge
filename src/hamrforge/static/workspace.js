(function () {
  function init(options) {
    const runForm = document.getElementById("workspace-run-form");
    const runRegion = document.getElementById("workspace-run-output-region");
    if (!runForm || !runRegion || !window.fetch) {
      return;
    }

    runForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitButton = runForm.querySelector('button[type="submit"]');
      const originalText = submitButton ? submitButton.textContent : "";
      setButtonState(submitButton, "Running...", true);
      runRegion.innerHTML = loadingMarkup();

      try {
        const formData = new FormData(runForm);
        const contentField = runForm.querySelector(".workspace-buffer-content");
        if (contentField && options && typeof options.getEditorValue === "function") {
          contentField.value = options.getEditorValue();
          formData.set("content", contentField.value);
        }

        const runnerSelect = document.getElementById("workspace-runner-select");
        if (runnerSelect) {
          formData.set("runner", runnerSelect.value);
        }

        const response = await fetch("/api/workspace/run", {
          method: "POST",
          body: formData,
          headers: { Accept: "application/json" },
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          runRegion.innerHTML = errorMarkup(payload.error || "Run failed.");
          return;
        }
        runRegion.innerHTML = payload.run_output_html;
        showTransientNotice(payload.notice || "Workspace saved and program run.");
      } catch (error) {
        runRegion.innerHTML = errorMarkup(error && error.message ? error.message : "Run failed.");
      } finally {
        setButtonState(submitButton, originalText, false);
      }
    });
  }

  function setButtonState(button, text, disabled) {
    if (!button) {
      return;
    }
    button.textContent = text;
    button.disabled = disabled;
  }

  function loadingMarkup() {
    return [
      '<article class="card run-output-card run-loading">',
      "<h2>Run Output</h2>",
      '<p class="muted">Running program...</p>',
      "</article>",
    ].join("");
  }

  function errorMarkup(message) {
    return [
      '<article class="card run-output-card">',
      "<h2>Run Output</h2>",
      '<section class="notice error" role="alert">',
      "<strong>Could not run program.</strong>",
      "<pre>",
      escapeHtml(message),
      "</pre>",
      "</section>",
      "</article>",
    ].join("");
  }

  function showTransientNotice(message) {
    const title = document.querySelector(".workspace-title-status");
    if (!title) {
      return;
    }
    title.innerHTML = '<section class="notice" role="status">' + escapeHtml(message) + "</section>";
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  window.HamrForgeWorkspace = { init };
})();
