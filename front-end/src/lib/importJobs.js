// An import is saved by the server in the background. These steps run outside React, so a finished import is
// still announced after the user has closed the dialog or left the page (like exportJobs.js).
import { getImport, startImport } from "../api/endpoints";
import { getToken } from "./auth";
import customToaster from "../utils/customToaster";

export const POLL_INTERVAL_MS = 1000;
export const GIVE_UP_AFTER_MS = 2 * 60 * 1000;

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const plural = (count, one, many) => `${count} ${count === 1 ? one : many}`;

/** Ask the server to save the checked file and say it is queued. Resolves the job, or null if it could not be queued. */
export async function queueImport(jobId) {
    const result = await startImport(jobId, getToken());
    if (!result.ok) {
        const message =
            result.status === 409 || result.status === 404 || result.status === 422
                ? result.detail || "Não foi possível iniciar a importação."
                : "Não foi possível iniciar a importação. Tente novamente.";
        customToaster("Erro", "error", message);
        return null;
    }
    customToaster("Importação na fila", "info", "Estamos importando as transações. Avisaremos quando terminar.");
    return result.data;
}

/** Wait for the job and say how it went: how many rows were imported and skipped, or that it failed. */
export async function followImport(job) {
    const deadline = Date.now() + GIVE_UP_AFTER_MS;

    while (Date.now() < deadline) {
        await wait(POLL_INTERVAL_MS);

        const token = getToken();
        if (!token) return; // the user logged out: do not keep working for them

        const state = await getImport(job.id, token);

        if (state.status === 401 || state.status === 403) {
            customToaster("Erro", "error", "Sua sessão expirou. Entre de novo e confira suas transações.");
            return;
        }
        if (state.status === 404) {
            customToaster("Erro", "error", "Não encontramos essa importação. Confira suas transações.");
            return;
        }
        if (!state.ok) continue; // a hiccup in the connection: try again

        if (state.data.status === "failed") {
            customToaster("Erro", "error", `${state.data.error || "Não foi possível importar o arquivo."} Nada foi importado.`);
            return;
        }
        if (state.data.status === "done") {
            const skipped = state.data.skipped_count;
            customToaster(
                "Importação concluída",
                "success",
                `${plural(state.data.imported_count, "transação importada", "transações importadas")}` +
                    (skipped ? ` e ${plural(skipped, "ignorada porque já existia", "ignoradas porque já existiam")}.` : "."),
            );
            return;
        }
    }
    customToaster("Erro", "error", "A importação não terminou. Confira suas transações daqui a pouco.");
}
