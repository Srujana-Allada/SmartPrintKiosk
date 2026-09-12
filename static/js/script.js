document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.querySelector("#document-upload");
  const fileName = document.querySelector("[data-file-name]");
  const uploadArea = document.querySelector("[data-upload-area]");

  if (fileInput && fileName) {
    fileInput.addEventListener("change", () => {
      const selectedFile = fileInput.files[0];
      fileName.textContent = selectedFile ? `Selected: ${selectedFile.name}` : "";
      fileName.classList.toggle("visible", Boolean(selectedFile));
    });
  }

  if (uploadArea && fileInput) {
    ["dragenter", "dragover"].forEach((eventName) => uploadArea.addEventListener(eventName, (event) => {
      event.preventDefault();
      uploadArea.classList.add("is-dragging");
    }));
    ["dragleave", "drop"].forEach((eventName) => uploadArea.addEventListener(eventName, (event) => {
      event.preventDefault();
      uploadArea.classList.remove("is-dragging");
    }));
    uploadArea.addEventListener("drop", (event) => {
      if (event.dataTransfer.files.length) {
        fileInput.files = event.dataTransfer.files;
        fileInput.dispatchEvent(new Event("change"));
      }
    });
  }

  document.querySelectorAll("[data-stepper]").forEach((stepper) => {
    const input = stepper.querySelector("input");
    stepper.querySelectorAll("button[data-step]").forEach((button) => button.addEventListener("click", () => {
      const nextValue = Number(input.value || 1) + Number(button.dataset.step);
      input.value = Math.min(Number(input.max || 500), Math.max(Number(input.min || 1), nextValue));
    }));
  });

  const settingsForm = document.querySelector("[data-settings-form]");
  if (settingsForm) {
    const validationMessage = settingsForm.querySelector("[data-settings-validation]");
    const requiredGroups = settingsForm.querySelectorAll("[data-required-setting]");
    const validateSettings = () => {
      let missingCount = 0;
      requiredGroups.forEach((group) => {
        const selected = group.querySelector("input[type=radio]:checked");
        const missing = !selected;
        group.classList.toggle("needs-selection", missing);
        if (missing) missingCount += 1;
      });
      if (validationMessage) validationMessage.classList.toggle("visible", missingCount > 0);
      return missingCount === 0;
    };

    settingsForm.addEventListener("change", (event) => {
      if (event.target.matches("input[type=radio]")) validateSettings();
    });
    settingsForm.addEventListener("submit", (event) => {
      if (event.submitter && event.submitter.getAttribute("formaction")) return;
      if (!validateSettings()) {
        event.preventDefault();
        const firstMissing = settingsForm.querySelector(".needs-selection");
        if (firstMissing) firstMissing.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  const printForm = document.querySelector("[data-print-form]");
  if (printForm) {
    printForm.addEventListener("submit", (event) => {
      event.preventDefault();
      printForm.classList.add("is-processing");
      const button = printForm.querySelector("button");
      if (button) {
        button.disabled = true;
        button.innerHTML = '<svg class="icon"><use href="#icon-printer"></use></svg> Processing print...';
      }

      const stageCard = document.querySelector("[data-print-stage-card]");
      const stageKicker = document.querySelector("[data-stage-kicker]");
      const stageTitle = document.querySelector("[data-stage-title]");
      const stageDescription = document.querySelector("[data-stage-description]");
      const trackSteps = document.querySelectorAll("[data-track-step]");
      const stages = [
        ["Preparing your print", "Preparing document", "Getting your document ready.", "ready"],
        ["Scanning document", "Scanning document", "Checking the document preview.", "processing"],
        ["Printing", "Printing", "Sending the job to the test printer flow.", "printing"],
        ["Print complete", "Your document is ready", "Please collect your document.", "complete"],
      ];
      const showStage = (stage) => {
        const [kicker, title, description, key] = stage;
        if (stageKicker) stageKicker.textContent = kicker;
        if (stageTitle) stageTitle.textContent = title;
        if (stageDescription) stageDescription.textContent = description;
        trackSteps.forEach((step) => step.classList.toggle("active", step.dataset.trackStep === key));
        if (stageCard) stageCard.dataset.stage = key;
      };
      stages.forEach((stage, index) => window.setTimeout(() => showStage(stage), index * 1050));
      window.setTimeout(() => printForm.submit(), stages.length * 1050 + 250);
    });
  }
});
