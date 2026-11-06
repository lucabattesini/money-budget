// An AI app (the Claude app) sends the person here to ask for access. The person may have to sign in first, so the
// question is kept for the time it takes, and shown again after the login.
const PENDING_KEY = "pending_connect";

export function rememberPendingConnect(search) {
    try {
        sessionStorage.setItem(PENDING_KEY, search);
    } catch {
        // without storage the person will have to start again from the app
    }
}

// The query string (with its "?") kept before the login, once; null if there is none.
export function takePendingConnect() {
    try {
        const search = sessionStorage.getItem(PENDING_KEY);
        sessionStorage.removeItem(PENDING_KEY);
        return search;
    } catch {
        return null;
    }
}

// What the app asked, read from the address; null when something is missing (the page was not opened by an app).
export function readConnectRequest(search) {
    const params = new URLSearchParams(search);
    const request = {
        client_id: params.get("client_id"),
        redirect_uri: params.get("redirect_uri"),
        response_type: params.get("response_type"),
        code_challenge: params.get("code_challenge"),
        code_challenge_method: params.get("code_challenge_method"),
        state: params.get("state") ?? "",
    };
    const complete = ["client_id", "redirect_uri", "response_type", "code_challenge", "code_challenge_method"].every(
        (key) => request[key],
    );
    if (!complete) return null;
    // Where the person will be sent back to: anyone can register an app under any name, so the address is what tells apps apart
    let returnHost = "";
    try {
        returnHost = new URL(request.redirect_uri).host;
    } catch {
        return null;
    }
    return { request, app: params.get("app") || "Um aplicativo", returnHost };
}

// Leave this page for the address the app is waiting at. (A function of its own so tests can see where it goes.)
// Where the Claude app itself sends people back to. Anyone can register an app under any name (even "Claude"), so an
// address that is not one of these is shown as unverified.
const KNOWN_RETURN_HOSTS = ["claude.ai", "claude.com"];
export const isKnownApp = (host) => KNOWN_RETURN_HOSTS.some((known) => host === known || host.endsWith("." + known));

export function leaveTo(url) {
    window.location.assign(url);
}
