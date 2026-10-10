(function () {
    const script = document.currentScript;
    const main = document.querySelector('main');
    if (!script || !main) {
        return;
    }

    function isExportableTable(table) {
        return table.tHead &&
            table.tBodies.length &&
            !table.hasAttribute('data-no-excel-export') &&
            !table.closest('.modal');
    }

    const exportableTables = Array.from(main.querySelectorAll('table')).filter(
        isExportableTable
    );
    if (!exportableTables.length) {
        return;
    }

    const toolbar = document.createElement('div');
    toolbar.className = 'd-flex justify-content-end mb-3';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-outline-success';
    button.textContent = 'Esporta in Excel';
    toolbar.appendChild(button);

    const firstTableContainer =
        exportableTables[0].closest('.table-responsive') || exportableTables[0];
    firstTableContainer.parentNode.insertBefore(toolbar, firstTableContainer);

    function cellText(cell) {
        const checkbox = cell.querySelector('input[type="checkbox"]');
        if (checkbox) {
            return checkbox.checked ? 'Sì' : 'No';
        }
        const input = cell.querySelector('input:not([type="hidden"]), textarea');
        if (input) {
            return input.value;
        }
        const select = cell.querySelector('select');
        if (select) {
            return select.selectedOptions.length
                ? select.selectedOptions[0].textContent.trim()
                : '';
        }
        return cell.innerText.trim();
    }

    function isExportableColumn(header) {
        const title = header.trim();
        return title !== '' && !/^(azioni|seleziona|generazione)$/i.test(title);
    }

    function precedingTitle(table, doc) {
        const headings = Array.from(doc.querySelectorAll('main h1, main h2, main h3'));
        const preceding = headings.filter(function (heading) {
            return Boolean(
                heading.compareDocumentPosition(table) &
                Node.DOCUMENT_POSITION_FOLLOWING
            );
        });
        return preceding.length
            ? preceding[preceding.length - 1].innerText.trim()
            : doc.title;
    }

    function logicalCells(row) {
        const cells = [];
        Array.from(row.cells).forEach(function (cell) {
            cells.push(cell);
            for (let index = 1; index < cell.colSpan; index += 1) {
                cells.push(null);
            }
        });
        return cells;
    }

    function extractTable(table, doc) {
        const headerRows = Array.from(table.tHead.rows);
        if (!headerRows.length) {
            return null;
        }
        const headers = logicalCells(headerRows[headerRows.length - 1]).map(
            function (cell) {
                return cell ? cell.innerText.trim() : '';
            }
        );
        const columnIndexes = headers
            .map(function (header, index) {
                return isExportableColumn(header) ? index : null;
            })
            .filter(function (index) {
                return index !== null;
            });
        if (!columnIndexes.length) {
            return null;
        }

        const rows = [columnIndexes.map(function (index) { return headers[index]; })];
        Array.from(table.tBodies).forEach(function (body) {
            Array.from(body.rows).forEach(function (row) {
                const cells = logicalCells(row);
                const values = columnIndexes.map(function (index) {
                    return cells[index] ? cellText(cells[index]) : '';
                });
                if (values.some(function (value) { return value !== ''; })) {
                    rows.push(values);
                }
            });
        });
        if (table.tFoot) {
            Array.from(table.tFoot.rows).forEach(function (row) {
                const cells = logicalCells(row);
                rows.push(columnIndexes.map(function (index) {
                    return cells[index] ? cellText(cells[index]) : '';
                }));
            });
        }

        return {
            name: precedingTitle(table, doc) || 'Elenco',
            rows: rows
        };
    }

    function nextPageUrl(doc, currentUrl) {
        const navigation = doc.querySelector('nav .pagination');
        if (!navigation || !navigation.lastElementChild) {
            return null;
        }
        const lastItem = navigation.lastElementChild;
        const link = lastItem.classList.contains('disabled')
            ? null
            : lastItem.querySelector('a[href]');
        if (!link || link.getAttribute('href') === '#') {
            return null;
        }
        const nextUrl = new URL(link.href, currentUrl);
        return nextUrl.origin === window.location.origin
            ? nextUrl.href
            : null;
    }

    async function collectPaginatedSheets() {
        const initialUrl = window.location.href;
        const visitedPages = new Set();
        const sheets = [];
        const sheetIndexByTable = new Map();
        let pageUrl = initialUrl;

        while (pageUrl && !visitedPages.has(pageUrl)) {
            visitedPages.add(pageUrl);
            let pageDocument = document;
            if (pageUrl !== initialUrl) {
                const response = await fetch(pageUrl, {
                    credentials: 'same-origin'
                });
                if (!response.ok) {
                    throw new Error('Impossibile caricare tutte le pagine filtrate.');
                }
                const responseUrl = new URL(response.url);
                if (
                    responseUrl.origin !== window.location.origin ||
                    responseUrl.pathname !== window.location.pathname
                ) {
                    throw new Error('La sessione è scaduta. Accedi di nuovo e riprova.');
                }
                pageDocument = new DOMParser().parseFromString(
                    await response.text(),
                    'text/html'
                );
            }

            const pageMain = pageDocument.querySelector('main');
            if (!pageMain) {
                throw new Error('La pagina non contiene tabelle esportabili.');
            }
            const pageTables = Array.from(pageMain.querySelectorAll('table')).filter(
                isExportableTable
            );
            pageTables.forEach(function (table, tableIndex) {
                const pageSheet = extractTable(table, pageDocument);
                if (!pageSheet) {
                    return;
                }
                if (!sheetIndexByTable.has(tableIndex)) {
                    sheetIndexByTable.set(tableIndex, sheets.length);
                    sheets.push(pageSheet);
                    return;
                }

                const sheet = sheets[sheetIndexByTable.get(tableIndex)];
                if (JSON.stringify(sheet.rows[0]) !== JSON.stringify(pageSheet.rows[0])) {
                    throw new Error('Le colonne della tabella cambiano tra le pagine.');
                }
                sheet.rows.push.apply(sheet.rows, pageSheet.rows.slice(1));
            });

            pageUrl = nextPageUrl(pageDocument, pageUrl);
        }
        return sheets;
    }

    function currentPageName() {
        const pathParts = window.location.pathname.split('/').filter(Boolean);
        const lastSection = pathParts.length
            ? decodeURIComponent(pathParts[pathParts.length - 1])
            : 'pagina';
        const safeName = lastSection
            .normalize('NFKD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^A-Za-z0-9_-]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .slice(0, 80);
        return safeName || 'pagina';
    }

    function showError(message) {
        let error = document.getElementById('errore-esportazione-excel');
        if (!error) {
            error = document.createElement('div');
            error.id = 'errore-esportazione-excel';
            error.className = 'alert alert-danger';
            error.setAttribute('role', 'alert');
            toolbar.insertAdjacentElement('afterend', error);
        }
        error.textContent = message;
    }

    button.addEventListener('click', async function () {
        button.disabled = true;
        button.textContent = 'Preparazione del file Excel…';
        const previousError = document.getElementById('errore-esportazione-excel');
        if (previousError) {
            previousError.remove();
        }

        try {
            const sheets = await collectPaginatedSheets();
            const response = await fetch(script.dataset.exportUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector(
                        '#table-export-csrf [name=csrfmiddlewaretoken]'
                    ).value
                },
                body: JSON.stringify({
                    page_name: currentPageName(),
                    sheets: sheets
                })
            });
            if (!response.ok) {
                const contentType = response.headers.get('content-type') || '';
                const result = contentType.includes('application/json')
                    ? await response.json()
                    : {};
                throw new Error(
                    result.error || 'Esportazione Excel non riuscita. Accedi di nuovo e riprova.'
                );
            }

            const file = await response.blob();
            const downloadUrl = URL.createObjectURL(file);
            const downloadLink = document.createElement('a');
            downloadLink.href = downloadUrl;
            const contentDisposition =
                response.headers.get('Content-Disposition') || '';
            const filename = contentDisposition.match(/filename="([^"]+)"/i);
            downloadLink.download = filename
                ? filename[1]
                : currentPageName() + '.xlsx';
            document.body.appendChild(downloadLink);
            downloadLink.click();
            downloadLink.remove();
            URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            showError(error.message);
        } finally {
            button.disabled = false;
            button.textContent = 'Esporta in Excel';
        }
    });
})();
