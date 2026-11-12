import { useEffect, useId, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";

// Panels (drawers and dialogs) are not routes, so on a phone the back gesture used to leave the page with the panel
// still open. This gives an open panel its own history entry: back closes the panel and stays on the page, and
// closing the panel by hand removes that entry again, so back does not "re-open" anything.
// `onBack` may return false to refuse (a step that cannot be interrupted); the entry is then put back.
export default function useBackClosesOverlay(open, onBack) {
    const navigate = useNavigate();
    const location = useLocation();
    const key = useId();
    const pushed = useRef(false); // this panel owns an entry
    const seen = useRef(false); // the entry has shown up in the location
    const latest = useRef(onBack);
    latest.current = onBack;
    const stack = location.state?.overlays ?? [];
    const active = stack.includes(key);

    const push = () => navigate({ pathname: location.pathname, search: location.search, hash: location.hash }, { state: { ...location.state, overlays: [...stack, key] } });

    useEffect(() => {
        if (open && !pushed.current) {
            pushed.current = true;
            seen.current = false;
            push();
        } else if (!open && pushed.current) {
            pushed.current = false;
            if (active) navigate(-1); // closed by hand: drop the entry
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps -- reacts to the panel opening or closing only
    }, [open]);

    useEffect(() => {
        if (!pushed.current) return;
        if (active) {
            seen.current = true;
        } else if (seen.current) {
            // back (or forward past it) took the entry away: the panel closes
            pushed.current = false;
            seen.current = false;
            if (latest.current() === false) {
                pushed.current = true;
                push();
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps -- reacts to the location only
    }, [location]);
}
