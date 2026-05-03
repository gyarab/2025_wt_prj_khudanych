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
        var form = document.getElementById("countries-search-form");
        var searchInput = document.getElementById("search");
        var regionSelect = document.getElementById("region");
        var countriesGrid = document.getElementById("countries-grid");
        var paginationBlock = document.querySelector('nav[aria-label="Countries pagination"]');
        var paginationInfo = document.querySelector("[data-pagination-info]");

        if (!form || !searchInput || !countriesGrid) {
            return;
        }

        var searchApiUrl = form.dataset.searchApi || "/api/countries/search/";
        var statusFilter = form.dataset.searchStatus || "";
        var minQueryLength = parseInt(form.dataset.minQueryLength || "2", 10);
        if (!isFinite(minQueryLength) || minQueryLength < 1) {
            minQueryLength = 2;
        }

        var emptyMessage = countriesGrid.dataset.emptyMessage || "No countries found matching your search.";
        var flagLabel = countriesGrid.dataset.flagLabel || "Flag of";
        var compactCards = countriesGrid.dataset.compactCards === "1";

        var initialCards = Array.from(countriesGrid.querySelectorAll(".country-card-col")).map(function (card) {
            return card.cloneNode(true);
        });

        form.addEventListener("submit", function (event) {
            event.preventDefault();
        });

        function renderCountries(items) {
            if (!items.length) {
                countriesGrid.innerHTML = '<div class="col-12"><p class="text-center text-muted py-5">' + escapeHtml(emptyMessage) + '</p></div>';
                return;
            }

            countriesGrid.innerHTML = items.map(function (item) {
                var name = escapeHtml(item.localized_name || item.name);
                var capital = escapeHtml(item.capital || "");
                var img = item.img ? escapeHtml(item.img) : "";
                var emoji = escapeHtml(item.emoji || "FLAG");
                var link = item.link ? escapeHtml(item.link) : "";
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
            }).join("");

            if (window.FlagImageCache && typeof window.FlagImageCache.scan === "function") {
                window.FlagImageCache.scan(countriesGrid);
            }
        }

        function restoreInitialPage() {
            countriesGrid.innerHTML = "";
            initialCards.forEach(function (card) {
                countriesGrid.appendChild(card.cloneNode(true));
            });
            if (paginationBlock) {
                paginationBlock.classList.remove("d-none");
            }
            if (paginationInfo) {
                paginationInfo.classList.remove("d-none");
            }
        }

        var requestId = 0;
        var activeController = null;

        function applySearch() {
            var query = searchInput.value.trim();

            if (query.length < 1) {
                if (activeController) {
                    activeController.abort();
                    activeController = null;
                }
                restoreInitialPage();
                return;
            }

            if (query.length < minQueryLength) {
                if (activeController) {
                    activeController.abort();
                    activeController = null;
                }
                restoreInitialPage();
                return;
            }

            if (paginationBlock) {
                paginationBlock.classList.add("d-none");
            }
            if (paginationInfo) {
                paginationInfo.classList.add("d-none");
            }

            var currentRequest = ++requestId;
            var params = new URLSearchParams({ q: query });
            if (statusFilter) {
                params.append("status", statusFilter);
            }
            var regionId = getRegionId(regionSelect);
            if (regionId) {
                params.append("region", regionId);
            }

            if (activeController) {
                activeController.abort();
            }
            activeController = new AbortController();

            fetch(searchApiUrl + "?" + params.toString(), {
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
                    renderCountries(data.items || []);
                })
                .catch(function (error) {
                    if (error && error.name !== "AbortError") {
                        console.error("Search error:", error);
                    }
                });
        }

        var timer = null;
        searchInput.addEventListener("input", function () {
            if (timer) {
                clearTimeout(timer);
            }
            timer = setTimeout(function () {
                applySearch();
            }, 220);
        });

        if (regionSelect) {
            regionSelect.addEventListener("change", function () {
                if (searchInput.value.trim().length >= minQueryLength) {
                    applySearch();
                }
            });
        }

        if (searchInput.value.trim().length >= minQueryLength) {
            applySearch();
        }
    });
})();
