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

    
    document.querySelectorAll("[data-period-tabs]").forEach((tabGroup) => {
        const container = tabGroup.closest(".periods-only") || document;
        const tabs = Array.from(tabGroup.querySelectorAll("[data-period-tab]"));
        const panels = Array.from(container.querySelectorAll("[data-period-panel]"));
        const activateTab = (target) => {
            tabs.forEach((tab) => {
                const isActive = tab.dataset.periodTab === target;
                tab.classList.toggle("period-tab--active", isActive);
                tab.setAttribute("aria-selected", String(isActive));
            });
            panels.forEach((panel) => {
                panel.hidden = panel.dataset.periodPanel !== target;
            });
        };
        tabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                const target = tab.dataset.periodTab || "active";
                activateTab(target);
                if (target === "archive") {
                    window.history.replaceState(null, "", "#periode-archief");
                } else if (window.location.hash === "#periode-archief") {
                    window.history.replaceState(null, "", window.location.pathname + window.location.search + "#periodes");
                }
            });
        });
        activateTab(window.location.hash === "#periode-archief" ? "archive" : "active");
    });

    const sidebar = document.querySelector(".sidebar");
    const mobileMenuToggle = document.querySelector("[data-mobile-menu-toggle]");
    const mobileMenu = document.querySelector("[data-mobile-menu]");
    const mobileMenuBreakpoint = window.matchMedia("(max-width: 980px)");

    const setMobileMenuOpen = (isOpen) => {
        if (!sidebar || !mobileMenuToggle || !mobileMenu) {
            return;
        }
        sidebar.classList.toggle("sidebar--open", isOpen);
        mobileMenuToggle.setAttribute("aria-expanded", String(isOpen));
        mobileMenuToggle.setAttribute("aria-label", isOpen ? "Menu sluiten" : "Menu openen");
    };

    mobileMenuToggle?.addEventListener("click", () => {
        const isOpen = mobileMenuToggle.getAttribute("aria-expanded") === "true";
        setMobileMenuOpen(!isOpen);
    });

    mobileMenu?.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => setMobileMenuOpen(false));
    });

    document.addEventListener("click", (event) => {
        if (!mobileMenuBreakpoint.matches || !sidebar?.classList.contains("sidebar--open")) {
            return;
        }
        if (!sidebar.contains(event.target)) {
            setMobileMenuOpen(false);
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            setMobileMenuOpen(false);
        }
    });

    const auditDetailModal = document.querySelector("[data-audit-detail-modal]");
    const auditDetailTitle = document.querySelector("[data-audit-detail-modal-title]");
    const auditDetailMeta = document.querySelector("[data-audit-detail-modal-meta]");
    const auditDetailBody = document.querySelector("[data-audit-detail-modal-body]");
    const auditDetailExtra = document.querySelector("[data-audit-detail-modal-extra]");
    const auditDetailExtraSection = document.querySelector("[data-audit-extra-section]");
    const auditDetailBodyTitle = document.querySelector("[data-audit-detail-modal-body-title]");
    const auditDetailExtraTitle = document.querySelector("[data-audit-detail-modal-extra-title]");
    const closeAuditDetail = () => {
        if (auditDetailModal) {
            auditDetailModal.hidden = true;
        }
    };

    document.querySelectorAll("[data-audit-detail-open]").forEach((button) => {
        button.addEventListener("click", () => {
            if (!auditDetailModal) {
                return;
            }
            auditDetailTitle.textContent = button.querySelector("[data-audit-detail-title]")?.textContent?.trim() || "Auditregel";
            auditDetailMeta.textContent = button.querySelector("[data-audit-detail-meta]")?.textContent?.trim() || "";
            auditDetailBody.textContent = button.querySelector("[data-audit-detail-body]")?.textContent?.trim() || "";
            const isApiAudit = auditDetailTitle.textContent.includes("ChatGPT API");
            if (auditDetailBodyTitle) {
                auditDetailBodyTitle.textContent = isApiAudit ? "Naar ChatGPT gestuurd" : "Omschrijving";
            }
            if (auditDetailExtraTitle) {
                auditDetailExtraTitle.textContent = isApiAudit ? "Van ChatGPT teruggekregen" : "Data";
            }
            const extra = button.querySelector("[data-audit-detail-extra]")?.textContent?.trim() || "";
            auditDetailExtra.textContent = extra;
            if (auditDetailExtraSection) {
                auditDetailExtraSection.hidden = !extra;
            }
            auditDetailModal.hidden = false;
        });
    });

    document.querySelector("[data-audit-detail-close]")?.addEventListener("click", closeAuditDetail);
    auditDetailModal?.addEventListener("click", (event) => {
        if (event.target === auditDetailModal) {
            closeAuditDetail();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeAuditDetail();
        }
    });

    const auditSearch = document.querySelector("[data-audit-search]");
    const auditGroups = Array.from(document.querySelectorAll("[data-audit-group]"));
    const normalizeAuditText = (value) => (value || "")
        .toString()
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");

    const filterAuditRows = () => {
        const query = normalizeAuditText(auditSearch?.value || "");
        auditGroups.forEach((group) => {
            const rows = Array.from(group.querySelectorAll("[data-audit-detail-open]"));
            let visibleCount = 0;
            rows.forEach((row) => {
                const haystack = normalizeAuditText([
                    row.textContent,
                    row.querySelector("[data-audit-detail-title]")?.textContent,
                    row.querySelector("[data-audit-detail-meta]")?.textContent,
                    row.querySelector("[data-audit-detail-body]")?.textContent,
                    row.querySelector("[data-audit-detail-extra]")?.textContent,
                ].join(" "));
                const isVisible = !query || haystack.includes(query);
                row.hidden = !isVisible;
                if (isVisible) {
                    visibleCount += 1;
                }
            });
            group.hidden = query ? visibleCount === 0 : false;
            if (query && visibleCount > 0) {
                group.open = true;
            }
            const countLabel = group.querySelector("[data-audit-group-count]");
            if (countLabel) {
                const total = rows.length;
                countLabel.textContent = query ? `${visibleCount}/${total} regels` : `${total} regels`;
            }
        });
    };

    auditSearch?.addEventListener("input", filterAuditRows);

    mobileMenuBreakpoint.addEventListener?.("change", (event) => {
        if (!event.matches) {
            setMobileMenuOpen(false);
        }
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

    document.querySelectorAll("[data-payroll-workbook]").forEach((workbook) => {
        const tabs = workbook.querySelectorAll("[data-payroll-tab]");
        const panels = workbook.querySelectorAll("[data-payroll-panel]");
        const requestedTab = new URL(window.location.href).searchParams.get("week") || new URL(window.location.href).searchParams.get("tab");
        const activatePayrollTab = (target) => {
            tabs.forEach((item) => {
                const active = item.dataset.payrollTab === target;
                item.classList.toggle("payroll-workbook-tab--active", active);
                item.setAttribute("aria-selected", active ? "true" : "false");
            });
            panels.forEach((panel) => {
                panel.classList.toggle("payroll-workbook-panel--active", panel.dataset.payrollPanel === target);
            });
        };
        tabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                activatePayrollTab(tab.dataset.payrollTab);
            });
        });
        if (requestedTab && [...tabs].some((tab) => tab.dataset.payrollTab === requestedTab)) {
            activatePayrollTab(requestedTab);
        }

        workbook.querySelectorAll("[data-workbook-table]").forEach((table) => {
            const tbody = table.tBodies[0];
            table.querySelectorAll("[data-workbook-sort-column]").forEach((button) => {
                button.addEventListener("click", () => {
                    if (!tbody) {
                        return;
                    }
                    const column = Number(button.dataset.workbookSortColumn);
                    const direction = button.dataset.sortDirection === "asc" ? "desc" : "asc";
                    table.querySelectorAll("[data-workbook-sort-column]").forEach((item) => {
                        item.dataset.sortDirection = "";
                    });
                    button.dataset.sortDirection = direction;
                    const rows = Array.from(tbody.rows);
                    rows.sort((a, b) => {
                        const aValue = workbookCellSortValue(a.cells[column]);
                        const bValue = workbookCellSortValue(b.cells[column]);
                        const compare = aValue.localeCompare(bValue, "nl", { numeric: true, sensitivity: "base" });
                        return direction === "asc" ? compare : -compare;
                    });
                    rows.forEach((row) => tbody.appendChild(row));
                });
            });
        });

        workbook.querySelectorAll("[data-payroll-cell]").forEach((input) => {
            let saveTimer = null;
            const recalculatePayslipRow = () => {
                if (input.dataset.tabLabel !== "Loonstrook") {
                    return;
                }
                const row = input.closest("tr");
                if (!row) {
                    return;
                }
                const field = (key) => row.querySelector(`.payroll-col-${key} [data-payroll-cell]`);
                const parseMoney = (value) => {
                    const normalized = String(value || "")
                        .replace(/[^\d,.-]/g, "")
                        .replace(/\./g, "")
                        .replace(",", ".");
                    const parsed = Number.parseFloat(normalized);
                    return Number.isFinite(parsed) ? parsed : 0;
                };
                const formatMoney = (value) => new Intl.NumberFormat("nl-NL", {
                    style: "currency",
                    currency: "EUR",
                }).format(Math.max(value, 0));
                const periodTotal = parseMoney(field("period-total")?.value);
                const alreadyReceived = parseMoney(field("already-received-net")?.value);
                const payslipAdvance = parseMoney(field("payslip-advance")?.value);
                const netToReceive = formatMoney(periodTotal - alreadyReceived - payslipAdvance);
                ["net-to-receive", "net-total"].forEach((key) => {
                    const target = field(key);
                    if (target) {
                        target.value = netToReceive;
                    }
                });
            };
            const save = async () => {
                const value = input.value;
                const originalValue = input.dataset.originalValue || "";
                if (value === originalValue && !input.dataset.dirtyOnce) {
                    return;
                }
                input.dataset.dirtyOnce = "1";
                input.classList.add("payroll-cell-input--saving");
                try {
                    const response = await fetch(input.dataset.saveUrl, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            tab_label: input.dataset.tabLabel,
                            row_key: input.dataset.rowKey,
                            employee_name: input.dataset.employeeName,
                            relation_id: input.dataset.relationId,
                            column_key: input.dataset.columnKey,
                            column_label: input.dataset.columnLabel,
                            original_value: originalValue,
                            previous_value: input.dataset.previousValue || originalValue,
                            value,
                        }),
                    });
                    if (!response.ok) {
                        throw new Error("Opslaan mislukt");
                    }
                    const result = await response.json();
                    input.dataset.previousValue = result.previous_value || "";
                    input.dataset.originalValue = result.value || value;
                    input.classList.remove("payroll-cell-input--error");
                    recalculatePayslipRow();
                    const meta = input.parentElement?.querySelector("[data-cell-meta]");
                    if (meta) {
                        meta.textContent = `Vorig: ${result.previous_value || "-"} · Mutatie: ${result.updated_at || "-"}`;
                    }
                } catch (error) {
                    input.classList.add("payroll-cell-input--error");
                } finally {
                    input.classList.remove("payroll-cell-input--saving");
                }
            };
            input.addEventListener("input", () => {
                input.classList.add("payroll-cell-input--dirty");
                recalculatePayslipRow();
                window.clearTimeout(saveTimer);
                saveTimer = window.setTimeout(save, 650);
            });
            input.addEventListener("change", () => {
                input.classList.add("payroll-cell-input--dirty");
                recalculatePayslipRow();
                window.clearTimeout(saveTimer);
                save();
            });
            input.addEventListener("blur", () => {
                window.clearTimeout(saveTimer);
                save();
            });
        });
    });

    function workbookCellSortValue(cell) {
        const input = cell?.querySelector?.("[data-payroll-cell]");
        if (input) {
            return input.value || "";
        }
        return cell?.textContent?.trim() || "";
    }

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

    const periodCreateModal = document.querySelector("[data-period-create-modal]");
    const openPeriodCreateModal = () => {
        if (!periodCreateModal) {
            return;
        }
        periodCreateModal.hidden = false;
        periodCreateModal.querySelector("input, select, button")?.focus();
    };
    const closePeriodCreateModal = () => {
        if (periodCreateModal) {
            periodCreateModal.hidden = true;
        }
    };
    document.querySelector("[data-period-create-open]")?.addEventListener("click", openPeriodCreateModal);
    document.querySelector("[data-period-create-close]")?.addEventListener("click", closePeriodCreateModal);
    periodCreateModal?.addEventListener("click", (event) => {
        if (event.target === periodCreateModal) {
            closePeriodCreateModal();
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && periodCreateModal && !periodCreateModal.hidden) {
            closePeriodCreateModal();
        }
    });

    const manualTimesheetModal = document.querySelector("[data-manual-timesheet-modal]");
    const openManualTimesheetModal = () => {
        if (!manualTimesheetModal) {
            return;
        }
        manualTimesheetModal.hidden = false;
        manualTimesheetModal.querySelector("input, select, button")?.focus();
    };
    const closeManualTimesheetModal = () => {
        if (manualTimesheetModal) {
            manualTimesheetModal.hidden = true;
        }
    };
    document.querySelector("[data-manual-timesheet-open]")?.addEventListener("click", openManualTimesheetModal);
    document.querySelectorAll("[data-manual-timesheet-close]").forEach((button) => {
        button.addEventListener("click", closeManualTimesheetModal);
    });
    manualTimesheetModal?.addEventListener("click", (event) => {
        if (event.target === manualTimesheetModal) {
            closeManualTimesheetModal();
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && manualTimesheetModal && !manualTimesheetModal.hidden) {
            closeManualTimesheetModal();
        }
    });

    document.querySelectorAll("[data-candidate-match-select]").forEach((select) => {
        const form = select.closest("form");
        const searchInput = form?.querySelector("[data-candidate-match-search]");
        const employeeNameInput = form?.querySelector('[name="field_employee_name"]');
        const employeePhoneInput = form?.querySelector('[name="field_employee_phone"]');
        const suggestionsTarget = form?.querySelector("[data-candidate-suggestions]");
        const summaryTarget = form?.querySelector("[data-candidate-match-summary]");
        const searchUrl = select.dataset.candidateSearchUrl;
        let candidateSearchTimer = null;
        let candidateSearchSequence = 0;

        const normalize = (value) => (value || "")
            .toString()
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[^a-z0-9]+/g, " ")
            .trim();

        const scoreCandidate = (option, parsedName, parsedPhone) => {
            const name = normalize(option.dataset.name || option.textContent);
            const phone = (option.dataset.phone || "").replace(/\D/g, "");
            const query = normalize(parsedName);
            const queryPhone = (parsedPhone || "").replace(/\D/g, "");
            if (!option.value || (!query && !queryPhone)) {
                return 0;
            }
            if (queryPhone && phone && phone.endsWith(queryPhone.slice(-8))) {
                return 120;
            }
            if (!query || !name) {
                return 0;
            }
            if (name === query) {
                return 100;
            }
            if (name.includes(query) || query.includes(name)) {
                return 82;
            }
            const nameParts = new Set(name.split(" ").filter(Boolean));
            const queryParts = query.split(" ").filter(Boolean);
            const editDistance = (left, right) => {
                if (Math.abs(left.length - right.length) > 2) {
                    return 3;
                }
                const costs = Array.from({ length: right.length + 1 }, (_, index) => index);
                for (let i = 1; i <= left.length; i += 1) {
                    let previous = i;
                    for (let j = 1; j <= right.length; j += 1) {
                        const next = left[i - 1] === right[j - 1]
                            ? costs[j - 1]
                            : Math.min(costs[j - 1], previous, costs[j]) + 1;
                        costs[j - 1] = previous;
                        previous = next;
                    }
                    costs[right.length] = previous;
                }
                return costs[right.length];
            };
            const hits = queryParts.filter((part) => nameParts.has(part) || [...nameParts].some((namePart) => (
                namePart.startsWith(part)
                || part.startsWith(namePart)
                || (part.length >= 5 && namePart.length >= 5 && editDistance(part, namePart) <= 2)
            ))).length;
            return queryParts.length ? Math.round((hits / queryParts.length) * 72) : 0;
        };

        const applySelectedCandidate = () => {
            const option = select.selectedOptions[0];
            if (!option || !option.value) {
                if (summaryTarget) {
                    summaryTarget.classList.remove("accordion-metric--green", "accordion-metric--orange");
                    summaryTarget.classList.add("accordion-metric--red");
                    summaryTarget.innerHTML = "<i></i>Kandidaat: Niet gekoppeld";
                }
                return;
            }
            if (employeeNameInput && option.dataset.name) {
                employeeNameInput.value = option.dataset.name;
                employeeNameInput.dispatchEvent(new Event("input", { bubbles: true }));
            }
            if (employeePhoneInput && option.dataset.phone) {
                employeePhoneInput.value = option.dataset.phone;
                employeePhoneInput.dispatchEvent(new Event("input", { bubbles: true }));
            }
            if (searchInput && option.dataset.name) {
                searchInput.value = option.dataset.name;
            }
            if (summaryTarget) {
                summaryTarget.classList.remove("accordion-metric--red", "accordion-metric--orange");
                summaryTarget.classList.add("accordion-metric--green");
                summaryTarget.innerHTML = `<i></i>Kandidaat: ${option.dataset.name || option.textContent}`;
            }
        };

        const renderCandidateOptions = (results, selectedValue = "") => {
            const emptyOption = select.querySelector('option[value=""]')?.cloneNode(true)
                || new Option("Geen kandidaat gekoppeld", "");
            select.innerHTML = "";
            select.append(emptyOption);
            results.forEach((candidate) => {
                const parts = [candidate.name, candidate.phone, candidate.city].filter(Boolean);
                const option = new Option(parts.join(" | "), candidate.value);
                option.dataset.name = candidate.name || "";
                option.dataset.phone = candidate.phone || "";
                option.dataset.city = candidate.city || "";
                select.append(option);
            });
            if (selectedValue && [...select.options].some((option) => option.value === selectedValue)) {
                select.value = selectedValue;
            }
        };

        const chooseCurrentCandidate = () => {
            if (select.value) {
                applySelectedCandidate();
            }
        };

        const loadCandidates = async (query, previousValue, sequence) => {
            try {
                const response = await fetch(`${searchUrl}?q=${encodeURIComponent(query)}&limit=80`);
                if (!response.ok || sequence !== candidateSearchSequence) {
                    return false;
                }
                const data = await response.json();
                const results = Array.isArray(data.results) ? data.results : [];
                renderCandidateOptions(results, previousValue);
                chooseCurrentCandidate();
                renderSuggestions();
                return true;
            } catch (error) {
                console.warn("Kandidaten zoeken mislukt", error);
                return false;
            }
        };

        const filterCandidates = (delay = 70) => {
            const query = (searchInput?.value || "").trim();
            if (!searchUrl) {
                return;
            }
            window.clearTimeout(candidateSearchTimer);
            candidateSearchTimer = window.setTimeout(async () => {
                const sequence = candidateSearchSequence + 1;
                candidateSearchSequence = sequence;
                await loadCandidates(query, select.value, sequence);
            }, delay);
        };

        const renderSuggestions = () => {
            if (!suggestionsTarget) {
                return;
            }
            const parsedName = employeeNameInput?.value || "";
            const parsedPhone = employeePhoneInput?.value || "";
            const scored = [...select.options]
                .filter((option) => option.value)
                .map((option) => ({ option, score: scoreCandidate(option, parsedName, parsedPhone) }))
                .filter((item) => item.score >= 35)
                .sort((a, b) => b.score - a.score)
                .slice(0, 4);
            suggestionsTarget.innerHTML = "";
            if (!scored.length) {
                const empty = document.createElement("div");
                empty.className = "candidate-suggestion-empty";
                empty.textContent = "Geen match in kandidatendatabase";
                suggestionsTarget.append(empty);
                return;
            }
            scored.forEach(({ option, score }) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "candidate-suggestion";
                button.innerHTML = `<strong>${option.dataset.name || option.textContent}</strong><span>${Math.min(score, 100)}% match</span>`;
                button.addEventListener("click", () => {
                    select.value = option.value;
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                });
                suggestionsTarget.append(button);
            });
        };

        select.addEventListener("change", () => {
            applySelectedCandidate();
            form?.dispatchEvent(new Event("change", { bubbles: true }));
        });
        searchInput?.addEventListener("input", () => filterCandidates());
        searchInput?.addEventListener("keydown", async (event) => {
            if (event.key !== "Enter") {
                return;
            }
            event.preventDefault();
            window.clearTimeout(candidateSearchTimer);
            const query = (searchInput.value || "").trim();
            if (searchUrl) {
                const sequence = candidateSearchSequence + 1;
                candidateSearchSequence = sequence;
                await loadCandidates(query, select.value, sequence);
            }
            chooseCurrentCandidate();
            form?.requestSubmit();
        });
        select.addEventListener("keydown", (event) => {
            if (event.key !== "Enter") {
                return;
            }
            event.preventDefault();
            chooseCurrentCandidate();
            form?.requestSubmit();
        });
        employeeNameInput?.addEventListener("input", renderSuggestions);
        employeePhoneInput?.addEventListener("input", renderSuggestions);
        renderSuggestions();
        if (employeeNameInput?.value && searchUrl) {
            searchInput.value = employeeNameInput.value;
            filterCandidates();
        }
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
        const absenceInput = form.elements.field_absence_code;
        const autosaveStatus = form.querySelector("[data-autosave-status]");
        let autosaveTimer = null;
        let autosaveController = null;
        const principalSearchInput = form.querySelector("[data-principal-search]");
        let principalSearchTimer = null;
        let principalSearchSequence = 0;
        const dayCodeInputs = [
            ["field_monday_code", "field_monday_hours"],
            ["field_tuesday_code", "field_tuesday_hours"],
            ["field_wednesday_code", "field_wednesday_hours"],
            ["field_thursday_code", "field_thursday_hours"],
            ["field_friday_code", "field_friday_hours"],
            ["field_saturday_code", "field_saturday_hours"],
            ["field_sunday_code", "field_sunday_hours"],
        ].map(([codeName, hoursName]) => ({
            code: form.elements[codeName],
            hours: form.elements[hoursName],
        })).filter((item) => item.code && item.hours);

        const syncWorkflowIds = () => {
            if (principalTarget && principalSelect) {
                principalTarget.value = principalSelect.selectedOptions[0]?.dataset.id || "";
            }
            if (projectTarget && projectSelect) {
                projectTarget.value = projectSelect.selectedOptions[0]?.dataset.id || "";
            }
        };

        const renderPrincipalOptions = (principals, selectedValue, selectedLabel) => {
            if (!principalSelect) {
                return;
            }
            principalSelect.innerHTML = "";
            principalSelect.append(new Option("Kies opdrachtgever", ""));
            const hasSelectedInResults = principals.some((principal) => String(principal.name || "") === selectedValue);
            if (selectedValue && selectedLabel && !hasSelectedInResults) {
                const selectedOption = new Option(selectedLabel, selectedValue);
                selectedOption.dataset.id = principalTarget?.value || "";
                selectedOption.selected = true;
                principalSelect.append(selectedOption);
            }
            principals.forEach((principal) => {
                if (!principal.name) {
                    return;
                }
                const option = new Option(principal.name, principal.name);
                option.dataset.id = principal.id || "";
                option.selected = principal.name === selectedValue;
                principalSelect.append(option);
            });
        };

        const searchPrincipals = () => {
            const searchUrl = principalSelect?.dataset.principalSearchUrl;
            if (!searchUrl || !principalSearchInput) {
                return;
            }
            window.clearTimeout(principalSearchTimer);
            principalSearchTimer = window.setTimeout(async () => {
                const sequence = principalSearchSequence + 1;
                principalSearchSequence = sequence;
                const selectedOption = principalSelect.selectedOptions[0];
                const selectedValue = principalSelect.value;
                const selectedLabel = selectedOption?.textContent?.trim() || selectedValue;
                try {
                    const response = await fetch(`${searchUrl}?q=${encodeURIComponent(principalSearchInput.value.trim())}&limit=250`);
                    if (!response.ok || sequence !== principalSearchSequence) {
                        return;
                    }
                    const data = await response.json();
                    renderPrincipalOptions(Array.isArray(data.results) ? data.results : [], selectedValue, selectedLabel);
                    syncWorkflowIds();
                } catch (error) {
                    console.warn("Opdrachtgevers zoeken mislukt", error);
                }
            }, 120);
        };

        principalSelect?.addEventListener("change", () => {
            if (principalSearchInput) {
                principalSearchInput.value = principalSelect.value || "";
            }
            syncWorkflowIds();
        });
        principalSearchInput?.addEventListener("input", searchPrincipals);
        principalSearchInput?.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                searchPrincipals();
            }
        });
        if (principalSearchInput && principalSelect?.value) {
            principalSearchInput.value = principalSelect.value;
        }
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

        const setAutosaveStatus = (text, state = "") => {
            if (!autosaveStatus) {
                return;
            }
            autosaveStatus.textContent = text;
            autosaveStatus.dataset.state = state;
        };

        const setSummaryMetric = (target, value, state = "green") => {
            const metric = form.querySelector(`[data-summary-target="${target}"]`);
            if (!metric) {
                return;
            }
            const label = metric.dataset.summaryLabel || "";
            const unit = metric.dataset.summaryUnit || "";
            const cleanValue = String(value || "").trim();
            metric.classList.remove("accordion-metric--red", "accordion-metric--orange", "accordion-metric--green");
            metric.classList.add(`accordion-metric--${cleanValue ? state : "red"}`);
            metric.title = cleanValue ? `${label}: bijgewerkt` : `${label}: leeg`;
            metric.innerHTML = `<i></i>${label}: ${cleanValue ? `${cleanValue}${unit}` : "Leeg"}`;
        };

        const syncSumCheck = (inputs, totalField, calculatedField, checkField, unit, missingMessage) => {
            if (!calculatedField || !checkField) {
                return;
            }
            const values = inputs.map((input) => parseHours(input.value)).filter((value) => value !== null);
            if (!values.length) {
                calculatedField.value = "";
                checkField.value = "";
                setSummaryMetric(totalField?.name?.replace("field_", ""), "", "red");
                setSummaryMetric(checkField.name.replace("field_", ""), "", "red");
                setSummaryMetric(calculatedField.name.replace("field_", ""), "", "red");
                return;
            }
            const calculated = values.reduce((sum, value) => sum + value, 0);
            calculatedField.value = formatHours(calculated);
            const stated = parseHours(totalField?.value);
            if (stated === null) {
                if (totalField) {
                    totalField.value = formatHours(calculated);
                }
                checkField.value = "klopt";
                setSummaryMetric(totalField?.name?.replace("field_", ""), totalField?.value || "", "green");
                setSummaryMetric(checkField.name.replace("field_", ""), checkField.value, "green");
                setSummaryMetric(calculatedField.name.replace("field_", ""), calculatedField.value, "green");
                return;
            }
            const difference = Math.abs(calculated - stated);
            if (difference >= 0.005) {
                checkField.value = `bijlage ${formatHours(stated)}, som ${formatHours(calculated)}`;
            } else {
                checkField.value = "klopt";
            }
            const checkState = difference < 0.005 ? "green" : "red";
            setSummaryMetric(totalField?.name?.replace("field_", ""), totalField?.value || "", difference < 0.005 ? "green" : "orange");
            setSummaryMetric(checkField.name.replace("field_", ""), checkField.value, checkState);
            setSummaryMetric(calculatedField.name.replace("field_", ""), calculatedField.value, "green");
        };

        const syncTotalCheck = (source = "") => {
            syncSumCheck(dayInputs, totalInput, calculatedInput, checkInput, "uur", "totaal ontbreekt");
            syncSumCheck(kmInputs, totalKmInput, calculatedKmInput, checkKmInput, "km", "totaal km ontbreekt");
        };

        const saveCorrections = async () => {
            if (!form.action) {
                return;
            }
            autosaveController?.abort();
            autosaveController = new AbortController();
            setAutosaveStatus("Opslaan...", "saving");
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),
                    headers: {
                        "X-Requested-With": "fetch",
                        Accept: "application/json",
                    },
                    signal: autosaveController.signal,
                });
                if (!response.ok) {
                    throw new Error(`Opslaan mislukt: ${response.status}`);
                }
                setAutosaveStatus("Opgeslagen", "saved");
            } catch (error) {
                if (error.name === "AbortError") {
                    return;
                }
                console.warn("Automatisch opslaan mislukt", error);
                setAutosaveStatus("Niet opgeslagen", "error");
            }
        };

        const scheduleAutosave = () => {
            setAutosaveStatus("Wijziging klaarzetten...", "pending");
            window.clearTimeout(autosaveTimer);
            autosaveTimer = window.setTimeout(saveCorrections, 650);
        };

        const applyAbsenceCode = () => {
            const absenceCode = (absenceInput?.value || "").trim();
            if (!absenceCode) {
                return;
            }
            dayCodeInputs.forEach(({ code, hours }) => {
                const hoursValue = String(hours.value || "").trim().replace(",", ".");
                const hoursNumber = Number(hoursValue || "0");
                if (!code.value.trim() && (!hoursValue || hoursNumber === 0)) {
                    code.value = absenceCode;
                }
            });
        };

        dayInputs.forEach((input) => input.addEventListener("input", () => {
            syncTotalCheck("hours");
            scheduleAutosave();
        }));
        totalInput?.addEventListener("input", () => {
            syncTotalCheck("total");
            scheduleAutosave();
        });
        kmInputs.forEach((input) => input.addEventListener("input", () => {
            syncTotalCheck("km");
            scheduleAutosave();
        }));
        totalKmInput?.addEventListener("input", () => {
            syncTotalCheck("total_km");
            scheduleAutosave();
        });
        form.addEventListener("change", () => {
            syncWorkflowIds();
            syncTotalCheck();
            scheduleAutosave();
        });
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            syncWorkflowIds();
            syncTotalCheck();
            saveCorrections();
        });
        absenceInput?.addEventListener("change", () => {
            applyAbsenceCode();
            scheduleAutosave();
        });
        applyAbsenceCode();
        syncTotalCheck("hours");
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
        if (!action.includes("/api/whatsapp/timesheet/") || action.includes("/delete") || action.includes("/corrections")) {
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

    document.querySelectorAll("[data-test-file-input]").forEach((input) => {
        input.addEventListener("change", () => {
            if (input.files?.length && input.form) {
                input.form.requestSubmit ? input.form.requestSubmit() : input.form.submit();
            }
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
