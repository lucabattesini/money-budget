import { Flex, Box } from "@chakra-ui/react";
import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { getFamily } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { setLocale } from "../lib/locale";
import Header from "./Header";
import { Toaster } from "./ui/toaster";

export default function Layout() {
    // The family's currency and language, for every page. If they cannot be loaded the app keeps reais and Portuguese.
    useEffect(() => {
        const token = getToken();
        if (token) getFamily(token).then((result) => result.ok && setLocale(result.data));
    }, []);

    return (
        <Flex direction="column" h="100dvh" w="full" overflow="hidden">
            <Header />
            <Toaster />
            {/* On a phone the menu is a bar at the bottom of the screen, so the page leaves room for it */}
            <Box flex="1" overflowY="auto" pb={{ base: "calc(60px + env(safe-area-inset-bottom))", md: 0 }}>
                <Outlet />
            </Box>
        </Flex>
    );
}
