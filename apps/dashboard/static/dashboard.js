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

    const relationTabs = document.querySelectorAll("[data-relation-tab]");
    if (relationTabs.length) {
        const tabStorageKey = "dashboard-relations-tab";
        const validTabs = new Set(["candidates", "principals"]);
        const url = new URL(window.location.href);
        const urlTab = url.searchParams.get("tab");
        const storedTab = window.localStorage.getItem(tabStorageKey);

        if (validTabs.has(urlTab)) {
            window.localStorage.setItem(tabStorageKey, urlTab);
        } else if (validTabs.has(storedTab) && window.location.pathname === "/dashboard/relations") {
            url.searchParams.set("tab", storedTab);
            url.hash = url.hash || "relaties";
            window.location.replace(url.toString());
        }

        relationTabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                if (validTabs.has(tab.dataset.relationTab)) {
                    window.localStorage.setItem(tabStorageKey, tab.dataset.relationTab);
                }
            });
        });
    }

    const persistSelects = document.querySelectorAll("[data-persist-select]");
    persistSelects.forEach((select) => {
        const key = select.dataset.persistSelect;
        const param = select.dataset.persistParam || select.name;
        const url = new URL(window.location.href);
        const hasUrlValue = url.searchParams.has(param);
        const storedValue = window.localStorage.getItem(key);

        const syncSelectState = () => {
            select.classList.toggle("select-has-value", Boolean(select.value));
        };

        if (hasUrlValue) {
            if (select.value) {
                window.localStorage.setItem(key, select.value);
            } else {
                window.localStorage.removeItem(key);
            }
        } else if (storedValue) {
            if (![...select.options].some((option) => option.value === storedValue)) {
                select.add(new Option(storedValue, storedValue));
            }
            select.value = storedValue;
            syncSelectState();
            if ((window.location.pathname === "/dashboard/relations" || window.location.pathname === "/dashboard/vacancies") && !url.searchParams.has("q")) {
                url.searchParams.set(param, storedValue);
                url.hash = url.hash || (window.location.pathname === "/dashboard/vacancies" ? "vacatures" : "relaties");
                window.location.replace(url.toString());
                return;
            }
        }

        syncSelectState();
        select.addEventListener("change", () => {
            if (select.value) {
                window.localStorage.setItem(key, select.value);
            } else {
                window.localStorage.removeItem(key);
            }
            syncSelectState();
        });
    });

    document.querySelectorAll("[data-clear-persist]").forEach((clearLink) => {
        clearLink.addEventListener("click", () => {
            clearLink.dataset.clearPersist.split(",").forEach((key) => {
                if (key.trim()) {
                    window.localStorage.removeItem(key.trim());
                }
            });
        });
    });

    document.querySelectorAll("[data-sort-table]").forEach((table) => {
        const tbody = table.tBodies[0];
        if (!tbody) {
            return;
        }
        table.querySelectorAll("[data-sort-column]").forEach((button) => {
            button.addEventListener("click", () => {
                const column = Number(button.dataset.sortColumn);
                const currentDirection = button.dataset.sortDirection === "asc" ? "desc" : "asc";
                table.querySelectorAll("[data-sort-column]").forEach((item) => {
                    item.dataset.sortDirection = "";
                });
                button.dataset.sortDirection = currentDirection;
                const rows = Array.from(tbody.querySelectorAll("tr"));
                rows.sort((left, right) => {
                    const leftCell = left.children[column];
                    const rightCell = right.children[column];
                    const leftValue = leftCell?.dataset.sortValue || leftCell?.textContent || "";
                    const rightValue = rightCell?.dataset.sortValue || rightCell?.textContent || "";
                    const leftNumber = Number(leftValue);
                    const rightNumber = Number(rightValue);
                    const result = Number.isFinite(leftNumber) && Number.isFinite(rightNumber)
                        ? leftNumber - rightNumber
                        : leftValue.trim().localeCompare(rightValue.trim(), "nl", { numeric: true, sensitivity: "base" });
                    return currentDirection === "asc" ? result : -result;
                });
                rows.forEach((row) => tbody.appendChild(row));
            });
        });
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
    const relationEditorModal = document.querySelector("[data-relation-editor-modal]");

    const closeRelationEditor = () => {
        const closeUrl = relationEditorModal?.dataset.closeUrl;
        if (closeUrl) {
            window.location.href = closeUrl;
        }
    };

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

    relationEditorModal?.addEventListener("click", (event) => {
        if (event.target === relationEditorModal) {
            closeRelationEditor();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && relationEditorModal) {
            closeRelationEditor();
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

    document.querySelectorAll("[data-candidate-match-select]").forEach((select) => {
        const form = select.closest("form");
        const searchInput = form?.querySelector("[data-candidate-match-search]");
        const employeeNameInput = form?.querySelector('[name="field_employee_name"]');
        const employeePhoneInput = form?.querySelector('[name="field_employee_phone"]');

        const applySelectedCandidate = () => {
            const option = select.selectedOptions[0];
            if (!option || !option.value) {
                return;
            }
            if (employeeNameInput && option.dataset.name) {
                employeeNameInput.value = option.dataset.name;
            }
            if (employeePhoneInput && option.dataset.phone) {
                employeePhoneInput.value = option.dataset.phone;
            }
        };

        const filterCandidates = () => {
            const query = (searchInput?.value || "").trim().toLowerCase();
            [...select.options].forEach((option) => {
                if (!option.value) {
                    option.hidden = false;
                    return;
                }
                const haystack = `${option.textContent || ""} ${option.dataset.name || ""} ${option.dataset.phone || ""}`.toLowerCase();
                option.hidden = query ? !haystack.includes(query) : false;
            });
        };

        select.addEventListener("change", applySelectedCandidate);
        searchInput?.addEventListener("input", filterCandidates);
        if (select.value) {
            applySelectedCandidate();
        }
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

    const processingStatus = document.querySelector("[data-processing-status]");
    const processingStatusTitle = document.querySelector("[data-processing-status-title]");
    const processingStatusText = document.querySelector("[data-processing-status-text]");
    const showProcessingStatus = (text, title = "Bezig met verwerken") => {
        if (!processingStatus) {
            return;
        }
        if (processingStatusTitle) {
            processingStatusTitle.textContent = title;
        }
        if (processingStatusText) {
            processingStatusText.textContent = text;
        }
        processingStatus.hidden = false;
        processingStatus.scrollIntoView({ behavior: "smooth", block: "nearest" });
    };

    document.querySelectorAll("form").forEach((form) => {
        const action = form.getAttribute("action") || "";
        if (!action.includes("/api/whatsapp/timesheet/") || action.includes("/delete")) {
            return;
        }
        form.addEventListener("submit", () => {
            const message = action.includes("/reparse")
                ? "Het urenbriefje wordt opnieuw gelezen en geparseerd."
                : action.includes("/corrections")
                    ? "Correcties worden opgeslagen en totalen worden gecontroleerd."
                    : action.includes("/validate")
                        ? "De uren worden gevalideerd voor loonberekening."
                        : action.includes("/payroll")
                            ? "De taak wordt klaargezet voor loonadministratie."
                            : "De taak wordt verwerkt.";
            showProcessingStatus(message);
        });
    });

    document.querySelectorAll(".whatsapp-upload-form").forEach((form) => {
        form.addEventListener("submit", () => {
            const phoneInput = form.querySelector('[name="sender_phone"]');
            if (phoneInput && !phoneInput.value.trim()) {
                phoneInput.value = "onbekend";
            }
            showProcessingStatus("Het urenbriefje wordt geupload en geparseerd.");
        });
    });

    const uploadModal = document.querySelector("[data-timesheet-upload-modal]");
    const uploadModalForm = uploadModal?.querySelector("form");
    const uploadNameInput = uploadModal?.querySelector("[data-timesheet-upload-name]");
    const uploadPhoneInput = uploadModal?.querySelector("[data-timesheet-upload-phone]");
    const uploadFileName = uploadModal?.querySelector("[data-timesheet-upload-file-name]");
    let activeDropzone = null;

    const closeUploadModal = () => {
        if (uploadModal) {
            uploadModal.hidden = true;
        }
    };

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

            try {
                const transfer = new DataTransfer();
                transfer.items.add(file);
                input.files = transfer.files;
                activeDropzone = dropzone;
                if (uploadFileName) {
                    uploadFileName.textContent = file.name;
                }
                if (uploadNameInput) {
                    uploadNameInput.value = "";
                }
                if (uploadPhoneInput) {
                    uploadPhoneInput.value = "";
                }
                if (uploadModal) {
                    uploadModal.hidden = false;
                    uploadNameInput?.focus();
                }
                setDropState("", `Gekozen: ${file.name}`);
            } catch (error) {
                setDropState("error", "Gebruik Bestand kiezen om te uploaden.");
            }
        };

        button?.addEventListener("click", () => input?.click());
        input?.addEventListener("change", () => {
            if (input.files?.[0]) {
                uploadFile(input.files[0]);
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

    uploadModalForm?.addEventListener("submit", (event) => {
        event.preventDefault();
        if (!activeDropzone) {
            closeUploadModal();
            return;
        }
        const senderName = activeDropzone.querySelector("[data-timesheet-upload-sender-name]");
        const senderPhone = activeDropzone.querySelector("[data-timesheet-upload-sender-phone]");
        if (senderName) {
            senderName.value = uploadNameInput?.value.trim() || "";
        }
        if (senderPhone) {
            senderPhone.value = uploadPhoneInput?.value.trim() || "onbekend";
        }
        activeDropzone.dataset.dropState = "uploading";
        showProcessingStatus("Het urenbriefje wordt geupload en geparseerd.");
        closeUploadModal();
        if (activeDropzone.requestSubmit) {
            activeDropzone.requestSubmit();
        } else {
            activeDropzone.submit();
        }
    });

    document.querySelectorAll("[data-timesheet-upload-cancel]").forEach((button) => {
        button.addEventListener("click", closeUploadModal);
    });
    uploadModal?.addEventListener("click", (event) => {
        if (event.target === uploadModal) {
            closeUploadModal();
        }
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
            closeUploadModal();
        }
    });
})();
