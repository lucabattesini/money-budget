import { Component } from "react";
import { Button, Center, Stack, Text } from "@chakra-ui/react";

const CHUNK_ERROR = /dynamically imported module|importing a module script failed|failed to fetch/i;
const RELOADED = "money-budget-reloaded-for-new-version";

// A page is its own file, downloaded when first opened. After a new version is deployed the old file names are gone, so
// an open tab can fail to download a page. Reloading once fetches the new version; a second failure is shown, not looped.
export function reloadOnce() {
    try {
        if (sessionStorage.getItem(RELOADED)) return false;
        sessionStorage.setItem(RELOADED, "1");
    } catch {
        return false; // storage blocked: do not risk a reload loop
    }
    window.location.reload();
    return true;
}

export default class PageErrorBoundary extends Component {
    state = { failed: false };

    static getDerivedStateFromError() {
        return { failed: true };
    }

    componentDidMount() {
        // The app has stayed up for a while: a later failure (another deploy) may reload once again
        this.timer = setTimeout(() => {
            try { sessionStorage.removeItem(RELOADED); } catch { /* nothing to clear */ }
        }, 10000);
    }

    componentWillUnmount() {
        clearTimeout(this.timer);
    }

    componentDidCatch(error) {
        if (CHUNK_ERROR.test(String(error?.message ?? error))) reloadOnce();
    }

    render() {
        if (!this.state.failed) {
            return this.props.children;
        }
        return (
            <Center minH="60dvh" px={6}>
                <Stack align="center" gap={3} textAlign="center">
                    <Text fontWeight="semibold">Não foi possível abrir esta página.</Text>
                    <Text color="fg.muted" fontSize="sm">Verifique sua conexão ou tente de novo. Pode haver uma versão nova do app.</Text>
                    <Button onClick={() => window.location.reload()}>Recarregar</Button>
                </Stack>
            </Center>
        );
    }
}
