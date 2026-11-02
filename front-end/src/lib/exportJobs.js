// Exports are built by the server in the background. These two steps run outside React, so a
// finished export is still announced (and downloaded) after the user has left the page.
import { createExport, downloadExport, getExport } from "../api/endpoints";
import { getToken } from "./auth";
import { saveBlob } from "./download";
import customToaster from "../utils/customToaster";

export const POLL_INTERVAL_MS = 1000;
export const GIVE_UP_AFTER_MS = 2 * 60 * 1000;

const FORMAT_NAMES = { xlsx: "Excel", csv: "CSV" };

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Ask the server for an export and say it is queued. Resolves the job, or null if it could not be queued. */
export async function enqueueExport(format) {
    const result = await createExport(format, getToken());
    if (!result.ok) {
        const message =
            result.status === 409
                ? "Você já tem uma exportação em andamento. Aguarde ela terminar."
                : "Não foi possível iniciar a exportação. Tente novamente.";
        customToaster("Erro", "error", message);
        return null;
    }
    customToaster(
        "Exportação na fila",
        "info",
        `Estamos gerando o arquivo ${FORMAT_NAMES[format] ?? format}. Avisaremos quando estiver pronto.`,
    );
    return result.job;
}

/** Wait for the job, download its file and say it is done (or why it was not). */
export async function followExport(job) {
    const deadline = Date.now() + GIVE_UP_AFTER_MS;

    while (Date.now() < deadline) {
        await wait(POLL_INTERVAL_MS);

        const token = getToken();
        if (!token) return; // the user logged out: do not keep working for them, or download into the next session

        const state = await getExport(job.id, token);

        if (state.status === 401 || state.status === 403) {
            customToaster("Erro", "error", "Sua sessão expirou. Entre de novo e exporte outra vez.");
            return;
        }
        if (state.status === 404) {
            customToaster("Erro", "error", "Não encontramos essa exportação. Tente novamente.");
            return;
        }
        if (!state.ok) continue; // a hiccup in the connection: try again

        if (state.job.status === "failed") {
            customToaster("Erro", "error", "Não foi possível gerar o arquivo. Tente novamente.");
            return;
        }
        if (state.job.status === "done") {
            const file = await downloadExport(job.id, token);
            if (!file.ok) {
                customToaster("Erro", "error", "O arquivo ficou pronto, mas não foi possível baixá-lo. Tente novamente.");
                return;
            }
            saveBlob(file.blob, state.job.filename);
            customToaster("Exportação concluída", "success", `O arquivo ${state.job.filename} foi baixado.`);
            return;
        }
    }
    customToaster("Erro", "error", "A exportação não terminou. Tente novamente em instantes.");
}
