(function () {
    "use strict";

    function escapeHtml(value) {
        return String(value || "").replace(/[&<>'"]/g, function (ch) {
            return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[ch];
        });
    }

    function getRegionId(regionSelect) {
        if (!regionSelect) {
            return "";
        }
        if (regionSelect.tagName === "SELECT") {
            var option = regionSelect.options[regionSelect.selectedIndex];
            if (option && option.dataset && option.dataset.regionId) {
                return option.dataset.regionId;
            }
            var selected = regionSelect.value || "";
            return /^[0-9]+$/.test(selected) ? selected : "";
        }
        var value = regionSelect.value || "";
        return /^[0-9]+$/.test(value) ? value : "";
    }

    document.addEventListener("DOMContentLoaded", function () {
        var inputs = document.querySelectorAll("input[data-api-url]");
        if (!inputs || inputs.length === 0) {
            return;
        }

        inputs.forEach(function (input) {
            var form = input.closest("form");
            var gridId = input.dataset.gridId;
            var grid = gridId ? document.getElementById(gridId) : null;
            
            // Prefer region select from the same form, fallback to global id
            var regionSelect = form ? form.querySelector("select[name='region']") : document.getElementById("region");
            
            // The pagination is usually page-global, we find it.
            var paginationBlock = document.querySelector("[data-pagination-block]") || document.getElementById("flags-pagination-block");
            var paginationInfo = document.querySelector("[data-pagination-info]");

            if (!grid) {
                // If this search input doesn't target a specific grid, don't handle it here
                // (It might be a navbar search meant for global navigation)
                return;
            }

            var apiUrl = input.dataset.apiUrl;
            var minLength = parseInt(input.dataset.minLength || "2", 10);
            if (!isFinite(minLength) || minLength < 1) {
                minLength = 2;
            }

            var emptyMessage = grid.dataset.emptyMessage || "No items found matching your search.";
            var flagLabel = grid.dataset.flagLabel || "Flag of";
            var fallbackEmoji = grid.dataset.fallbackEmoji || "";
            var compactCards = grid.dataset.compactCards === "1";
            var statusFilter = input.dataset.searchStatus || (form ? form.dataset.searchStatus : "");
            var cardType = input.dataset.cardType || "country";

            var initialCards = Array.from(grid.children).map(function (card) {
                return card.cloneNode(true);
            });

            if (form) {
                form.addEventListener("submit", function (event) {
                    event.preventDefault();
                });
            }

            // Explicitly prevent Enter key native submission just in case
            input.addEventListener("keydown", function (event) {
                if (event.key === "Enter") {
                    event.preventDefault();
                    if (timer) {
                        clearTimeout(timer);
                    }
                    applySearch();
                }
            });

            function showPagination(show) {
                if (paginationBlock) {
                    paginationBlock.style.display = show ? "" : "none";
                }
                if (paginationInfo) {
                    paginationInfo.style.display = show ? "" : "none";
                }
            }

            function restoreInitialPage() {
                grid.innerHTML = "";
                initialCards.forEach(function (card) {
                    grid.appendChild(card.cloneNode(true));
                });
                showPagination(true);
            }

            function renderItems(items) {
                if (!items.length) {
                    grid.innerHTML = '<div class="col-12"><p class="text-center text-muted py-5">' + escapeHtml(emptyMessage) + '</p></div>';
                    return;
                }

                grid.innerHTML = items.map(function (item) {
                    var name = escapeHtml(item.localized_name || item.name);
                    var capital = escapeHtml(item.capital || "");
                    var img = item.img ? escapeHtml(item.img) : "";
                    var emoji = escapeHtml(item.emoji || fallbackEmoji || "FLAG");
                    var link = item.link ? escapeHtml(item.link) : "";

                    if (cardType === "flag") {
                        var flagInner = '' +
                            '<div class="flag-item h-100 d-flex flex-column m-0"' +
                            ' data-flag-detail-link="' + link + '"' +
                            ' data-flag-image-src="' + img + '">' +
                            '<div class="flag-img-wrap flex-shrink-0">' +
                            (img
                                ? '<img src="' + img + '" alt="' + escapeHtml(name) + '" class="flag-display" loading="lazy" decoding="async">'
                                : '<span class="flag-emoji-display">' + emoji + '</span>') +
                            '</div>' +
                            '<div class="flag-body" style="padding: 0.75rem; text-align: center; display: flex; flex-direction: column; flex-grow: 1;">' +
                            '<div class="flag-caption" title="' + name + '">' + name + '</div>' +
                            '</div>' +
                            '</div>';

                        return '' +
                            '<div class="col-6 col-sm-4 col-md-3 col-lg-2 flag-card-col">' +
                            (link ? '<a href="' + link + '" class="flag-link h-100 text-decoration-none d-block">' + flagInner + '</a>'
                                  : '<div class="text-decoration-none d-block h-100">' + flagInner + '</div>') +
                            '</div>';
                    } else {
                        var cardBodyClass = compactCards ? "country-card-body flex-grow-1 compact-territory" : "country-card-body flex-grow-1";

                        var cardInner = '' +
                            '<div class="country-grid-card d-flex flex-column m-0"' +
                            ' data-flag-detail-link="' + link + '"' +
                            ' data-flag-image-src="' + img + '">' +
                            (img
                                ? '<img src="' + img + '" alt="' + escapeHtml(flagLabel) + ' ' + name + '" class="flag-thumbnail flex-shrink-0" loading="lazy" decoding="async">'
                                : '<div class="flag-thumbnail flex-shrink-0 d-flex align-items-center justify-content-center" style="font-size: 4rem;">' + emoji + '</div>') +
                            '<div class="' + cardBodyClass + '">' +
                            '<h3 class="country-title">' + name + '</h3>' +
                            (capital ? '<div class="info-badge"><i class="bi bi-building"></i> ' + capital + '</div>' : '') +
                            '</div>' +
                            '</div>';

                        return '' +
                            '<div class="col-6 col-md-4 col-lg-3 country-card-col">' +
                            (link ? '<a href="' + link + '" class="text-decoration-none d-block h-100">' + cardInner + '</a>'
                                  : '<div class="text-decoration-none d-block h-100">' + cardInner + '</div>') +
                            '</div>';
                    }
                }).join("");

                if (window.FlagImageCache && typeof window.FlagImageCache.scan === "function") {
                    window.FlagImageCache.scan(grid);
                }
            }

            var requestId = 0;
            var activeController = null;

            function applySearch() {
                var query = input.value.trim();

                if (query.length < 1 || query.length < minLength) {
                    if (activeController) {
                        activeController.abort();
                        activeController = null;
                    }
                    restoreInitialPage();
                    return;
                }

                showPagination(false);

                var currentRequest = ++requestId;
                
                var urlObj = new URL(apiUrl, window.location.origin);
                urlObj.searchParams.set("q", query);
                
                var category = input.dataset.searchCategory;
                if (category) {
                    urlObj.searchParams.set("category", category);
                }
                
                if (statusFilter) {
                    urlObj.searchParams.set("status", statusFilter);
                }
                
                var regionId = getRegionId(regionSelect);
                if (regionId) {
                    urlObj.searchParams.set("region", regionId);
                }

                var currentLang = document.documentElement.lang;
                if (currentLang) {
                    urlObj.searchParams.set("lang", currentLang);
                }

                if (activeController) {
                    activeController.abort();
                }
                activeController = new AbortController();

                fetch(urlObj.toString(), {
                    signal: activeController.signal,
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                })
                    .then(function (response) {
                        if (!response.ok || currentRequest !== requestId) {
                            return null;
                        }
                        return response.json();
                    })
                    .then(function (data) {
                        if (!data || currentRequest !== requestId) {
                            return;
                        }
                        renderItems(data.items || []);
                    })
                    .catch(function (error) {
                        if (error && error.name !== "AbortError") {
                            console.error("Search error:", error);
                        }
                    });
            }

            var timer = null;
            input.addEventListener("input", function () {
                if (timer) {
                    clearTimeout(timer);
                }
                timer = setTimeout(function () {
                    applySearch();
                }, 220);
            });

            if (regionSelect) {
                regionSelect.addEventListener("change", function () {
                    if (input.value.trim().length >= minLength) {
                        applySearch();
                    }
                });
            }

            if (input.value.trim().length >= minLength) {
                applySearch();
            }
        });
    });
})();
