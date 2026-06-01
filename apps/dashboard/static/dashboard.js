(() => {
    const themeToggle = document.querySelector("[data-theme-toggle]");
    const themeLabel = document.querySelector("[data-theme-label]");
    const storedTheme = window.localStorage.getItem("dashboard-theme") || "dark";

    const setTheme = (theme) => {
        const normalized = theme === "light" ? "light" : "dark";
        document.body.dataset.theme = normalized;
        window.localStorage.setItem("dashboard-theme", normalized);
        if (themeToggle) {
            themeToggle.checked = normalized === "light";
        }
        if (themeLabel) {
            themeLabel.textContent = normalized === "light" ? "Light theme" : "Dark theme";
        }
    };

    setTheme(storedTheme);
    themeToggle?.addEventListener("change", () => {
        setTheme(themeToggle.checked ? "light" : "dark");
    });

    const normalizeRotation = (value) => {
        const rotated = Number(value) || 0;
        return ((rotated % 360) + 360) % 360;
    };

    const setRotation = (documentId, rotation) => {
        const normalized = normalizeRotation(rotation);
        const frame = document.querySelector(`[data-document-frame="${documentId}"]`);
        const label = document.querySelector(`[data-rotation-controls="${documentId}"] [data-rotation-label]`);

        if (frame) {
            frame.style.setProperty("--document-rotation", `${normalized}deg`);
        }

        if (label) {
            label.textContent = `${normalized} graden`;
        }

        window.localStorage.setItem(`timesheet-document-rotation:${documentId}`, String(normalized));
    };

    document.querySelectorAll("[data-rotation-controls]").forEach((controls) => {
        const documentId = controls.dataset.rotationControls;
        const storedRotation = window.localStorage.getItem(`timesheet-document-rotation:${documentId}`);

        setRotation(documentId, storedRotation || 0);

        controls.querySelectorAll("[data-rotate-step]").forEach((button) => {
            button.addEventListener("click", () => {
                const current = window.localStorage.getItem(`timesheet-document-rotation:${documentId}`) || 0;
                setRotation(documentId, Number(current) + Number(button.dataset.rotateStep));
            });
        });

        const resetButton = controls.querySelector("[data-rotate-reset]");
        if (resetButton) {
            resetButton.addEventListener("click", () => setRotation(documentId, 0));
        }
    });

    document.querySelectorAll("[data-relation-form]").forEach((form) => {
        const typeSelect = form.querySelector("[data-relation-type]");
        const candidateFields = form.querySelectorAll("[data-candidate-field]");
        const principalFields = form.querySelectorAll("[data-principal-field]");

        const syncRelationFields = () => {
            const isPrincipal = typeSelect.value === "principal";
            candidateFields.forEach((field) => {
                field.hidden = isPrincipal;
            });
            principalFields.forEach((field) => {
                field.hidden = !isPrincipal;
            });
        };

        typeSelect.addEventListener("change", syncRelationFields);
        syncRelationFields();
    });

    const relationModal = document.querySelector("[data-relation-modal]");
    const relationForm = document.querySelector("[data-relation-form]");
    const relationTypeSelect = relationForm?.querySelector("[data-relation-type]");
    const relationFormPanel = document.querySelector("#relatie-formulier");

    const closeRelationModal = () => {
        if (relationModal) {
            relationModal.hidden = true;
        }
    };

    const clearRelationForm = () => {
        if (!relationForm || relationForm.action.includes("/api/relations/")) {
            return;
        }
        relationForm.querySelectorAll("input, textarea").forEach((field) => {
            if (field.type !== "file") {
                field.value = "";
            }
        });
    };

    document.querySelector("[data-open-relation-modal]")?.addEventListener("click", () => {
        if (relationModal) {
            relationModal.hidden = false;
        }
    });

    document.querySelector("[data-close-relation-modal]")?.addEventListener("click", closeRelationModal);
    relationModal?.addEventListener("click", (event) => {
        if (event.target === relationModal) {
            closeRelationModal();
        }
    });

    document.querySelectorAll("[data-new-relation-type]").forEach((button) => {
        button.addEventListener("click", () => {
            if (relationTypeSelect) {
                clearRelationForm();
                relationTypeSelect.value = button.dataset.newRelationType;
                relationTypeSelect.dispatchEvent(new Event("change"));
            }
            closeRelationModal();
            relationFormPanel?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
    });

    document.querySelectorAll(".correction-form").forEach((form) => {
        const principalSelect = form.querySelector('[name="field_principal_name"]');
        const projectSelect = form.querySelector('[name="field_work_name"]');
        const principalTarget = document.querySelector("[data-workflow-principal-id]");
        const projectTarget = document.querySelector("[data-workflow-project-id]");
        const dayInputs = [
            "field_monday_hours",
            "field_tuesday_hours",
            "field_wednesday_hours",
            "field_thursday_hours",
            "field_friday_hours",
            "field_saturday_hours",
            "field_sunday_hours",
        ].map((name) => form.elements[name]).filter(Boolean);
        const totalInput = form.elements.field_total_hours;
        const calculatedInput = form.elements.field_calculated_total_hours;
        const checkInput = form.elements.field_total_hours_check;
        const kmInputs = [
            "field_monday_km",
            "field_tuesday_km",
            "field_wednesday_km",
            "field_thursday_km",
            "field_friday_km",
            "field_saturday_km",
            "field_sunday_km",
        ].map((name) => form.elements[name]).filter(Boolean);
        const totalKmInput = form.elements.field_total_km;
        const calculatedKmInput = form.elements.field_calculated_total_km;
        const checkKmInput = form.elements.field_total_km_check;

        const syncWorkflowIds = () => {
            if (principalTarget && principalSelect) {
                principalTarget.value = principalSelect.selectedOptions[0]?.dataset.id || "";
            }
            if (projectTarget && projectSelect) {
                projectTarget.value = projectSelect.selectedOptions[0]?.dataset.id || "";
            }
        };

        principalSelect?.addEventListener("change", syncWorkflowIds);
        projectSelect?.addEventListener("change", syncWorkflowIds);
        syncWorkflowIds();

        const parseHours = (value) => {
            const normalized = String(value || "").replace(",", ".").trim();
            if (!normalized) {
                return null;
            }
            const parsed = Number(normalized);
            return Number.isFinite(parsed) ? parsed : null;
        };

        const formatHours = (value) => Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2))).replace(".", ",");

        const syncSumCheck = (inputs, totalField, calculatedField, checkField, unit, missingMessage) => {
            if (!calculatedField || !checkField) {
                return;
            }
            const values = inputs.map((input) => parseHours(input.value)).filter((value) => value !== null);
            if (!values.length) {
                calculatedField.value = "";
                checkField.value = "";
                return;
            }
            const calculated = values.reduce((sum, value) => sum + value, 0);
            calculatedField.value = formatHours(calculated);
            const stated = parseHours(totalField?.value);
            if (stated === null) {
                checkField.value = missingMessage;
                return;
            }
            const difference = Math.abs(calculated - stated);
            checkField.value = difference < 0.005 ? "klopt" : `verschil ${formatHours(difference)} ${unit}`;
        };

        const syncTotalCheck = () => {
            syncSumCheck(dayInputs, totalInput, calculatedInput, checkInput, "uur", "totaal ontbreekt");
            syncSumCheck(kmInputs, totalKmInput, calculatedKmInput, checkKmInput, "km", "totaal km ontbreekt");
        };

        dayInputs.forEach((input) => input.addEventListener("input", syncTotalCheck));
        totalInput?.addEventListener("input", syncTotalCheck);
        kmInputs.forEach((input) => input.addEventListener("input", syncTotalCheck));
        totalKmInput?.addEventListener("input", syncTotalCheck);
        syncTotalCheck();
    });

    document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-fill-field]");
        if (!button) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        const form = button.closest("form");
        const target = form?.elements?.[button.dataset.fillField] || form?.querySelector(`[name="${button.dataset.fillField}"]`);
        if (target) {
            target.value = button.dataset.fillValue || "";
            target.dispatchEvent(new Event("input", { bubbles: true }));
            target.dispatchEvent(new Event("change", { bubbles: true }));
            target.focus();
        }
    });

    document.querySelectorAll(".whatsapp-upload-form").forEach((form) => {
        form.addEventListener("submit", () => {
            const phoneInput = form.querySelector('[name="sender_phone"]');
            if (phoneInput && !phoneInput.value.trim()) {
                phoneInput.value = "onbekend";
            }
        });
    });

    document.querySelectorAll("[data-timesheet-dropzone]").forEach((dropzone) => {
        const input = dropzone.querySelector("[data-timesheet-drop-input]");
        const button = dropzone.querySelector("[data-timesheet-drop-button]");
        const originalText = dropzone.querySelector("small")?.textContent || "";

        const setDropState = (state, text) => {
            dropzone.dataset.dropState = state;
            const label = dropzone.querySelector("small");
            if (label && text) {
                label.textContent = text;
            }
        };

        const uploadFile = (file) => {
            if (!file) {
                return;
            }
            const isAllowed = file.type.startsWith("image/") || file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
            if (!isAllowed) {
                setDropState("error", "Gebruik een afbeelding of PDF.");
                return;
            }

            setDropState("uploading", "Nieuwe taak wordt aangemaakt...");
            try {
                const transfer = new DataTransfer();
                transfer.items.add(file);
                input.files = transfer.files;
                if (dropzone.requestSubmit) {
                    dropzone.requestSubmit();
                } else {
                    dropzone.submit();
                }
            } catch (error) {
                setDropState("error", "Gebruik Bestand kiezen om te uploaden.");
            }
        };

        button?.addEventListener("click", () => input?.click());
        input?.addEventListener("change", () => {
            if (input.files?.[0]) {
                setDropState("uploading", "Nieuwe taak wordt aangemaakt...");
                if (dropzone.requestSubmit) {
                    dropzone.requestSubmit();
                } else {
                    dropzone.submit();
                }
            }
        });

        ["dragenter", "dragover"].forEach((eventName) => {
            dropzone.addEventListener(eventName, (event) => {
                event.preventDefault();
                setDropState("active", "Laat los om een taak aan te maken.");
            });
        });

        ["dragleave", "drop"].forEach((eventName) => {
            dropzone.addEventListener(eventName, (event) => {
                event.preventDefault();
                if (eventName === "drop") {
                    uploadFile(event.dataTransfer?.files?.[0]);
                    return;
                }
                setDropState("", originalText);
            });
        });
    });

    const zoomModal = document.querySelector("[data-document-zoom-modal]");
    const zoomImage = document.querySelector("[data-document-zoom-image]");
    const closeZoom = () => {
        if (zoomModal) {
            zoomModal.hidden = true;
        }
    };

    document.querySelectorAll("[data-document-zoom-open]").forEach((button) => {
        button.addEventListener("click", () => {
            const image = button.querySelector("img");
            const documentId = button.dataset.documentZoomOpen;
            const rotation = window.localStorage.getItem(`timesheet-document-rotation:${documentId}`) || 0;
            if (zoomImage && image) {
                zoomImage.src = image.src;
                zoomImage.alt = image.alt || "Vergroot urenbriefje";
                zoomImage.style.setProperty("--zoom-document-rotation", `${normalizeRotation(rotation)}deg`);
            }
            if (zoomModal) {
                zoomModal.hidden = false;
            }
        });
    });

    document.querySelector("[data-document-zoom-close]")?.addEventListener("click", closeZoom);
    zoomModal?.addEventListener("click", (event) => {
        if (event.target === zoomModal) {
            closeZoom();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeZoom();
        }
    });
})();
