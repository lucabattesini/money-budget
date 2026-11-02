// Handing a file to the browser's download.

const pad = (n) => String(n).padStart(2, "0");

/** "transacoes-2026-03-15.xlsx": the day is the user's local day. */
export function exportFileName(extension, date = new Date()) {
    return `transacoes-${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}.${extension}`;
}

/** Make the browser download `blob` as `filename`. */
export function saveBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}
