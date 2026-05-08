(function () {
  function init(options) {
    const runForm = document.getElementById("workspace-run-form");
    const runRegion = document.getElementById("workspace-run-output-region");
    const gradeForm = document.getElementById("workspace-grade-form");
    if (!window.fetch) {
      return;
    }

    if (runForm && runRegion) {
      runForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitButton = runForm.querySelector('button[type="submit"]');
        const originalText = submitButton ? submitButton.textContent : "";
        setButtonState(submitButton, "Running...", true);
        runRegion.innerHTML = loadingMarkup();

        try {
          const formData = workspaceFormData(runForm, options);
          const response = await fetch("/api/workspace/run", {
            method: "POST",
            body: formData,
            headers: { Accept: "application/json" },
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            runRegion.innerHTML = errorMarkup("Run Output", "Could not run program.", payload.error || "Run failed.");
            return;
          }
          runRegion.innerHTML = payload.run_output_html;
          showTransientNotice(payload.notice || "Workspace saved and program run.");
        } catch (error) {
          runRegion.innerHTML = errorMarkup(
            "Run Output",
            "Could not run program.",
            error && error.message ? error.message : "Run failed."
          );
        } finally {
          setButtonState(submitButton, originalText, false);
        }
      });
    }

    if (gradeForm) {
      gradeForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitButton = gradeForm.querySelector('button[type="submit"]');
        const originalText = submitButton ? submitButton.textContent : "";
        setButtonState(submitButton, "Grading...", true);
        updateRegion("workspace-feedback-summary-region", gradingLoadingMarkup());
        showTransientNotice("Workspace saved and grading job running...");

        try {
          const formData = workspaceFormData(gradeForm, options);
          const response = await fetch("/api/workspace/grade", {
            method: "POST",
            body: formData,
            headers: { Accept: "application/json" },
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            updateRegion(
              "workspace-feedback-summary-region",
              errorMarkup("Latest Job", "Could not grade workspace.", payload.error || "Grade failed.")
            );
            showTransientNotice("Could not grade workspace.");
            return;
          }
          updateGradeFragments(payload);
          showTransientNotice(payload.notice || "Workspace saved and grading job completed.");
        } catch (error) {
          updateRegion(
            "workspace-feedback-summary-region",
            errorMarkup(
              "Latest Job",
              "Could not grade workspace.",
              error && error.message ? error.message : "Grade failed."
            )
          );
          showTransientNotice("Could not grade workspace.");
        } finally {
          setButtonState(submitButton, originalText, false);
        }
      });
    }
  }

  function workspaceFormData(form, options) {
    const formData = new FormData(form);
    const contentField = form.querySelector(".workspace-buffer-content");
    if (contentField && options && typeof options.getEditorValue === "function") {
      contentField.value = options.getEditorValue();
      formData.set("content", contentField.value);
    }

    const runnerSelect = document.getElementById("workspace-runner-select");
    if (runnerSelect) {
      formData.set("runner", runnerSelect.value);
    }
    return formData;
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

  function gradingLoadingMarkup() {
    return [
      '<aside class="latest-panel feedback-summary-card">',
      "<h2>Feedback Summary</h2>",
      '<span class="status-label">running</span>',
      '<p class="muted">Grading current workspace snapshot...</p>',
      "</aside>",
    ].join("");
  }

  function errorMarkup(title, heading, message) {
    return [
      '<article class="card run-output-card">',
      "<h2>",
      escapeHtml(title),
      "</h2>",
      '<section class="notice error" role="alert">',
      "<strong>",
      escapeHtml(heading),
      "</strong>",
      "<pre>",
      escapeHtml(message),
      "</pre>",
      "</section>",
      "</article>",
    ].join("");
  }

  function updateGradeFragments(payload) {
    updateRegion("workspace-feedback-summary-region", payload.feedback_summary_html);
    updateRegion("workspace-activity-region", payload.activity_html);
    updateRegion("workspace-latest-job-region", payload.latest_job_html);
    updateRegion("workspace-latest-result-region", payload.latest_result_html);
    updateRegion("workspace-attempt-history-region", payload.attempt_history_html);
    updateRegion("workspace-job-history-region", payload.job_history_html);
    updateRegion("workspace-diagnostics-region", payload.diagnostics_html);
  }

  function updateRegion(id, html) {
    const region = document.getElementById(id);
    if (region && typeof html === "string") {
      region.innerHTML = html;
    }
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
