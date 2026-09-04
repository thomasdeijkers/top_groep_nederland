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

    const settingsCards = Array.from(document.querySelectorAll(".settings-only .settings-card"));
    const activeSettingsTarget = window.location.hash ? document.querySelector(window.location.hash) : null;
    settingsCards.forEach((card) => {
        const header = card.querySelector(":scope > .settings-card-heading") || card.firstElementChild;
        if (!header) {
            return;
        }
        header.classList.add("settings-collapse-header");
        const title = header.querySelector("h2")?.textContent?.trim() || "Instelling";
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "settings-collapse-toggle";
        toggle.setAttribute("aria-expanded", "false");
        toggle.textContent = "Openen";
        header.appendChild(toggle);
        const setCollapsed = (collapsed) => {
            card.dataset.settingsCollapsed = collapsed ? "true" : "false";
            toggle.setAttribute("aria-expanded", String(!collapsed));
            toggle.textContent = collapsed ? "Openen" : "Sluiten";
            toggle.setAttribute("aria-label", `${collapsed ? "Open" : "Sluit"} ${title}`);
        };
        setCollapsed(!(activeSettingsTarget && card === activeSettingsTarget));
        toggle.addEventListener("click", () => {
            const nextCollapsed = card.dataset.settingsCollapsed !== "true";
            setCollapsed(nextCollapsed);
        });
    });

    document.querySelectorAll("[data-settings-edit-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            const target = document.getElementById(button.dataset.settingsEditToggle || "");
            if (!target) {
                return;
            }
            target.hidden = !target.hidden;
            button.textContent = target.hidden ? "Aanpassen" : "Sluiten";
        });
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
                const params = new URLSearchParams(window.location.search);
                if (params.has("flow")) {
                    params.delete("flow");
                    const query = params.toString();
                    const hash = target === "archive" ? "#periode-archief" : "#periodes";
                    window.location.href = `${window.location.pathname}${query ? `?${query}` : ""}${hash}`;
                    return;
                }
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

        const summaryParseNumber = (value) => {
            let normalized = String(value || "").replace(/[^\d,.-]/g, "").trim();
            if (normalized.includes(",") && normalized.includes(".")) {
                normalized = normalized.replace(/\./g, "").replace(",", ".");
            } else if (normalized.includes(",")) {
                normalized = normalized.replace(",", ".");
            }
            const parsed = Number.parseFloat(normalized);
            return Number.isFinite(parsed) ? parsed : 0;
        };
        const summaryFormatMoney = (value) => new Intl.NumberFormat("nl-NL", {
            style: "currency",
            currency: "EUR",
        }).format(value || 0);
        const recalculatePaymentSummary = () => {
            const totals = { "Uit te betalen": 0, "Uitbetaald": 0 };
            workbook.querySelectorAll('[data-payroll-panel="Uit te betalen"], [data-payroll-panel="Uitbetaald"]').forEach((panel) => {
                const label = panel.dataset.payrollPanel;
                panel.querySelectorAll(".payroll-col-net-amount [data-payroll-cell]").forEach((input) => {
                    totals[label] += summaryParseNumber(input.value);
                });
            });
            Object.entries(totals).forEach(([label, total]) => {
                const target = document.querySelector(`[data-payroll-summary-total="${label}"]`);
                if (target) {
                    target.textContent = summaryFormatMoney(total);
                }
            });
        };

        const payrollBlockModal = document.querySelector("[data-payroll-block-modal]");
        const payrollBlockList = document.querySelector("[data-payroll-block-list]");
        const payrollBlockSummary = document.querySelector("[data-payroll-block-summary]");
        const closePayrollBlockModal = () => {
            if (payrollBlockModal) {
                payrollBlockModal.hidden = true;
            }
        };
        const cleanBlockerText = (text) => String(text || "")
            .replace(/\s+/g, " ")
            .replace(/[.;]\s*$/, "")
            .trim();
        const splitBlockerFields = (blocker) => {
            const text = cleanBlockerText(blocker);
            if (!text) {
                return [];
            }
            const colonIndex = text.indexOf(":");
            if (colonIndex === -1) {
                return [text];
            }
            const prefix = text.slice(0, colonIndex).trim();
            const fieldText = text.slice(colonIndex + 1);
            const fields = fieldText
                .split(",")
                .map((field) => cleanBlockerText(field))
                .filter(Boolean);
            if (!fields.length) {
                return [text];
            }
            return fields.map((field) => `${prefix}: ${field}`);
        };
        const blockerItemsFromButton = (button) => {
            const rawItems = (button.dataset.blockFields || "")
                .split("||")
                .map((item) => cleanBlockerText(item))
                .filter(Boolean);
            const items = (rawItems.length ? rawItems : [button.dataset.blockReason || "Deze loonregel mist nog gegevens."])
                .flatMap(splitBlockerFields);
            return [...new Set(items)].filter(Boolean);
        };
        const openPayrollBlockModal = (button) => {
            const items = blockerItemsFromButton(button);
            if (!payrollBlockModal || !payrollBlockList) {
                window.alert(`Uitbetalen kan nog niet.\n\n${items.join("\n")}`);
                return;
            }
            payrollBlockList.innerHTML = "";
            items.forEach((item) => {
                const listItem = document.createElement("li");
                listItem.textContent = item;
                payrollBlockList.appendChild(listItem);
            });
            if (payrollBlockSummary) {
                payrollBlockSummary.textContent = `${items.length} punt${items.length === 1 ? "" : "en"} ontbre${items.length === 1 ? "ekt" : "ken"} voor verloning.`;
            }
            payrollBlockModal.hidden = false;
            payrollBlockModal.querySelector("[data-payroll-block-close]")?.focus();
        };

        document.querySelectorAll("[data-payroll-block-close]").forEach((button) => {
            button.addEventListener("click", closePayrollBlockModal);
        });
        payrollBlockModal?.addEventListener("click", (event) => {
            if (event.target === payrollBlockModal) {
                closePayrollBlockModal();
            }
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && payrollBlockModal && !payrollBlockModal.hidden) {
                closePayrollBlockModal();
            }
        });

        workbook.querySelectorAll("[data-payroll-blocked-payment]").forEach((button) => {
            button.addEventListener("click", () => {
                openPayrollBlockModal(button);
            });
        });

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
            const row = input.closest("tr");
            const field = (key) => row?.querySelector(`.payroll-col-${key} [data-payroll-cell]`);
            const parseNumber = (value) => {
                let normalized = String(value || "")
                    .replace(/[^\d,.-]/g, "")
                    .trim();
                if (normalized.includes(",") && normalized.includes(".")) {
                    normalized = normalized.replace(/\./g, "").replace(",", ".");
                } else if (normalized.includes(",")) {
                    normalized = normalized.replace(",", ".");
                }
                const parsed = Number.parseFloat(normalized);
                return Number.isFinite(parsed) ? parsed : 0;
            };
            const formatNumber = (value) => new Intl.NumberFormat("nl-NL", {
                minimumFractionDigits: 0,
                maximumFractionDigits: 2,
            }).format(value);
            const formatMoney = (value) => new Intl.NumberFormat("nl-NL", {
                style: "currency",
                currency: "EUR",
            }).format(Math.max(value, 0));
            const setFieldValue = (key, value) => {
                const target = field(key);
                if (target && target !== input) {
                    target.value = value;
                    target.classList.add("payroll-cell-input--dirty");
                }
            };
            const setSourceMeta = (target, updatedAt = "") => {
                const meta = target?.parentElement?.querySelector("[data-cell-meta]");
                if (!meta) {
                    return;
                }
                const sourceValue = target.dataset.sourceValue || "leeg";
                const isOverride = (target.value || "") !== (target.dataset.sourceValue || "");
                meta.textContent = isOverride
                    ? `Override actief (origineel urenbriefje: ${sourceValue || "leeg"})${updatedAt ? ` · ${updatedAt}` : ""}`
                    : `Origineel urenbriefje: ${sourceValue || "leeg"}`;
                target.classList.toggle("payroll-cell-input--overridden", isOverride);
            };
            const recalculateWorkbookRow = () => {
                if (!row) {
                    return;
                }
                if (input.dataset.tabLabel.startsWith("WK")) {
                    const workedHours = parseNumber(field("worked-hours")?.value);
                    const workedDays = parseNumber(field("worked-days")?.value);
                    const singleTripKm = parseNumber(field("single-trip-km")?.value);
                    const workKm = parseNumber(field("work-km")?.value);
                    let commuteKm = parseNumber(field("commute-km")?.value);
                    if (input.dataset.columnKey === "single_trip_km" && singleTripKm && workedDays) {
                        commuteKm = singleTripKm * workedDays * 2;
                        setFieldValue("commute-km", formatNumber(commuteKm));
                    }
                    setFieldValue("net-amount", formatMoney((750 * workedHours) / 40));
                    setFieldValue("total-km", formatNumber(commuteKm + workKm));
                    return;
                }
                if (input.dataset.tabLabel === "Periode") {
                    const contractHours = parseNumber(field("contract-hours")?.value);
                    const grossHourlyWage = parseNumber(field("gross-hourly-wage")?.value);
                    const grossTotal = contractHours * grossHourlyWage;
                    setFieldValue("gross-total", formatMoney(grossTotal));
                    setFieldValue("labor-cost-margin", formatMoney(grossTotal * 0.18));
                    if (!field("net-period-basis")?.value) {
                        setFieldValue("net-period-basis", formatMoney(750));
                    }
                    return;
                }
                const field = (key) => row.querySelector(`.payroll-col-${key} [data-payroll-cell]`);
                if (input.dataset.tabLabel !== "Loonstrook") {
                    return;
                }
                const totalHours = parseNumber(field("total-worked-hours")?.value);
                const hourlyWage = parseNumber(field("hourly-wage")?.value);
                const totalKm = parseNumber(field("total-km")?.value);
                const declarations = parseNumber(field("extra-reimbursements")?.value);
                const grossWage = totalHours && hourlyWage ? totalHours * hourlyWage : parseNumber(field("gross-wage")?.value);
                let periodTotal = parseNumber(field("period-total")?.value);
                if (grossWage) {
                    const pension = grossWage * 0.035;
                    const tax = grossWage * 0.29;
                    const travel = totalKm * 0.23;
                    const weeklyAgreement = parseNumber(field("weekly-wage")?.value) || 750;
                    periodTotal = ((weeklyAgreement * totalHours) / 40) + travel + declarations;
                    setFieldValue("gross-wage", formatMoney(grossWage));
                    setFieldValue("weekly-wage", formatMoney(weeklyAgreement));
                    setFieldValue("pension-deduction", formatMoney(pension));
                    setFieldValue("payroll-tax", formatMoney(tax));
                    setFieldValue("net-after-deductions", formatMoney(Math.max(grossWage - pension - tax, 0)));
                    setFieldValue("wkr-reimbursements", formatMoney(travel));
                    setFieldValue("period-total", formatMoney(periodTotal));
                }
                const alreadyReceived = parseNumber(field("already-received-net")?.value);
                const payslipAdvance = parseNumber(field("payslip-advance")?.value);
                const netToReceive = formatMoney(Math.max(periodTotal - alreadyReceived - payslipAdvance, 0));
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
                const sourceValue = input.dataset.sourceValue ?? originalValue;
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
                            original_value: sourceValue,
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
                    recalculateWorkbookRow();
                    setSourceMeta(input, result.updated_at || "");
                    recalculatePaymentSummary();
                } catch (error) {
                    input.classList.add("payroll-cell-input--error");
                } finally {
                    input.classList.remove("payroll-cell-input--saving");
                }
            };
            input.addEventListener("input", () => {
                input.classList.add("payroll-cell-input--dirty");
                recalculateWorkbookRow();
                setSourceMeta(input);
                recalculatePaymentSummary();
                window.clearTimeout(saveTimer);
                saveTimer = window.setTimeout(save, 650);
            });
            input.addEventListener("change", () => {
                input.classList.add("payroll-cell-input--dirty");
                recalculateWorkbookRow();
                setSourceMeta(input);
                recalculatePaymentSummary();
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
        const workflowCandidateTarget = document.querySelector("[data-workflow-candidate-id]");
        const validateButton = document.querySelector("[data-workflow-validate-button]");
        const candidateNote = document.querySelector("[data-workflow-candidate-note]");
        const createCandidatePanel = document.querySelector("[data-candidate-create-panel]");
        const searchUrl = select.dataset.candidateSearchUrl;
        const canApproveControl = validateButton?.dataset.canApproveControl === "1";
        const canSendToPayroll = validateButton?.dataset.canSendToPayroll === "1";
        const canUseWorkflowButton = canApproveControl || canSendToPayroll;
        let candidateSearchTimer = null;
        let candidateSearchSequence = 0;

        const normalize = (value) => (value || "")
            .toString()
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[^a-z0-9]+/g, " ")
            .trim();

        const namePrefixes = new Set(["de", "den", "der", "het", "in", "op", "te", "ten", "ter", "tot", "uit", "van", "vd", "von"]);
        const nameParts = (value) => normalize(value).split(" ").filter((part) => part.length >= 2);
        const lastNameQuery = (value) => {
            const parts = nameParts(value);
            if (!parts.length) {
                return "";
            }
            if (parts.length === 1) {
                return parts[0];
            }
            const last = parts[parts.length - 1];
            const prefixes = [];
            for (let index = parts.length - 2; index >= 0; index -= 1) {
                if (!namePrefixes.has(parts[index])) {
                    break;
                }
                prefixes.unshift(parts[index]);
            }
            return [...prefixes, last].join(" ");
        };

        const scoreCandidate = (option, parsedName, parsedPhone) => {
            const name = normalize(option.dataset.name || option.textContent);
            const firstName = normalize(option.dataset.firstName || "");
            const lastName = normalize(option.dataset.lastName || "");
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
                return 120;
            }
            const queryParts = nameParts(query);
            const queryLast = lastNameQuery(query);
            const plainQueryLast = queryLast.split(" ").pop() || "";
            const candidateLast = lastName || lastNameQuery(name);
            const candidateParts = new Set(nameParts(name));
            let score = 0;
            if (queryLast && (candidateLast === queryLast || name.endsWith(queryLast))) {
                score += 85;
            } else if (plainQueryLast && (candidateLast.split(" ").includes(plainQueryLast) || name.endsWith(plainQueryLast))) {
                score += 75;
            }
            const hits = queryParts.filter((part) => candidateParts.has(part)).length;
            score += Math.min(30, hits * 15);
            if (firstName && queryParts[0] && firstName.split(" ").includes(queryParts[0])) {
                score += 15;
            }
            if (!score && name.includes(query)) {
                score = 45;
            }
            return Math.min(score, 130);
        };
        const applySelectedCandidate = () => {
            const option = select.selectedOptions[0];
            if (!option || !option.value) {
                if (workflowCandidateTarget) {
                    workflowCandidateTarget.value = "";
                }
                if (validateButton) {
                    validateButton.disabled = true;
                    validateButton.title = canUseWorkflowButton
                        ? "Koppel eerst een kandidaat"
                        : "Deze actie is nu niet beschikbaar.";
                }
                if (candidateNote) {
                    candidateNote.hidden = false;
                }
                if (createCandidatePanel) {
                    createCandidatePanel.hidden = false;
                }
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
            if (workflowCandidateTarget) {
                workflowCandidateTarget.value = option.value;
            }
            if (validateButton) {
                validateButton.disabled = !canUseWorkflowButton;
                if (canUseWorkflowButton) {
                    validateButton.removeAttribute("title");
                } else {
                    validateButton.title = "Deze actie is nu niet beschikbaar.";
                }
            }
            if (candidateNote) {
                candidateNote.hidden = canUseWorkflowButton;
            }
            if (createCandidatePanel) {
                createCandidatePanel.hidden = true;
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
                option.dataset.firstName = candidate.first_name || "";
                option.dataset.lastName = candidate.last_name || "";
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
                .filter((item) => item.score >= 25)
                .sort((a, b) => b.score - a.score)
                .slice(0, 8);
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
        const principalSuggestions = form.querySelector("[data-principal-suggestions]");
        const projectSearchInput = form.querySelector("[data-project-search]");
        const projectSuggestions = form.querySelector("[data-project-suggestions]");
        let principalSearchTimer = null;
        let principalSearchSequence = 0;
        let projectSearchTimer = null;
        let projectSearchSequence = 0;
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

        const sortByLabel = (items, key = "name") => [...items].sort((left, right) => String(left[key] || "").localeCompare(String(right[key] || ""), "nl", { sensitivity: "base" }));

        const syncWorkflowIds = () => {
            if (principalTarget && principalSelect) {
                principalTarget.value = principalSelect.selectedOptions[0]?.dataset.id || "";
            }
            if (projectTarget && projectSelect) {
                projectTarget.value = projectSelect.selectedOptions[0]?.dataset.id || "";
            }
        };

        const renderEntitySuggestions = (target, items, labelKey, metaBuilder, onPick) => {
            if (!target) {
                return;
            }
            target.innerHTML = "";
            const visible = items.slice(0, 6);
            if (!visible.length) {
                const empty = document.createElement("div");
                empty.className = "entity-suggestion-empty";
                empty.textContent = "Geen resultaten";
                target.append(empty);
                return;
            }
            visible.forEach((item) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "entity-suggestion";
                button.innerHTML = `<strong>${item[labelKey] || "Onbekend"}</strong><span>${metaBuilder(item)}</span>`;
                button.addEventListener("click", () => onPick(item));
                target.append(button);
            });
        };

        const renderPrincipalOptions = (principals, selectedValue, selectedLabel) => {
            if (!principalSelect) {
                return [];
            }
            const sorted = sortByLabel(principals, "name");
            principalSelect.innerHTML = "";
            principalSelect.append(new Option("Kies opdrachtgever", ""));
            const hasSelectedInResults = sorted.some((principal) => String(principal.name || "") === selectedValue);
            if (selectedValue && selectedLabel && !hasSelectedInResults) {
                const selectedOption = new Option(selectedLabel, selectedValue);
                selectedOption.dataset.id = principalTarget?.value || "";
                selectedOption.selected = true;
                principalSelect.append(selectedOption);
            }
            sorted.forEach((principal) => {
                if (!principal.name) {
                    return;
                }
                const option = new Option(principal.name, principal.name);
                option.dataset.id = principal.id || "";
                option.selected = principal.name === selectedValue;
                principalSelect.append(option);
            });
            renderEntitySuggestions(principalSuggestions, sorted, "name", (item) => [item.city, item.contact].filter(Boolean).join(" - ") || "Opdrachtgever", (item) => {
                principalSelect.value = item.name || "";
                principalSelect.dispatchEvent(new Event("change", { bubbles: true }));
            });
            return sorted;
        };

        const renderProjectOptions = (projects, selectedValue, selectedLabel) => {
            if (!projectSelect) {
                return [];
            }
            const sorted = sortByLabel(projects, "title");
            projectSelect.innerHTML = "";
            projectSelect.append(new Option("Kies project", ""));
            const hasSelectedInResults = sorted.some((project) => String(project.title || "") === selectedValue);
            if (selectedValue && selectedLabel && !hasSelectedInResults) {
                const selectedOption = new Option(selectedLabel, selectedValue);
                selectedOption.dataset.id = projectTarget?.value || "";
                selectedOption.selected = true;
                projectSelect.append(selectedOption);
            }
            sorted.forEach((project) => {
                if (!project.title) {
                    return;
                }
                const meta = [project.reference_number, project.relation_name, project.cao_name ? `CAO: ${project.cao_name}` : ""].filter(Boolean).join(" - ");
                const option = new Option(meta ? `${project.title} - ${meta}` : project.title, project.title);
                option.dataset.id = project.id || "";
                option.selected = project.title === selectedValue;
                projectSelect.append(option);
            });
            renderEntitySuggestions(projectSuggestions, sorted, "title", (item) => [item.reference_number, item.relation_name, item.cao_name].filter(Boolean).join(" - ") || "Project", (item) => {
                projectSelect.value = item.title || "";
                projectSelect.dispatchEvent(new Event("change", { bubbles: true }));
            });
            return sorted;
        };

        const searchEntities = ({ input, select, timerRef, sequenceRef, setTimer, setSequence, renderOptions, label }) => {
            const searchUrl = select?.dataset.principalSearchUrl || select?.dataset.projectSearchUrl;
            if (!searchUrl || !input) {
                return;
            }
            window.clearTimeout(timerRef());
            setTimer(window.setTimeout(async () => {
                const sequence = sequenceRef() + 1;
                setSequence(sequence);
                const selectedOption = select.selectedOptions[0];
                const selectedValue = select.value;
                const selectedLabel = selectedOption?.textContent?.trim() || selectedValue;
                try {
                    const response = await fetch(`${searchUrl}?q=${encodeURIComponent(input.value.trim())}&limit=250`);
                    if (!response.ok || sequence !== sequenceRef()) {
                        return;
                    }
                    const data = await response.json();
                    renderOptions(Array.isArray(data.results) ? data.results : [], selectedValue, selectedLabel);
                    syncWorkflowIds();
                } catch (error) {
                    console.warn(`${label} zoeken mislukt`, error);
                }
            }, 120));
        };

        const searchPrincipals = () => searchEntities({
            input: principalSearchInput,
            select: principalSelect,
            timerRef: () => principalSearchTimer,
            sequenceRef: () => principalSearchSequence,
            setTimer: (timer) => { principalSearchTimer = timer; },
            setSequence: (sequence) => { principalSearchSequence = sequence; },
            renderOptions: renderPrincipalOptions,
            label: "Opdrachtgevers",
        });

        const searchProjects = () => searchEntities({
            input: projectSearchInput,
            select: projectSelect,
            timerRef: () => projectSearchTimer,
            sequenceRef: () => projectSearchSequence,
            setTimer: (timer) => { projectSearchTimer = timer; },
            setSequence: (sequence) => { projectSearchSequence = sequence; },
            renderOptions: renderProjectOptions,
            label: "Projecten",
        });

        const chooseFirstVisibleOption = (select) => {
            const first = [...(select?.options || [])].find((option) => option.value);
            if (first) {
                select.value = first.value;
                select.dispatchEvent(new Event("change", { bubbles: true }));
            }
        };

        principalSelect?.addEventListener("change", () => {
            if (principalSearchInput) {
                principalSearchInput.value = principalSelect.value || principalSearchInput.value || "";
            }
            syncWorkflowIds();
        });
        projectSelect?.addEventListener("change", () => {
            if (projectSearchInput) {
                projectSearchInput.value = projectSelect.value || projectSearchInput.value || "";
            }
            syncWorkflowIds();
        });
        principalSearchInput?.addEventListener("input", searchPrincipals);
        projectSearchInput?.addEventListener("input", searchProjects);
        principalSearchInput?.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                searchPrincipals();
                window.setTimeout(() => chooseFirstVisibleOption(principalSelect), 180);
            }
        });
        projectSearchInput?.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                searchProjects();
                window.setTimeout(() => chooseFirstVisibleOption(projectSelect), 180);
            }
        });
        if (principalSearchInput) {
            principalSearchInput.value = principalSelect?.value || principalSearchInput.value || "";
            if (principalSearchInput.value) {
                searchPrincipals();
            }
        }
        if (projectSearchInput) {
            projectSearchInput.value = projectSelect?.value || projectSearchInput.value || "";
            if (projectSearchInput.value) {
                searchProjects();
            }
        }
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

        const syncSumCheck = (inputs, totalField, calculatedField, checkField, unit, missingMessage, forceTotal = false) => {
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
            if (forceTotal && totalField) {
                totalField.value = calculatedField.value;
            }
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

        const syncTotalCheck = (source = "", forceTotals = false) => {
            syncSumCheck(dayInputs, totalInput, calculatedInput, checkInput, "uur", "totaal ontbreekt", forceTotals || source === "hours");
            syncSumCheck(kmInputs, totalKmInput, calculatedKmInput, checkKmInput, "km", "totaal km ontbreekt", forceTotals || source === "km");
        };

        const syncEditableSummary = (input) => {
            if (!input?.name || !input.name.startsWith("field_")) {
                return;
            }
            const key = input.name.replace("field_", "");
            const value = input.tagName === "SELECT"
                ? (input.selectedOptions[0]?.textContent || input.value || "").trim()
                : input.value;
            setSummaryMetric(key, value, "green");
        };

        const saveCorrections = async (submitter = null) => {
            if (!form.action) {
                return;
            }
            autosaveController?.abort();
            autosaveController = new AbortController();
            setAutosaveStatus("Opslaan...", "saving");
            const formData = new FormData(form);
            if (submitter?.name) {
                formData.set(submitter.name, submitter.value || "1");
            }
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: formData,
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
            syncEditableSummary(input);
            scheduleAutosave();
        }));
        totalInput?.addEventListener("input", () => {
            syncTotalCheck("total");
            syncEditableSummary(totalInput);
            scheduleAutosave();
        });
        kmInputs.forEach((input) => input.addEventListener("input", () => {
            syncTotalCheck("km");
            syncEditableSummary(input);
            scheduleAutosave();
        }));
        totalKmInput?.addEventListener("input", () => {
            syncTotalCheck("total_km");
            syncEditableSummary(totalKmInput);
            scheduleAutosave();
        });
        form.querySelectorAll("input[name^='field_'], select[name^='field_'], textarea[name^='field_']").forEach((input) => {
            input.addEventListener("input", () => syncEditableSummary(input));
            input.addEventListener("change", () => syncEditableSummary(input));
        });
        form.addEventListener("change", () => {
            syncWorkflowIds();
            syncTotalCheck();
            scheduleAutosave();
        });
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            syncWorkflowIds();
            syncTotalCheck("submit", event.submitter?.dataset.manualParseSave === "true");
            saveCorrections(event.submitter);
        });
        form.querySelector("[data-manual-fields-open]")?.addEventListener("click", () => {
            form.querySelectorAll(".timesheet-accordion").forEach((section) => {
                section.open = true;
            });
            const firstManualField = form.querySelector("[data-parsed-employee-name]") || form.querySelector("input:not([readonly]), select, textarea");
            firstManualField?.focus();
            setAutosaveStatus("Handmatig invullen actief - sla op als de velden zijn overgenomen", "pending");
        });
        absenceInput?.addEventListener("change", () => {
            applyAbsenceCode();
            scheduleAutosave();
        });
        applyAbsenceCode();
        syncTotalCheck("hours");
    });

    document.querySelectorAll("[data-force-parse-button]").forEach((button) => {
        button.addEventListener("click", (event) => {
            event.preventDefault();
            button.disabled = true;
            button.textContent = "OCR + OpenAI bezig...";
            button.form?.requestSubmit();
        });
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

    const pdfViewer = document.querySelector("[data-pdf-viewer]");
    const pdfFrame = document.querySelector("[data-pdf-viewer-frame]");
    const pdfTitle = document.querySelector("[data-pdf-viewer-title]");
    let pdfUrl = "";
    const closePdfViewer = () => {
        if (pdfViewer) pdfViewer.hidden = true;
        if (pdfFrame) pdfFrame.src = "about:blank";
        pdfUrl = "";
    };
    document.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-pdf-open]");
        if (!trigger) return;
        event.preventDefault();
        pdfUrl = trigger.dataset.pdfOpen || trigger.getAttribute("href") || "";
        if (!pdfUrl) return;
        if (pdfTitle) pdfTitle.textContent = trigger.dataset.pdfTitle || "PDF-document";
        if (pdfFrame) pdfFrame.src = pdfUrl;
        if (pdfViewer) pdfViewer.hidden = false;
    });
    document.querySelector("[data-pdf-viewer-close]")?.addEventListener("click", closePdfViewer);
    pdfViewer?.addEventListener("click", (event) => {
        if (event.target === pdfViewer) closePdfViewer();
    });
    document.querySelector("[data-pdf-viewer-print]")?.addEventListener("click", () => {
        if (pdfFrame?.contentWindow) {
            pdfFrame.contentWindow.focus();
            pdfFrame.contentWindow.print();
        }
    });
    document.querySelector("[data-pdf-viewer-download]")?.addEventListener("click", () => {
        if (!pdfUrl) return;
        const link = document.createElement("a");
        link.href = pdfUrl;
        link.download = "document.pdf";
        document.body.appendChild(link);
        link.click();
        link.remove();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closePdfViewer();
    });

    document.querySelectorAll("[data-invoice-relation-select]").forEach((select) => {
        const preview = select.closest(".invoice-form-section")?.querySelector("[data-invoice-logo-preview]");
        const image = preview?.querySelector("[data-invoice-logo-image]");
        const label = preview?.querySelector("[data-invoice-logo-label]");
        const refreshPreview = () => {
            const option = select.options[select.selectedIndex];
            if (image) image.src = option?.dataset.logoUrl || "/dashboard/static/olympusbouw.png";
            if (label) label.textContent = option?.value ? option.textContent.trim() : "Nog geen zzp'er gekozen";
        };
        select.addEventListener("change", refreshPreview);
        refreshPreview();
    });

    document.querySelectorAll("[data-zzp-invoice]").forEach((calculator) => {
        const body = calculator.querySelector("[data-zzp-invoice-body]");
        const template = calculator.querySelector("[data-zzp-invoice-template]");
        const addButton = document.querySelector("[data-zzp-invoice-add]");
        const defaultSales = calculator.querySelector("[data-zzp-default-sales]");
        const defaultPurchase = calculator.querySelector("[data-zzp-default-purchase]");
        const vatRate = calculator.querySelector("[data-zzp-vat-rate]");
        const parseNumber = (value) => {
            const normalized = String(value || "").replace(/[^0-9,.-]/g, "").replace(/\./g, "").replace(",", ".");
            const number = Number(normalized || "0");
            return Number.isFinite(number) ? number : 0;
        };
        const formatNumber = (value) => new Intl.NumberFormat("nl-NL", { minimumFractionDigits: value % 1 === 0 ? 0 : 2, maximumFractionDigits: 2 }).format(value || 0);
        const formatMoney = (value) => new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" }).format(value || 0);
        const setText = (selector, value) => document.querySelectorAll(selector).forEach((target) => { target.textContent = value; });
        const recalculate = () => {
            let includedRows = 0;
            let totalHours = 0;
            let totalSales = 0;
            let totalPurchase = 0;
            calculator.querySelectorAll("[data-zzp-invoice-row]").forEach((row) => {
                const include = row.querySelector("[data-zzp-include]")?.checked ?? true;
                const hours = parseNumber(row.querySelector("[data-zzp-hours]")?.value);
                const salesRate = parseNumber(row.querySelector("[data-zzp-sales-rate]")?.value);
                const purchaseRate = parseNumber(row.querySelector("[data-zzp-purchase-rate]")?.value);
                const salesAmount = hours * salesRate;
                const purchaseAmount = hours * purchaseRate;
                row.querySelector("[data-zzp-sales-amount]").textContent = formatMoney(salesAmount);
                row.querySelector("[data-zzp-purchase-amount]").textContent = formatMoney(purchaseAmount);
                row.querySelector("[data-zzp-margin-amount]").textContent = formatMoney(salesAmount - purchaseAmount);
                row.classList.toggle("invoicing-row--excluded", !include);
                if (include) {
                    includedRows += 1;
                    totalHours += hours;
                    totalSales += salesAmount;
                    totalPurchase += purchaseAmount;
                }
            });
            const vat = totalSales * (parseNumber(vatRate?.value) / 100);
            setText("[data-zzp-total-lines]", String(includedRows));
            setText("[data-zzp-total-hours]", formatNumber(totalHours));
            setText("[data-zzp-total-sales], [data-zzp-total-sales-bottom]", formatMoney(totalSales));
            setText("[data-zzp-total-purchase]", formatMoney(totalPurchase));
            setText("[data-zzp-total-margin], [data-zzp-total-margin-bottom]", formatMoney(totalSales - totalPurchase));
            setText("[data-zzp-total-vat]", formatMoney(vat));
            setText("[data-zzp-total-including-vat]", formatMoney(totalSales + vat));
        };
        const wireRow = (row) => row.querySelectorAll("input").forEach((input) => {
            input.addEventListener("input", recalculate);
            input.addEventListener("change", recalculate);
        });
        calculator.querySelectorAll("[data-zzp-invoice-row]").forEach(wireRow);
        calculator.querySelector("[data-zzp-apply-defaults]")?.addEventListener("click", () => {
            calculator.querySelectorAll("[data-zzp-invoice-row]").forEach((row) => {
                row.querySelector("[data-zzp-sales-rate]").value = defaultSales?.value || "";
                row.querySelector("[data-zzp-purchase-rate]").value = defaultPurchase?.value || "";
            });
            recalculate();
        });
        addButton?.addEventListener("click", () => {
            const row = template?.content?.firstElementChild?.cloneNode(true);
            if (!row || !body) return;
            row.querySelector("[data-zzp-sales-rate]").value = defaultSales?.value || "";
            row.querySelector("[data-zzp-purchase-rate]").value = defaultPurchase?.value || "";
            body.appendChild(row);
            wireRow(row);
            row.querySelector("[data-zzp-principal]")?.focus();
            recalculate();
        });
        vatRate?.addEventListener("input", recalculate);
        recalculate();
    });

})();
